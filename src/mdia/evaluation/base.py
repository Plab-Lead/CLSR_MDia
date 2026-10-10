"""Evaluation extension contract."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..schemas import EvaluationRecord, TaskRecord


@runtime_checkable
class Evaluator(Protocol):
    evaluator_id: str

    def evaluate(self, task: TaskRecord, output: str) -> EvaluationRecord: ...


__all__ = ["Evaluator"]
