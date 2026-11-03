"""Verify the scalar supplement against the original archived reports when available."""

import argparse
import gzip
import hashlib
import json
from math import isclose
from pathlib import Path

from reproduce_mdia_evidence_20261103 import ensure

PINS = {
    "writing/20261101-qa-delivery-v1.json": "3eea974a6213a6af069479ee1815f6d5f8e6541a53b953c1b70feff541a006c2",
    "evidence/WRITING_CONTRASTS.json": "22d205873e0698063588288e729237de3b2f6c501953b64894a825a91dd056f9",
    "evidence/inherited/crux_glm256.json.gz": "a4379a0b3cff70c4ed52c0addf700cdee66ee52ff1b656e62b443f5feb79b5b1",
    "evidence/inherited/qwen_matched_online96.json.gz": "416af577d02eedee76359f90152f8fc9a25f00b8781709f9f5718fd5b8416288",
}
QA = {
    "gpqa_structure_v2_256": "gpqa-pro",
    "multihop_frontier_v1_256": "multihop-pro",
    "multihop_qwen_transfer_v1_256": "multihop-qwen",
    "aime_transfer_v1_60": "aime-flash",
}
PUBLIC = Path(__file__).resolve().parents[1] / "artifacts/research/token-efficiency-v1/supplement.json"


def project(snapshot):
    reports = {}
    for name, digest in PINS.items():
        raw = (snapshot / name).read_bytes()
        ensure(hashlib.sha256(raw).hexdigest() == digest, f"Source checksum mismatch in {name}")
        reports[name] = json.loads(gzip.decompress(raw) if name.endswith(".gz") else raw)

    panels = reports["writing/20261101-qa-delivery-v1.json"]["panels"]
    unknown = {
        key: {
            arm: m["rows_with_reported_prior_unknown_attempts"]
            for arm, m in panels[study]["full_logical_serving_totals"].items()
            if arm not in (panels[study]["selected_method"], panels[study]["paired_english"])
        }
        for study, key in QA.items()
    }
    evidence = {r["id"]: r for r in reports["evidence/WRITING_CONTRASTS.json"]["contrasts"]}
    extra = []
    for key in ("C2", "C6"):
        contrast = evidence[key]
        report = reports[contrast["source"]]
        ci = contrast["paired_uncertainty"]
        n = ci["instances"]
        arms = []
        for name, side in zip(
            ("method", "comparator"), ("method_metrics", "comparator_metrics"), strict=True
        ):
            arm = contrast[name]
            metrics = contrast[side]
            if key == "C2":
                m = report["cohorts"]["combined256"]["all_arm_metrics"][arm]
                ensure(m["planned_rows"] == m["complete_rows"] == n, "Incomplete GLM arm")
                ensure(
                    m["unknown_or_missing_input_tokens_rows"]
                    == m["unknown_or_missing_output_tokens_rows"]
                    == 0,
                    "Incomplete GLM serving usage",
                )
                score, unknown_rows = m["correct_known"], m["rows_with_unknown_prior_attempt_cost"]
            else:
                m = report["all_arm_metrics"][arm]
                ensure(m["planned"] == m["complete"] == n, "Incomplete Qwen arm")
                full = report["paired_analysis"]["cohorts"]["full"]["all_arm_metrics"][arm]
                ensure(full["rows_with_unknown_token_usage"] == 0, "Incomplete Qwen serving usage")
                score, unknown_rows = m["correct_available"], full["rows_reporting_unknown_attempts"]
            ensure(n == metrics["n"] and score == metrics["correct"], "Incorrect cohort or score")
            totals = []
            for field, registered in (("input_tokens", "input"), ("output_tokens", "generated")):
                mean = m[field]
                ensure(mean == metrics[registered], "Token mean differs between archives")
                total = round(n * mean)
                ensure(isclose(total, n * mean, rel_tol=0, abs_tol=1e-7), "Nonintegral token subtotal")
                totals.append(total)
            arms.append(
                dict(
                    correct=score,
                    input_tokens=totals[0],
                    generation_tokens=totals[1],
                    reported_prior_unknown_attempts=unknown_rows,
                )
            )
        extra.append(
            dict(
                id=key,
                model=report["model"],
                questions=n,
                groups=ci["groups"],
                arm_names=[contrast["method"], contrast["comparator"]],
                arms=arms,
                archived_interval95_pp=ci["percentile95_pp"],
            )
        )
    qwen = reports[evidence["C6"]["source"]]["all_arm_metrics"]["Baseline:online_matched_depth3_leaf24"]
    added = reports[evidence["C2"]["source"]]["cohorts"]["additional64"]
    context = {
        "qwen_matched_baseline_router": [qwen["correct_available"], qwen["complete"]],
        "glm_added_subset": [
            added["all_arm_metrics"][evidence["C2"][side]]["correct_known"]
            for side in ("method", "comparator")
        ]
        + [added["instances"]],
    }
    return {
        "source_sha256": PINS,
        "qa_control_prior_unknown_rows": unknown,
        "crux_comparisons": extra,
        "crux_context": context,
    }


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument(
        "snapshot", type=Path, help="directory containing the original writing and evidence reports"
    )
    output = cli.add_mutually_exclusive_group(required=True)
    output.add_argument("--check", action="store_true", help="compare the projected bytes with the release")
    output.add_argument("--output", type=Path, help="write a new scalar supplement")
    args = cli.parse_args()
    body = (json.dumps(project(args.snapshot), ensure_ascii=False, indent=2) + "\n").encode()
    if args.check:
        ensure(PUBLIC.read_bytes() == body, "Supplement differs from the pinned archives")
        print("Verified both CRUXEval pairs and the seven QA control accounting records.")
    else:
        with args.output.open("xb") as stream:
            stream.write(body)
