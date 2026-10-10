from __future__ import annotations

import json
from pathlib import Path

from mdia.evaluation.exact import ExactMatchEvaluator
from mdia.pipeline.orchestrator import run_pipeline
from mdia.routing.dialect import UtilityDialectRouter
from mdia.schemas import DataSplit, RouteBudget, RouteMode, RuleExecutionStatus
from tests.support import MemoryAdapter, RecordingProvider, make_task


def _adapter(prefix: str) -> MemoryAdapter:
    return MemoryAdapter(
        {
            split: [
                make_task(
                    f"{prefix}-{split.value}",
                    split=split,
                    query=f"{prefix} question for {split.value}",
                    gold="A",
                    metadata={"benchmark": "toy", "task_tag": "toy"},
                )
            ]
            for split in DataSplit
        }
    )


def _assert_route_integrity(artifacts: object) -> None:
    bank_ids = {card.dialect_id for card in artifacts.frozen_bank}  # type: ignore[attr-defined]
    digest_by_id = {card.dialect_id: card.specification_digest for card in artifacts.frozen_bank}  # type: ignore[attr-defined]
    assert bank_ids
    for plan in artifacts.execution.route_plans:  # type: ignore[attr-defined]
        assert set(plan.dialect_ids) <= bank_ids
        assert all(
            digest_by_id[dialect_id] == digest
            for dialect_id, digest in zip(plan.dialect_ids, plan.specification_digests, strict=True)
        )


def test_mdia_pipeline_runs_two_member_community_end_to_end(tmp_path: Path) -> None:
    provider_a = RecordingProvider(default="A", model="model-a")
    provider_b = RecordingProvider(default="A", model="model-b")
    router = UtilityDialectRouter(listener_id="listener-a")
    run_dir = tmp_path / "mdia-run"
    artifacts = run_pipeline(
        _adapter("mdia"),
        {"listener-a": provider_a, "listener-b": provider_b},
        ExactMatchEvaluator(),
        router,
        run_dir=run_dir,
        budget=RouteBudget(token_budget=20, max_steps=1),
        config={
            "preset": "mdia",
            "create": {"top_k": 2, "speaker_diversity": True},
            "evolve": {"max_generations": 1},
            "select": {"min_support": 1, "max_cards": 2},
            "rules": {"iterations": 100},
        },
        code_revision="test",
        provider_revision="fixture-v1",
        model_revisions={"listener-a": "a1", "listener-b": "b1"},
        seed=7,
    )

    assert len(artifacts.traces) == 2
    assert {card.creator_id for card in artifacts.frozen_bank} == {"listener-a", "listener-b"}
    assert all(card.empirical_profile["profiled"] == 1.0 for card in artifacts.frozen_bank)
    assert all(card.profile_ids for card in artifacts.frozen_bank)
    assert len(artifacts.execution.predictions) == 1
    assert artifacts.execution.evaluations[0].correct is True
    assert len(artifacts.rule_results) == 100
    assert all(result.status is RuleExecutionStatus.NOT_EVALUATED for result in artifacts.rule_results)
    assert artifacts.manifest.metadata["clsr_special_case"] is False
    assert set(artifacts.manifest.candidate_pool) == {card.dialect_id for card in artifacts.frozen_bank}
    assert artifacts.report_path.is_file()
    assert (run_dir / "direct_traces.jsonl").is_file()
    assert (run_dir / "selection" / "frozen_dialect_bank.json").is_file()
    assert (run_dir / "execution" / "token_accounting.json").is_file()
    assert "report.md" in artifacts.manifest.artifact_checksums
    _assert_route_integrity(artifacts)


def test_clsr_pipeline_is_homogeneous_special_case(tmp_path: Path) -> None:
    provider = RecordingProvider(default="A", model="clsr-backbone")
    run_dir = tmp_path / "clsr-run"
    artifacts = run_pipeline(
        _adapter("clsr"),
        {"clsr-backbone": provider},
        ExactMatchEvaluator(),
        UtilityDialectRouter(listener_id="clsr-backbone"),
        run_dir=run_dir,
        budget=RouteBudget(token_budget=20, max_steps=1),
        config={
            "preset": "clsr",
            "create": {"top_k": 1, "speaker_diversity": False},
            "evolve": {"max_generations": 1},
            "select": {"min_support": 1, "max_cards": 1},
            "rules": {"enabled": False, "iterations": 100},
        },
        code_revision="test",
        provider_revision="fixture-v1",
        model_revisions={"clsr-backbone": "fixture"},
        seed=7,
    )

    assert len(artifacts.traces) == 1
    assert len(artifacts.frozen_bank) == 1
    assert artifacts.frozen_bank[0].creator_id == "clsr-backbone"
    assert artifacts.manifest.metadata["clsr_special_case"] is True
    assert artifacts.rule_results == ()
    assert artifacts.execution.route_plans[0].mode is RouteMode.SINGLE
    _assert_route_integrity(artifacts)

    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["metadata"]["clsr_special_case"] is True
    assert manifest["split_hashes"].keys() == {split.value for split in DataSplit}
