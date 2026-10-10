"""JSONL dataset adapter with explicit split-leakage checks."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from ..config import DatasetConfig
from ..io import iter_jsonl
from ..schemas import DataSplit, TaskRecord, public_task_metadata, stable_digest, task_manifest_digest


class SplitIsolationError(ValueError):
    """Raised when a row appears in more than one immutable split."""


class JsonlDatasetAdapter:
    """Read either one split-labelled JSONL or one JSONL per split.

    Parsed records are cached as immutable tuples. In strict mode, both stable
    task IDs and gold-free query/metadata fingerprints must be unique across
    splits, so accidental train/test overlap fails before a stage runs.
    """

    def __init__(
        self,
        config: DatasetConfig,
        *,
        base_dir: Path | None = None,
    ) -> None:
        self.config = config
        self.base_dir = (base_dir or Path.cwd()).resolve()
        self._cache: dict[DataSplit, tuple[TaskRecord, ...]] | None = None

    def _resolve(self, path: Path) -> Path:
        return path if path.is_absolute() else (self.base_dir / path).resolve()

    def _row_to_task(self, row: dict[str, Any], expected_split: DataSplit | None, source: str) -> TaskRecord:
        cfg = self.config
        raw_split = row.get(cfg.split_field)
        if raw_split is None:
            if expected_split is None:
                raise SplitIsolationError(f"{source}: missing required split field {cfg.split_field!r}")
            split = expected_split
        else:
            try:
                split = DataSplit(str(raw_split))
            except ValueError as exc:
                raise SplitIsolationError(f"{source}: unknown split {raw_split!r}") from exc
        if expected_split is not None and split is not expected_split:
            raise SplitIsolationError(
                f"{source}: row declares split={split.value!r} inside {expected_split.value!r} manifest"
            )
        if cfg.query_field not in row:
            raise ValueError(f"{source}: missing query field {cfg.query_field!r}")

        raw_metadata = row.get(cfg.metadata_field, {})
        if raw_metadata is None:
            raw_metadata = {}
        if not isinstance(raw_metadata, Mapping):
            raise ValueError(f"{source}: metadata field {cfg.metadata_field!r} must be an object")
        consumed = {
            cfg.id_field,
            cfg.split_field,
            cfg.query_field,
            cfg.gold_field,
            cfg.metadata_field,
            "content_hash",
        }
        metadata: dict[str, JsonValue] = dict(raw_metadata)
        for key, value in row.items():
            if key not in consumed and key not in metadata:
                metadata[key] = value

        task_id = row.get(cfg.id_field, "")
        return TaskRecord(
            task_id="" if task_id is None else str(task_id),
            split=split,
            query=str(row[cfg.query_field]),
            gold=row.get(cfg.gold_field),
            metadata=metadata,
            content_hash=str(row.get("content_hash", "")),
        )

    def _read_path(self, path: Path, expected_split: DataSplit | None) -> list[TaskRecord]:
        records: list[TaskRecord] = []
        for line_number, row in enumerate(iter_jsonl(path), start=1):
            records.append(self._row_to_task(row, expected_split, f"{path}:{line_number}"))
        return records

    def _build_cache(self) -> dict[DataSplit, tuple[TaskRecord, ...]]:
        grouped: dict[DataSplit, list[TaskRecord]] = defaultdict(list)
        if self.config.path is not None:
            path = self._resolve(self.config.path)
            for record in self._read_path(path, None):
                grouped[record.split].append(record)
        else:
            for split, raw_path in self.config.split_paths.items():
                grouped[split].extend(self._read_path(self._resolve(raw_path), split))

        seen_ids: dict[str, DataSplit] = {}
        seen_public: dict[str, DataSplit] = {}
        for split in DataSplit:
            local_ids: set[str] = set()
            for record in grouped.get(split, []):
                if record.task_id in local_ids:
                    raise SplitIsolationError(
                        f"duplicate task_id {record.task_id!r} within split {split.value!r}"
                    )
                local_ids.add(record.task_id)
                previous = seen_ids.get(record.task_id)
                if previous is not None and previous is not split:
                    raise SplitIsolationError(
                        f"task_id {record.task_id!r} occurs in both {previous.value!r} and {split.value!r}"
                    )
                seen_ids[record.task_id] = split
                if self.config.strict_split_isolation:
                    fingerprint = stable_digest(
                        {"query": record.query, "metadata": public_task_metadata(record.metadata)}
                    )
                    previous = seen_public.get(fingerprint)
                    if previous is not None and previous is not split:
                        raise SplitIsolationError(
                            f"identical public task content occurs in both {previous.value!r} and {split.value!r}"
                        )
                    seen_public[fingerprint] = split
        return {split: tuple(grouped.get(split, ())) for split in DataSplit}

    def load(self, split: DataSplit) -> tuple[TaskRecord, ...]:
        requested = DataSplit(split)
        if self._cache is None:
            self._cache = self._build_cache()
        return self._cache[requested]

    def manifest_hash(self, split: DataSplit) -> str:
        return task_manifest_digest(self.load(split))


__all__ = ["JsonlDatasetAdapter", "SplitIsolationError"]
