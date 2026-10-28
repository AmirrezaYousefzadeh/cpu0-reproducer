#!/usr/bin/env python3
"""Sudo helper: compare Performance/Balanced, then search 100 MHz CPU-limit steps."""
import argparse
import ctypes
import fcntl
import json
import os
from pathlib import Path
import pwd
import resource
import signal
import subprocess
import sys
import time
from controls import now, restore_limits, temporary_limits, stop_supervisor, save_status
from run import sample

ROOT = Path(__file__).resolve().parent
CPUS = (0, 6)
POLICIES = {c: Path(f"/sys/devices/system/cpu/cpufreq/policy{c}") for c in CPUS}


def user_environment(account):
    env = os.environ.copy()
    # Restore the HOME belonging to the UID we run as. This is not a scratch
    # directory: inheriting sudo's /root caused the earlier invalid startup.
    env.update(HOME=account.pw_dir, USER=account.pw_name, LOGNAME=account.pw_name,
               PYTHONDONTWRITEBYTECODE="1")
    return env


def profile():
    return subprocess.check_output(["powerprofilesctl", "get"], text=True).strip()


def set_profile(value):
    subprocess.run(["powerprofilesctl", "set", value], check=True, timeout=30)
    if profile() != value:
        raise RuntimeError("Power profile read-back mismatch")


def inspect():
    policies = {}
    for c, p in POLICIES.items():
        d = {n: (p / n).read_text().strip() for n in
             ("related_cpus", "scaling_driver", "scaling_min_freq", "scaling_max_freq", "base_frequency")}
        if d["related_cpus"] != str(c) or d["scaling_driver"] != "intel_pstate":
            raise RuntimeError("Expected independent intel_pstate policies for CPUs 0 and 6")
        if int(d["base_frequency"]) != 3700000 or int(d["scaling_min_freq"]) > 3700000:
            raise RuntimeError("Expected an available 3.7 GHz base-frequency limit")
        policies[c] = d
    if not {0, 6, 7}.issubset(os.sched_getaffinity(0)):
        raise RuntimeError("CPUs 0, 6 and 7 must be available")
    return {"time": now(), "profile": profile(), "policies": policies,
            "bios": Path("/sys/class/dmi/id/bios_version").read_text().strip(),
            "microcode": Path("/sys/devices/system/cpu/cpu0/microcode/version").read_text().strip(),
            "plan": "Performance, Balanced, Performance; 3.7 GHz base check; adaptive 100 MHz search; repeated confirmation; restore original profile and limits",
            "writes": ["power-profiles-daemon active profile", *[str(p / "scaling_max_freq") for p in POLICIES.values()]]}


def validate_sweep(results_root, description):
    rows = json.loads((results_root / description["label"] / "results.json").read_text())
    expected = {(c, t) for c in description["cpus"] for t in range(1, description["trials"] + 1)}
    if {(r["cpu"], r["trial"]) for r in rows} != expected or any(
            r["stop_reason"] or r["classification"] == "setup_error" for r in rows):
        raise RuntimeError("The preceding all-core sweep is incomplete or invalid; review it before changing settings")
    if any(r["cpu"] == 6 and r["classification"] != "pass" for r in rows):
        raise RuntimeError("CPU 6 failed the all-core screen; choose a passing control before the matrix")


def run_phase(name, cpus, trials, expected, cfg, out, status, owner):
    uid, gid, account = owner
    label = out.name + "_" + name
    command = ["/usr/bin/taskset", "-c", "0,6,7", "/usr/bin/python3", "-B", str(ROOT / "run.py"),
               "--pdk-root", cfg["pdk_root"], "--python", cfg["python"],
               "--openroad", cfg["openroad"], "--label", label,
               "--cpus", *map(str, cpus), "--trials", str(trials)]
    entry = {"name": name, "started": now(), "profile": profile(), "expected_limits_khz": expected,
             "result_directory": "results/" + label, "workload_uid": uid}
    status["phases"].append(entry)
    save_status(out, status, uid, gid)
    print("START", name, "profile=" + entry["profile"], "limits=" + str(expected), flush=True)
    process = None
    try:
        with (out / (name + ".log")).open("w") as log, (out / (name + "_monitor.jsonl")).open("w") as trace:
            process = subprocess.Popen(command, cwd=ROOT, env=user_environment(account),
                                       user=uid, group=gid, extra_groups=os.getgrouplist(account.pw_name, gid),
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            begin = time.monotonic()
            while process.poll() is None:
                snapshots = {c: sample(c) for c in CPUS}
                trace.write(json.dumps(snapshots) + "\n"); trace.flush()
                if {c: int(snapshots[c]["maximum_khz"]) for c in CPUS} != expected:
                    raise RuntimeError("Frequency limit changed unexpectedly")
                temps = snapshots[0]["temperatures_c"]
                if not temps or max(temps.values()) >= 85:
                    raise RuntimeError("Temperature safety stop")
                if time.monotonic() - begin > len(cpus) * trials * 310 + 60:
                    raise RuntimeError("Phase runtime limit")
                time.sleep(2)
            if process.returncode:
                raise RuntimeError("Runner/setup/safety failure; inspect " + name + ".log")
        results = json.loads((ROOT / "results" / label / "results.json").read_text())
        entry.update(finished=now(), results=results)
        for r in results:
            print(f"  CPU {r['cpu']} trial {r['trial']}: {r['classification']} ({r['elapsed_seconds']} s)", flush=True)
        if len(results) != len(cpus) * trials or any(r["stop_reason"] or r["classification"] == "setup_error" for r in results):
            raise RuntimeError("Incomplete or invalid workload comparison")
        if any(r["cpu"] == 6 and r["classification"] != "pass" for r in results):
            raise RuntimeError("CPU 6 control failed; comparison stopped")
        return all(r["classification"] == "pass" for r in results if r["cpu"] == 0)
    finally:
        old = {s: signal.signal(s, signal.SIG_IGN) for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
        try:
            if process is not None and process.poll() is None:
                stop_supervisor(process)
            save_status(out, status, uid, gid)
        finally:
            for s, handler in old.items():
                signal.signal(s, handler)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=ROOT / ".local/host.json")
    p.add_argument("--check", action="store_true")
    p.add_argument("--wait", action="store_true", help="queue behind the current isolated comparison")
    args = p.parse_args()
    before = inspect()
    cfg = json.loads(args.config.read_text())
    if args.check:
        print(json.dumps(before, indent=2)); return 0
    if os.geteuid() != 0 or not os.environ.get("SUDO_UID") or int(os.environ["SUDO_UID"]) == 0:
        p.error("Run with sudo from the regular user's terminal")
    uid, gid = int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"])
    account = pwd.getpwuid(uid)
    owner = uid, gid, account
    originals = {c: int(before["policies"][c]["scaling_max_freq"]) for c in CPUS}
    if any(v != 5700000 for v in originals.values()):
        raise RuntimeError("This matrix expects the original 5.7 GHz ceilings")
    os.nice(10)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0):
        raise OSError(ctypes.get_errno(), "Core-dump suppression failed")
    with (ROOT / ".local/controller.lock").open("a") as lock:
        try:
            if args.wait:
                print("Waiting for the current isolated comparison to finish; settings are unchanged.", flush=True)
            fcntl.flock(lock, fcntl.LOCK_EX | (0 if args.wait else fcntl.LOCK_NB))
        except BlockingIOError:
            p.error("Another hardware comparison is running. Use --wait to queue; no settings were changed.")
        except KeyboardInterrupt:
            print("Queue cancelled before changing settings.", flush=True)
            return 130
        # A queued test must capture the state at its actual start, not before
        # waiting. Keep the broad affinity until this second preflight finishes.
        before = inspect()
        originals = {c: int(before["policies"][c]["scaling_max_freq"]) for c in CPUS}
        if any(v != 5700000 for v in originals.values()):
            raise RuntimeError("Original ceilings changed while waiting; no settings changed")
        pending_sweep = ROOT / ".local/latest_sweep.json"
        if args.wait and pending_sweep.exists():
            validate_sweep(ROOT / "results", json.loads(pending_sweep.read_text()))
        os.sched_setaffinity(0, {7})
        out = ROOT / "results" / ("matrix_" + time.strftime("%Y%m%d_%H%M%S"))
        out.mkdir(parents=True, exist_ok=False); os.chown(out, uid, gid)
        status = {"started": now(), "before": before, "phases": [], "restoration_verified": False}
        save_status(out, status, uid, gid)
        def interrupted(signum, frame):
            raise KeyboardInterrupt(f"signal {signum}")
        for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(s, interrupted)
        code = 0
        try:
            set_profile("performance")
            normal_pass = run_phase("performance_before", CPUS, 1, originals, cfg, out, status, owner)
            set_profile("balanced")
            run_phase("balanced", CPUS, 1, originals, cfg, out, status, owner)
            set_profile("performance")
            normal_again = run_phase("performance_repeat", CPUS, 1, originals, cfg, out, status, owner)
            def capped(mhz, cpus, trials, name):
                with temporary_limits(POLICIES, originals, mhz * 1000):
                    return run_phase(name, cpus, trials, {c: mhz * 1000 for c in CPUS}, cfg, out, status, owner)
            base_pass = capped(3700, CPUS, 1, "base_3700")
            status["confirmed_passing_candidate_limit_mhz"] = None
            if base_pass:
                low, high = 37, 57
                if normal_pass and normal_again:
                    low = high
                else:
                    while high - low > 1:
                        middle = (low + high) // 2
                        if capped(middle * 100, (0,), 1, f"probe_{middle * 100}"):
                            low = middle
                        else:
                            high = middle
                status["candidate_limit_mhz"] = low * 100
                if capped(low * 100, CPUS, 3, "confirm_candidate"):
                    status["confirmed_passing_candidate_limit_mhz"] = low * 100
                status["interpretation"] = "Finite trials and requested ceilings; not a guarantee of stability. Inspect measured frequencies; frequency-response may be non-monotonic."
            else:
                status["interpretation"] = "CPU 0 failed even at the base-frequency ceiling; no passing frequency established by this matrix."
            restore_limits(POLICIES, originals)
            set_profile(before["profile"])
            run_phase("restored_final", CPUS, 1, originals, cfg, out, status, owner)
        except (Exception, KeyboardInterrupt) as error:
            status["error"] = f"{type(error).__name__}: {error}"; print(status["error"], flush=True); code = 1
        finally:
            for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                signal.signal(s, signal.SIG_IGN)
            errors = []
            try:
                set_profile(before["profile"])
            except Exception as error:
                errors.append("profile: " + str(error))
            try:
                restore_limits(POLICIES, originals)
            except Exception as error:
                errors.append("frequency: " + str(error))
            status.update(finished=now(), restoration_verified=not errors, restoration_errors=errors)
            save_status(out, status, uid, gid)
            if errors:
                code = 2
        print("Original profile/limits restored:", status["restoration_verified"], flush=True)
        print("Saved:", out, flush=True)
        return code


if __name__ == "__main__":
    raise SystemExit(main())
