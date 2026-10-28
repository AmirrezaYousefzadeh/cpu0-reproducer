#!/usr/bin/env python3
"""Replay different CPU affinities with exactly the same child working paths."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
from run import now, sample, stop, classify

ROOT = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--label", required=True)
    p.add_argument("--cpus", nargs="+", type=int, default=[6, 0, 6, 0])
    args = p.parse_args()
    if not args.label.replace("_", "").replace("-", "").isalnum():
        p.error("Use a simple label")
    allowed = os.sched_getaffinity(0)
    if not set(args.cpus).issubset(allowed):
        p.error("Unavailable CPU")
    cfg = json.loads((ROOT / ".local/host.json").read_text())
    if not (ROOT / ".build/disable_core.so").is_file():
        p.error("Run the normal CTS reproducer once to build its core-dump guard")
    with (ROOT / ".local/controller.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            p.error("Another hardware comparison is running; wait for it to finish")
        subprocess.run([sys.executable, "-B", str(ROOT / "run.py"), "--check", "--label", args.label,
                        "--pdk-root", cfg["pdk_root"], "--python", cfg["python"], "--openroad", cfg["openroad"],
                        "--cpus", *map(str, sorted(set(args.cpus)))], check=True, stdout=subprocess.DEVNULL)
        out = ROOT / "results" / args.label; out.mkdir(exist_ok=False)
        (out / "metadata.json").write_text(json.dumps({
            "started": now(), "cpus_in_sequence": args.cpus,
            "profile": subprocess.check_output(["powerprofilesctl", "get"], text=True).strip(),
            "bios": Path("/sys/class/dmi/id/bios_version").read_text().strip(),
            "microcode": Path("/sys/devices/system/cpu/cpu0/microcode/version").read_text().strip(),
            "initial_samples": {cpu: sample(cpu) for cpu in sorted(set(args.cpus))}}, indent=2) + "\n")
        work = out / "same_working_path"
        os.nice(19)
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        env = os.environ.copy()
        env.update(LD_PRELOAD=str(ROOT / ".build/disable_core.so"), TMPDIR=str(out), PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1", NUM_THREADS="1")
        env["PATH"] = str(Path(cfg["openroad"]).parent) + os.pathsep + env["PATH"]
        records = []
        for index, cpu in enumerate(args.cpus, 1):
            others = allowed - {cpu}
            coordinator = 7 if 7 in others else min(others or allowed)
            os.sched_setaffinity(0, {coordinator})
            work.mkdir()
            command = ["taskset", "-c", str(cpu), cfg["python"], "-B", str(ROOT / "replay.py"),
                       "--trial", str(work), "--pdk-root", cfg["pdk_root"]]
            print("START path control", index, "CPU", cpu, flush=True)
            process = None; reason = None; begin = time.monotonic()
            record = {"cpu": cpu, "sequence": index, "started": now(), "coordinator_cpu": coordinator,
                      "child_working_directory": str(work), "command": command}
            try:
                with (work / "workload.log").open("w") as log, (work / "telemetry.jsonl").open("w") as trace:
                    process = subprocess.Popen(command, cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    while process.poll() is None:
                        s = sample(cpu); trace.write(json.dumps(s) + "\n"); trace.flush()
                        if not s["temperatures_c"] or max(s["temperatures_c"].values()) >= 85:
                            reason = "temperature safety stop"
                        if time.monotonic() - begin > 300:
                            reason = "five-minute runtime stop"
                        if reason:
                            stop(process); break
                        time.sleep(5)
                    process.wait()
            finally:
                if process is not None:
                    stop(process)
            text = (work / "workload.log").read_text()
            record.update(classification=classify(text, process.returncode), returncode=process.returncode,
                          elapsed_seconds=round(time.monotonic() - begin, 3), stop_reason=reason,
                          generated_input_hashes={n: hashlib.sha256((work / n).read_bytes()).hexdigest()
                                                  for n in ["config.json", "state.json"] if (work / n).exists()})
            # Archive only after completion; the next child sees the same paths.
            work.rename(out / f"saved_{index}_cpu{cpu}")
            records.append(record)
            (out / "results.json").write_text(json.dumps(records, indent=2) + "\n")
            print("DONE", cpu, record["classification"], record["elapsed_seconds"], flush=True)
            if reason or record["classification"] == "setup_error":
                raise RuntimeError(reason or "Invalid setup")
        hashes = [r["generated_input_hashes"] for r in records]
        if any(h != hashes[0] for h in hashes):
            raise RuntimeError("Generated input files differed between trials; comparison is inconclusive")


if __name__ == "__main__":
    main()
