"""Dataset extension contract."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from ..schemas import DataSplit, TaskRecord


@runtime_checkable
class DatasetAdapter(Protocol):
    """Load one immutable logical split at a time."""

    def load(self, split: DataSplit) -> Iterable[TaskRecord]: ...


__all__ = ["DatasetAdapter"]
