from __future__ import annotations

import json
from pathlib import Path

from pytest import MonkeyPatch

from mdia.cli import main
from mdia.config import load_config


def test_one_command_offline_pipeline_is_reproducible(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    repository = Path(__file__).resolve().parents[1]
    config_path = repository / "configs" / "toy_mdia.yaml"
    first = tmp_path / "first"
    second = tmp_path / "second"

    monkeypatch.setenv("MDIA_CODE_REVISION", "test-revision")
    assert main(["pipeline", "--config", str(config_path), "--run-dir", str(first)]) == 0
    assert main(["pipeline", "--config", str(config_path), "--run-dir", str(second)]) == 0

    for relative in (
        "selection/frozen_dialect_bank.json",
        "execution/route_plans.jsonl",
        "execution/predictions.jsonl",
    ):
        assert (first / relative).read_bytes() == (second / relative).read_bytes()

    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    rules = json.loads((first / "rules" / "results.json").read_text(encoding="utf-8"))
    assert manifest["config_hash"] == load_config(config_path).config_hash
    assert manifest["code_revision"] == "test-revision"
    assert len(manifest["split_hashes"]) == 4
    assert rules["n_rules"] == 100
    assert {record["status"] for record in rules["records"]} == {"not_evaluated"}
    assert (first / "report.md").is_file()
    assert (first / "dialects" / "generation-001.json").is_file()
    assert not (first / "dialects" / "generation-002.json").exists()

    predictions = first / "execution" / "predictions.jsonl"
    predictions.write_text(predictions.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert main(["report", "--config", str(config_path), "--run-dir", str(first)]) == 2
