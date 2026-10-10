"""Clearly labelled diagnostic evaluators for toy and smoke-test data."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import JsonValue

from ..schemas import EvaluationRecord, TaskRecord, canonical_json


def normalize_text(
    value: str,
    *,
    case_sensitive: bool = False,
    strip: bool = True,
    normalize_whitespace: bool = True,
) -> str:
    if strip:
        value = value.strip()
    if normalize_whitespace:
        value = re.sub(r"\s+", " ", value)
    return value if case_sensitive else value.casefold()


def _parse_json(text: str) -> JsonValue:
    value = json.loads(text)
    return value


class ExactMatchEvaluator:
    """Diagnostic exact match; not a substitute for official harnesses."""

    def __init__(
        self,
        *,
        evaluator_id: str = "exact-match-v1",
        case_sensitive: bool = False,
        strip: bool = True,
        normalize_whitespace: bool = True,
        json_field: str | None = None,
    ) -> None:
        self.evaluator_id = evaluator_id
        self.case_sensitive = case_sensitive
        self.strip = strip
        self.normalize_whitespace = normalize_whitespace
        self.json_field = json_field

    def evaluate(self, task: TaskRecord, output: str) -> EvaluationRecord:
        parsed: JsonValue | None = output
        candidate: Any = output
        parse_failure = False
        if self.json_field is not None:
            try:
                parsed = _parse_json(output)
                if not isinstance(parsed, dict) or self.json_field not in parsed:
                    raise ValueError(f"JSON output has no field {self.json_field!r}")
                candidate = parsed[self.json_field]
            except (json.JSONDecodeError, ValueError):
                parsed = None
                candidate = None
                parse_failure = True
        elif task.gold is not None and not isinstance(task.gold, str):
            try:
                parsed = _parse_json(output)
                candidate = parsed
            except json.JSONDecodeError:
                parsed = None
                candidate = None
                parse_failure = True

        if task.gold is None:
            correct: bool | None = None
            score: float | None = None
        elif candidate is None:
            correct = False
            score = 0.0
        elif isinstance(task.gold, str) and isinstance(candidate, str):
            correct = normalize_text(
                candidate,
                case_sensitive=self.case_sensitive,
                strip=self.strip,
                normalize_whitespace=self.normalize_whitespace,
            ) == normalize_text(
                task.gold,
                case_sensitive=self.case_sensitive,
                strip=self.strip,
                normalize_whitespace=self.normalize_whitespace,
            )
            score = float(correct)
        else:
            correct = canonical_json(candidate) == canonical_json(task.gold)
            score = float(correct)

        return EvaluationRecord(
            task_id=task.task_id,
            evaluator_id=self.evaluator_id,
            output=output,
            parsed_output=parsed,
            correct=correct,
            score=score,
            parse_failure=parse_failure,
            official=False,
            diagnostic=True,
            details={
                "warning": "diagnostic evaluator; use the benchmark's official harness for paper claims"
            },
        )


class DiagnosticEvaluator:
    """Parse-only evaluator for outputs that have no redistributable gold."""

    def __init__(self, *, evaluator_id: str = "diagnostic-v1", json_field: str | None = None) -> None:
        self.evaluator_id = evaluator_id
        self.json_field = json_field

    def evaluate(self, task: TaskRecord, output: str) -> EvaluationRecord:
        parsed: JsonValue | None = output
        parse_failure = False
        if self.json_field is not None:
            try:
                parsed = _parse_json(output)
                if not isinstance(parsed, dict) or self.json_field not in parsed:
                    raise ValueError
                parsed = parsed[self.json_field]
            except (json.JSONDecodeError, ValueError):
                parsed = None
                parse_failure = True
        return EvaluationRecord(
            task_id=task.task_id,
            evaluator_id=self.evaluator_id,
            output=output,
            parsed_output=parsed,
            correct=None,
            score=None,
            parse_failure=parse_failure,
            official=False,
            diagnostic=True,
            details={"warning": "diagnostic parse only; no performance claim is supported"},
        )


__all__ = ["DiagnosticEvaluator", "ExactMatchEvaluator", "normalize_text"]
