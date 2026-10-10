"""Optional metadata router for controller/prompt families.

This router does not select dialect cards. It is intentionally a separate
interface from ``DialectRouter`` to avoid the historical v2 ambiguity.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import JsonValue

from ..schemas import ControllerRoutePlan, RouteBudget, is_private_task_key

DEFAULT_CONTROLLER_ROUTES: dict[str, dict[str, str]] = {
    "bfcl": {"_default": "parallel_zip"},
    "livecodebench_output": {"_default": "schema"},
    "multihop_rag": {
        "comparison_query": "silent",
        "inference_query": "verify",
        "null_query": "yesno_guard",
        "_default": "verify",
    },
    "musr": {
        "murder_mystery": "contrast",
        "object_placements": "contrast",
        "team_allocation": "schema",
        "_default": "contrast",
    },
}

DEFAULT_KEY_FIELDS = {"multihop_rag": "question_type", "musr": "subdomain"}

DEFAULT_ANSWER_CONTRACTS = {
    "parallel_zip": "Return one parseable list whose call order and argument slots match the requested calls.",
    "schema": "Return only the exact parser-facing schema requested by the task.",
    "silent": "Return a concise final answer grounded in the supplied evidence.",
    "verify": "Verify evidence sufficiency before returning a concise final answer.",
    "yesno_guard": "Return the requested answer only when support exists; otherwise use the task's null form.",
    "contrast": "Contrast candidate states, reject contradictions, and return the consistent final choice.",
    "raw": "Answer directly using the task's observable output contract.",
}


class MetadataControllerRouter:
    router_id = "controller-metadata-v1"

    def __init__(
        self,
        routes: Mapping[str, Mapping[str, str]] | None = None,
        *,
        key_fields: Mapping[str, str] | None = None,
        default_controller: str | None = None,
        estimated_overhead: Mapping[str, int] | None = None,
        reasons: Mapping[str, str] | None = None,
        answer_contracts: Mapping[str, str] | None = None,
    ) -> None:
        self.routes = {
            benchmark: dict(route) for benchmark, route in (routes or DEFAULT_CONTROLLER_ROUTES).items()
        }
        self.key_fields = dict(key_fields or DEFAULT_KEY_FIELDS)
        self.default_controller = default_controller
        self.estimated_overhead = dict(estimated_overhead or {})
        self.reasons = dict(reasons or {})
        self.answer_contracts = dict(DEFAULT_ANSWER_CONTRACTS)
        self.answer_contracts.update(answer_contracts or {})

    def route(
        self,
        task_metadata: Mapping[str, JsonValue],
        listener_profile: Mapping[str, JsonValue],
        budget: RouteBudget,
    ) -> ControllerRoutePlan:
        private = sorted(key for key in task_metadata if is_private_task_key(key))
        if private:
            raise ValueError(f"controller metadata contains reserved gold field(s): {', '.join(private)}")
        benchmark = str(task_metadata.get("benchmark", ""))
        table = self.routes.get(benchmark)
        key_field = self.key_fields.get(benchmark)
        key = str(task_metadata.get(key_field, "_default")) if key_field else "_default"
        controller: str | None = None
        if table is not None:
            controller = table.get(key) or table.get("_default")
        controller = controller or self.default_controller
        if controller is None:
            controller = "raw"
            reason = f"no configured controller for observable key {benchmark}:{key}"
            stop_reason = reason
            overhead = 0
        else:
            reason = self.reasons.get(controller, f"metadata route selected from {benchmark}:{key}")
            stop_reason = None
            overhead = self.estimated_overhead.get(controller, 0)
            if overhead > budget.remaining_tokens:
                controller = "raw"
                stop_reason = "controller overhead exceeds remaining token budget"
                reason = stop_reason
                overhead = 0
        return ControllerRoutePlan(
            router_id=self.router_id,
            controller_family=controller,
            answer_contract=self.answer_contracts.get(controller, DEFAULT_ANSWER_CONTRACTS["raw"]),
            metadata_key=f"{benchmark}:{key}",
            reason=reason,
            estimated_tokens=overhead,
            token_budget=budget.token_budget,
            stop_reason=stop_reason,
            metadata={
                "consumed_tokens": budget.consumed_tokens,
                "listener_profile_used": bool(listener_profile),
                "routes_dialects": False,
            },
        )


__all__ = [
    "DEFAULT_ANSWER_CONTRACTS",
    "DEFAULT_CONTROLLER_ROUTES",
    "DEFAULT_KEY_FIELDS",
    "MetadataControllerRouter",
]
