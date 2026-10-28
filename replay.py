#!/usr/bin/env python3
"""Replay only the saved CTS step, using the selected LibreLane environment."""
import argparse
import json
from pathlib import Path
import librelane
from librelane.steps import Step

p = argparse.ArgumentParser()
p.add_argument("--trial", required=True, type=Path)
p.add_argument("--pdk-root", required=True, type=Path)
args = p.parse_args()
root = Path(__file__).resolve().parent
replacements = {"@FIXTURE_DIR@": str(root / "fixture"),
                "@PDK_ROOT@": str(args.pdk_root.resolve()),
                "@LIBRELANE_SCRIPTS@": str(Path(librelane.__file__).parent / "scripts")}
for name in ("config", "state"):
    text = (root / "fixture" / f"{name}.template.json").read_text()
    # Substitute parsed strings, so spaces and backslashes remain valid JSON.
    def expand(v):
        if isinstance(v, dict):
            return {k: expand(x) for k, x in v.items()}
        if isinstance(v, list):
            return [expand(x) for x in v]
        if isinstance(v, str):
            for old, new in replacements.items():
                v = v.replace(old, new)
        return v
    (args.trial / f"{name}.json").write_text(json.dumps(expand(json.loads(text)), indent=2) + "\n")
step = Step.load(str(args.trial / "config.json"), str(args.trial / "state.json"),
                 pdk_root=str(args.pdk_root.resolve()))
step.start(step_dir=str(args.trial / "step"))
print("CPU_AFFINITY_REPRO_SUCCESS", flush=True)

