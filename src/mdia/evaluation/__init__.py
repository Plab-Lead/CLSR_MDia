"""Evaluation contracts and diagnostic evaluators."""

from __future__ import annotations

from ..config import EvaluatorConfig
from .base import Evaluator
from .exact import DiagnosticEvaluator, ExactMatchEvaluator, normalize_text


def build_evaluator(config: EvaluatorConfig) -> Evaluator:
    if config.official:
        raise ValueError(
            "built-in evaluators are diagnostic only; configure an official harness adapter instead"
        )
    if config.kind == "diagnostic":
        return DiagnosticEvaluator(evaluator_id=config.evaluator_id, json_field=config.json_field)
    return ExactMatchEvaluator(
        evaluator_id=config.evaluator_id,
        case_sensitive=config.case_sensitive,
        strip=config.strip,
        normalize_whitespace=config.normalize_whitespace,
        json_field=config.json_field,
    )


__all__ = [
    "DiagnosticEvaluator",
    "Evaluator",
    "ExactMatchEvaluator",
    "build_evaluator",
    "normalize_text",
]
