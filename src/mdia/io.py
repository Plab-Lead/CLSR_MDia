"""Small, deterministic I/O helpers used by pipeline stages."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .schemas import canonical_json


class JsonlError(ValueError):
    """Raised for a malformed JSONL record."""


def read_json(path: str | os.PathLike[str]) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def iter_jsonl(path: str | os.PathLike[str]) -> Iterator[dict[str, Any]]:
    source = Path(path)
    with source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise JsonlError(f"{source}:{line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(value, dict):
                raise JsonlError(f"{source}:{line_number}: each JSONL row must be an object")
            yield value


def _serializable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=False)
    return value


def atomic_write_text(path: str | os.PathLike[str], text: str) -> Path:
    """Replace ``path`` atomically after fsyncing a sibling temporary file."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def write_json_atomic(path: str | os.PathLike[str], value: Any) -> Path:
    return atomic_write_text(path, f"{canonical_json(_serializable(value))}\n")


def write_jsonl_atomic(path: str | os.PathLike[str], records: Iterable[Any]) -> Path:
    payload = "".join(f"{canonical_json(_serializable(record))}\n" for record in records)
    return atomic_write_text(path, payload)


def sha256_file(path: str | os.PathLike[str], *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_checksums(
    paths: Iterable[str | os.PathLike[str]], *, root: Path | None = None
) -> dict[str, str]:
    checksums: dict[str, str] = {}
    base = root.resolve() if root is not None else None
    for raw_path in paths:
        path = Path(raw_path).resolve()
        key = path.relative_to(base).as_posix() if base is not None else path.name
        checksums[key] = sha256_file(path)
    return dict(sorted(checksums.items()))


def assert_unique_keys(records: Iterable[Mapping[str, Any]], key: str, *, source: str = "records") -> None:
    seen: set[Any] = set()
    for index, record in enumerate(records):
        value = record.get(key)
        if value in seen:
            raise ValueError(f"duplicate {key}={value!r} at {source} row {index + 1}")
        seen.add(value)


__all__ = [
    "JsonlError",
    "artifact_checksums",
    "assert_unique_keys",
    "atomic_write_text",
    "iter_jsonl",
    "read_json",
    "sha256_file",
    "write_json_atomic",
    "write_jsonl_atomic",
]
