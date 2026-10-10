"""Language-model provider extension contract."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..schemas import Completion, CompletionRequest


class ProviderError(RuntimeError):
    """Base exception for completion-provider failures."""


@runtime_checkable
class ChatProvider(Protocol):
    provider_id: str
    revision: str

    def complete(self, request: CompletionRequest) -> Completion: ...


__all__ = ["ChatProvider", "ProviderError"]
