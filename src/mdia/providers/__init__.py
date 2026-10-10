"""Completion providers and provider factory."""

from __future__ import annotations

from pathlib import Path

from ..config import ProviderConfig
from .base import ChatProvider, ProviderError
from .openai_compatible import OpenAICompatibleProvider
from .replay import ReplayEntry, ReplayMissError, ReplayProvider


def build_provider(config: ProviderConfig, *, base_dir: Path | None = None) -> ChatProvider:
    if config.kind == "replay":
        if config.replay_path is None:
            return ReplayProvider(
                model=config.model,
                default_text=config.replay_default_text,
                revision=config.revision,
            )
        path = config.replay_path
        if not path.is_absolute():
            path = ((base_dir or Path.cwd()) / path).resolve()
        return ReplayProvider.from_jsonl(
            path,
            model=config.model,
            default_text=config.replay_default_text,
            revision=config.revision,
        )
    return OpenAICompatibleProvider(
        model=config.model,
        base_url=config.base_url,
        api_key_env=config.api_key_env,
        timeout_seconds=config.timeout_seconds,
        retries=config.retries,
        revision=config.revision,
    )


__all__ = [
    "ChatProvider",
    "OpenAICompatibleProvider",
    "ProviderError",
    "ReplayEntry",
    "ReplayMissError",
    "ReplayProvider",
    "build_provider",
]
