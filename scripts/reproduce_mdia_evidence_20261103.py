#!/usr/bin/env python3
"""Reproduce the November MDia tables from anonymous numerical records, offline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sys
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

RELEASE = Path(__file__).resolve().parents[1] / "artifacts/research/20261103"


def ensure(condition, why):
    if not condition:
        raise ValueError(why)


def signed(value):
    rounded = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return format(rounded, "+.2f")


def csv_text(rows):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=rows[0], lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def token_delta(left, right):
    ensure(right > 0, "zero token denominator")
    return 100 * (left - right) / right


def correct_pair(r):
    n = r["questions"]
    ensure(type(n) is int and 0 < r["groups"] <= n, r["id"] + ": denominators")
    marginals = [a["correct"] for a in r["arms"]]
    ensure(len(marginals) == 2 and all(type(v) is int and 0 <= v <= n for v in marginals), r["id"])
    x = r["paired_counts"]
    if x is None:
        return tuple(marginals)
    ensure(
        len(x) == 4 and all(type(v) is int and v >= 0 for v in x) and sum(x) == n,
        r["id"] + ": paired coverage",
    )
    left, right, both, _ = x
    ensure([left + both, right + both] == marginals, r["id"] + ": paired/marginal discrepancy")
    return left + both, right + both


def deployment_contrast(table, n):
    """Resample whole BFCL tasks exactly using their joint signed differences."""
    values = {"loss": -1, "tie": 0, "win": 1}
    hist = Counter()
    for i, x in values.items():
        for j, y in values.items():
            count = table[i][j]
            ensure(type(count) is int and count >= 0, "invalid paired deployment count")
            if count:
                hist[x - y] += count
    ensure(sum(hist.values()) == n, "BFCL deployment pairing")
    # Coefficients of (sum_k hist[k] z^k)^n count all bootstrap resamples.
    weights = {0: 1}
    for _ in range(n):
        nxt = Counter()
        for total, ways in weights.items():
            for k, count in hist.items():
                nxt[total + k] += ways * count
        weights = nxt
    den = n**n
    ensure(sum(weights.values()) == den, "bootstrap mass")

    def quantile(percent_thousand):
        accumulated = 0
        for k, count in sorted(weights.items()):
            accumulated += count
            if 1000 * accumulated >= percent_thousand * den:
                return 100 * k / n
        raise ValueError("empty bootstrap distribution")

    return 100 * sum(k * v for k, v in hist.items()) / n, [quantile(25), quantile(975)]


def outputs(data):
    rows = data["comparisons"]
    ids = {r["id"]: r for r in rows}
    ensure(len(ids) == len(rows), "duplicate comparison id")
    evidence = []
    meters = []
    table = [
        "# Benchmark comparisons",
        "",
        "Counts are paired on the stated cohort. Change in tokens uses recorded native input plus generation. "
        "Intervals are the archived, unadjusted group-paired 95% intervals; a dash means none was supplied for this contrast. "
        "The accompanying [scope and methods](README.md) describe exposure, accounting and the controls.",
        "",
        "| Benchmark · receiver | Procedure vs comparator | Questions / groups | Correct | Gain (pp) | 95% interval (pp) | Total tokens | Other controls (correct, same cohort) |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        x, y = correct_pair(r)
        a, b = r["arms"]
        n = r["questions"]
        ensure(all(k in data["source_report_sha256"] for k in r["sources"]), r["id"] + ": source")
        gain = 100 * (x - y) / n
        for name, m in zip(r["arm_names"], r["arms"], strict=True):
            for k in ("input_tokens", "generation_tokens"):
                ensure(type(m[k]) is int and m[k] >= 0, r["id"] + ": " + k)
            coverage = m["latency_rows"]
            ensure(coverage is None or 0 <= coverage <= n, r["id"] + ": latency coverage")
            meters.append(dict(comparison=r["id"], arm=name, **m))
        tc = token_delta(
            a["input_tokens"] + a["generation_tokens"], b["input_tokens"] + b["generation_tokens"]
        )
        ci = r["archived_interval95_pp"]
        if ci is not None:
            ensure(len(ci) == 2 and -100 <= ci[0] <= ci[1] <= 100, "invalid interval")
        evidence.append(
            dict(
                comparison=r["id"],
                benchmark=r["benchmark"],
                model=r["model"],
                procedure=r["procedure"],
                reference=r["reference"],
                scope=r["scope"],
                questions=n,
                whole_groups=r["groups"],
                procedure_correct=x,
                reference_correct=y,
                difference_pp=signed(gain),
                archived_ci_lower_pp="" if ci is None else signed(ci[0]),
                archived_ci_upper_pp="" if ci is None else signed(ci[1]),
                recorded_total_tokens_change_pct=signed(tc),
            )
        )
        model = r["model"].split("/")[-1]
        context = "; ".join(
            f"{label.split(':')[-1].replace('_', ' ')}: {score}"
            for label, score in r["comparison_context"].items()
        )
        bench = r["benchmark"] + (" (Level 5)" if r["id"] == "math-flash" else "")
        table.append(
            f"| {bench} · {model} | {r['procedure']} vs {r['reference']} | {n} / {r['groups']} | {x} / {y} | "
            f"{signed(gain)} | {', '.join(map(signed, ci)) if ci is not None else '—'} | {signed(tc)}% | {context} |"
        )

    d = data["diagnostics"]
    findings = [
        "# Where the differences arise",
        "",
        "These paired analyses concern supplied procedures, recorded outputs and evaluator decisions on exposed cohorts.",
        "",
        "| QA comparison | Both answers extractable | Only procedure correct / only English correct among those pairs | Net gain outside those pairs |",
        "|---|---:|---:|---:|",
    ]
    for key, v in d["qa_extraction"].items():
        r = ids[key]
        x, y = correct_pair(r)
        bins = v["bins"]
        ensure(all(len(z) == 5 and sum(z[1:]) == z[0] for z in bins.values()), "QA extraction bins")
        ensure(
            [sum(z[i] for z in bins.values()) for i in range(1, 5)] == r["paired_counts"],
            "QA extraction totals",
        )
        parts = list(v["partitions"].values())
        ensure(
            sum(t["questions"] for t in parts) == r["questions"]
            and [sum(t["counts"][i] for t in parts) for i in (0, 1)] == [x, y],
            "QA added cohorts",
        )
        n, wins, losses, _, _ = bins["both_accepted"]
        findings.append(
            f"| {r['benchmark']} · {r['model'].split('/')[-1]} | {n}/{r['questions']} | {wins} / {losses} | {x - y - (wins - losses):+d} |"
        )
    findings.extend(
        [
            "",
            "On both MultiHop deployments, the whole margin occurred among pairs with extractable answers. "
            "On AIME, extraction also contributed. These observations locate score differences in the outputs; they do not identify a change in internal reasoning.",
            "",
            "| Stronger English comparison | Correct (procedure / English) | Accuracy 95% interval (pp) | Change in recorded total tokens |",
            "|---|---:|---:|---:|",
        ]
    )
    for key, control in [("gpqa-pro", "Source:obligation_english"), ("multihop-pro", "NL:flat_terminal")]:
        r = ids[key]
        a = r["arms"][0]
        v = d["qa_extraction"][key]
        change = token_delta(a["input_tokens"] + a["generation_tokens"], sum(v["control_tokens"][control]))
        findings.append(
            f"| {r['benchmark']} · {control.split(':')[-1].replace('_', ' ')} | {a['correct']} / {r['comparison_context'][control]} | {', '.join(map(signed, d['strong_english_accuracy_intervals'][key]))} | {signed(change)}% |"
        )
    findings += [
        "",
        "Both paired intervals for the accuracy difference against these stronger English controls include zero.",
        "",
        "## Recipient and output format",
        "",
        "| Reference | Additional GEPA gain on Kimi-K2.7-Code relative to Kimi-K2.6 (pp) | Exact paired bootstrap 95% interval (pp) |",
        "|---|---:|---:|",
    ]
    for ref, v in d["bfcl_deployment"].items():
        value, ci = deployment_contrast(v["code_by_kimi_win_tie_loss"], ids["bfcl-code"]["questions"])
        ensure(
            all(
                math.isclose(x, y, abs_tol=1e-10)
                for x, y in zip(ci, v["paired_interaction_interval95_pp"], strict=True)
            ),
            "BFCL interaction interval",
        )
        findings.append(f"| {ref.replace('_', ' ')} | {signed(value)} | {signed(ci[0])}, {signed(ci[1])} |")
    b = d["bfcl_code_envelope"]
    counts = b["procedure_only"]
    par = b["parallel_procedure_only"]
    ensure(sum(counts.values()) == ids["bfcl-code"]["paired_counts"][0], "BFCL envelope coverage")
    findings += [
        "",
        f"On Code, {counts['identical_call_objects']} of {sum(counts.values())} procedure-only wins contained the same proposed calls as English "
        f"but differed in output format. This held for {par['identical_call_objects']}/{sum(par.values())} procedure-only wins on parallel calls. "
        "Both optimized procedures were written in English. These wins locate a difference at the output contract.",
        "",
    ]
    z = d["bfcl_common_errors"]
    expectation = z["recovered_Pro"] * z["recovered_Qwen"] / z["common_reference_errors"]
    findings.append(
        f"DeepSeek and Qwen each recovered {z['recovered_Pro']} of the {z['common_reference_errors']} tasks both English controls missed. "
        f"The observed overlap was {z['recovered_by_both']}; the expected overlap conditional on the two recovery counts was {expectation:g}."
    )
    m = d["math_partitions"]
    a, b = correct_pair(ids["math-flash"])
    ensure(
        [a + m["complement"]["counts"][0], b + m["complement"]["counts"][1]] == m["full"]["counts"]
        and ids["math-flash"]["questions"] + m["complement"]["questions"] == m["full"]["questions"],
        "MATH subgroup and complement",
    )
    findings += [
        "",
        "## Subgroup and instruction effects",
        "",
        f"On MATH Level 5, derive-and-substitute solved {a} questions and English solved {b}. The other {m['complement']['questions']} questions "
        f"gave {m['complement']['counts'][0]} versus {m['complement']['counts'][1]}, yielding a full-panel tie at {m['full']['counts'][0]}/{m['full']['questions']}.",
        "",
    ]
    a, b = correct_pair(ids["lcb-flash"])
    c, e = d["lcb_machine_frame"]
    interaction = 100 * ((c - e) - (a - b)) / ids["lcb-flash"]["questions"]
    ci = d["lcb_interaction_interval95_pp"]
    findings += [
        f"On LiveCodeBench, the symbolic / lexical counts were {a} / {b} with ordinary-English reasoning instructions and {c} / {e} "
        f"with machine-dialect instructions. The interaction was {signed(interaction)} pp (archived 95% interval {signed(ci[0])} to {signed(ci[1])}). "
        "The procedures differ in wording and length as well as notation.",
        "",
        "## Construction history",
        "",
    ]
    t = d["origin_transitions"]["lsf"]
    ensure(t == d["origin_transitions"]["natural"], "construction and matched English")
    findings.append(
        f"Before construction, GLM and Qwen delivered different instructions on {t['different_to_equal'] + t['different_to_different']}/{sum(t.values())} groups. "
        f"After construction, they differed on {t['equal_to_different'] + t['different_to_different']}/{sum(t.values())}. "
        f"GLM changed to match Qwen on {d['converged_changed_family']['GLM_only']} groups. Matched English had the same transition counts. Equality here means identical instruction text."
    )
    added = d["crux_added"]
    replay = d["musr_replay_components"]
    screen = d["raw_screen"]
    findings.extend(
        [
            "",
            "## Comparison scope",
            "",
            f"On the 64 CRUX groups added to the selective-integrity panel, the procedure solved {added['procedure']} and English piece trace solved {added['English piece trace']}. The 192- and 256-group panels overlap.",
            "",
            f"The MuSR question-based baseline replay combined two fixed controls for {sum(z['correct_questions'] for z in replay.values())}/{sum(z['questions'] for z in replay.values())} correct. Its components were chosen retrospectively; this was not an online router.",
            "",
            f"Across the four full panels with same-cap Raw comparisons (FOLIO, MuSR, BBEH and MMLU-Pro), {screen['positive']} of {screen['compatible']} compatible registered contrasts favored the procedure. "
            "Their named positive comparisons appear in the table. The breadth count represents benchmarks; it is not a win rate or a fully crossed family-by-benchmark design.",
        ]
    )
    findings.extend(
        [
            "",
            "## Reading an action from a working note",
            "",
            "A calibration on synthetic tasks measured how often the same reader found a single explicitly tagged choice. "
            "The two information conditions used 16 notes per model. Counts below refer to readable choices, not benchmark accuracy.",
            "",
            "| Native model | Full-information tagged / notes | Local-information tagged / notes |",
            "|---|---:|---:|",
        ]
    )
    for prefix, model in [("glm52", "GLM-5.2"), ("qwen36", "Qwen3.6-35B-A3B"), ("kimi26", "Kimi-K2.6")]:
        records = [d["synthetic_records"][f"{prefix}__{cond}_generic_record"] for cond in ("full", "local")]
        findings.append(
            f"| {model} | " + " | ".join(f"{t['tagged_choice']}/{t['notes']}" for t in records) + " |"
        )
    findings.extend(
        [
            "",
            "Two further Qwen calibrations compared strict parsing with a frozen renderer on the same model responses.",
            "",
            "| Calibration | Full: strict / rendered correct | Local: strict / rendered correct | Cases per condition |",
            "|---|---:|---:|---:|",
        ]
    )
    for label, pairs in d["synthetic_calibration"].items():
        full, local = pairs["full"], pairs["local"]
        ensure(full["complete"] == local["complete"], "calibration coverage")
        for point in pairs.values():
            gain = point["correct_observed"] - point["raw_correct_observed"]
            ensure(
                0 <= gain + 2 * point["raw_to_render_harms"] <= point["render_changes"] <= point["complete"],
                "calibration changes do not reconcile",
            )
        findings.append(
            f"| {label} | {full['raw_correct_observed']} / {full['correct_observed']} | "
            f"{local['raw_correct_observed']} / {local['correct_observed']} | {full['complete']} |"
        )
    findings.extend(
        [
            "",
            "Rendering made existing choices scoreable. These small calibrations measure answer delivery; "
            "they do not test transmission between agents and are outside the benchmark count.",
        ]
    )
    return {
        "COMPARISONS.md": "\n".join(table) + "\n",
        "FINDINGS.md": "\n".join(findings) + "\n",
        "comparisons.csv": csv_text(evidence),
        "serving.csv": csv_text(meters),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--check",
        action="store_true",
        help="verify the release manifest and regenerate all four outputs in memory",
    )
    action.add_argument("--output", type=Path, help="write the four outputs to an empty directory")
    opt = parser.parse_args()
    result = outputs(json.loads((RELEASE / "records.json").read_text(encoding="utf-8")))
    if opt.check:
        root = RELEASE.parents[2]
        expected_paths = {
            (RELEASE / name).relative_to(root).as_posix() for name in (*result, "records.json", "README.md")
        } | {"scripts/reproduce_mdia_evidence_20261103.py"}
        lines = (RELEASE / "SHA256SUMS").read_text().splitlines()
        manifest = dict((name, digest) for digest, name in (line.split("  ", 1) for line in lines))
        ensure(len(lines) == len(manifest) and set(manifest) == expected_paths, "unexpected manifest members")
        for name, digest in manifest.items():
            ensure(
                hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name + ": checksum mismatch"
            )
        for name, body in result.items():
            ensure((RELEASE / name).read_bytes() == body.encode("utf-8"), name + ": reproduction mismatch")
        print(
            "Verified the manifest, paired outcomes, cohort partitions, BFCL intervals and all four numerical outputs."
        )
    else:
        opt.output.mkdir(parents=True, exist_ok=True)
        ensure(not any(opt.output.iterdir()), "--output must be empty")
        for name, body in result.items():
            (opt.output / name).write_bytes(body.encode("utf-8"))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError) as err:
        sys.exit(str(err))
