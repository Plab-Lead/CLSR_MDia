#!/usr/bin/env python3
"""Summarize accuracy-token frontier rows from compact MDia outputs."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mdia.io_utils import write_csv  # noqa: E402


def read_outputs(path: str | Path) -> list[dict]:
    rows = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def summarize(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["benchmark"], row.get("method") or row.get("route") or "unknown")].append(row)
    out = []
    for (benchmark, route), items in sorted(grouped.items()):
        n = len(items)
        correct = [item for item in items if item.get("success") is True]
        parse_ok = [item for item in items if item.get("parse_ok") is True]
        out.append(
            {
                "benchmark": benchmark,
                "method": route,
                "n": n,
                "accuracy": len(correct) / n if n else 0.0,
                "parse_rate": len(parse_ok) / n if n else 0.0,
                "mean_completion_tokens": sum(float(item.get("completion_tokens") or 0) for item in items) / n,
                "mean_total_tokens": sum(float(item.get("total_tokens") or 0) for item in items) / n,
            }
        )
    return out


def attach_targets(summary: list[dict], baseline_csv: str | Path | None) -> list[dict]:
    if not baseline_csv:
        return summary
    by_benchmark = defaultdict(list)
    with Path(baseline_csv).open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            by_benchmark[row["benchmark"]].append(row)
    targets = {}
    for benchmark, rows in by_benchmark.items():
        targets[benchmark] = {
            "best_baseline_accuracy": max(float(row["accuracy"]) for row in rows),
            "lowest_baseline_completion_tokens": min(float(row["mean_completion_tokens"]) for row in rows),
        }
    for row in summary:
        target = targets.get(row["benchmark"])
        if target:
            row.update(target)
            row["official_win"] = (
                row["accuracy"] > target["best_baseline_accuracy"]
                and row["mean_completion_tokens"] < target["lowest_baseline_completion_tokens"]
            )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs", required=True, help="Compact selected routed outputs JSONL.")
    parser.add_argument("--baseline-csv", default=None, help="Aggregate baseline CSV with accuracy and mean_completion_tokens.")
    parser.add_argument("--out-csv", required=True, help="Summary CSV path.")
    args = parser.parse_args()

    rows = read_outputs(args.outputs)
    summary = attach_targets(summarize(rows), args.baseline_csv)
    write_csv(args.out_csv, summary)
    print(f"Wrote {args.out_csv} ({len(summary)} rows)")


if __name__ == "__main__":
    main()
