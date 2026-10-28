#!/usr/bin/env python3
"""Summarize a completed or in-progress core sweep without changing test settings."""
import argparse
import json
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("label")
    args = p.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.label):
        p.error("Use a simple results label")
    folder = ROOT / "results" / args.label
    metadata = json.loads((folder / "metadata.json").read_text())
    results = json.loads((folder / "results.json").read_text())
    topology = json.loads((folder / "topology.json").read_text()) if (folder / "topology.json").exists() else {}
    info = {r["cpu"]: r for r in topology.get("rows", [])}
    rows = []
    for cpu in metadata["cpus"]:
        records = [r for r in results if r["cpu"] == cpu]
        trials = []
        for record in records:
            trace = folder / f"trial{record['trial']}_cpu{cpu}/telemetry.jsonl"
            samples = [json.loads(line) for line in trace.read_text().splitlines()] if trace.exists() else []
            clocks = [int(s["frequency_khz"]) / 1000 for s in samples[1:] if s.get("frequency_khz")]
            trials.append({"trial": record["trial"],
                           "result": "inconclusive_safety_stop" if record["stop_reason"] else record["classification"],
                           "stop_reason": record["stop_reason"], "elapsed_seconds": record["elapsed_seconds"],
                           "maximum_sampled_temperature_c": record["max_sampled_temperature_c"],
                           "median_sampled_mhz": round(statistics.median(clocks), 1) if clocks else None,
                           "coordinator_cpu": record.get("coordinator_cpu")})
        rows.append({"cpu": cpu, "physical_core_id": info.get(cpu, {}).get("physical_core_id"),
                     "base_khz": info.get(cpu, {}).get("base_khz"), "trials": trials})
    complete = len(results) == len(metadata["cpus"]) * metadata["trials"]
    summary = {"label": args.label, "complete": complete, "profile": metadata.get("profile"),
               "bios": metadata.get("bios"), "microcode": metadata.get("microcode"),
               "completed_trials": len(results), "expected_trials": len(metadata["cpus"]) * metadata["trials"],
               "cores_with_crashes": [r["cpu"] for r in rows if any(t["result"] == "SIGSEGV" for t in r["trials"])],
               "cores_with_passes": [r["cpu"] for r in rows if any(t["result"] == "pass" for t in r["trials"])],
               "rows": rows, "limits": "Finite workload trials; a pass is not a CPU health certificate. Timeouts/setup errors are inconclusive."}
    (folder / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = [f"Core sweep: {args.label}", "", f"Completed: {len(results)}/{summary['expected_trials']} trials. Complete: {complete}.", "",
             "| Logical CPU | Physical core ID | Trial results | Elapsed seconds | Maximum sampled C |",
             "|---:|---:|---|---|---|"]
    for row in rows:
        ts = row["trials"]
        lines.append(f"| {row['cpu']} | {row['physical_core_id']} | " +
                     (", ".join(t["result"] for t in ts) or "pending") + " | " +
                     ", ".join(str(t["elapsed_seconds"]) for t in ts) + " | " +
                     ", ".join(str(t["maximum_sampled_temperature_c"]) for t in ts) + " |")
    (folder / "summary.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({k: summary[k] for k in ["complete", "completed_trials", "expected_trials", "cores_with_crashes", "cores_with_passes"]}))


if __name__ == "__main__":
    main()
