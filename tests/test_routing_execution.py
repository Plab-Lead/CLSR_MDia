from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mdia.config import RoutingConfig
from mdia.evaluation.exact import ExactMatchEvaluator
from mdia.pipeline.execution import run
from mdia.routing.aggregation import aggregate_outputs
from mdia.routing.controller import MetadataControllerRouter
from mdia.routing.dialect import UtilityDialectRouter, utility_score
from mdia.schemas import (
    AggregationMethod,
    DataSplit,
    DialectCard,
    DialectRoutePlan,
    RouteBudget,
    RouteMode,
    TaskView,
)
from tests.support import OverspendingProvider, RecordingProvider, make_card, make_profile, make_task


class StaticRouter:
    def __init__(self, plan: DialectRoutePlan) -> None:
        self.plan = plan
        self.views: list[TaskView] = []

    def route(self, task_view: TaskView, _profiles: Any, _bank: Any, _budget: Any) -> DialectRoutePlan:
        self.views.append(task_view)
        return self.plan


def _plan(
    task_id: str,
    cards: list[DialectCard],
    mode: RouteMode,
    *,
    aggregation: AggregationMethod | None = None,
    weights: tuple[float, ...] = (),
    utility_scores: dict[str, float] | None = None,
    budget: int = 20,
    max_steps: int | None = None,
    metadata: dict[str, Any] | None = None,
    stop_reason: str | None = None,
) -> DialectRoutePlan:
    return DialectRoutePlan(
        task_id=task_id,
        router_id="static",
        listener_id="listener",
        mode=mode,
        dialect_ids=tuple(card.dialect_id for card in cards),
        specification_digests=tuple(card.specification_digest for card in cards),
        aggregation=aggregation,
        weights=weights,
        utility_scores=utility_scores or {},
        estimated_tokens=len(cards),
        token_budget=budget,
        max_steps=max_steps or max(1, len(cards)),
        metadata=metadata or {},
        stop_reason=stop_reason,
    )


def test_aggregation_algorithms_are_distinct() -> None:
    assert aggregate_outputs(AggregationMethod.MAJORITY, ["A", " a ", "B"]) == "A"
    assert aggregate_outputs(AggregationMethod.WEIGHTED, ["A", "B"], weights=[0.1, 0.9]) == "B"
    assert aggregate_outputs(AggregationMethod.SCORE, ["A", "B"], scores=[0.8, 0.2]) == "A"
    assert aggregate_outputs(AggregationMethod.JUDGE, ["A", "B"], judge=lambda values: 1) == "B"
    with pytest.raises(ValueError, match="requires weights"):
        aggregate_outputs(AggregationMethod.WEIGHTED, ["A", "B"])
    with pytest.raises(ValueError, match="explicit judge"):
        aggregate_outputs(AggregationMethod.JUDGE, ["A"])


def test_utility_router_uses_validation_profiles_and_concrete_bank() -> None:
    best = make_card("best", suffix="best")
    second = make_card("second", suffix="second")
    profiles = [
        make_profile(best, "listener", tokens=(4, 4), utility=0.9),
        make_profile(second, "listener", tokens=(3, 3), utility=0.8),
    ]
    task = make_task("route", metadata={"benchmark": "toy"}).to_view()
    budget = RouteBudget(token_budget=20, max_steps=2)

    single = UtilityDialectRouter(RoutingConfig(mode=RouteMode.SINGLE), listener_id="listener").route(
        task, profiles, [best, second], budget
    )
    assert single.dialect_ids == (best.dialect_id,)
    assert single.specification_digests == (best.specification_digest,)

    aggregate = UtilityDialectRouter(
        RoutingConfig(
            mode=RouteMode.AGGREGATE,
            aggregation=AggregationMethod.WEIGHTED,
            max_dialects=2,
            max_steps=2,
        ),
        listener_id="listener",
    ).route(task, profiles, [best, second], budget)
    assert aggregate.dialect_ids == (best.dialect_id, second.dialect_id)
    assert sum(aggregate.weights) == pytest.approx(1.0)

    compose = UtilityDialectRouter(
        RoutingConfig(mode=RouteMode.COMPOSE, max_dialects=2, max_steps=2), listener_id="listener"
    ).route(task, profiles, [best, second], budget)
    assert compose.mode is RouteMode.COMPOSE
    assert len(compose.dialect_ids) == 2
    assert utility_score(profiles[0]) == pytest.approx(0.996)


def test_utility_router_enforces_budget_and_validation_only_profiles() -> None:
    card = make_card("speaker")
    task = make_task("budget").to_view()
    router = UtilityDialectRouter(RoutingConfig(mode=RouteMode.SINGLE), listener_id="listener")
    too_costly = make_profile(card, "listener", tokens=(50, 50), utility=1.0)
    fallback = router.route(task, [too_costly], [card], RouteBudget(token_budget=10, max_steps=1))
    assert fallback.mode is RouteMode.RAW_FALLBACK
    assert not fallback.dialect_ids

    test_profile = make_profile(card, "listener", split=DataSplit.TEST)
    with pytest.raises(ValueError, match="never induction or test"):
        router.route(task, [test_profile], [card], RouteBudget(token_budget=100, max_steps=1))


def test_controller_router_is_separate_and_rejects_gold_metadata() -> None:
    router = MetadataControllerRouter()
    plan = router.route(
        {"benchmark": "multihop_rag", "question_type": "null_query"},
        {"openness": 0.5},
        RouteBudget(token_budget=20),
    )
    assert plan.controller_family == "yesno_guard"
    assert "support" in plan.answer_contract
    assert plan.metadata["routes_dialects"] is False
    with pytest.raises(ValueError, match="reserved gold"):
        router.route({"benchmark": "musr", "gold_answer": "A"}, {}, RouteBudget(token_budget=20))


@pytest.mark.parametrize(
    ("aggregation", "answers", "weights", "scores", "expected"),
    [
        (AggregationMethod.MAJORITY, ["A", "A", "B"], (), {}, "A"),
        (AggregationMethod.WEIGHTED, ["A", "B"], (0.2, 0.8), {}, "B"),
        (AggregationMethod.SCORE, ["A", "B"], (), {0: 0.1, 1: 0.9}, "B"),
    ],
)
def test_run_executes_nonjudge_aggregation_and_accounts_tokens(
    tmp_path: Path,
    aggregation: AggregationMethod,
    answers: list[str],
    weights: tuple[float, ...],
    scores: dict[int, float],
    expected: str,
) -> None:
    task = make_task(f"aggregate-{aggregation.value}", gold=expected)
    cards = [make_card(f"s{index}", suffix=str(index)) for index in range(len(answers))]
    provider = RecordingProvider(
        answers={card.dialect_id: answer for card, answer in zip(cards, answers, strict=True)}
    )
    utility_scores = {cards[index].dialect_id: value for index, value in scores.items()}
    plan = _plan(
        task.task_id,
        cards,
        RouteMode.AGGREGATE,
        aggregation=aggregation,
        weights=weights,
        utility_scores=utility_scores,
        budget=20,
        max_steps=len(cards),
    )
    artifacts = run(
        [task],
        cards,
        StaticRouter(plan),
        {"listener": provider},
        ExactMatchEvaluator(),
        budget=RouteBudget(token_budget=20, max_steps=len(cards)),
        output_dir=tmp_path / aggregation.value,
    )
    prediction = artifacts.predictions[0]
    assert prediction["output"] == expected
    assert artifacts.evaluations[0].correct is True
    assert artifacts.token_accounting["completion_tokens"] == len(cards)
    assert artifacts.token_accounting["prompt_tokens"] == 2 * len(cards)
    assert artifacts.token_accounting["cost"] == pytest.approx(0.01 * len(cards))


def test_run_executes_single_compose_judge_fallback_and_abstain(tmp_path: Path) -> None:
    task = make_task("modes", gold="A", metadata={"benchmark": "toy", "gold_answer": "hidden"})
    first = make_card("first", suffix="first")
    second = make_card("second", suffix="second")
    provider = RecordingProvider(answers={first.dialect_id: "draft", second.dialect_id: "A"}, default="A")

    single_plan = _plan(task.task_id, [second], RouteMode.SINGLE, budget=10, max_steps=1)
    single_router = StaticRouter(single_plan)
    single = run(
        [task],
        [first, second],
        single_router,
        {"listener": provider},
        ExactMatchEvaluator(),
        controller_router=MetadataControllerRouter(default_controller="verify"),
        budget=RouteBudget(token_budget=10, max_steps=1),
        output_dir=tmp_path / "single",
    )
    assert single.predictions[0]["output"] == "A"
    assert single.predictions[0]["controller_family"] == "verify"
    assert "Controller answer contract" in provider.requests[-1].messages[0].content
    assert "hidden" not in single_router.views[0].model_dump_json()

    compose_plan = _plan(task.task_id, [first, second], RouteMode.COMPOSE, budget=10, max_steps=2)
    composed = run(
        [task],
        [first, second],
        StaticRouter(compose_plan),
        {"listener": provider},
        ExactMatchEvaluator(),
        budget=RouteBudget(token_budget=10, max_steps=2),
        output_dir=tmp_path / "compose",
    )
    assert composed.predictions[0]["output"] == "A"
    assert len(composed.predictions[0]["steps"]) == 2

    judge_plan = _plan(
        task.task_id,
        [first, second],
        RouteMode.AGGREGATE,
        aggregation=AggregationMethod.JUDGE,
        budget=10,
        max_steps=3,
        metadata={"judge_reserved_tokens": 2},
    )
    judged = run(
        [task],
        [first, second],
        StaticRouter(judge_plan),
        {"listener": provider},
        ExactMatchEvaluator(),
        judge_provider=RecordingProvider(default="A"),
        budget=RouteBudget(token_budget=10, max_steps=3),
        output_dir=tmp_path / "judge",
    )
    assert judged.predictions[0]["output"] == "A"
    assert judged.predictions[0]["steps"][-1]["role"] == "judge"

    fallback_plan = _plan(
        task.task_id, [], RouteMode.RAW_FALLBACK, budget=10, max_steps=1, stop_reason="mismatch"
    )
    fallback = run(
        [task],
        [first],
        StaticRouter(fallback_plan),
        {"listener": provider},
        ExactMatchEvaluator(),
        budget=RouteBudget(token_budget=10),
        output_dir=tmp_path / "fallback",
    )
    assert fallback.predictions[0]["output"] == "A"

    abstain_plan = _plan(task.task_id, [], RouteMode.ABSTAIN, budget=10, max_steps=1, stop_reason="unsafe")
    abstained = run(
        [task],
        [first],
        StaticRouter(abstain_plan),
        {"listener": provider},
        ExactMatchEvaluator(),
        budget=RouteBudget(token_budget=10),
        output_dir=tmp_path / "abstain",
    )
    assert abstained.predictions[0]["completion_tokens"] == 0
    assert abstained.evaluations[0].correct is False


def test_run_rejects_unknown_card_and_provider_budget_overspend(tmp_path: Path) -> None:
    task = make_task("integrity")
    card = make_card("known")
    unknown = make_card("unknown")
    bad_plan = _plan(task.task_id, [unknown], RouteMode.SINGLE, budget=5, max_steps=1)
    with pytest.raises(ValueError, match="outside the frozen bank"):
        run(
            [task],
            [card],
            StaticRouter(bad_plan),
            RecordingProvider(),
            ExactMatchEvaluator(),
            budget=RouteBudget(token_budget=5),
            output_dir=tmp_path / "unknown",
        )

    good_plan = _plan(task.task_id, [card], RouteMode.SINGLE, budget=5, max_steps=1)
    with pytest.raises(RuntimeError, match="more completion tokens"):
        run(
            [task],
            [card],
            StaticRouter(good_plan),
            OverspendingProvider(),
            ExactMatchEvaluator(),
            budget=RouteBudget(token_budget=5),
            output_dir=tmp_path / "overspend",
        )
