from __future__ import annotations

import json
from pathlib import Path

import pytest

from mdia.evaluation.exact import ExactMatchEvaluator
from mdia.pipeline.lifecycle import collect, create, evolve, profile, select, select_top_k_traces
from mdia.schemas import CompletionRequest, DataSplit, TraceRecord
from tests.support import MemoryAdapter, RecordingProvider, make_card, make_profile, make_task


def _trace(task: str, speaker: str, tokens: int, *, output: str, correct: bool = True) -> TraceRecord:
    return TraceRecord(
        task_id=task,
        split=DataSplit.INDUCTION,
        speaker_id=speaker,
        model_id=speaker,
        output=output,
        completion_tokens=tokens,
        correct=correct,
    )


def test_collect_exposes_no_gold_to_provider_and_resumes(tmp_path: Path) -> None:
    task = make_task(
        "induce",
        split=DataSplit.INDUCTION,
        query="Public question",
        gold="private-gold",
        metadata={"benchmark": "toy", "gold_answer": "metadata-gold"},
    )
    adapter = MemoryAdapter({DataSplit.INDUCTION: [task]})
    provider = RecordingProvider(default="private-gold")
    target = tmp_path / "traces.jsonl"

    first = collect(adapter, {"speaker": provider}, ExactMatchEvaluator(), output_path=target)
    second = collect(adapter, {"speaker": provider}, ExactMatchEvaluator(), output_path=target)

    assert len(first) == len(second) == 1
    assert len(provider.requests) == 1
    request: CompletionRequest = provider.requests[0]
    serialized = request.model_dump_json()
    assert "private-gold" not in serialized
    assert "metadata-gold" not in serialized
    assert json.loads(target.read_text().splitlines()[0])["split"] == "induction"


def test_top_k_filters_incorrect_and_enforces_speaker_diversity() -> None:
    traces = [
        _trace("t", "a", 1, output="a-fast"),
        _trace("t", "a", 2, output="a-second"),
        _trace("t", "b", 3, output="b"),
        _trace("t", "c", 0, output="wrong", correct=False),
    ]
    ordinary = select_top_k_traces(traces, top_k=2)
    diverse = select_top_k_traces(traces, top_k=2, speaker_diversity=True)

    assert [item.output for item in ordinary] == ["a-fast", "a-second"]
    assert [item.speaker_id for item in diverse] == ["a", "b"]
    cards = create(traces, top_k=2, speaker_diversity=True)
    assert len(cards) == 2
    assert {card.creator_id for card in cards} == {"a", "b"}
    assert all(card.generation == 0 and card.source_trace_ids for card in cards)
    creator_filtered = create(traces, top_k=2, creator_ids=("b",))
    assert [card.creator_id for card in creator_filtered] == ["b"]
    with pytest.raises(ValueError, match="no eligible creator traces"):
        create(traces, creator_ids=("missing",))


def test_evolution_checkpoints_inheritance_borrowing_and_resume(tmp_path: Path) -> None:
    cards = [make_card("a", suffix="a"), make_card("b", suffix="b")]
    output = tmp_path / "generations"
    first = evolve(
        cards,
        validation_failures=[{"split": "evolution_validation", "task_id": "f"}],
        discussion_summaries=["borrow useful notation"],
        max_generations=2,
        output_dir=output,
    )
    resumed = evolve(cards, max_generations=3, output_dir=output, resume=True)

    assert {path.name for path in output.glob("generation-*.json")} == {
        "generation-000.json",
        "generation-001.json",
        "generation-002.json",
        "generation-003.json",
    }
    assert all(card.generation == 2 and len(card.parent_ids) == 2 for card in first)
    assert all(card.generation == 3 and card.parent_ids for card in resumed)
    assert all(card.metadata["evolution_mode"] == "inheritance_with_borrowing" for card in resumed)

    restarted = evolve(
        cards,
        max_generations=2,
        patience=1,
        output_dir=output,
        score_generation=lambda _cards: 1.0,
        resume=False,
    )
    assert restarted[0].generation == 1
    assert {path.name for path in output.glob("generation-*.json")} == {
        "generation-000.json",
        "generation-001.json",
    }

    vertical_only = evolve(
        cards,
        max_generations=1,
        enable_horizontal_borrowing=False,
        output_dir=tmp_path / "vertical-only",
    )
    assert all(len(card.parent_ids) == 1 for card in vertical_only)
    assert all(card.metadata["evolution_mode"] == "vertical_inheritance" for card in vertical_only)


def test_evolution_stops_only_on_validation_saturation(tmp_path: Path) -> None:
    card = make_card("a")
    calls = 0

    def score(_cards: object) -> float:
        nonlocal calls
        calls += 1
        return 1.0

    result = evolve(
        [card],
        max_generations=10,
        patience=2,
        output_dir=tmp_path / "saturation",
        score_generation=score,
    )
    assert result[0].generation == 2
    assert calls == 3


def test_profile_is_validation_only_and_computes_item_metrics(tmp_path: Path) -> None:
    task = make_task("v", split=DataSplit.ROUTER_VALIDATION, gold="A")
    card = make_card("speaker")
    provider = RecordingProvider(default="A", completion_tokens=4, prompt_tokens=2, cost=0.2, latency_ms=5)
    profiles = profile(
        [task],
        [card],
        {"listener": provider},
        ExactMatchEvaluator(),
        split=DataSplit.ROUTER_VALIDATION,
        output_path=tmp_path / "profiles.jsonl",
    )
    result = profiles[0]
    assert result.n_items == 1
    assert result.accuracy == 1.0
    assert result.mean_completion_tokens == 4
    assert result.mean_cost == 0.2
    assert result.confidence_interval[0] < result.confidence_interval[1]
    assert provider.requests[0].metadata["specification_digest"] == card.specification_digest

    with pytest.raises(ValueError, match="restricted"):
        profile(
            [make_task("bad", split=DataSplit.TEST)],
            [card],
            provider,
            ExactMatchEvaluator(),
            split=DataSplit.TEST,
        )


def test_select_uses_validation_pareto_support_and_diversity(tmp_path: Path) -> None:
    fast = make_card("a", suffix="fast")
    slow = make_card("a", suffix="slow")
    other = make_card("b", suffix="other")
    profiles = [
        make_profile(fast, "l", correct=(True, True), tokens=(2, 2), utility=0.9),
        make_profile(slow, "l", correct=(True, True), tokens=(10, 10), utility=0.8),
        make_profile(other, "l", correct=(True, False), tokens=(1, 1), utility=0.7),
    ]
    selected = select(
        [fast, slow, other],
        profiles,
        min_support=2,
        max_cards=2,
        minimum_speakers=2,
        diversity_key="creator_id",
        output_path=tmp_path / "bank.json",
    )
    assert [card.dialect_id for card in selected] == [fast.dialect_id, other.dialect_id]
    assert slow.dialect_id not in {card.dialect_id for card in selected}
    assert all(card.empirical_profile["profiled"] == 1.0 for card in selected)
    assert all(card.profile_ids for card in selected)
    payload = json.loads((tmp_path / "bank.json").read_text())
    assert payload["selection_basis"] == "validation_only_pareto"
    assert set(payload["candidate_pool"]) == {fast.dialect_id, slow.dialect_id, other.dialect_id}

    with pytest.raises(ValueError, match="validation profiles only"):
        select([fast], [make_profile(fast, "l", split=DataSplit.TEST)])
    with pytest.raises(ValueError, match="minimum_speakers"):
        select([fast], [make_profile(fast, "l")], max_cards=1, minimum_speakers=2)
