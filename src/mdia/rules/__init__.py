"""Machine-sociolinguistic rule registry and validation utilities."""

from mdia.rules.registry import FAMILIES, RULE_REGISTRY, build_registry, get_rule
from mdia.rules.statistics import (
    TestOutcome,
    benjamini_hochberg,
    paired_bootstrap,
    permutation_test,
    simple_regression,
)
from mdia.rules.validation import EvidenceInput, validate_rules

__all__ = [
    "EvidenceInput",
    "FAMILIES",
    "RULE_REGISTRY",
    "TestOutcome",
    "benjamini_hochberg",
    "build_registry",
    "get_rule",
    "paired_bootstrap",
    "permutation_test",
    "simple_regression",
    "validate_rules",
]
