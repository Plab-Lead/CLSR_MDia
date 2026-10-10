"""Leakage-safe dialect routing and execution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from mdia.pipeline.io import read_jsonl, write_json_atomic, write_jsonl_atomic
from mdia.pipeline.lifecycle import (
    ChatProvider,
    Evaluator,
    ProviderMap,
    _dialect_system_prompt,
    _provider_map,
    _provider_model,
)
from mdia.routing.aggregation import majority_vote, score_vote, weighted_vote
from mdia.schemas import (
    AggregationMethod,
    ChatMessage,
    Completion,
    CompletionRequest,
    ControllerRoutePlan,
    DataSplit,
    DialectCard,
    DialectProfile,
    DialectRoutePlan,
    EvaluationRecord,
    JsonValue,
    RouteBudget,
    RouteMode,
    TaskRecord,
    TaskView,
)


class DialectRouter(Protocol):
    def route(
        self,
        task_view: Any,
        listener_profile: Sequence[DialectProfile],
        bank: Sequence[DialectCard],
        budget: RouteBudget,
    ) -> DialectRoutePlan: ...


class ControllerRouter(Protocol):
    def route(
        self,
        task_metadata: Mapping[str, JsonValue],
        listener_profile: Mapping[str, JsonValue],
        budget: RouteBudget,
    ) -> ControllerRoutePlan: ...


@dataclass(frozen=True)
class RunArtifacts:
    route_plans: tuple[DialectRoutePlan, ...]
    controller_route_plans: tuple[ControllerRoutePlan, ...]
    predictions: tuple[dict[str, Any], ...]
    evaluations: tuple[EvaluationRecord, ...]
    token_accounting: dict[str, Any]


def _public_task_view(task: TaskRecord) -> TaskView:
    """Return the schema-owned recursive gold-free projection."""

    return task.to_view()


def majority_aggregate(outputs: Sequence[str]) -> str:
    """Return the most frequent complete output with stable route-order ties."""

    return majority_vote(outputs)


def weighted_aggregate(outputs: Sequence[str], weights: Sequence[float]) -> str:
    return weighted_vote(outputs, weights)


def score_aggregate(outputs: Sequence[str], dialect_ids: Sequence[str], scores: Mapping[str, float]) -> str:
    if len(outputs) != len(dialect_ids):
        raise ValueError("score aggregation requires one dialect ID per output")
    return score_vote(
        outputs,
        [float(scores.get(dialect_id, float("-inf"))) for dialect_id in dialect_ids],
    )


def _provider_for_listener(providers: ProviderMap | ChatProvider, listener_id: str) -> ChatProvider:
    normalized = _provider_map(providers)
    if listener_id in normalized:
        return normalized[listener_id]
    if len(normalized) == 1:
        return next(iter(normalized.values()))
    raise KeyError(f"no provider configured for routed listener {listener_id!r}")


def _complete(
    provider: ChatProvider,
    *,
    listener_id: str,
    task: TaskRecord,
    system: str,
    user: str,
    max_tokens: int,
    temperature: float,
    seed: int,
    metadata: Mapping[str, JsonValue],
) -> Completion:
    if max_tokens <= 0:
        raise ValueError("route token budget exhausted")
    view = _public_task_view(task)
    request_metadata = dict(metadata)
    request_metadata.update({"task_id": view.task_id, "public_digest": view.public_digest})
    request = CompletionRequest(
        model=_provider_model(provider, listener_id),
        messages=(ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)),
        max_tokens=max_tokens,
        temperature=temperature,
        seed=seed,
        metadata=request_metadata,
    )
    return provider.complete(request)


def _validate_plan(
    plan: DialectRoutePlan, task: TaskRecord, bank: Mapping[str, DialectCard], budget: RouteBudget
) -> None:
    if plan.task_id != task.task_id:
        raise ValueError("router returned a route for another task")
    if plan.token_budget != budget.token_budget or plan.max_steps != budget.max_steps:
        raise ValueError("router changed the supplied route budget")
    for dialect_id, digest in zip(plan.dialect_ids, plan.specification_digests, strict=True):
        if dialect_id not in bank:
            raise ValueError(f"route references a dialect outside the frozen bank: {dialect_id}")
        if bank[dialect_id].specification_digest != digest:
            raise ValueError(f"route specification digest mismatch for {dialect_id}")


def _execute_plan(
    task: TaskRecord,
    plan: DialectRoutePlan,
    bank: Mapping[str, DialectCard],
    providers: ProviderMap | ChatProvider,
    *,
    controller_plan: ControllerRoutePlan | None,
    judge_provider: ChatProvider | None,
    temperature: float,
    seed: int,
) -> dict[str, Any]:
    provider = _provider_for_listener(providers, plan.listener_id)
    completion_outputs: list[str] = []
    completion_records: list[dict[str, Any]] = []
    consumed_completion_tokens = 0
    consumed_prompt_tokens = 0
    total_cost = 0.0
    total_latency_ms = 0.0
    controller_suffix = ""
    if controller_plan is not None:
        controller_suffix = (
            f"\nController family: {controller_plan.controller_family}\n"
            f"Controller answer contract: {controller_plan.answer_contract}"
        )
    view = _public_task_view(task)

    def run_card(card: DialectCard, user: str, step: int, available: int) -> Completion:
        nonlocal consumed_completion_tokens, consumed_prompt_tokens, total_cost, total_latency_ms
        completion = _complete(
            provider,
            listener_id=plan.listener_id,
            task=task,
            system=_dialect_system_prompt(card) + controller_suffix,
            user=user,
            max_tokens=available,
            temperature=temperature,
            seed=seed + step,
            metadata={
                "stage": "run",
                "route_id": plan.route_id,
                "dialect_id": card.dialect_id,
                "specification_digest": card.specification_digest,
                "step": step,
            },
        )
        if completion.completion_tokens > available:
            raise RuntimeError("provider returned more completion tokens than requested")
        consumed_completion_tokens += completion.completion_tokens
        consumed_prompt_tokens += completion.prompt_tokens
        total_cost += completion.cost
        total_latency_ms += completion.latency_ms
        completion_outputs.append(completion.text)
        completion_records.append(
            {
                "dialect_id": card.dialect_id,
                "request_id": completion.request_id,
                "output": completion.text,
                "prompt_tokens": completion.prompt_tokens,
                "completion_tokens": completion.completion_tokens,
                "latency_ms": completion.latency_ms,
                "cost": completion.cost,
            }
        )
        return completion

    if plan.mode is RouteMode.ABSTAIN:
        final_output = ""
        stop_reason = plan.stop_reason or "router_abstained"
    elif plan.mode is RouteMode.RAW_FALLBACK:
        raw = _complete(
            provider,
            listener_id=plan.listener_id,
            task=task,
            system=(
                "Answer directly in plain language and finish with a clear final answer." + controller_suffix
            ),
            user=view.query,
            max_tokens=plan.token_budget,
            temperature=temperature,
            seed=seed,
            metadata={"stage": "run", "route_id": plan.route_id, "mode": "raw_fallback"},
        )
        if raw.completion_tokens > plan.token_budget:
            raise RuntimeError("provider returned more completion tokens than requested")
        final_output = raw.text
        consumed_completion_tokens = raw.completion_tokens
        consumed_prompt_tokens = raw.prompt_tokens
        total_cost = raw.cost
        total_latency_ms = raw.latency_ms
        completion_records.append(
            {
                "dialect_id": None,
                "request_id": raw.request_id,
                "output": raw.text,
                "prompt_tokens": raw.prompt_tokens,
                "completion_tokens": raw.completion_tokens,
                "latency_ms": raw.latency_ms,
                "cost": raw.cost,
            }
        )
        stop_reason = plan.stop_reason or "raw_fallback"
    elif plan.mode is RouteMode.SINGLE:
        card = bank[plan.dialect_ids[0]]
        final_output = run_card(card, view.query, 0, plan.token_budget).text
        stop_reason = "single_complete"
    elif plan.mode is RouteMode.COMPOSE:
        current = view.query
        stop_reason = "max_steps_reached"
        for step, dialect_id in enumerate(plan.dialect_ids[: plan.max_steps]):
            remaining = plan.token_budget - consumed_completion_tokens
            if remaining <= 0:
                stop_reason = "token_budget_exhausted"
                break
            completion = run_card(bank[dialect_id], current, step, remaining)
            current = (
                f"Original task:\n{view.query}\n\n"
                f"Previous dialect result:\n{completion.text}\n\n"
                "Refine or verify the result under your dialect and return the final answer."
            )
            stop_reason = "compose_complete"
        final_output = completion_outputs[-1] if completion_outputs else ""
    else:
        dialect_ids = plan.dialect_ids[: plan.max_steps]
        judge_reserve = 0
        if plan.aggregation is AggregationMethod.JUDGE:
            raw_reserve = plan.metadata.get("judge_reserved_tokens", 1)
            if isinstance(raw_reserve, bool) or not isinstance(raw_reserve, int) or raw_reserve <= 0:
                raise ValueError("judge_reserved_tokens must be a positive integer")
            if raw_reserve >= plan.token_budget:
                raise ValueError("judge token reserve must be smaller than the route budget")
            judge_reserve = raw_reserve
        stop_reason = "aggregate_complete"
        for step, dialect_id in enumerate(dialect_ids):
            remaining = plan.token_budget - consumed_completion_tokens
            calls_left = len(dialect_ids) - step
            allocatable = remaining - judge_reserve
            available = allocatable // calls_left if calls_left else allocatable
            if available <= 0:
                stop_reason = "token_budget_exhausted"
                break
            run_card(bank[dialect_id], view.query, step, available)
        executed_ids = dialect_ids[: len(completion_outputs)]
        if not completion_outputs:
            final_output = ""
        elif plan.aggregation is AggregationMethod.MAJORITY:
            final_output = majority_aggregate(completion_outputs)
        elif plan.aggregation is AggregationMethod.WEIGHTED:
            weights = plan.weights[: len(completion_outputs)] or tuple(1.0 for _ in completion_outputs)
            final_output = weighted_aggregate(completion_outputs, weights)
        elif plan.aggregation is AggregationMethod.SCORE:
            final_output = score_aggregate(completion_outputs, executed_ids, plan.utility_scores)
        elif plan.aggregation is AggregationMethod.JUDGE:
            if judge_provider is None:
                raise ValueError("judge aggregation requires judge_provider")
            remaining = plan.token_budget - consumed_completion_tokens
            if remaining <= 0 or len(completion_records) >= plan.max_steps:
                raise RuntimeError("no route budget remains for the configured judge")
            candidates = "\n\n".join(
                f"Candidate {index + 1} ({dialect_id}):\n{output}"
                for index, (dialect_id, output) in enumerate(
                    zip(executed_ids, completion_outputs, strict=True)
                )
            )
            judged = _complete(
                judge_provider,
                listener_id="judge",
                task=task,
                system=(
                    "Select or synthesize the most correct candidate. Return only the final answer contract."
                    + controller_suffix
                ),
                user=f"Task:\n{view.query}\n\n{candidates}",
                max_tokens=remaining,
                temperature=temperature,
                seed=seed + len(completion_records),
                metadata={"stage": "run", "route_id": plan.route_id, "aggregation": "judge"},
            )
            if judged.completion_tokens > remaining:
                raise RuntimeError("judge returned more completion tokens than requested")
            consumed_completion_tokens += judged.completion_tokens
            consumed_prompt_tokens += judged.prompt_tokens
            total_cost += judged.cost
            total_latency_ms += judged.latency_ms
            final_output = judged.text
            completion_records.append(
                {
                    "dialect_id": None,
                    "role": "judge",
                    "request_id": judged.request_id,
                    "output": judged.text,
                    "prompt_tokens": judged.prompt_tokens,
                    "completion_tokens": judged.completion_tokens,
                    "latency_ms": judged.latency_ms,
                    "cost": judged.cost,
                }
            )
        else:  # guarded by DialectRoutePlan validation
            raise ValueError(f"unsupported aggregation method: {plan.aggregation}")

    if consumed_completion_tokens > plan.token_budget:
        raise RuntimeError("route exceeded its completion-token budget")
    return {
        "task_id": task.task_id,
        "split": task.split.value,
        "route_id": plan.route_id,
        "listener_id": plan.listener_id,
        "mode": plan.mode.value,
        "dialect_ids": list(plan.dialect_ids),
        "specification_digests": list(plan.specification_digests),
        "output": final_output,
        "steps": completion_records,
        "prompt_tokens": consumed_prompt_tokens,
        "completion_tokens": consumed_completion_tokens,
        "cost": total_cost,
        "latency_ms": total_latency_ms,
        "stop_reason": stop_reason,
    }


def run(
    tasks: Sequence[TaskRecord],
    bank: Sequence[DialectCard],
    router: DialectRouter,
    providers: ProviderMap | ChatProvider,
    evaluator: Evaluator,
    *,
    profiles: Sequence[DialectProfile] = (),
    budget: RouteBudget,
    output_dir: str | Path,
    controller_router: ControllerRouter | None = None,
    controller_profile: Mapping[str, JsonValue] | None = None,
    judge_provider: ChatProvider | None = None,
    temperature: float = 0.0,
    seed: int = 0,
    resume: bool = True,
) -> RunArtifacts:
    """Route, execute, and score router-validation or held-out tasks."""

    for task in tasks:
        if task.split not in {DataSplit.ROUTER_VALIDATION, DataSplit.TEST}:
            raise ValueError("run accepts only router_validation or test tasks")
    if len({task.task_id for task in tasks}) != len(tasks):
        raise ValueError("run tasks contain duplicate task IDs")
    bank_by_id = {card.dialect_id: card for card in bank}
    if not bank_by_id:
        raise ValueError("run requires a non-empty frozen dialect bank")
    if len(bank_by_id) != len(bank):
        raise ValueError("frozen dialect bank contains duplicate IDs")
    for item in profiles:
        if item.split not in {DataSplit.EVOLUTION_VALIDATION, DataSplit.ROUTER_VALIDATION}:
            raise ValueError("routers may consume validation profiles only")

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    route_path = directory / "route_plans.jsonl"
    controller_path = directory / "controller_route_plans.jsonl"
    prediction_path = directory / "predictions.jsonl"
    evaluation_path = directory / "evaluations.jsonl"
    accounting_path = directory / "token_accounting.json"
    route_plans: list[DialectRoutePlan] = []
    controller_plans: list[ControllerRoutePlan] = []
    predictions: list[dict[str, Any]] = []
    evaluations: list[EvaluationRecord] = []
    if resume:
        if route_path.exists():
            route_plans = [DialectRoutePlan.model_validate(row) for row in read_jsonl(route_path)]
        if controller_path.exists():
            controller_plans = [
                ControllerRoutePlan.model_validate(row) for row in read_jsonl(controller_path)
            ]
        if prediction_path.exists():
            predictions = read_jsonl(prediction_path)
        if evaluation_path.exists():
            evaluations = [EvaluationRecord.model_validate(row) for row in read_jsonl(evaluation_path)]
    completed = {str(row["task_id"]) for row in predictions}
    evaluated = {item.task_id for item in evaluations}
    if completed != evaluated:
        raise ValueError("resume artifacts disagree: predictions and evaluations must cover the same tasks")

    for task in tasks:
        if task.task_id in completed:
            continue
        view = _public_task_view(task)
        plan = router.route(view, profiles, tuple(bank), budget)
        _validate_plan(plan, task, bank_by_id, budget)
        controller_plan: ControllerRoutePlan | None = None
        if controller_router is not None:
            controller_plan = controller_router.route(view.metadata, controller_profile or {}, budget)
            if controller_plan.token_budget != budget.token_budget:
                raise ValueError("controller router changed the supplied token budget")
        prediction = _execute_plan(
            task,
            plan,
            bank_by_id,
            providers,
            controller_plan=controller_plan,
            judge_provider=judge_provider,
            temperature=temperature,
            seed=seed,
        )
        evaluation = evaluator.evaluate(task, str(prediction["output"]))
        route_plans.append(plan)
        if controller_plan is not None:
            controller_plans.append(controller_plan)
            prediction["controller_route_id"] = controller_plan.route_id
            prediction["controller_family"] = controller_plan.controller_family
            prediction["controller_answer_contract"] = controller_plan.answer_contract
        predictions.append(prediction)
        evaluations.append(evaluation)
        write_jsonl_atomic(route_path, route_plans)
        if controller_plans:
            write_jsonl_atomic(controller_path, controller_plans)
        write_jsonl_atomic(prediction_path, predictions)
        write_jsonl_atomic(evaluation_path, evaluations)

    accounting: dict[str, Any] = {
        "n_tasks": len(predictions),
        "prompt_tokens": sum(int(row.get("prompt_tokens", 0)) for row in predictions),
        "completion_tokens": sum(int(row.get("completion_tokens", 0)) for row in predictions),
        "cost": sum(float(row.get("cost", 0.0)) for row in predictions),
        "latency_ms": sum(float(row.get("latency_ms", 0.0)) for row in predictions),
        "by_task": {
            str(row["task_id"]): {
                "prompt_tokens": int(row.get("prompt_tokens", 0)),
                "completion_tokens": int(row.get("completion_tokens", 0)),
                "cost": float(row.get("cost", 0.0)),
                "steps": len(row.get("steps", [])),
                "stop_reason": row.get("stop_reason"),
            }
            for row in predictions
        },
    }
    write_json_atomic(accounting_path, accounting)
    return RunArtifacts(
        route_plans=tuple(route_plans),
        controller_route_plans=tuple(controller_plans),
        predictions=tuple(predictions),
        evaluations=tuple(evaluations),
        token_accounting=accounting,
    )


__all__ = [
    "ControllerRouter",
    "DialectRouter",
    "RunArtifacts",
    "majority_aggregate",
    "run",
    "score_aggregate",
    "weighted_aggregate",
]
