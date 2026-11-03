"""Reproduce the paired accuracy and native token tables from released scalar evidence."""

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from reproduce_mdia_evidence_20261103 import correct_pair, csv_text, ensure, signed

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "artifacts/research"
RELEASE = RESEARCH / "token-efficiency-v1"
CASES = RESEARCH / "20261005/data/core/paired_case_data.jsonl"
PANELS = RESEARCH / "20261005/data/core/baseline_source_data.json"
INTERVALS = RESEARCH / "20261005/results/CORE_PAIRED.json"
RECORDS = RESEARCH / "20261103/records.json"
SUPPLEMENT = RELEASE / "supplement.json"
START = "<!-- mdia-paired-efficiency:start -->"
END = "<!-- mdia-paired-efficiency:end -->"

# Display labels for the seven archived October pairs, in their original order.
OCTOBER = {
    "GPQA_GLM": ("GPQA", "GLM-5.3", "Obligation card", "Paired English"),
    "BFCL_Qwen": ("BFCL", "Qwen3.6-35B-A3B", "Parent card (8192)", "Direct (8192)"),
    "MultiHop_Flash": ("MultiHop-RAG", "DeepSeek-V4-Flash", "Parent card (8192)", "Sketch-of-Thought (8192)"),
    "LCB_Flash": ("LiveCodeBench", "DeepSeek-V4-Flash", "Compiled card (2048)", "Raw CoT (8192)"),
    "CRUX_Flash": ("CRUXEval", "DeepSeek-V4-Flash", "Python state", "Paired English"),
    "CRUX_Qwen": ("CRUXEval", "Qwen (transfer panel)", "Python state", "Original English"),
    "GPQA_Pro": ("GPQA", "DeepSeek-V4-Pro", "Compiled card (2048)", "Direct (2048)"),
}
CONTROL_NAMES = {
    "Source:raw_2048": "Raw CoT (2048)",
    "Source:obligation_english": "Adapted English (obligations)",
    "NL:flat_terminal": "Flat-terminal English",
    "Target:TALE_EP_reimplementation": "TALE reimplementation",
    "Target:schema_only_8192": "Schema (8192)",
    "Source:raw_8192": "Raw CoT (8192)",
    "Source:parent_8192": "Parent card (8192)",
}
STRONG_ENGLISH = {"Source:obligation_english", "NL:flat_terminal"}
EXTRA = {
    "C2": ("Selective literal integrity", "English piece trace", "Combined 192 + 64 disjoint groups"),
    "C6": ("Fixed specialist C2", "Raw CoT (2048)", "Exposed fixed specialist on the 96-group online panel"),
}


def verify_inputs():
    paths = {p.relative_to(ROOT).as_posix() for p in (CASES, PANELS, INTERVALS, RECORDS, SUPPLEMENT)}
    checks = [line.split("  ", 1) for line in (RELEASE / "inputs.sha256").read_text().splitlines()]
    ensure(len(checks) == len(paths) and {name for _, name in checks} == paths, "Unexpected source manifest")
    for digest, name in checks:
        ensure(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, f"Source mismatch in {name}")


def october_pairs():
    paired = defaultdict(lambda: {"candidate": {}, "reference": {}})
    for line in CASES.read_bytes().splitlines():
        row = json.loads(line)
        cases = paired[row["pair_id"]][row["side"]]
        ensure(row["case_key"] not in cases, "Duplicate case on one side of an October pair")
        cases[row["case_key"]] = row
    archived = json.loads(INTERVALS.read_bytes())
    ensure(set(paired) == set(OCTOBER) == {r["pair_id"] for r in archived}, "Incomplete October roster")
    for spec in archived:
        key = spec["pair_id"]
        left, right = (paired[key][side] for side in ("candidate", "reference"))
        groups = {v["group_key"] for v in left.values()}
        ensure(left.keys() == right.keys() and len(left) == spec["n"] and len(groups) == spec["groups"], key)
        ensure(all(left[k]["group_key"] == right[k]["group_key"] for k in left), key + " grouping")
        wins = sum(left[k]["correct"] and not right[k]["correct"] for k in left)
        losses = sum(right[k]["correct"] and not left[k]["correct"] for k in left)
        ensure((wins, losses) == (spec["wins"], spec["losses"]), key + " discordances")
        arms = [
            dict(
                correct=sum(r["correct"] for r in side.values()),
                input_tokens=sum(r["input_tokens"] for r in side.values()),
                generation_tokens=sum(r["output_tokens"] for r in side.values()),
                reported_prior_unknown_attempts=sum(r["cost_unknown_attempts"] for r in side.values()),
            )
            for side in (left, right)
        ]
        benchmark, model, procedure, reference = OCTOBER[key]
        yield dict(
            id=key,
            benchmark=benchmark,
            model=model,
            procedure=procedure,
            reference=reference,
            scope="Archived exposed panel",
            questions=len(left),
            groups=len(groups),
            arms=arms,
            paired_counts=None,
            archived_interval95_pp=spec["accuracy_interval_pp"],
        )


def comparisons(data, supplement):
    yield from october_pairs()
    diag = data["diagnostics"]
    reported = supplement["qa_control_prior_unknown_rows"]
    for r in data["comparisons"]:
        yield r
        key = r["id"]
        if key not in diag["qa_extraction"]:
            continue
        qa = diag["qa_extraction"][key]
        ensure(qa["control_tokens"].keys() == reported[key].keys(), key + " accounting roster")
        for name, (itok, otok) in qa["control_tokens"].items():
            reference = dict(
                correct=r["comparison_context"][name],
                input_tokens=itok,
                generation_tokens=otok,
                reported_prior_unknown_attempts=reported[key][name],
            )
            wins, losses = qa["paired_with_strong_controls"][name]
            both = r["arms"][0]["correct"] - wins
            ci = diag["strong_english_accuracy_intervals"][key] if name in STRONG_ENGLISH else None
            yield dict(
                r,
                id=f"{key}/{name}",
                reference=CONTROL_NAMES[name],
                arms=[r["arms"][0], reference],
                paired_counts=[wins, losses, both, r["questions"] - wins - losses - both],
                archived_interval95_pp=ci,
            )
    for r in supplement["crux_comparisons"]:
        procedure, reference, scope = EXTRA[r["id"]]
        yield dict(
            r, benchmark="CRUXEval", procedure=procedure, reference=reference, scope=scope, paired_counts=None
        )


def describe(r):
    n, groups = r["questions"], r["groups"]
    left, right = correct_pair(r)
    method, ref = r["arms"]
    mi, mo = method["input_tokens"], method["generation_tokens"]
    ri, ro = ref["input_tokens"], ref["generation_tokens"]
    ensure(
        all(type(v) is int and v >= 0 for v in (mi, mo, ri, ro)) and ri > 0 and ro > 0, r["id"] + " tokens"
    )
    mu, ru = (a["reported_prior_unknown_attempts"] for a in (method, ref))
    ensure(all(v is None or (type(v) is int and v >= 0) for v in (mu, ru)), r["id"] + " unknown usage")
    mt, rt = mi + mo, ri + ro
    saves_output = left >= right and mo < ro
    joint = saves_output and mt < rt
    ci = r["archived_interval95_pp"]
    return dict(
        comparison=r["id"],
        benchmark="MATH (Level 5)" if r["id"] == "math-flash" else r["benchmark"],
        model=r["model"].split("/")[-1],
        procedure=r["procedure"],
        reference=r["reference"],
        cohort=r["scope"],
        questions=n,
        whole_groups=groups,
        reference_accuracy_pct=signed(100 * right / n).lstrip("+"),
        procedure_accuracy_pct=signed(100 * left / n).lstrip("+"),
        accuracy_difference_pp=signed(100 * (left - right) / n),
        reference_correct=right,
        procedure_correct=left,
        paired_accuracy_ci_low_pp=signed(ci[0]) if ci else "",
        paired_accuracy_ci_high_pp=signed(ci[1]) if ci else "",
        procedure_input=mi,
        reference_input=ri,
        procedure_output=mo,
        reference_output=ro,
        procedure_total=mt,
        reference_total=rt,
        generation_saved_pct=signed(100 * (ro - mo) / ro),
        procedure_unknown_usage=mu,
        reference_unknown_usage=ru,
        matched_or_higher_with_lower_output=saves_output,
        also_lower_total=joint,
        overview=joint and groups >= 96 and mu == ru == 0,
    )


def table(rows):
    lines = [
        "| Benchmark · model | MDia procedure vs reference | Questions / groups | Reference accuracy | MDia accuracy | Generated tokens per question (ref → MDia) | Generation saved |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        n = row["questions"]
        bench = (
            "LiveCodeBench (output prediction)" if row["benchmark"] == "LiveCodeBench" else row["benchmark"]
        )
        lines.append(
            f"| {bench} · {row['model']} | {row['procedure']} vs {row['reference']} | "
            f"{n} / {row['whole_groups']} | {row['reference_accuracy_pct']}% | {row['procedure_accuracy_pct']}% | "
            f"{row['reference_output'] / n:,.2f} → {row['procedure_output'] / n:,.2f} | "
            f"{row['generation_saved_pct'].lstrip('+')}% |"
        )
    return "\n".join(lines) + "\n"


def outputs():
    verify_inputs()
    data = json.loads(RECORDS.read_bytes())
    supplement = json.loads(SUPPLEMENT.read_bytes())
    rows = sorted(
        map(describe, comparisons(data, supplement)),
        key=lambda r: (r["benchmark"], r["model"], r["comparison"]),
    )
    ensure(len({r["comparison"] for r in rows}) == len(rows), "Duplicate comparison")
    lower_output = [r for r in rows if r["matched_or_higher_with_lower_output"]]
    overview = sorted(
        (r for r in lower_output if r["overview"]),
        key=lambda r: r["procedure_output"] / r["reference_output"],
    )
    balance = [r for r in lower_output if r["also_lower_total"] and not r["overview"]]
    output_only = [r for r in lower_output if not r["also_lower_total"]]
    context = supplement["crux_context"]
    router_score, router_n = context["qwen_matched_baseline_router"]
    glm_correct, english_correct, added_n = context["glm_added_subset"]
    panels = json.loads(PANELS.read_bytes())["panels"]
    gpqa = next(p for p in panels if p["setting"] == "GPQA / GLM original256")
    (schema,) = (point for point in gpqa["points"] if point["label"] == "schema_only_8192")
    november = {r["id"]: r for r in data["comparisons"]}
    qwen, lcb = november["multihop-qwen"], november["lcb-flash"]
    tale_score = qwen["comparison_context"]["Target:TALE_EP_reimplementation"]
    ensure(tale_score == qwen["comparison_context"]["Target:schema_only_8192"], "Qwen control scores differ")
    readme_table = table(overview)
    report = (
        "# Paired accuracy and native token use\n\n"
        f"The comparison inventory contains {len(rows)} named contrasts. In {len(lower_output)}, the procedure "
        f"matched or exceeded its reference's observed accuracy and used fewer output tokens. "
        f"{len(overview) + len(balance)} also used fewer recorded input-plus-output tokens. Several comparisons "
        "reuse the same questions or procedures, which limits their independence.\n\n"
        "## Lower output and total token use\n\n"
        "Every row below meets both token criteria on at least 96 whole groups, with zero prior unknown-usage "
        "indicators reported for either arm. Generation saved is the percentage reduction in native output tokens "
        "relative to the named reference. Generation includes reasoning tokens where the provider reports them.\n\n"
        + readme_table
        + "\nThe Qwen CRUXEval row evaluates a fixed specialist. The matched baseline router reached "
        f"{100 * router_score / router_n:.2f}% on the same panel. For GLM-5.2, the combined CRUXEval estimate includes "
        f"{added_n} additional groups on which English reached {100 * english_correct / added_n:.2f}% and MDia "
        f"reached {100 * glm_correct / added_n:.2f}%. On GPQA, the archived GLM-5.3 schema control reached "
        f"{100 * schema['correct'] / schema['n']:.2f}%. On Qwen MultiHop-RAG, TALE and schema each reached "
        f"{100 * tale_score / qwen['questions']:.2f}%. The natural-language LiveCodeBench control reached "
        f"{100 * lcb['comparison_context']['natural_2048'] / lcb['questions']:.2f}%. The displayed "
        "LiveCodeBench pair holds the ordinary-English reasoning frame fixed.\n"
        + "\n## Smaller panels and incomplete attempt accounting\n\n"
        "The following pairs also meet both observed token criteria. The Qwen transfer panel has 48 groups. "
        "On MultiHop-RAG Pro the procedure has one prior attempt with unknown usage. On MMLU-Pro the Raw CoT "
        "reference has one. Their totals cover recorded usage.\n\n"
        + table(balance)
        + "\n## Shorter generations with greater total token use\n\n"
        "In these pairs, the additional input tokens outweighed the reduction in generation. "
        "The MATH Level 5 subgroup was chosen after inspecting outcomes. "
        "The BFCL GEPA comparisons use two English procedures.\n\n"
        + table(output_only)
        + "\n## Sources and interpretation\n\n"
        "The inventory includes the seven October core pairs, all 16 November comparisons, the seven metered "
        "QA companion controls and two archived CRUXEval comparisons (C2 and C6). Each comparison uses the same "
        "questions on both sides. Benchmark panels were development-exposed and contrasts were selected retrospectively. "
        "Generated tokens per question is the output subtotal divided by the question count. Generation saved is "
        "100 × (reference output − procedure output) / reference output, computed from integer subtotals before rounding. "
        "The CSV lists raw token sums by arm, group counts, prior unknown-usage indicators and available unadjusted "
        "paired 95% accuracy intervals. A blank interval or usage field means unavailable. Formal equivalence would "
        "require a prespecified accuracy margin and a paired equivalence analysis. The token totals cover serving and exclude construction. Charges and "
        "latency require separate accounting. See the October baseline panels and the November comparison and serving "
        "tables under `artifacts/research/20261005` and `artifacts/research/20261103` in the repository. "
        "[Generation savings data](output-savings.csv)\n\n"
        "From the repository root, run the following with Python 3.10 or later. The first command verifies the "
        "input digests, the README table and the published numerical outputs. The second writes those outputs, "
        "a standalone README table and the full comparison inventory to a new or empty directory.\n\n"
        "~~~sh\npython3 -B scripts/reproduce_mdia_token_efficiency.py --check\n"
        "python3 -B scripts/reproduce_mdia_token_efficiency.py --output runs/mdia-token-efficiency\n~~~\n"
        "\nThe seven October comparisons are re-paired by case and whole group. The November records supply paired "
        "counts and arm-level token sums. The scalar supplement in `artifacts/research/token-efficiency-v1/supplement.json` "
        "supplies the two additional CRUXEval pairs and QA control accounting. Its exporter, "
        "`scripts/export_mdia_token_efficiency_sources.py`, verifies those values against four archived reports identified by SHA-256.\n"
    )
    return {
        "RESULTS.md": report,
        "output-savings.csv": csv_text(lower_output),
        "audit.csv": csv_text(rows),
        "readme-table.md": readme_table,
    }


def check_readme(readme, expected):
    ensure(readme.count(START) == readme.count(END) == 1, "Missing or duplicate README table markers")
    ensure(
        readme.partition(START)[2].partition(END)[0] == "\n\n" + expected + "\n",
        "README table differs from source",
    )


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    action = cli.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--check", action="store_true", help="verify the repository tables and their source records"
    )
    action.add_argument("--output", type=Path, help="write numerical outputs to a new or empty directory")
    args = cli.parse_args()
    files = outputs()
    if args.check:
        check_readme((ROOT / "README.md").read_text(encoding="utf-8"), files["readme-table.md"])
        for name in ("RESULTS.md", "output-savings.csv"):
            ensure((RELEASE / name).read_bytes() == files[name].encode(), f"{name} differs from source")
        print("Verified the source checksums, paired efficiency results, CSV and README table.")
    else:
        args.output.mkdir(exist_ok=True, parents=True)
        ensure(not any(args.output.iterdir()), "--output must be empty")
        for name, body in files.items():
            (args.output / name).write_bytes(body.encode())


if __name__ == "__main__":
    main()
