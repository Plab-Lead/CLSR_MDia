"""Deterministic offline completion replay."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from ..io import iter_jsonl
from ..schemas import Completion, CompletionRequest
from .base import ProviderError


class ReplayMissError(ProviderError, KeyError):
    """Raised when a strict replay has no row for a request."""


class ReplayEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(min_length=1)
    text: str
    model: str | None = None
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    finish_reason: str = "stop"
    latency_ms: float = Field(default=0.0, ge=0.0)
    cost: float = Field(default=0.0, ge=0.0)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ReplayProvider:
    """Return one immutable completion per deterministic request key.

    Duplicate keys are rejected instead of being consumed in order, making
    results independent of execution order and concurrency.
    """

    provider_id = "replay"

    def __init__(
        self,
        entries: Iterable[ReplayEntry | Mapping[str, Any]] = (),
        *,
        model: str = "replay",
        default_text: str | None = None,
        revision: str = "offline-fixture",
    ) -> None:
        index: dict[str, ReplayEntry] = {}
        for raw_entry in entries:
            entry = raw_entry if isinstance(raw_entry, ReplayEntry) else ReplayEntry.model_validate(raw_entry)
            if entry.key in index:
                raise ValueError(f"duplicate replay key: {entry.key}")
            index[entry.key] = entry
        self._entries = index
        self._default_text = default_text
        self.model = model
        self.revision = revision

    @classmethod
    def from_jsonl(
        cls,
        path: str | Path,
        *,
        model: str = "replay",
        default_text: str | None = None,
        revision: str = "offline-fixture",
    ) -> ReplayProvider:
        return cls(iter_jsonl(path), model=model, default_text=default_text, revision=revision)

    def complete(self, request: CompletionRequest) -> Completion:
        entry = self._entries.get(request.replay_key)
        if entry is None:
            if self._default_text is None:
                raise ReplayMissError(f"no replay completion for key {request.replay_key!r}")
            return Completion(
                request_id=request.request_id,
                text=self._default_text,
                model=request.model,
                completion_tokens=len(self._default_text.split()),
                metadata={"replay_default": True},
            )
        return Completion(
            request_id=request.request_id,
            text=entry.text,
            model=entry.model or request.model,
            prompt_tokens=entry.prompt_tokens,
            completion_tokens=entry.completion_tokens,
            finish_reason=entry.finish_reason,
            latency_ms=entry.latency_ms,
            cost=entry.cost,
            metadata={**entry.metadata, "replay_key": entry.key},
        )

    @property
    def keys(self) -> frozenset[str]:
        return frozenset(self._entries)


__all__ = ["ReplayEntry", "ReplayMissError", "ReplayProvider"]
