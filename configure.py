#!/usr/bin/env python3
"""Validate an existing toolchain and save ignored, machine-local paths."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--pdk-root", type=Path, required=True)
p.add_argument("--python", default=sys.executable)
p.add_argument("--openroad", default=shutil.which("openroad"))
p.add_argument("--cpus", nargs="+", type=int, default=[0, 6])
args = p.parse_args()
if not args.openroad:
    p.error("OpenROAD must be on PATH, or supplied with --openroad")
cfg = {"pdk_root": str(args.pdk_root.resolve()), "python": str(Path(args.python).absolute()),
       "openroad": str(Path(args.openroad).absolute())}
subprocess.run([sys.executable, "-B", str(root / "run.py"), "--check", "--label", "configure",
                "--pdk-root", cfg["pdk_root"], "--python", cfg["python"], "--openroad", cfg["openroad"],
                "--cpus", *map(str, args.cpus)], check=True)
(root / ".local").mkdir(exist_ok=True)
(root / ".local/host.json").write_text(json.dumps(cfg, indent=2) + "\n")
print("Saved .local/host.json (ignored by Git)")

