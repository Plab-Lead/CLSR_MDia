"""Concrete-dialect and optional controller routing."""

from .aggregation import (
    Judge,
    aggregate_outputs,
    judge_vote,
    majority_vote,
    normalize_vote,
    score_vote,
    weighted_vote,
)
from .base import ControllerRouter, DialectRouter
from .controller import (
    DEFAULT_ANSWER_CONTRACTS,
    DEFAULT_CONTROLLER_ROUTES,
    DEFAULT_KEY_FIELDS,
    MetadataControllerRouter,
)
from .dialect import FixedSingleDialectRouter, UtilityDialectRouter, utility_score

__all__ = [
    "ControllerRouter",
    "DEFAULT_ANSWER_CONTRACTS",
    "DEFAULT_CONTROLLER_ROUTES",
    "DEFAULT_KEY_FIELDS",
    "DialectRouter",
    "FixedSingleDialectRouter",
    "Judge",
    "MetadataControllerRouter",
    "UtilityDialectRouter",
    "aggregate_outputs",
    "judge_vote",
    "majority_vote",
    "normalize_vote",
    "score_vote",
    "utility_score",
    "weighted_vote",
]
