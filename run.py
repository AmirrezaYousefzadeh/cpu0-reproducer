#!/usr/bin/env python3
"""Portable single-core CTS comparison. Does not change power or BIOS settings."""
import argparse
import ctypes
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def now():
    return dt.datetime.now().astimezone().isoformat()


def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def sample(cpu):
    temps = {}
    for hw in Path("/sys/class/hwmon").glob("hwmon*"):
        if read(hw / "name") != "coretemp":
            continue
        for p in hw.glob("temp*_input"):
            v = read(p)
            if v is not None:
                temps[read(p.with_name(p.name.replace("_input", "_label"))) or p.name] = int(v) / 1000
    base = Path(f"/sys/devices/system/cpu/cpu{cpu}/cpufreq")
    return {"time": now(), "cpu": cpu, "temperatures_c": temps,
            "frequency_khz": read(base / "scaling_cur_freq"),
            "maximum_khz": read(base / "scaling_max_freq"),
            "epp": read(base / "energy_performance_preference")}


def stop(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def classify(text, code):
    if any(s in text for s in ("Permission denied", "ModuleNotFoundError", "No such file or directory")):
        return "setup_error"
    if code == 0 and "CPU_AFFINITY_REPRO_SUCCESS" in text:
        return "pass"
    if re.search(r"Signal\s+11\s+received", text) or code == -signal.SIGSEGV:
        return "SIGSEGV"
    return "unexpected_failure"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdk-root", required=True, type=Path)
    p.add_argument("--python", default=sys.executable)
    p.add_argument("--openroad", default=shutil.which("openroad"))
    p.add_argument("--cpus", nargs="+", type=int, default=[0, 6])
    p.add_argument("--trials", type=int, default=1)
    p.add_argument("--label", required=True)
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.label):
        p.error("Use a simple label")
    if args.trials < 1 or not set(args.cpus).issubset(os.sched_getaffinity(0)):
        p.error("Invalid trials or unavailable CPU")
    if not args.openroad or not Path(args.openroad).is_file():
        p.error("Supply --openroad or put it on PATH")
    if not (args.pdk_root / "sky130A").is_dir():
        p.error("PDK root must contain sky130A")
    for line in (ROOT / "fixture/SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        if hashlib.sha256((ROOT / "fixture" / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"Fixture hash mismatch: {name}")
    for line in (ROOT / "toolchain/pdk-inputs.sha256").read_text().splitlines():
        digest, name = line.split("  ", 1)
        path = args.pdk_root / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            p.error(f"Pinned PDK input differs or is missing: {name}")
    check = subprocess.run([args.python, "-B", "-c", "import librelane; print(librelane.__version__)"],
                           capture_output=True, text=True)
    if check.returncode:
        p.error("Selected Python cannot import LibreLane: " + check.stderr[-1000:])
    version = subprocess.run([str(args.openroad), "-version"], capture_output=True, text=True)
    expected = json.loads((ROOT / "toolchain/versions.json").read_text())
    if expected["openroad_commit"] not in version.stdout + version.stderr:
        p.error("OpenROAD revision differs from toolchain/versions.json; use the pinned environment")
    if expected["librelane_version"] not in check.stdout:
        p.error("LibreLane version differs from the pinned version")
    profile = subprocess.run(["powerprofilesctl", "get"], capture_output=True, text=True) if shutil.which("powerprofilesctl") else None
    meta = {"started": now(), "cpus": args.cpus, "trials": args.trials,
            "cpu_model": next((s.split(":", 1)[1].strip() for s in Path("/proc/cpuinfo").read_text().splitlines() if s.startswith("model name")), None),
            "bios": read("/sys/class/dmi/id/bios_version"),
            "microcode": read("/sys/devices/system/cpu/cpu0/microcode/version"),
            "openroad_version": version.stdout.strip(), "librelane_version": check.stdout.strip(),
            "profile": profile.stdout.strip() if profile and profile.returncode == 0 else None,
            "python": str(args.python), "openroad": str(args.openroad),
            "pdk_root": str(args.pdk_root.resolve()), "fixture_checksums_verified": True,
            "boot_id": read("/proc/sys/kernel/random/boot_id"), "kernel": os.uname().release}
    if args.check:
        print(json.dumps(meta, indent=2))
        return 0
    build = ROOT / ".build"
    build.mkdir(exist_ok=True)
    guard = build / "disable_core.so"
    source_hash = hashlib.sha256((ROOT / "src/disable_core.c").read_bytes()).hexdigest()
    if not guard.exists() or read(build / "guard-source.sha256") != source_hash:
        subprocess.run(["gcc", "-shared", "-fPIC", "-O2", "-o", str(guard), str(ROOT / "src/disable_core.c")], check=True)
        (build / "guard-source.sha256").write_text(source_hash + "\n")
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "Core-dump suppression failed")
    allowed = os.sched_getaffinity(0)
    coordinator = 7 if 7 in allowed and 7 not in args.cpus else min(allowed - set(args.cpus) or allowed)
    os.sched_setaffinity(0, {coordinator})
    os.nice(19)
    out = ROOT / "results" / args.label
    out.mkdir(parents=True, exist_ok=False)
    (out / "tmp").mkdir()
    (out / "metadata.json").write_text(json.dumps(meta, indent=2) + "\n")
    records = []
    for trial in range(1, args.trials + 1):
        for cpu in args.cpus:
            # Keep the supervisor on a different core even when the requested
            # sweep includes every CPU. Preserve the original allowed mask.
            others = allowed - {cpu}
            coordinator = 7 if 7 in others else (6 if 6 in others else min(others or allowed))
            os.sched_setaffinity(0, {coordinator})
            available = int(next(s.split()[1] for s in Path("/proc/meminfo").read_text().splitlines() if s.startswith("MemAvailable:")))
            if available < 16 * 1024**2:
                raise RuntimeError("At least 16 GiB available memory is required")
            directory = out / f"trial{trial}_cpu{cpu}"
            directory.mkdir()
            env = os.environ.copy()
            env.update(TMPDIR=str(out / "tmp"), PYTHONDONTWRITEBYTECODE="1", LD_PRELOAD=str(guard), OMP_NUM_THREADS="1", NUM_THREADS="1")
            env["PATH"] = str(Path(args.openroad).parent) + os.pathsep + env["PATH"]
            command = ["taskset", "-c", str(cpu), str(args.python), "-B", str(ROOT / "replay.py"),
                       "--trial", str(directory), "--pdk-root", str(args.pdk_root.resolve())]
            record = {"cpu": cpu, "trial": trial, "started": now(), "command": command,
                      "coordinator_cpu": coordinator}
            process = None
            reason = None
            maximum = 0
            begin = time.monotonic()
            print(f"START trial={trial} cpu={cpu}", flush=True)
            try:
                with (directory / "workload.log").open("w") as log, (directory / "telemetry.jsonl").open("w") as trace:
                    process = subprocess.Popen(command, cwd=directory, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    while process.poll() is None:
                        s = sample(cpu)
                        trace.write(json.dumps(s) + "\n"); trace.flush()
                        maximum = max([maximum, *s["temperatures_c"].values()])
                        if not s["temperatures_c"] or maximum >= 85:
                            reason = "temperature safety stop"
                        if time.monotonic() - begin > 300:
                            reason = "five-minute runtime stop"
                        journal = subprocess.run(["journalctl", "-k", "-b", "0", "--since", record["started"], "--no-pager", "-o", "cat"], capture_output=True, text=True)
                        if re.search(r"\[Hardware Error\]|Machine check events logged", journal.stdout, re.I):
                            reason = "new kernel hardware error"
                        if reason:
                            stop(process)
                            break
                        time.sleep(5)
                    process.wait()
            except BaseException:
                if process is not None:
                    stop(process)
                raise
            text = (directory / "workload.log").read_text()
            record.update(returncode=process.returncode, elapsed_seconds=round(time.monotonic() - begin, 3),
                          classification=classify(text, process.returncode), stop_reason=reason,
                          max_sampled_temperature_c=maximum, finished=now())
            records.append(record)
            (out / "results.json").write_text(json.dumps(records, indent=2) + "\n")
            print(f"DONE cpu={cpu}: {record['classification']} ({record['elapsed_seconds']} s)", flush=True)
            if reason or record["classification"] == "setup_error":
                raise RuntimeError(reason or "Setup error; excluded from hardware evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
