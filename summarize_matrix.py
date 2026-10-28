#!/usr/bin/env python3
"""Produce a portable profile/frequency report from a matrix status file."""
import argparse
import json
from pathlib import Path
import re
import signal
import statistics

ROOT = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("label")
    args = p.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.label):
        p.error("Use a simple results label")
    folder = ROOT / "results" / args.label
    status = json.loads((folder / "status.json").read_text())
    rows = []
    for phase in status["phases"]:
        trial_folder = ROOT / phase["result_directory"]
        result_file = trial_folder / "results.json"
        records = phase.get("results")
        if records is None:
            records = json.loads(result_file.read_text()) if result_file.exists() else []
        for record in records:
            cpu = record["cpu"]
            trace = trial_folder / f"trial{record['trial']}_cpu{cpu}/telemetry.jsonl"
            samples = [json.loads(line) for line in trace.read_text().splitlines()] if trace.exists() else []
            # Exclude the first sample, which can precede application startup.
            clocks = [int(s["frequency_khz"]) / 1000 for s in samples[1:] if s.get("frequency_khz")]
            expected = phase["expected_limits_khz"]
            limit = expected.get(str(cpu), expected.get(cpu))
            log = trial_folder / f"trial{record['trial']}_cpu{cpu}/workload.log"
            numbers = sorted({int(n) for n in re.findall(r"Signal\s+(\d+)\s+received", log.read_text())}) if log.exists() else []
            names = [signal.Signals(n).name if n in signal.valid_signals() else str(n) for n in numbers]
            rows.append({
                "phase": phase["name"], "profile": phase["profile"],
                "cpu": cpu, "trial": record["trial"],
                "requested_ceiling_mhz": limit / 1000 if limit is not None else None,
                "result": "inconclusive_safety_stop" if record["stop_reason"] else record["classification"],
                "stop_reason": record["stop_reason"], "elapsed_seconds": record["elapsed_seconds"],
                "application_signals_in_log": names,
                "maximum_sampled_temperature_c": record["max_sampled_temperature_c"],
                "sampled_frequency_mhz": {
                    "count": len(clocks),
                    "minimum": round(min(clocks), 1) if clocks else None,
                    "median": round(statistics.median(clocks), 1) if clocks else None,
                    "maximum": round(max(clocks), 1) if clocks else None},
                "sampled_epp_values": sorted({s["epp"] for s in samples if s.get("epp")}),
                "all_sampled_ceilings_match": bool(samples) and all(
                    int(s["maximum_khz"]) == limit for s in samples if s.get("maximum_khz"))})
    summary = {"label": args.label, "started": status["started"],
               "finished": status.get("finished"), "error": status.get("error"),
               "restoration_verified": status["restoration_verified"],
               "restoration_errors": status.get("restoration_errors", []),
               "candidate_limit_mhz": status.get("candidate_limit_mhz"),
               "confirmed_passing_candidate_limit_mhz": status.get("confirmed_passing_candidate_limit_mhz"),
               "interpretation": status.get("interpretation"), "rows": rows,
               "measurement_limit": "scaling_cur_freq sampled every five seconds; startup/idle samples and missed transients are possible. Requested ceiling and sampled frequency are distinct. Finite passes do not establish long-term stability or a global highest passing frequency."}
    (folder / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = [f"Profile/frequency matrix: {args.label}", "",
             f"Finished: {bool(summary['finished'])}. Restoration verified: {summary['restoration_verified']}.", "",
             "| Phase | Profile | CPU | Trial | Ceiling MHz | Result | Seconds | Median sampled MHz | Maximum sampled C |",
             "|---|---|---:|---:|---:|---|---:|---:|---:|"]
    for row in rows:
        result = row["result"]
        if row["application_signals_in_log"]:
            result += " (" + ", ".join(row["application_signals_in_log"]) + ")"
        lines.append("| " + " | ".join(str(v) for v in [row["phase"], row["profile"], row["cpu"], row["trial"],
                     row["requested_ceiling_mhz"], result, row["elapsed_seconds"],
                     row["sampled_frequency_mhz"]["median"], row["maximum_sampled_temperature_c"]]) + " |")
    lines.extend(["", summary["measurement_limit"]])
    if summary["error"]:
        lines.extend(["", "Controller error: " + summary["error"]])
    if summary["interpretation"]:
        lines.extend(["", summary["interpretation"]])
    (folder / "summary.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({k: summary[k] for k in ["label", "finished", "error", "restoration_verified", "confirmed_passing_candidate_limit_mhz"]}))


if __name__ == "__main__":
    main()
