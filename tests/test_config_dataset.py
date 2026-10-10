from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from mdia.config import DatasetConfig, RunConfig, load_config
from mdia.datasets.jsonl import JsonlDatasetAdapter, SplitIsolationError
from mdia.schemas import DataSplit

ROOT = Path(__file__).resolve().parents[1]


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_checked_in_mdia_and_clsr_presets_validate() -> None:
    mdia = load_config(ROOT / "configs" / "toy_mdia.yaml")
    clsr = load_config(ROOT / "configs" / "clsr.yaml")

    assert mdia.community.preset == "mdia"
    assert not mdia.community.homogeneous
    assert mdia.rules.enabled
    assert mdia.resolve_path(mdia.dataset.path).is_file()  # type: ignore[arg-type]

    assert clsr.community.preset == "clsr"
    assert clsr.community.homogeneous
    assert len(clsr.community.creators) == len(clsr.community.speakers) == len(clsr.community.listeners) == 1
    assert not clsr.rules.enabled


def test_clsr_config_rejects_cross_family_rule_analysis() -> None:
    clsr = load_config(ROOT / "configs" / "clsr.yaml")
    payload = clsr.model_dump(mode="json")
    payload["rules"]["enabled"] = True
    with pytest.raises(ValidationError, match="CLSR disables"):
        RunConfig.model_validate(payload)


def test_provider_config_accepts_only_environment_variable_name() -> None:
    mdia = load_config(ROOT / "configs" / "toy_mdia.yaml")
    payload = mdia.model_dump(mode="json")
    payload["provider"] = {
        "kind": "openai_compatible",
        "model": "fixture",
        "api_key_env": "literal-secret-value!",
    }
    with pytest.raises(ValidationError, match="environment variable"):
        RunConfig.model_validate(payload)


def test_jsonl_adapter_loads_all_immutable_splits(tmp_path: Path) -> None:
    source = tmp_path / "tasks.jsonl"
    rows = [
        {"task_id": f"id-{split.value}", "split": split.value, "query": f"q-{split.value}", "gold": "A"}
        for split in DataSplit
    ]
    _write_jsonl(source, rows)
    adapter = JsonlDatasetAdapter(DatasetConfig(path=source))

    hashes = {split: adapter.manifest_hash(split) for split in DataSplit}
    assert all(len(adapter.load(split)) == 1 for split in DataSplit)
    assert len(set(hashes.values())) == 4


@pytest.mark.parametrize("collision", ["id", "content"])
def test_jsonl_adapter_rejects_cross_split_leakage(tmp_path: Path, collision: str) -> None:
    source = tmp_path / "leaky.jsonl"
    first = {"task_id": "shared" if collision == "id" else "a", "split": "induction", "query": "same"}
    second = {"task_id": "shared" if collision == "id" else "b", "split": "test", "query": "same"}
    _write_jsonl(source, [first, second])
    adapter = JsonlDatasetAdapter(DatasetConfig(path=source, strict_split_isolation=True))

    with pytest.raises(SplitIsolationError, match="both|identical public"):
        adapter.load(DataSplit.TEST)


def test_per_split_manifest_rejects_mislabeled_row(tmp_path: Path) -> None:
    source = tmp_path / "induction.jsonl"
    _write_jsonl(source, [{"task_id": "x", "split": "test", "query": "wrong split"}])
    adapter = JsonlDatasetAdapter(DatasetConfig(split_paths={DataSplit.INDUCTION: source}))
    with pytest.raises(SplitIsolationError, match="inside 'induction' manifest"):
        adapter.load(DataSplit.INDUCTION)
