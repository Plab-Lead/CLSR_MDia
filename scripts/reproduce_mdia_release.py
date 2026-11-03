#!/usr/bin/env python3
# ruff: noqa: B905, E402
"""Reproduce the MDia 2026-10-05 scalar, paired and frontier evidence offline."""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import socket
import sys
from pathlib import Path

from verify_mdia_release import verify_manifest


def block_network(*args, **kwargs):
    raise RuntimeError("This evidence reproduction runs offline.")


socket.socket.connect = block_network
socket.socket.connect_ex = block_network
socket.create_connection = block_network
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
sys.dont_write_bytecode = True

import numpy as np
from _mdia_evidence_math import (
    bfcl_check_alias,
    bfcl_front,
    bfcl_schema,
    bfcl_stats,
    core_aggregate,
    core_paired,
    crux_close,
    crux_compute,
)

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/research/20261005"


def read(path):
    return json.loads(Path(path).read_text())


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def csvwrite(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open("w", newline="") as f:
        writer = csv.DictWriter(f, fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                    for k, v in row.items()
                }
            )


def numeric_equal(actual, expected):
    crux_close(actual, expected)


def compute_core():
    rows = jsonl(ART / "data/core/paired_case_data.jsonl")
    specs = read(ART / "data/core/pair_specifications.json")["pairs"]
    assert len(rows) == 2752 and len(specs) == 7
    aggregates, pairs = [], []
    for index, spec in enumerate(specs):
        rr = [r for r in rows if r["pair_id"] == spec["pair_id"]]
        assert len(rr) == 2 * spec["n"]
        entry = {"pair_id": spec["pair_id"]}
        for side in ["candidate", "reference"]:
            ss = [r for r in rr if r["side"] == side]
            assert len({r["case_key"] for r in ss}) == spec["n"]
            entry[side] = core_aggregate(ss)
            assert entry[side]["groups"] == spec["groups"]
        aggregates.append(entry)
        p = core_paired(rr, index)
        p.pop("scope")
        pairs.append({"pair_id": spec["pair_id"], **p})
    numeric_equal({"rows": aggregates}, read(ART / "expected/core_aggregates.json"))
    numeric_equal(pairs, read(ART / "expected/core_pairs.json"))
    return aggregates, pairs


def compute_bfcl():
    rows = jsonl(ART / "data/bfcl192/scalar_rows.jsonl")
    for r in rows:
        bfcl_schema(r)
    assert len(rows) == len({r["record_id"] for r in rows}) == 6912
    idx = {(r["arm"], r["group_order"]): r for r in rows}
    assert len(idx) == 6912 and {r["group_order"] for r in rows} == set(range(192))
    assert len({r["source_task_sha256"] for r in rows}) == 192
    assert len({r["group_sha256"] for r in rows}) == 192
    byrecord = {r["record_id"]: r for r in rows}
    for r in rows:
        if r["exact_alias_of_record_id"]:
            bfcl_check_alias(r, byrecord[r["exact_alias_of_record_id"]])
    arm_order = read(ART / "data/bfcl192/cohort_order.json")["arm_order"]
    ref = read(ART / "expected/bfcl192.json")
    assert len(arm_order) == 36
    points = {a: bfcl_stats([idx[(a, i)] for i in range(192)]) for a in arm_order}
    numeric_equal(points, ref["points"])
    draw = np.random.Generator(np.random.PCG64(20261003)).integers(0, 192, (10000, 192))
    paired = []
    for prefix in ["Qwen", "Pro"]:
        a = prefix + ":parent_8192"
        aa = np.array([idx[(a, i)]["correct"] for i in range(192)], dtype=int)
        g = np.array([idx[(a, i)]["generated"] for i in range(192)])
        for b in arm_order:
            if not b.startswith(prefix + ":") or b == a:
                continue
            bb = np.array([idx[(b, i)]["correct"] for i in range(192)], dtype=int)
            h = np.array([idx[(b, i)]["generated"] for i in range(192)])
            diff = (aa - bb) * 100
            unknown = points[a]["unknown_attempts"] + points[b]["unknown_attempts"]
            paired.append(
                dict(
                    candidate=a,
                    control=b,
                    n=192,
                    wins=int(((aa == 1) & (bb == 0)).sum()),
                    losses=int(((aa == 0) & (bb == 1)).sum()),
                    accuracy_diff_pp=float(diff.mean()),
                    accuracy_CI_pp=np.percentile(diff[draw].mean(1), [2.5, 97.5]).tolist(),
                    generated_saving=None if unknown else float(1 - g.mean() / h.mean()),
                    generated_saving_CI=None
                    if unknown
                    else np.percentile(1 - g[draw].mean(1) / h[draw].mean(1), [2.5, 97.5]).tolist(),
                    interval_scope=ref["intervals"],
                )
            )
    numeric_equal(paired, ref["paired"])
    fronts = {
        p: {
            "accuracy_generated": bfcl_front({k: v for k, v in points.items() if k.startswith(p + ":")}),
            "accuracy_generated_input": bfcl_front(
                {k: v for k, v in points.items() if k.startswith(p + ":")}, True
            ),
        }
        for p in ["Qwen", "Pro"]
    }
    numeric_equal(fronts, ref["frontiers"])
    counts = dict(
        incorrect_policy_rows=sum(not r["correct"] for r in rows),
        unparsed_policy_rows=sum(not r["parse_ok"] for r in rows),
        unknown_cost_policy_rows=sum(r["cost_unknown_attempts"] > 0 for r in rows),
        Pro_exact_alias_logical_rows=sum(bool(r["exact_alias_of_record_id"]) for r in rows),
    )
    numeric_equal(counts, ref["failures"])
    return points, paired, fronts


def point_frontier(points, three=False):
    good = [
        p
        for p in points
        if p.get("n")
        and p.get("generated") is not None
        and p.get("input") is not None
        and not p.get("unknown_attempts", 0)
    ]

    def dominates(a, b):
        aa = [a["correct"] / a["n"], -a["generated"]]
        bb = [b["correct"] / b["n"], -b["generated"]]
        if three:
            aa.append(-a["input"])
            bb.append(-b["input"])
        return all(x >= y for x, y in zip(aa, bb)) and any(x > y for x, y in zip(aa, bb))

    return [p["label"] for p in good if not any(dominates(q, p) for q in good)]


def comparator_tables(out):
    baseline = read(ART / "data/core/baseline_source_data.json")["panels"]
    frontier = read(ART / "data/core/frontier_source_data.json")["panels"]
    assert len(baseline) == 14 and sum(len(p["points"]) for p in baseline) == 303
    assert len(frontier) == 8 and sum(len(p["points"]) for p in frontier) == 149
    rows = []
    for panel in baseline:
        for p in panel["points"]:
            rows.append(
                {
                    "setting": panel["setting"],
                    "label": p["label"],
                    "n": p["n"],
                    "groups": p.get("groups"),
                    "trial": p.get("trial"),
                    "correct": p["correct"],
                    "generated": p.get("generated"),
                    "input": p.get("input"),
                    "unknown_attempts": p.get("unknown_attempts"),
                    "cost_status": p.get("cost_status"),
                    "native_params": p.get("native_params"),
                }
            )
    csvwrite(out / "ALL_BASELINE_PANELS.csv", rows)
    fronts = []
    for p in frontier:
        fronts.append(
            {
                "setting": p["setting"],
                "accuracy_generated": point_frontier(p["points"]),
                "accuracy_generated_input": point_frontier(p["points"], True),
            }
        )
    save(out / "CORE_FRONTIERS.json", fronts)
    curated = [{"setting": panel["setting"], **p} for panel in frontier for p in panel["points"]]
    csvwrite(out / "ALL_CURATED_FRONTIER_POINTS.csv", curated)
    flash = [{"setting": panel["setting"], **p} for panel in frontier[2:5] for p in panel["points"]]
    assert len(flash) == 55 and all(p["n"] == 256 for p in flash)
    csvwrite(out / "FLASH256_ALL_POINTS.csv", flash)
    return frontier


def write_tables(out, core, pairs, bfcl, crux):
    source = read(ART / "data/core/setting_table.json")["rows"]
    assert len(source) == len(core) == len(pairs) == 7
    assert all(r["pair_id"] == a["pair_id"] == p["pair_id"] for r, a, p in zip(source, core, pairs))
    rows = []
    for r, a, p in zip(source, core, pairs):
        aa, bb = a["candidate"], a["reference"]
        rows.append(
            {
                "setting": r["setting"],
                "n": aa["n"],
                "groups": aa["groups"],
                "candidate": r["candidate"]["label"],
                "reference": r["reference"]["label"],
                "candidate_correct": aa["correct"],
                "reference_correct": bb["correct"],
                "candidate_generated": aa["generated"],
                "reference_generated": bb["generated"],
                "candidate_input": aa["input"],
                "reference_input": bb["input"],
                "generated_saving_percent": p["generated_saving_percent"],
                "native_recipe": r["native_recipe"],
                "sampling_frame": r["sampling_frame"],
            }
        )
    csvwrite(out / "POSITIVE_RESULTS.csv", rows)
    lines = [
        "# MDia benchmark results",
        "",
        "Native generated tokens per case include reasoning once; inputs are separate.",
        "",
        "| Setting | Cases / groups | Correct: MDia / comparator | Generated: MDia / comparator | Input: MDia / comparator |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['setting']} | {r['n']} / {r['groups']} | "
            f"{r['candidate_correct']} / {r['reference_correct']} | "
            f"{r['candidate_generated']:.3f} / {r['reference_generated']:.3f} | "
            f"{r['candidate_input']:.3f} / {r['reference_input']:.3f} |"
        )
    (out / "POSITIVE_RESULTS.md").write_text("\n".join(lines) + "\n")
    csvwrite(out / "BFCL192_ALL_POINTS.csv", [{"arm": k, **v} for k, v in bfcl.items()])
    cruxrows = [{"backbone": p, "arm": a, **v} for p, dd in crux.items() for a, v in dd.items()]
    csvwrite(out / "CRUX192_ALL_POINTS.csv", cruxrows)


def plot_positive_panels(out, panels, bfcl):
    os.environ["MPLCONFIGDIR"] = str(out / ".mplcache")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

    plt.rcParams.update({"font.size": 10, "svg.hashsalt": "MDia-release-20261005"})
    fig, axs = plt.subplots(2, 3, figsize=(17, 10), layout="constrained")
    highlights = [
        "obligation-frontiers-20260927-v1-mdia",
        "parent_8192",
        "parent_8192",
        "compiled128_2048",
        "python_state",
    ]
    settings = read(ART / "data/core/setting_table.json")["rows"]
    for ix, panel in enumerate(panels[:5]):
        ax = axs.flat[ix]
        points = panel["points"]
        setting = panel["setting"]
        if ix == 1:
            points = [
                {
                    "label": k.split(":", 1)[1],
                    "n": v["n"],
                    "correct": v["correct"],
                    "generated": v["mean_generated"],
                    "input": v["mean_input"],
                    "unknown_attempts": v["unknown_attempts"],
                }
                for k, v in bfcl.items()
                if k.startswith("Qwen:")
            ]
            setting = "BFCL / Qwen — common 192"
        good = [p for p in points if p.get("generated") is not None and not p.get("unknown_attempts", 0)]
        for p in good:
            target_id = settings[ix]["candidate"].get("policy_id")
            highlight = (
                p["label"] == highlights[ix]
                or (ix == 3 and p["label"] == "historical__" + highlights[ix])
                or (target_id is not None and p.get("policy_id") == target_id)
            )
            ax.scatter(
                p["generated"],
                100 * p["correct"] / p["n"],
                s=45 + min(p.get("input") or 0, 1500) * 0.11,
                color="#1465c0" if highlight else "#a0a9b4",
                marker="*" if highlight else "o",
                alpha=0.95 if highlight else 0.7,
                linewidths=0.7,
                edgecolors="#ffffff",
                zorder=4 if highlight else 2,
            )
            if highlight:
                ax.annotate(
                    "MDia",
                    (p["generated"], 100 * p["correct"] / p["n"]),
                    xytext=(9, 9),
                    textcoords="offset points",
                    fontweight="bold",
                    color="#1465c0",
                )
        ff = point_frontier(points)
        line = sorted([p for p in good if p["label"] in ff], key=lambda p: p["generated"])
        if line:
            ax.plot(
                [p["generated"] for p in line],
                [100 * p["correct"] / p["n"] for p in line],
                color="#6e8095",
                linewidth=1,
                zorder=1,
            )
        ax.set_title(setting)
        ax.set_xscale("log")
        ax.xaxis.set_major_locator(LogLocator(base=10, numticks=4))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, pos: f"{x:g}"))
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.set_xlabel("Native generated tokens / case")
        ax.set_ylabel("Registered accuracy (%)")
        ax.grid(alpha=0.2)
        ax.margins(x=0.25, y=0.15)
        unavailable = len(points) - len(good)
        if unavailable:
            ax.text(
                0.02,
                0.03,
                f"All {len(points)} labelled points included in data",
                transform=ax.transAxes,
                fontsize=8,
                color="#667085",
            )
    axs.flat[5].axis("off")
    axs.flat[5].text(0.03, 0.92, "MDia evidence release", fontsize=22, weight="bold", color="#1465c0")
    axs.flat[5].text(
        0.03,
        0.75,
        "Five benchmarks · Three LLM families\n"
        "Complete comparator panels\n"
        "Whole-group paired reproduction\n"
        "Native input and generated usage\n\n"
        "Blue stars: retained MDia specialists\n"
        "Bubble size: separate input tokens\n"
        "Full numerical panels accompany this view",
        fontsize=13,
        linespacing=1.8,
        va="top",
    )
    fig.savefig(out / "POSITIVE_FRONTIERS.png", dpi=150)
    fig.savefig(out / "POSITIVE_FRONTIERS.svg", metadata={"Date": None})
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="A new output directory")
    args = parser.parse_args()
    checksums = verify_manifest(ROOT)
    out = args.output.resolve()
    if out.exists():
        parser.error("Choose a new output directory.")
    out.mkdir(parents=True)
    core, pairs = compute_core()
    bfcl, bpairs, bfronts = compute_bfcl()
    crux = crux_compute(ART / "data/crux192")
    numeric_equal(crux["points.json"], read(ART / "expected/crux192_table_source_data.json"))
    numeric_equal(crux["paired.json"], read(ART / "expected/crux192_paired_results.json"))
    numeric_equal(crux["frontiers.json"], read(ART / "expected/crux192_frontiers.json"))
    for name, value in [
        ("CORE_AGGREGATES.json", core),
        ("CORE_PAIRED.json", pairs),
        ("BFCL192_POINTS.json", bfcl),
        ("BFCL192_PAIRED.json", bpairs),
        ("BFCL192_FRONTIERS.json", bfronts),
        ("CRUX192_POINTS.json", crux["points.json"]),
        ("CRUX192_PAIRED.json", crux["paired.json"]),
        ("CRUX192_FRONTIERS.json", crux["frontiers.json"]),
    ]:
        save(out / name, value)
    panels = comparator_tables(out)
    write_tables(out, core, pairs, bfcl, crux["points.json"])
    plot_positive_panels(out, panels, bfcl)
    validation = {
        "passed": True,
        "checksummed_files": checksums,
        "scalar_rows": 16576,
        "core_pairs": 7,
        "BFCL192_points": 36,
        "BFCL192_contrasts": 34,
        "CRUX192_points": 36,
        "CRUX192_contrasts": 52,
        "baseline_panels": 14,
        "baseline_rows": 303,
        "all_reference_values_match": True,
        "network_calls": 0,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "matplotlib": sys.modules["matplotlib"].__version__,
    }
    save(out / "VALIDATION.json", validation)
    print(json.dumps(validation))


if __name__ == "__main__":
    main()
