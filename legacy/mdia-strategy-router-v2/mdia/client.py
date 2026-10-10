"""Small OpenAI-compatible chat client.

Credentials are intentionally read only from environment variables at runtime.
No key or provider-specific secret should be committed with this package.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any


DEFAULT_API_BASE = "https://api.siliconflow.cn/v1"


def chat_completion(
    model: str,
    prompt: str,
    *,
    api_base: str | None = None,
    api_key_env: str = "MDIA_API_KEY",
    max_tokens: int = 160,
    temperature: float = 0.0,
    retries: int = 2,
    timeout: int = 120,
) -> dict[str, Any]:
    """Call an OpenAI-compatible ``/chat/completions`` endpoint."""

    key = os.environ.get(api_key_env, "").strip()
    if not key:
        raise RuntimeError(f"{api_key_env} is not set")

    base = (api_base or os.environ.get("MDIA_API_BASE") or DEFAULT_API_BASE).rstrip("/")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
        "enable_thinking": False,
    }
    data = json.dumps(payload).encode("utf-8")
    last_error = "unknown"

    for attempt in range(retries + 1):
        req = urllib.request.Request(
            f"{base}/chat/completions",
            data=data,
            method="POST",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                body = resp.read().decode("utf-8", errors="replace")
            obj = json.loads(body)
            choice = obj.get("choices", [{}])[0]
            message = choice.get("message", {}) if isinstance(choice, dict) else {}
            return {
                "ok": True,
                "content": str(message.get("content", "")),
                "usage": obj.get("usage", {}) if isinstance(obj, dict) else {},
                "raw": obj,
            }
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = str(exc)[:500]
            time.sleep(1.5 * (attempt + 1))

    return {"ok": False, "content": "", "usage": {}, "error": last_error}

