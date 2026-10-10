"""Routing extension contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, runtime_checkable

from pydantic import JsonValue

from ..schemas import (
    ControllerRoutePlan,
    DialectCard,
    DialectProfile,
    DialectRoutePlan,
    RouteBudget,
    TaskView,
)


@runtime_checkable
class DialectRouter(Protocol):
    router_id: str

    def route(
        self,
        task_view: TaskView,
        listener_profile: Sequence[DialectProfile],
        bank: Sequence[DialectCard],
        budget: RouteBudget,
    ) -> DialectRoutePlan: ...


@runtime_checkable
class ControllerRouter(Protocol):
    router_id: str

    def route(
        self,
        task_metadata: Mapping[str, JsonValue],
        listener_profile: Mapping[str, JsonValue],
        budget: RouteBudget,
    ) -> ControllerRoutePlan: ...


__all__ = ["ControllerRouter", "DialectRouter"]
