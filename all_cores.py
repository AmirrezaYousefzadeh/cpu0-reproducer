#!/usr/bin/env python3
"""Sequential workload screen of every online, allowed core; no setting changes."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def topology(cpus):
    def read(path):
        try:
            return Path(path).read_text().strip()
        except OSError:
            return None
    rows = []
    for cpu in cpus:
        root = Path(f"/sys/devices/system/cpu/cpu{cpu}")
        core = read(root / "topology/core_id")
        base = read(root / "cpufreq/base_frequency")
        rows.append({"cpu": cpu, "physical_core_id": int(core) if core else None,
                     "base_khz": int(base) if base else None,
                     "package_id": read(root / "topology/physical_package_id")})
    return {"rows": rows, "scope": "Online CPUs allowed by this process affinity"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=ROOT / ".local/host.json")
    p.add_argument("--trials", type=int, default=1)
    p.add_argument("--label", default="all_cores_" + time.strftime("%Y%m%d_%H%M%S"))
    args = p.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.label):
        p.error("Use a simple label")
    if args.trials < 1:
        p.error("At least one trial is required")
    cfg = json.loads(args.config.read_text())
    cpus = sorted(os.sched_getaffinity(0))
    with (ROOT / ".local/controller.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            p.error("Another profile/frequency/all-core comparison is running")
        (ROOT / ".local/latest_sweep.json").write_text(json.dumps(
            {"label": args.label, "cpus": cpus, "trials": args.trials}, indent=2) + "\n")
        command = [sys.executable, "-B", str(ROOT / "run.py"),
                   "--pdk-root", cfg["pdk_root"], "--python", cfg["python"], "--openroad", cfg["openroad"],
                   "--cpus", *map(str, cpus), "--trials", str(args.trials), "--label", args.label]
        print("Sequential sweep of CPUs:", cpus, flush=True)
        print("Profile/frequency matrix is locked out until this sweep finishes.", flush=True)
        # Retain the shared lock in the runner if this wrapper is interrupted.
        # The runner already cleans up its workload on a handled interrupt.
        try:
            code = subprocess.call(command, cwd=ROOT, pass_fds=(lock.fileno(),))
        except KeyboardInterrupt:
            code = 130
        folder = ROOT / "results" / args.label
        if folder.is_dir():
            (folder / "topology.json").write_text(json.dumps(topology(cpus), indent=2) + "\n")
        return code


if __name__ == "__main__":
    raise SystemExit(main())
