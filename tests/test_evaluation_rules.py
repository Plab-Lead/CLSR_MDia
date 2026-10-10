from __future__ import annotations

import pytest

from mdia.evaluation.exact import DiagnosticEvaluator, ExactMatchEvaluator
from mdia.providers.replay import ReplayMissError, ReplayProvider
from mdia.rules.registry import FAMILIES, RULE_REGISTRY, get_rule
from mdia.rules.statistics import benjamini_hochberg, paired_bootstrap, permutation_test, simple_regression
from mdia.rules.validation import validate_rules
from mdia.schemas import ChatMessage, CompletionRequest, RuleExecutionStatus, RuleSpec, RuleSupport
from tests.support import make_task


def test_exact_match_and_diagnostic_evaluators_label_scope() -> None:
    text_task = make_task("text", gold="  Answer A  ")
    text = ExactMatchEvaluator().evaluate(text_task, "answer   a")
    assert text.correct is True and text.score == 1.0
    assert text.diagnostic and not text.official

    json_task = make_task("json", gold={"value": 2})
    structured = ExactMatchEvaluator().evaluate(json_task, '{"value": 2}')
    assert structured.correct is True
    malformed = ExactMatchEvaluator(json_field="answer").evaluate(text_task, "not json")
    assert malformed.parse_failure and malformed.correct is False

    diagnostic = DiagnosticEvaluator(json_field="answer").evaluate(text_task, '{"answer": "A"}')
    assert diagnostic.parsed_output == "A"
    assert diagnostic.correct is None and diagnostic.score is None


def test_replay_provider_is_deterministic_and_preserves_usage() -> None:
    request = CompletionRequest(
        model="fixture",
        messages=(ChatMessage(role="user", content="question"),),
        max_tokens=10,
        seed=7,
    )
    provider = ReplayProvider(
        [
            {
                "key": request.replay_key,
                "text": "A",
                "prompt_tokens": 4,
                "completion_tokens": 1,
                "latency_ms": 2,
                "cost": 0.01,
            }
        ]
    )
    first = provider.complete(request)
    second = provider.complete(request)
    assert first == second
    assert first.prompt_tokens == 4 and first.completion_tokens == 1 and first.cost == 0.01
    with pytest.raises(ReplayMissError):
        provider.complete(request.model_copy(update={"request_id": "request-missing"}))


def test_registry_contains_exactly_100_rules_in_seven_families() -> None:
    assert tuple(FAMILIES) == tuple("ABCDEFG")
    assert len(RULE_REGISTRY) == 100
    assert [rule.rule_id for rule in RULE_REGISTRY] == [f"R{index:03d}" for index in range(1, 101)]
    assert {rule.family for rule in RULE_REGISTRY} == set("ABCDEFG")
    assert get_rule("R065").title == "Route simplicity can beat over-composition"
    with pytest.raises(KeyError):
        get_rule("R101")


def test_statistics_are_deterministic_and_validate_inputs() -> None:
    bootstrap = paired_bootstrap([2, 3, 4, 5], [1, 1, 1, 1], iterations=200, seed=5)
    assert bootstrap.n_units == 4
    assert bootstrap.estimate == pytest.approx(2.5)
    assert bootstrap == paired_bootstrap([2, 3, 4, 5], [1, 1, 1, 1], iterations=200, seed=5)

    permutation = permutation_test(["a", "a", "b", "b"], [0, 0, 2, 2], iterations=200, seed=5)
    assert permutation.n_units == 4
    assert 0 <= permutation.p_value <= 1  # type: ignore[operator]

    regression = simple_regression([0, 1, 2, 3], [1, 3, 5, 7])
    assert regression.estimate == pytest.approx(2.0)
    assert regression.details["r_squared"] == pytest.approx(1.0)

    with pytest.raises(ValueError, match="equal length"):
        paired_bootstrap([1, 2], [1], iterations=100)
    with pytest.raises(ValueError, match="invalid p-value"):
        benjamini_hochberg({"bad": 2.0})


def test_benjamini_hochberg_is_monotone() -> None:
    adjusted = benjamini_hochberg({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adjusted == pytest.approx({"a": 0.03, "b": 0.04, "c": 0.04})


def _paired_spec(rule_id: str, family: str) -> RuleSpec:
    return RuleSpec(
        rule_id=rule_id,
        family=family,
        title=f"Rule {rule_id}",
        hypothesis="Treatment improves over control.",
        manuscript_support=RuleSupport.WEAK,
        eligible_records="paired validation rows",
        unit_of_analysis="item",
        features=("treatment", "control"),
        statistic="paired mean difference",
        direction="positive",
        threshold=0.0,
        test_type="paired_bootstrap",
        evidence_stream="router validation",
        routing_implication="soft score only",
    )


def test_rule_validation_not_evaluated_and_bh_is_within_family() -> None:
    specs = [_paired_spec("X001", "A"), _paired_spec("X002", "A"), _paired_spec("X003", "B")]
    strong = [{"split": "router_validation", "treatment": 2.0, "control": 0.0} for _ in range(8)]
    null = [
        {"split": "router_validation", "treatment": value, "control": 0.0}
        for value in (1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0)
    ]
    results = validate_rules(
        {"X001": strong, "X002": null, "X003": strong},
        specs=specs,
        iterations=100,
        seed=9,
    )
    by_id = {result.rule_id: result for result in results}
    assert all(result.status is RuleExecutionStatus.EVALUATED for result in results)
    assert by_id["X001"].adjusted_p_value >= by_id["X001"].p_value  # type: ignore[operator]
    assert by_id["X003"].adjusted_p_value == pytest.approx(by_id["X003"].p_value)  # type: ignore[arg-type]
    assert by_id["X001"].passed is True
    assert by_id["X002"].passed is False
    assert by_id["X003"].passed is True

    excluded = validate_rules(
        {"X001": [{"split": "test", "treatment": 2.0, "control": 0.0}]},
        specs=[specs[0]],
        iterations=100,
    )[0]
    assert excluded.status is RuleExecutionStatus.NOT_EVALUATED
    assert excluded.reason and "excluded" in excluded.reason
    assert excluded.manuscript_support is RuleSupport.WEAK

    unscoped = validate_rules(
        {"X001": [{"treatment": 2.0, "control": 0.0}]},
        specs=[specs[0]],
        iterations=100,
    )[0]
    assert unscoped.status is RuleExecutionStatus.NOT_EVALUATED
    assert unscoped.reason and "must declare" in unscoped.reason


def test_empty_rule_evidence_never_reuses_manuscript_support() -> None:
    results = validate_rules({}, specs=[get_rule("R002")], iterations=100)
    assert len(results) == 1
    assert results[0].status is RuleExecutionStatus.NOT_EVALUATED
    assert results[0].manuscript_support is RuleSupport.FULL
    assert results[0].passed is None


def test_rule_validation_marks_fixed_archive_evolution_as_proxy() -> None:
    spec = RuleSpec(
        rule_id="XF01",
        family="F",
        title="Proxy",
        hypothesis="Archive signal exists.",
        manuscript_support=RuleSupport.BOUNDARY,
        eligible_records="validation rows",
        unit_of_analysis="archive",
        features=("estimate",),
        statistic="mean estimate",
        direction="descriptive",
        test_type="descriptive",
        evidence_stream="mechanism proxy",
        routing_implication="do not hard route",
        proxy=True,
    )
    fixed = validate_rules(
        {"XF01": [{"split": "evolution_validation", "estimate": 0.2}]}, specs=[spec], iterations=100
    )[0]
    live = validate_rules(
        {"XF01": [{"split": "evolution_validation", "estimate": 0.2, "live_evolution": True}]},
        specs=[spec],
        iterations=100,
    )[0]
    assert fixed.proxy is True
    assert live.proxy is False
