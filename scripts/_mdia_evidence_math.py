# ruff: noqa: B905, E721, E731
"""Deterministic scalar arithmetic extracted from sealed numerical reproductions."""

import collections
import json

import numpy as np


def read(p):
    return json.loads(p.read_text())


def crux_load(p):
    return json.loads(p.read_text())


def core_mean(x):
    return sum(x) / len(x)


def core_known(rows):
    return all(
        r["cost_unknown_attempts"] == 0
        and isinstance(r["input_tokens"], (int, float))
        and isinstance(r["output_tokens"], (int, float))
        for r in rows
    )


def core_aggregate(rows):
    n = len(rows)
    k = core_known(rows)
    return dict(
        n=n,
        groups=len({r["group_key"] for r in rows}),
        correct=sum(r["correct"] for r in rows),
        parsed=sum(r["parse_ok"] for r in rows),
        generated=core_mean([r["output_tokens"] for r in rows]) if k else None,
        input=core_mean([r["input_tokens"] for r in rows]) if k else None,
        unknown_attempts=sum(r["cost_unknown_attempts"] for r in rows),
        cost_available=k,
        finish_counts=dict(collections.Counter(r["finish_reason"] or "UNAVAILABLE" for r in rows)),
    )


def core_paired(rows, idx, B=10000, seed=20261001):
    import numpy as np

    sides = {s: {r["case_key"]: r for r in rows if r["side"] == s} for s in ["candidate", "reference"]}
    assert len(rows) == 2 * len(sides["candidate"]) and sides["candidate"].keys() == sides["reference"].keys()
    assert all((r["group_key"] == sides["reference"][k]["group_key"] for k, r in sides["candidate"].items()))
    groups = sorted({r["group_key"] for r in rows})
    gc = collections.defaultdict(list)
    for k, r in sorted(sides["candidate"].items()):
        gc[r["group_key"]].append((r, sides["reference"][k]))
    cost = core_known(rows)
    arr = []
    for g in groups:
        pairs = gc[g]
        a = [x[0] for x in pairs]
        b = [x[1] for x in pairs]
        arr.append(
            [
                len(pairs),
                sum(x["correct"] for x in a) - sum(x["correct"] for x in b),
                sum(x["parse_ok"] for x in a) - sum(x["parse_ok"] for x in b),
                sum(x["output_tokens"] for x in a) if cost else 0,
                sum(x["output_tokens"] for x in b) if cost else 0,
                sum(x["input_tokens"] for x in a) - sum(x["input_tokens"] for x in b) if cost else 0,
            ]
        )
    arr = np.asarray(arr, dtype=float)
    rng = np.random.Generator(np.random.PCG64(seed + idx))
    boots = arr[rng.integers(0, len(groups), (B, len(groups)))].sum(axis=1)
    totals = arr.sum(axis=0)
    acc = 100 * boots[:, 1] / boots[:, 0]
    parse = 100 * boots[:, 2] / boots[:, 0]
    ci = lambda x: [float(v) for v in np.percentile(x, [2.5, 97.5])]
    gen = 100 * (boots[:, 4] - boots[:, 3]) / boots[:, 4] if cost and np.all(boots[:, 4] > 0) else None
    sav = 100 * (totals[4] - totals[3]) / totals[4] if cost and totals[4] > 0 else None
    result = dict(
        n=int(totals[0]),
        groups=len(groups),
        wins=sum((a["correct"] and (not b["correct"]) for a, b in sum(gc.values(), []))),
        losses=sum((b["correct"] and (not a["correct"]) for a, b in sum(gc.values(), []))),
        accuracy_difference_pp=float(100 * totals[1] / totals[0]),
        accuracy_interval_pp=ci(acc),
        parse_difference_pp=float(100 * totals[2] / totals[0]),
        parse_interval_pp=ci(parse),
        generated_saving_percent=float(sav) if sav is not None else None,
        generated_saving_interval_percent=ci(gen) if gen is not None else None,
        input_difference_tokens_per_case=float(totals[5] / totals[0]) if cost else None,
        input_difference_interval=ci(boots[:, 5] / boots[:, 0]) if cost else None,
        bootstrap_replicates=B,
        seed=seed + idx,
        cost_available=cost,
        scope="New fixed-seed reproduction intervals, not replacements for original published endpoints; historical exposed development cohort",
    )
    return result


def bfcl_front(points, three=False):
    good = {
        k: v for k, v in points.items() if v["mean_generated"] is not None and v["mean_input"] is not None
    }
    return [
        k
        for k, p in good.items()
        if not any(
            (
                k != j
                and q["correct"] >= p["correct"]
                and (q["mean_generated"] <= p["mean_generated"])
                and (not three or q["mean_input"] <= p["mean_input"])
                and (
                    q["correct"] > p["correct"]
                    or q["mean_generated"] < p["mean_generated"]
                    or (three and q["mean_input"] < p["mean_input"])
                )
                for j, q in good.items()
            )
        )
    ]


def bfcl_stats(rr):
    n = len(rr)
    unknown = sum(r["cost_unknown_attempts"] for r in rr)
    return dict(
        n=n,
        correct=sum(r["correct"] for r in rr),
        parsed=sum(r["parse_ok"] for r in rr),
        unknown_attempts=unknown,
        mean_generated=None if unknown else sum(r["generated"] for r in rr) / n,
        mean_input=None if unknown else sum(r["input"] for r in rr) / n,
    )


def bfcl_schema(r):
    fields = {
        "record_id",
        "source_task_sha256",
        "group_sha256",
        "group_order",
        "arm",
        "correct",
        "parse_ok",
        "generated",
        "input",
        "cost_unknown_attempts",
        "finish_reason",
        "imported",
        "exact_alias_of_record_id",
        "original_grader_digest_absent",
        "original_grader_digest_sha256",
        "derived_frozen_grader_fingerprint",
        "grade_certificate_record_id",
        "original_diagnosis_sha256",
        "original_api_ok_absent",
        "original_finish_reason_absent",
        "finish_reason_source",
    }
    assert set(r) == fields
    for k in ["record_id", "source_task_sha256", "group_sha256"]:
        assert isinstance(r[k], str) and len(r[k]) == 64 and all(c in "0123456789abcdef" for c in r[k])
    for k in [
        "exact_alias_of_record_id",
        "original_grader_digest_sha256",
        "derived_frozen_grader_fingerprint",
        "grade_certificate_record_id",
        "original_diagnosis_sha256",
    ]:
        assert r[k] is None or (
            isinstance(r[k], str) and len(r[k]) == 64 and all(c in "0123456789abcdef" for c in r[k])
        )
    for k in [
        "correct",
        "parse_ok",
        "imported",
        "original_grader_digest_absent",
        "original_api_ok_absent",
        "original_finish_reason_absent",
    ]:
        assert type(r[k]) == bool
    for k in ["group_order", "cost_unknown_attempts"]:
        assert type(r[k]) == int and r[k] >= 0
    for k in ["generated", "input"]:
        assert r[k] is None or (type(r[k]) == int and r[k] >= 0)
    assert r["finish_reason"] in ["stop", "length", None]
    assert r["finish_reason_source"] in [
        "original_row_and_certified_solver_receipt",
        "certified_solver_receipt_original_field_absent",
    ]
    assert r["original_finish_reason_absent"] == (
        r["finish_reason_source"] == "certified_solver_receipt_original_field_absent"
    )
    assert r["arm"].startswith(("Qwen:", "Pro:"))


def bfcl_check_alias(r, a):
    assert r["exact_alias_of_record_id"] == a["record_id"]
    for k in [
        "source_task_sha256",
        "group_sha256",
        "group_order",
        "correct",
        "parse_ok",
        "generated",
        "input",
        "cost_unknown_attempts",
        "finish_reason",
    ]:
        assert r[k] == a[k]


FIELDS = [
    "backbone",
    "arm",
    "source_task_digest",
    "whole_group_digest",
    "record_digest",
    "correct",
    "registered_parse_ok",
    "generated_completed_response_tokens",
    "input_completed_response_tokens",
    "missing_usage_count",
    "whole_attempt_cost_available",
    "finish_reason",
    "imported",
    "raw_row_sha256",
    "passed_review_sha256",
]


def crux_stats(rr):
    u = sum(r["missing_usage_count"] for r in rr)
    g = sum(r["generated_completed_response_tokens"] for r in rr)
    i = sum(r["input_completed_response_tokens"] for r in rr)
    return dict(
        n=len(rr),
        groups=len({r["whole_group_digest"] for r in rr}),
        correct=sum(r["correct"] for r in rr),
        parsed=sum(r["registered_parse_ok"] for r in rr),
        unknown_attempts=u,
        known_generated_subtotal=g,
        known_input_subtotal=i,
        mean_generated=None if u else g / len(rr),
        mean_input=None if u else i / len(rr),
    )


def crux_frontier(pts, three=False):

    def dom(a, b):
        av = [a["correct"], -a["mean_generated"]]
        bv = [b["correct"], -b["mean_generated"]]
        if three:
            av.append(-a["mean_input"])
            bv.append(-b["mean_input"])
        return all((x >= y for x, y in zip(av, bv))) and any((x > y for x, y in zip(av, bv)))

    good = {a: x for a, x in pts.items() if x["mean_generated"] is not None}
    return dict(
        available_cost_frontier=[
            a for a, x in good.items() if not any((dom(y, x) for b, y in good.items() if a != b))
        ],
        cost_unavailable_points=[a for a, x in pts.items() if x["mean_generated"] is None],
        scope="Observed frontier among cost-available points only. Unknown-cost points remain retained and unclassified, not dominated or zero-imputed.",
    )


def crux_close(a, b, where="root"):
    if isinstance(a, dict):
        assert isinstance(b, dict) and set(a) == set(b), where
        for k in a:
            crux_close(a[k], b[k], where + "." + k)
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), where
        for j, (x, y) in enumerate(zip(a, b)):
            crux_close(x, y, where + f"[{j}]")
    elif isinstance(a, (float, int)) and (not isinstance(a, bool)):
        assert isinstance(b, (float, int)) and abs(a - b) < 1e-09, (where, a, b)
    else:
        assert a == b, (where, a, b)


def crux_compute(base):
    rows = [json.loads(x) for x in (base / "SAFE_SCALAR_ROWS.jsonl").read_text().splitlines()]
    assert len(rows) == 6912 and all(set(r) == set(FIELDS) for r in rows)
    assert len({(r["backbone"], r["arm"], r["source_task_digest"]) for r in rows}) == 6912
    meta = crux_load(base / "COHORT_METADATA.json")
    order = meta["task_order_digests"]
    assert len(order) == 192 and len(set(order)) == 192
    by = {p: {} for p in ["Qwen", "Flash"]}
    for r in rows:
        assert r["whole_attempt_cost_available"] == (r["missing_usage_count"] == 0)
        by[r["backbone"]].setdefault(r["arm"], {})[r["source_task_digest"]] = r
    assert [len(by[x]) for x in ["Qwen", "Flash"]] == [19, 17]
    for arms in by.values():
        for rr in arms.values():
            assert set(rr) == set(order) and len({r["whole_group_digest"] for r in rr.values()}) == 192
    points = {
        p: {a: crux_stats(list(rr.values())) for a, rr in sorted(arms.items())} for p, arms in by.items()
    }
    assert sum(x["unknown_attempts"] for arms in points.values() for x in arms.values()) == 3
    crux_close(points, crux_load(base / "TABLE_SOURCE_DATA.json"))
    draws = np.random.default_rng(20261002).integers(0, 192, (10000, 192))
    group_rows = np.array(
        [order.index(meta["group_to_task_digest"][g]) for g in meta["qwen_original_group_order_digests"]], int
    )
    indices = {"Qwen": group_rows[draws], "Flash": draws}
    pairs = {p: {} for p in by}
    for p in by:
        for key in meta["contrast_keys"][p]:
            left, right = key.split("__")
            aa = [by[p][left][t] for t in order]
            bb = [by[p][right][t] for t in order]
            ix = indices[p]
            d = np.array([int(a["correct"]) - int(b["correct"]) for a, b in zip(aa, bb)])
            z = dict(
                n=192,
                groups=192,
                accuracy_difference_pp=float(d.mean() * 100),
                accuracy_ci95_pp=np.percentile(d[ix].mean(axis=1) * 100, [2.5, 97.5]).tolist(),
                wins=sum((a["correct"] and (not b["correct"]) for a, b in zip(aa, bb))),
                losses=sum((b["correct"] and (not a["correct"]) for a, b in zip(aa, bb))),
                generated_saving_pct=None,
                generated_ci95_pct=None,
                input_difference=None,
            )
            if not any(r["missing_usage_count"] for r in aa + bb):
                x = np.array([r["generated_completed_response_tokens"] for r in aa])
                y = np.array([r["generated_completed_response_tokens"] for r in bb])
                den = y[ix].sum(axis=1)
                num = x[ix].sum(axis=1)
                z["generated_saving_pct"] = float((1 - x.sum() / y.sum()) * 100) if y.sum() else None
                z["generated_ci95_pct"] = (
                    np.percentile((1 - num[den > 0] / den[den > 0]) * 100, [2.5, 97.5]).tolist()
                    if any(den > 0)
                    else None
                )
                z["input_difference"] = float(
                    np.mean(
                        [
                            a["input_completed_response_tokens"] - b["input_completed_response_tokens"]
                            for a, b in zip(aa, bb)
                        ]
                    )
                )
            pairs[p][key] = z
    assert sum(len(x) for x in pairs.values()) == 52
    crux_close(pairs, crux_load(base / "PAIRED_RESULTS.json"))
    frontiers = {
        p: dict(accuracy_generated=crux_frontier(pts), accuracy_generated_input=crux_frontier(pts, True))
        for p, pts in points.items()
    }
    crux_close(frontiers, crux_load(base / "FRONTIERS.json"))
    failures = {
        p: {
            a: dict(
                incorrect=sum(not r["correct"] for r in rr.values()),
                registered_unparsed=sum(not r["registered_parse_ok"] for r in rr.values()),
                finish_reasons=dict(
                    sorted(collections.Counter(str(r["finish_reason"]) for r in rr.values()).items())
                ),
            )
            for a, rr in sorted(arms.items())
        }
        for p, arms in by.items()
    }
    assert sum(x["incorrect"] for arms in failures.values() for x in arms.values()) == 1374
    return {
        "points.json": points,
        "paired.json": pairs,
        "frontiers.json": frontiers,
        "failures.json": failures,
    }
