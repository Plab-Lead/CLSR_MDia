"""Dependency-light inferential statistics for rule validation."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class TestOutcome:
    n_units: int
    estimate: float
    confidence_interval: tuple[float, float] | None
    p_value: float | None
    details: dict[str, float | int | str]


def _finite(values: Sequence[float], name: str) -> list[float]:
    normalized = [float(value) for value in values]
    if not all(math.isfinite(value) for value in normalized):
        raise ValueError(f"{name} contains a non-finite value")
    return normalized


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("cannot average an empty sequence")
    return sum(values) / len(values)


def _percentile(sorted_values: Sequence[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("cannot take a percentile of an empty sequence")
    if probability <= 0:
        return sorted_values[0]
    if probability >= 1:
        return sorted_values[-1]
    position = probability * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def paired_bootstrap(
    treatment: Sequence[float],
    control: Sequence[float],
    *,
    iterations: int = 4000,
    seed: int = 0,
    confidence: float = 0.95,
) -> TestOutcome:
    """Per-item paired bootstrap with a centered-null two-sided p-value."""

    left = _finite(treatment, "treatment")
    right = _finite(control, "control")
    if len(left) != len(right):
        raise ValueError("paired samples must have equal length")
    if len(left) < 2:
        raise ValueError("paired bootstrap requires at least two units")
    if iterations < 100:
        raise ValueError("bootstrap iterations must be at least 100")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie between zero and one")
    differences = [a - b for a, b in zip(left, right, strict=True)]
    estimate = _mean(differences)
    centered = [value - estimate for value in differences]
    generator = random.Random(seed)
    raw_means: list[float] = []
    null_extreme = 0
    n_units = len(differences)
    for _ in range(iterations):
        indexes = [generator.randrange(n_units) for _ in range(n_units)]
        raw_mean = _mean([differences[index] for index in indexes])
        null_mean = _mean([centered[index] for index in indexes])
        raw_means.append(raw_mean)
        if abs(null_mean) >= abs(estimate):
            null_extreme += 1
    raw_means.sort()
    alpha = 1.0 - confidence
    interval = (_percentile(raw_means, alpha / 2.0), _percentile(raw_means, 1.0 - alpha / 2.0))
    p_value = (null_extreme + 1.0) / (iterations + 1.0)
    return TestOutcome(
        n_units=n_units,
        estimate=estimate,
        confidence_interval=interval,
        p_value=p_value,
        details={"iterations": iterations, "seed": seed, "method": "paired_bootstrap_centered_null"},
    )


def _between_group_statistic(groups: Sequence[str], values: Sequence[float]) -> float:
    by_group: dict[str, list[float]] = defaultdict(list)
    for group, value in zip(groups, values, strict=True):
        by_group[group].append(value)
    overall = _mean(values)
    return sum(len(items) * (_mean(items) - overall) ** 2 for items in by_group.values()) / len(values)


def permutation_test(
    groups: Sequence[str],
    values: Sequence[float],
    *,
    iterations: int = 4000,
    seed: int = 0,
) -> TestOutcome:
    """Permutation test of between-group mean variation."""

    normalized_groups = [str(group) for group in groups]
    normalized_values = _finite(values, "values")
    if len(normalized_groups) != len(normalized_values):
        raise ValueError("groups and values must have equal length")
    if len(normalized_values) < 3 or len(set(normalized_groups)) < 2:
        raise ValueError("permutation test requires at least three units and two groups")
    if iterations < 100:
        raise ValueError("permutation iterations must be at least 100")
    observed = _between_group_statistic(normalized_groups, normalized_values)
    generator = random.Random(seed)
    permuted = list(normalized_values)
    extreme = 0
    for _ in range(iterations):
        generator.shuffle(permuted)
        if _between_group_statistic(normalized_groups, permuted) >= observed:
            extreme += 1
    return TestOutcome(
        n_units=len(normalized_values),
        estimate=observed,
        confidence_interval=None,
        p_value=(extreme + 1.0) / (iterations + 1.0),
        details={
            "iterations": iterations,
            "seed": seed,
            "n_groups": len(set(normalized_groups)),
            "method": "label_permutation_between_group_variation",
        },
    )


def simple_regression(predictor: Sequence[float], outcome: Sequence[float]) -> TestOutcome:
    """OLS slope with an inferential interval for one numeric predictor."""

    x = _finite(predictor, "predictor")
    y = _finite(outcome, "outcome")
    if len(x) != len(y):
        raise ValueError("predictor and outcome must have equal length")
    if len(x) < 3:
        raise ValueError("simple regression requires at least three units")
    mean_x = _mean(x)
    mean_y = _mean(y)
    ss_x = sum((value - mean_x) ** 2 for value in x)
    if ss_x <= 0:
        raise ValueError("regression predictor has no variation")
    cross = sum((x_value - mean_x) * (y_value - mean_y) for x_value, y_value in zip(x, y, strict=True))
    slope = cross / ss_x
    intercept = mean_y - slope * mean_x
    residuals = [y_value - (intercept + slope * x_value) for x_value, y_value in zip(x, y, strict=True)]
    residual_ss = sum(value * value for value in residuals)
    standard_error = math.sqrt((residual_ss / (len(x) - 2)) / ss_x)
    if standard_error == 0.0:
        p_value = 0.0 if slope != 0.0 else 1.0
        critical = 0.0
    else:
        statistic = slope / standard_error
        try:
            from scipy.stats import t as student_t  # type: ignore[import-untyped]

            p_value = float(2.0 * student_t.sf(abs(statistic), df=len(x) - 2))
            critical = float(student_t.ppf(0.975, df=len(x) - 2))
        except ImportError:
            p_value = math.erfc(abs(statistic) / math.sqrt(2.0))
            critical = 1.959963984540054
    total_ss = sum((value - mean_y) ** 2 for value in y)
    r_squared = 1.0 - residual_ss / total_ss if total_ss > 0 else 0.0
    return TestOutcome(
        n_units=len(x),
        estimate=slope,
        confidence_interval=(slope - critical * standard_error, slope + critical * standard_error),
        p_value=max(0.0, min(1.0, p_value)),
        details={
            "intercept": intercept,
            "standard_error": standard_error,
            "r_squared": r_squared,
            "method": "ordinary_least_squares",
        },
    )


def benjamini_hochberg(p_values: Mapping[str, float]) -> dict[str, float]:
    """Benjamini-Hochberg adjusted p-values with monotonicity correction."""

    if not p_values:
        return {}
    for key, value in p_values.items():
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"invalid p-value for {key}: {value}")
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    count = len(ordered)
    adjusted: dict[str, float] = {}
    running = 1.0
    for rank_from_end in range(count - 1, -1, -1):
        key, value = ordered[rank_from_end]
        rank = rank_from_end + 1
        running = min(running, value * count / rank)
        adjusted[key] = min(1.0, running)
    return adjusted


__all__ = [
    "TestOutcome",
    "benjamini_hochberg",
    "paired_bootstrap",
    "permutation_test",
    "simple_regression",
]
