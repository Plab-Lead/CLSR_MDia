"""Small, deterministic artifact helpers used by all pipeline stages."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from mdia.schemas import canonical_json, stable_digest

ModelT = TypeVar("ModelT", bound=BaseModel)


def json_value(value: Any) -> Any:
    """Convert Pydantic records and common containers to JSON-compatible data."""

    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=False)
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return value


def write_json_atomic(path: str | Path, value: Any) -> Path:
    """Atomically replace ``path`` with canonical, human-readable JSON."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        json_value(value),
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    )
    fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return target


def write_jsonl_atomic(path: str | Path, records: Iterable[Any]) -> Path:
    """Atomically write records as canonical JSON Lines."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(canonical_json(json_value(record)))
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return target


def read_json(path: str | Path) -> Any:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            rows.append(value)
    return rows


def read_models(path: str | Path, model: type[ModelT]) -> list[ModelT]:
    target = Path(path)
    if not target.exists():
        return []
    if target.suffix == ".jsonl":
        values = read_jsonl(target)
    else:
        loaded = read_json(target)
        values = loaded.get("records", []) if isinstance(loaded, dict) else loaded
        if not isinstance(values, list):
            raise ValueError(f"{target}: expected a JSON array or an object with a records array")
    return [model.model_validate(value) for value in values]


def artifact_checksum(path: str | Path) -> str:
    """Return a SHA-256 checksum over the exact artifact bytes."""

    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def immutable_write(path: str | Path, value: Any) -> Path:
    """Write once, accepting an identical existing value but rejecting drift."""

    target = Path(path)
    normalized = json_value(value)
    if target.exists():
        existing = read_json(target)
        if stable_digest(existing) != stable_digest(normalized):
            raise FileExistsError(f"immutable artifact differs from existing file: {target}")
        return target
    return write_json_atomic(target, normalized)


__all__ = [
    "artifact_checksum",
    "immutable_write",
    "json_value",
    "read_json",
    "read_jsonl",
    "read_models",
    "write_json_atomic",
    "write_jsonl_atomic",
]
