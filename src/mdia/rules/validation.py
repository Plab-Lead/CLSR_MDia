"""Conservative, evidence-driven validation of the MDia rule bank."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from mdia.rules._io import write_json_atomic
from mdia.rules.registry import RULE_REGISTRY
from mdia.rules.statistics import (
    TestOutcome,
    benjamini_hochberg,
    paired_bootstrap,
    permutation_test,
    simple_regression,
)
from mdia.schemas import JsonValue, RuleExecutionStatus, RuleResult, RuleSpec

EvidenceRows = Sequence[Mapping[str, Any]]
EvidenceInput = Mapping[str, EvidenceRows | Mapping[str, Any]] | Sequence[Mapping[str, Any]]


def _normalize_evidence(
    evidence: EvidenceInput,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, tuple[str, ...]]]:
    rows_by_rule: dict[str, list[dict[str, Any]]] = defaultdict(list)
    artifacts_by_rule: dict[str, tuple[str, ...]] = {}
    if isinstance(evidence, Mapping):
        for rule_id, value in evidence.items():
            if isinstance(value, Mapping):
                raw_rows = value.get("records", [])
                raw_artifacts = value.get("artifacts", ())
                if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes)):
                    raise ValueError(f"{rule_id}: records must be a sequence")
                if not isinstance(raw_artifacts, Sequence) or isinstance(raw_artifacts, (str, bytes)):
                    raise ValueError(f"{rule_id}: artifacts must be a sequence")
                artifacts_by_rule[str(rule_id)] = tuple(str(item) for item in raw_artifacts)
            else:
                raw_rows = value
            for row in raw_rows:
                if not isinstance(row, Mapping):
                    raise ValueError(f"{rule_id}: every evidence row must be an object")
                rows_by_rule[str(rule_id)].append(dict(row))
    else:
        for row in evidence:
            if not isinstance(row, Mapping):
                raise ValueError("every evidence row must be an object")
            raw_rule_id = row.get("rule_id")
            if not isinstance(raw_rule_id, str) or not raw_rule_id:
                raise ValueError("flat evidence rows require rule_id")
            rows_by_rule[raw_rule_id].append(dict(row))
    return dict(rows_by_rule), artifacts_by_rule


def _validation_rows(rows: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    accepted: list[dict[str, Any]] = []
    excluded = 0
    for row in rows:
        split = row.get("split")
        if split in {"evolution_validation", "router_validation"}:
            accepted.append(row)
        else:
            excluded += 1
    return accepted, excluded


def _number(row: Mapping[str, Any], key: str) -> float:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"feature {key!r} must be numeric")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"feature {key!r} must be finite")
    return normalized


def _evaluate(spec: RuleSpec, rows: Sequence[dict[str, Any]], *, seed: int, iterations: int) -> TestOutcome:
    missing = sorted({feature for feature in spec.features if any(feature not in row for row in rows)})
    if missing:
        raise ValueError(f"missing declared features: {', '.join(missing)}")
    if spec.test_type == "paired_bootstrap":
        return paired_bootstrap(
            [_number(row, "treatment") for row in rows],
            [_number(row, "control") for row in rows],
            iterations=iterations,
            seed=seed,
        )
    if spec.test_type == "permutation":
        groups = [str(row["group"]) for row in rows]
        return permutation_test(
            groups, [_number(row, "value") for row in rows], iterations=iterations, seed=seed
        )
    if spec.test_type == "regression":
        return simple_regression(
            [_number(row, "predictor") for row in rows],
            [_number(row, "outcome") for row in rows],
        )
    if not rows:
        raise ValueError("descriptive validation requires at least one record")
    estimates = [_number(row, "estimate") for row in rows]
    estimate = sum(estimates) / len(estimates)
    return TestOutcome(
        n_units=len(rows),
        estimate=estimate,
        confidence_interval=None,
        p_value=None,
        details={"method": "descriptive_report", "n_reported_estimates": len(estimates)},
    )


def _not_evaluated(
    spec: RuleSpec,
    reason: str,
    *,
    artifacts: tuple[str, ...],
    proxy: bool,
    details: Mapping[str, JsonValue] | None = None,
) -> RuleResult:
    return RuleResult(
        rule_id=spec.rule_id,
        family=spec.family,
        status=RuleExecutionStatus.NOT_EVALUATED,
        manuscript_support=spec.manuscript_support,
        reason=reason,
        evidence_artifacts=artifacts,
        proxy=proxy,
        details=dict(details or {}),
    )


def _direction_passes(spec: RuleSpec, estimate: float, adjusted_p: float, alpha: float) -> bool:
    if adjusted_p > alpha:
        return False
    threshold = spec.threshold
    if spec.direction == "positive":
        if threshold is None:
            raise ValueError("positive rules require a declared threshold")
        return estimate > threshold
    if spec.direction == "negative":
        if threshold is None:
            raise ValueError("negative rules require a declared threshold")
        return estimate < threshold
    if spec.direction == "noninferior":
        if threshold is None:
            raise ValueError("noninferior rules require a declared threshold")
        return estimate >= threshold
    return True


def validate_rules(
    evidence: EvidenceInput,
    *,
    specs: Sequence[RuleSpec] | None = None,
    output_dir: str | Path | None = None,
    seed: int = 0,
    iterations: int = 4000,
    alpha: float = 0.05,
) -> list[RuleResult]:
    """Validate declared formulas and apply BH correction per paper taxonomy.

    Gold-bearing test rows are never eligible.  Missing, malformed, or
    insufficient evidence yields ``not_evaluated`` rather than a fabricated
    score.  The manuscript support label remains visible as provenance but is
    never used to decide the current execution result.
    """

    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must lie between zero and one")
    selected_specs = tuple(specs or RULE_REGISTRY)
    if len({spec.rule_id for spec in selected_specs}) != len(selected_specs):
        raise ValueError("rule specs contain duplicate IDs")
    rows_by_rule, artifacts_by_rule = _normalize_evidence(evidence)
    provisional: list[RuleResult] = []
    for index, spec in enumerate(selected_specs):
        raw_rows = rows_by_rule.get(spec.rule_id, [])
        rows, excluded = _validation_rows(raw_rows)
        artifacts = artifacts_by_rule.get(spec.rule_id, ())
        live_evolution = bool(rows) and all(row.get("live_evolution") is True for row in rows)
        proxy = spec.proxy and not live_evolution
        if not rows:
            reason = "no eligible validation evidence was supplied"
            if raw_rows and excluded:
                reason = (
                    "all supplied records were excluded because each rule row must declare "
                    "evolution_validation or router_validation"
                )
            provisional.append(
                _not_evaluated(
                    spec,
                    reason,
                    artifacts=artifacts,
                    proxy=proxy,
                    details={"excluded_non_validation_rows": excluded},
                )
            )
            continue
        if spec.direction in {"positive", "negative", "noninferior"} and spec.threshold is None:
            provisional.append(
                _not_evaluated(
                    spec,
                    "the rule has no paper-defined inferential effect threshold",
                    artifacts=artifacts,
                    proxy=proxy,
                    details={"eligible_rows": len(rows), "excluded_non_validation_rows": excluded},
                )
            )
            continue
        try:
            outcome = _evaluate(spec, rows, seed=seed + index, iterations=iterations)
        except ValueError as exc:
            provisional.append(
                _not_evaluated(
                    spec,
                    str(exc),
                    artifacts=artifacts,
                    proxy=proxy,
                    details={"eligible_rows": len(rows), "excluded_non_validation_rows": excluded},
                )
            )
            continue
        details: dict[str, JsonValue] = {
            key: value for key, value in outcome.details.items() if isinstance(value, (str, int, float, bool))
        }
        details.update(
            {
                "test_type": spec.test_type,
                "statistic": spec.statistic,
                "direction": spec.direction,
                "excluded_non_validation_rows": excluded,
            }
        )
        provisional.append(
            RuleResult(
                rule_id=spec.rule_id,
                family=spec.family,
                status=RuleExecutionStatus.EVALUATED,
                manuscript_support=spec.manuscript_support,
                n_units=outcome.n_units,
                estimate=outcome.estimate,
                confidence_interval=outcome.confidence_interval,
                p_value=outcome.p_value,
                passed=None,
                evidence_artifacts=artifacts,
                proxy=proxy,
                details=details,
            )
        )

    specs_by_id = {spec.rule_id: spec for spec in selected_specs}
    adjusted_by_rule: dict[str, float] = {}
    p_values_by_family: dict[str, dict[str, float]] = defaultdict(dict)
    for result in provisional:
        if result.status is RuleExecutionStatus.EVALUATED and result.p_value is not None:
            p_values_by_family[result.family][result.rule_id] = result.p_value
    for p_values in p_values_by_family.values():
        adjusted_by_rule.update(benjamini_hochberg(p_values))

    results: list[RuleResult] = []
    for result in provisional:
        adjusted = adjusted_by_rule.get(result.rule_id)
        if result.status is not RuleExecutionStatus.EVALUATED or adjusted is None:
            results.append(result)
            continue
        spec = specs_by_id[result.rule_id]
        if result.estimate is None:
            raise RuntimeError("evaluated inferential rule is missing its estimate")
        payload = result.model_dump(mode="json")
        payload["adjusted_p_value"] = adjusted
        payload["passed"] = _direction_passes(spec, result.estimate, adjusted, alpha)
        results.append(RuleResult.model_validate(payload))

    if output_dir is not None:
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        write_json_atomic(directory / "registry.json", list(selected_specs))
        write_json_atomic(
            directory / "results.json",
            {
                "alpha": alpha,
                "multiplicity": "Benjamini-Hochberg within each published A-G taxonomy",
                "n_rules": len(results),
                "records": results,
            },
        )
    return results


__all__ = ["EvidenceInput", "EvidenceRows", "validate_rules"]
