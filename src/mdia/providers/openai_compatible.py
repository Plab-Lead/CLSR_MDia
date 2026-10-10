"""Dependency-free client for OpenAI-compatible chat-completions APIs."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from ..schemas import Completion, CompletionRequest
from .base import ProviderError


class OpenAICompatibleProvider:
    """Call ``/chat/completions`` while reading credentials only from env."""

    provider_id = "openai_compatible"

    def __init__(
        self,
        *,
        model: str = "openai-compatible",
        base_url: str | None = None,
        api_key_env: str = "MDIA_API_KEY",
        timeout_seconds: float = 120.0,
        retries: int = 2,
        revision: str = "unspecified",
    ) -> None:
        self.model = model
        self.base_url = (base_url or os.getenv("MDIA_API_BASE") or "https://api.openai.com/v1").rstrip("/")
        self.api_key_env = api_key_env
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.revision = revision

    def _api_key(self) -> str:
        value = os.getenv(self.api_key_env, "").strip()
        if not value:
            raise ProviderError(f"required credential environment variable {self.api_key_env} is not set")
        return value

    @staticmethod
    def _content_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") in (None, "text"):
                    parts.append(str(item.get("text", "")))
            return "".join(parts)
        return str(content or "")

    def complete(self, request: CompletionRequest) -> Completion:
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [message.model_dump(mode="json", exclude_none=True) for message in request.messages],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": False,
        }
        if request.stop:
            payload["stop"] = list(request.stop)
        if request.seed is not None:
            payload["seed"] = request.seed
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Authorization": f"Bearer {self._api_key()}", "Content-Type": "application/json"}
        last_error: BaseException | None = None
        started = time.monotonic()

        for attempt in range(self.retries + 1):
            http_request = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=body,
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(http_request, timeout=self.timeout_seconds) as response:  # noqa: S310
                    raw = response.read().decode("utf-8")
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise ProviderError("provider response must be a JSON object")
                choices = result.get("choices")
                if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                    raise ProviderError("provider response has no completion choice")
                choice = choices[0]
                message = choice.get("message", {})
                if not isinstance(message, dict):
                    raise ProviderError("provider choice has no message object")
                usage = result.get("usage", {})
                if not isinstance(usage, dict):
                    usage = {}
                metadata: dict[str, Any] = {}
                for key in ("id", "created", "system_fingerprint"):
                    if result.get(key) is not None:
                        metadata[key] = result[key]
                return Completion(
                    request_id=request.request_id,
                    text=self._content_text(message.get("content")),
                    model=str(result.get("model") or request.model),
                    prompt_tokens=int(usage.get("prompt_tokens") or 0),
                    completion_tokens=int(usage.get("completion_tokens") or 0),
                    finish_reason=str(choice.get("finish_reason") or "stop"),
                    latency_ms=(time.monotonic() - started) * 1000.0,
                    metadata=metadata,
                )
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code < 500 and exc.code != 429:
                    break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ProviderError) as exc:
                last_error = exc
                if isinstance(exc, ProviderError):
                    break
            if attempt < self.retries:
                time.sleep(min(2.0**attempt, 8.0))
        raise ProviderError(f"chat completion failed after {self.retries + 1} attempt(s): {last_error}")


__all__ = ["OpenAICompatibleProvider"]
