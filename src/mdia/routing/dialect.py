"""Validation-profiled routing over concrete, frozen dialect cards."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..config import RoutingConfig
from ..schemas import (
    AggregationMethod,
    DataSplit,
    DialectCard,
    DialectProfile,
    DialectRoutePlan,
    RouteBudget,
    RouteMode,
    TaskView,
)


def utility_score(
    profile: DialectProfile,
    *,
    accuracy_weight: float = 1.0,
    token_penalty: float = 0.001,
    parse_failure_penalty: float = 0.25,
    latency_penalty: float = 0.0,
    cost_penalty: float = 0.0,
) -> float:
    """Compute a validation-only accuracy/resource utility."""

    return (
        accuracy_weight * profile.accuracy
        - token_penalty * profile.mean_completion_tokens
        - parse_failure_penalty * profile.parse_failure_rate
        - latency_penalty * profile.mean_latency_ms
        - cost_penalty * profile.mean_cost
    )


@dataclass(frozen=True)
class _Candidate:
    card: DialectCard
    profile: DialectProfile
    utility: float
    estimated_tokens: int


def _observable_task_tags(task: TaskView) -> frozenset[str]:
    tags: set[str] = set()
    for key in ("task_tag", "benchmark", "domain", "subdomain", "question_type"):
        value = task.metadata.get(key)
        if isinstance(value, (str, int, float, bool)):
            tags.add(str(value))
    many = task.metadata.get("task_tags")
    if isinstance(many, list):
        tags.update(str(value) for value in many if isinstance(value, (str, int, float, bool)))
    return frozenset(tags)


class UtilityDialectRouter:
    """Choose concrete dialect IDs from frozen validation profiles."""

    router_id = "dialect-utility-v1"

    def __init__(self, config: RoutingConfig | None = None, *, listener_id: str | None = None) -> None:
        self.config = config or RoutingConfig()
        self.listener_id = listener_id

    def _failure_plan(
        self,
        task: TaskView,
        listener_id: str,
        budget: RouteBudget,
        reason: str,
    ) -> DialectRoutePlan:
        mode = RouteMode.RAW_FALLBACK if self.config.raw_fallback_when_unroutable else RouteMode.ABSTAIN
        return DialectRoutePlan(
            task_id=task.task_id,
            router_id=self.router_id,
            listener_id=listener_id,
            mode=mode,
            estimated_tokens=0,
            token_budget=budget.token_budget,
            max_steps=budget.max_steps,
            stop_reason=reason,
            metadata={"consumed_tokens": budget.consumed_tokens},
        )

    def _profile_for_card(
        self,
        card: DialectCard,
        profiles: Sequence[DialectProfile],
        tags: frozenset[str],
    ) -> DialectProfile | None:
        eligible = [
            profile
            for profile in profiles
            if profile.dialect_id == card.dialect_id
            and profile.split in (DataSplit.EVOLUTION_VALIDATION, DataSplit.ROUTER_VALIDATION)
        ]
        tagged = [
            profile for profile in eligible if profile.task_tag is not None and profile.task_tag in tags
        ]
        pool = tagged or [profile for profile in eligible if profile.task_tag is None]
        if not pool:
            return None
        return max(pool, key=lambda profile: (profile.n_items, profile.profile_id))

    def _candidates(
        self,
        task: TaskView,
        profiles: Sequence[DialectProfile],
        bank: Sequence[DialectCard],
        listener_id: str,
    ) -> list[_Candidate]:
        tags = _observable_task_tags(task)
        candidates: list[_Candidate] = []
        seen_cards: set[str] = set()
        for card in bank:
            if card.dialect_id in seen_cards:
                raise ValueError(f"duplicate dialect card in bank: {card.dialect_id}")
            seen_cards.add(card.dialect_id)
            if card.task_tags and not tags.intersection(card.task_tags):
                continue
            profile = self._profile_for_card(
                card,
                [profile for profile in profiles if profile.listener_id == listener_id],
                tags,
            )
            if profile is None or profile.n_items == 0:
                continue
            conditioned_accuracy: float | None = None
            conditioned_tokens: float | None = None
            conditioned_parse: float | None = None
            conditioned = profile.metadata.get("task_conditioned")
            if isinstance(conditioned, dict):
                for tag in sorted(tags):
                    metrics = conditioned.get(tag)
                    support = metrics.get("n_items", 0) if isinstance(metrics, dict) else 0
                    if isinstance(metrics, dict) and isinstance(support, (int, float)) and support > 0:
                        accuracy_value = metrics.get("accuracy", profile.accuracy)
                        token_value = metrics.get("mean_completion_tokens", profile.mean_completion_tokens)
                        parse_value = metrics.get("parse_failure_rate", profile.parse_failure_rate)
                        if not isinstance(accuracy_value, (int, float)):
                            continue
                        if not isinstance(token_value, (int, float)):
                            continue
                        if not isinstance(parse_value, (int, float)):
                            continue
                        conditioned_accuracy = float(accuracy_value)
                        conditioned_tokens = float(token_value)
                        conditioned_parse = float(parse_value)
                        break
            score = profile.utility if conditioned_accuracy is None else None
            if score is None:
                if conditioned_accuracy is None:
                    accuracy = profile.accuracy
                    mean_tokens = profile.mean_completion_tokens
                    parse_rate = profile.parse_failure_rate
                else:
                    accuracy = conditioned_accuracy
                    mean_tokens = (
                        conditioned_tokens
                        if conditioned_tokens is not None
                        else profile.mean_completion_tokens
                    )
                    parse_rate = (
                        conditioned_parse if conditioned_parse is not None else profile.parse_failure_rate
                    )
                score = (
                    self.config.accuracy_weight * accuracy
                    - self.config.token_penalty * mean_tokens
                    - self.config.parse_failure_penalty * parse_rate
                    - self.config.latency_penalty * profile.mean_latency_ms
                    - self.config.cost_penalty * profile.mean_cost
                )
            minimum = self.config.minimum_utility
            if minimum is not None and score < minimum:
                continue
            token_estimate = (
                conditioned_tokens if conditioned_tokens is not None else profile.mean_completion_tokens
            )
            estimated_tokens = max(1, int(round(token_estimate)))
            candidates.append(_Candidate(card, profile, score, estimated_tokens))
        return sorted(
            candidates, key=lambda item: (-item.utility, item.estimated_tokens, item.card.dialect_id)
        )

    def route(
        self,
        task_view: TaskView,
        listener_profile: Sequence[DialectProfile],
        bank: Sequence[DialectCard],
        budget: RouteBudget,
    ) -> DialectRoutePlan:
        profile_list = tuple(listener_profile)
        listener_ids = {profile.listener_id for profile in profile_list}
        if self.listener_id is not None:
            listener_id = self.listener_id
            if listener_ids and listener_id not in listener_ids:
                raise ValueError(f"no supplied profile belongs to configured listener {listener_id!r}")
        elif len(listener_ids) == 1:
            listener_id = next(iter(listener_ids))
        elif not listener_ids:
            listener_id = "unknown-listener"
        else:
            raise ValueError("listener_profile must contain exactly one listener")

        if any(profile.split in (DataSplit.INDUCTION, DataSplit.TEST) for profile in profile_list):
            raise ValueError("routing may use validation profiles only, never induction or test outcomes")
        if self.config.mode in (RouteMode.ABSTAIN, RouteMode.RAW_FALLBACK):
            return DialectRoutePlan(
                task_id=task_view.task_id,
                router_id=self.router_id,
                listener_id=listener_id,
                mode=self.config.mode,
                token_budget=budget.token_budget,
                max_steps=budget.max_steps,
                stop_reason="configured routing policy",
                metadata={"consumed_tokens": budget.consumed_tokens},
            )
        if budget.remaining_tokens <= 0:
            return self._failure_plan(task_view, listener_id, budget, "token budget exhausted before routing")

        candidates = self._candidates(task_view, profile_list, bank, listener_id)
        if self.config.policy == "fixed_single":
            candidates = [
                candidate
                for candidate in candidates
                if candidate.card.dialect_id == self.config.fixed_dialect_id
            ]
        if not candidates:
            return self._failure_plan(
                task_view, listener_id, budget, "no validation-profiled dialect is eligible"
            )

        required_count = 1 if self.config.mode is RouteMode.SINGLE else 2
        judge_steps = (
            1
            if (
                self.config.mode is RouteMode.AGGREGATE and self.config.aggregation is AggregationMethod.JUDGE
            )
            else 0
        )
        selection_limit = min(self.config.max_dialects, budget.max_steps - judge_steps)
        if selection_limit < required_count:
            return self._failure_plan(
                task_view, listener_id, budget, "max_steps is too small for configured route mode"
            )

        selected: list[_Candidate] = []
        used_tokens = 0
        reserved_tokens = judge_steps
        for candidate in candidates:
            if len(selected) >= selection_limit:
                break
            if used_tokens + candidate.estimated_tokens + reserved_tokens > budget.remaining_tokens:
                continue
            selected.append(candidate)
            used_tokens += candidate.estimated_tokens
            if self.config.mode is RouteMode.SINGLE:
                break
        if len(selected) < required_count:
            return self._failure_plan(
                task_view,
                listener_id,
                budget,
                f"budget cannot fund the {required_count} dialects required by {self.config.mode.value} mode",
            )

        weights: tuple[float, ...] = ()
        if self.config.mode is RouteMode.AGGREGATE and self.config.aggregation is AggregationMethod.WEIGHTED:
            nonnegative = [max(0.0, candidate.utility) for candidate in selected]
            total = sum(nonnegative)
            weights = (
                tuple(value / total for value in nonnegative)
                if total
                else tuple(1.0 / len(selected) for _ in selected)
            )
        return DialectRoutePlan(
            task_id=task_view.task_id,
            router_id=self.router_id,
            listener_id=listener_id,
            mode=self.config.mode,
            dialect_ids=tuple(candidate.card.dialect_id for candidate in selected),
            specification_digests=tuple(candidate.card.specification_digest for candidate in selected),
            aggregation=self.config.aggregation,
            weights=weights,
            utility_scores={candidate.card.dialect_id: candidate.utility for candidate in selected},
            estimated_tokens=used_tokens + reserved_tokens,
            token_budget=budget.token_budget,
            max_steps=budget.max_steps,
            stop_reason="selection limit reached"
            if len(selected) == selection_limit
            else "candidate pool exhausted",
            metadata={
                "consumed_tokens": budget.consumed_tokens,
                "available_candidates": len(candidates),
                "task_conditioned": bool(_observable_task_tags(task_view)),
                "judge_reserved_tokens": reserved_tokens,
            },
        )


class FixedSingleDialectRouter(UtilityDialectRouter):
    """CLSR baseline that always uses one validation-profiled concrete card."""

    router_id = "dialect-fixed-single-v1"

    def __init__(self, dialect_id: str, *, listener_id: str | None = None, token_budget: int = 1024) -> None:
        super().__init__(
            RoutingConfig(
                policy="fixed_single",
                mode=RouteMode.SINGLE,
                fixed_dialect_id=dialect_id,
                token_budget=token_budget,
            ),
            listener_id=listener_id,
        )


__all__ = ["FixedSingleDialectRouter", "UtilityDialectRouter", "utility_score"]
