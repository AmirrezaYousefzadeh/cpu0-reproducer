#!/usr/bin/env python3
"""Bounded, single-core screening with published Prime95/mprime (not bundled)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import time
from run import sample, stop, now

ROOT = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--binary", type=Path, required=True)
    p.add_argument("--cpus", type=int, nargs="+", default=[0, 6])
    p.add_argument("--seconds", type=int, default=180)
    p.add_argument("--label", required=True)
    args = p.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.label) or not 15 <= args.seconds <= 3600:
        p.error("Invalid label or duration")
    if not set(args.cpus).issubset(os.sched_getaffinity(0)):
        p.error("Unavailable CPU")
    guard = ROOT / ".build/disable_core.so"
    if not guard.exists():
        p.error("Run the CTS reproducer once to build the core-dump guard")
    out = ROOT / "results" / args.label
    out.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {7}); os.nice(19)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    records = []
    for cpu in args.cpus:
        directory = out / f"cpu{cpu}"; directory.mkdir()
        config = "UsePrimenet=0\nStressTester=1\nTortureCores=1\nTortureHyperthreading=0\nTortureMultiThreadedFFTs=0\nEnableSetAffinity=0\nEnableSetPriority=0\nMinTortureFFT=8\nMaxTortureFFT=64\nTortureMem=0\nTortureTime=1\n"
        (directory / "prime.txt").write_text(config)
        env = os.environ.copy()
        env.update(LD_PRELOAD=str(guard), TMPDIR=str(directory))
        command = ["taskset", "-c", str(cpu), str(args.binary.resolve()), "-d", "-t", "-W" + str(directory)]
        begin = time.monotonic(); process = None; reason = None; maximum = 0
        print("START Prime95 cpu", cpu, flush=True)
        try:
            with (directory / "stdout.log").open("w") as log, (directory / "telemetry.jsonl").open("w") as trace:
                process = subprocess.Popen(command, cwd=directory, env=env, stdin=subprocess.DEVNULL,
                                           stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                while process.poll() is None and time.monotonic() - begin < args.seconds:
                    s = sample(cpu)
                    s["thread_affinity"] = {t.name: sorted(os.sched_getaffinity(int(t.name)))
                                            for t in Path(f"/proc/{process.pid}/task").glob("[0-9]*") if t.exists()}
                    trace.write(json.dumps(s) + "\n"); trace.flush()
                    maximum = max([maximum, *s["temperatures_c"].values()])
                    if not s["temperatures_c"] or maximum >= 85:
                        reason = "temperature safety stop"
                    if any(v != [cpu] for v in s["thread_affinity"].values()):
                        reason = "test thread escaped requested CPU"
                    texts = "\n".join(f.read_text(errors="replace") for f in directory.glob("*.txt"))
                    if re.search(r"FATAL ERROR|HARDWARE FAILURE|ILLEGAL SUMOUT|ROUNDING WAS", texts, re.I):
                        reason = "Prime95 reported an error"
                    if reason:
                        break
                    time.sleep(2)
                if process.poll() is None:
                    process.send_signal(signal.SIGINT)
                    try:
                        process.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        stop(process)
        finally:
            if process is not None:
                stop(process)
        texts = "\n".join(f.read_text(errors="replace") for f in directory.glob("*.txt"))
        successes = re.findall(r"Self-test.*?passed", texts, re.I)
        records.append({"cpu": cpu, "command": command, "requested_seconds": args.seconds,
                        "elapsed_seconds": round(time.monotonic() - begin, 3), "stop_reason": reason,
                        "completed_self_tests_reported": len(successes), "maximum_sampled_temperature_c": maximum,
                        "classification": "errors_detected" if reason == "Prime95 reported an error" else
                            ("short_screen_no_errors" if not reason and successes else "inconclusive"),
                        "binary_sha256": hashlib.sha256(args.binary.read_bytes()).hexdigest()})
        (out / "results.json").write_text(json.dumps(records, indent=2) + "\n")
        print(json.dumps(records[-1]), flush=True)
        if reason and reason != "Prime95 reported an error":
            break


if __name__ == "__main__":
    main()
