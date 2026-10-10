"""Distinct aggregation algorithms for routed dialect outputs."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from typing import Protocol

from ..schemas import AggregationMethod


def normalize_vote(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _validate_outputs(outputs: Sequence[str]) -> None:
    if not outputs:
        raise ValueError("at least one output is required")


def majority_vote(outputs: Sequence[str]) -> str:
    """Return the first output in the largest normalized answer group."""

    _validate_outputs(outputs)
    groups: dict[str, list[int]] = defaultdict(list)
    for index, output in enumerate(outputs):
        groups[normalize_vote(output)].append(index)
    winning_indices = max(groups.values(), key=lambda indices: (len(indices), -indices[0]))
    return outputs[winning_indices[0]]


def weighted_vote(outputs: Sequence[str], weights: Sequence[float]) -> str:
    """Sum nonnegative validation-derived weights by answer group."""

    _validate_outputs(outputs)
    if len(outputs) != len(weights):
        raise ValueError("weights must align with outputs")
    if any(weight < 0 for weight in weights):
        raise ValueError("weights cannot be negative")
    totals: dict[str, float] = defaultdict(float)
    first_index: dict[str, int] = {}
    for index, (output, weight) in enumerate(zip(outputs, weights, strict=True)):
        key = normalize_vote(output)
        totals[key] += weight
        first_index.setdefault(key, index)
    winner = max(totals, key=lambda key: (totals[key], -first_index[key]))
    return outputs[first_index[winner]]


def score_vote(outputs: Sequence[str], scores: Sequence[float]) -> str:
    """Choose the individually highest externally scored output.

    Unlike weighted voting, scores are not pooled across duplicate answers.
    """

    _validate_outputs(outputs)
    if len(outputs) != len(scores):
        raise ValueError("scores must align with outputs")
    winner = max(range(len(outputs)), key=lambda index: (scores[index], -index))
    return outputs[winner]


class Judge(Protocol):
    def __call__(self, outputs: tuple[str, ...]) -> int | str: ...


def judge_vote(outputs: Sequence[str], judge: Judge) -> str:
    """Delegate selection to an explicit judge; never mimic one heuristically."""

    _validate_outputs(outputs)
    result = judge(tuple(outputs))
    if isinstance(result, int):
        if result < 0 or result >= len(outputs):
            raise ValueError("judge returned an out-of-range output index")
        return outputs[result]
    if isinstance(result, str):
        return result
    raise TypeError("judge must return an output index or judged output text")


def aggregate_outputs(
    method: AggregationMethod,
    outputs: Sequence[str],
    *,
    weights: Sequence[float] | None = None,
    scores: Sequence[float] | None = None,
    judge: Judge | None = None,
) -> str:
    if method is AggregationMethod.MAJORITY:
        return majority_vote(outputs)
    if method is AggregationMethod.WEIGHTED:
        if weights is None:
            raise ValueError("weighted aggregation requires weights")
        return weighted_vote(outputs, weights)
    if method is AggregationMethod.SCORE:
        if scores is None:
            raise ValueError("score aggregation requires external scores")
        return score_vote(outputs, scores)
    if judge is None:
        raise ValueError("judge aggregation requires an explicit judge callback")
    return judge_vote(outputs, judge)


__all__ = [
    "Judge",
    "aggregate_outputs",
    "judge_vote",
    "majority_vote",
    "normalize_vote",
    "score_vote",
    "weighted_vote",
]
