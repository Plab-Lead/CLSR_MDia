"""Observable metadata routing for MDia-Routed-v2.

The route map intentionally uses only benchmark metadata available before
prediction. It does not use gold answers, task ids, or model outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RouteSpec:
    benchmark: str
    route: str
    key: str
    reason: str


ROUTE_MAP: dict[str, dict[str, str]] = {
    "bfcl": {
        "_default": "rmdia_bfcl_parallel_zip",
    },
    "livecodebench_output": {
        "_default": "rmdia_schema",
    },
    "multihop_rag": {
        "comparison_query": "rmdia_silent",
        "inference_query": "rmdia_verify",
        "null_query": "rmdia_mhop_yesno_guard",
        "_default": "rmdia_verify",
    },
    "musr": {
        "murder_mystery": "rmdia_contrast",
        "object_placements": "rmdia_contrast",
        "team_allocation": "rmdia_schema",
        "_default": "rmdia_contrast",
    },
}


ROUTE_REASONS = {
    "rmdia_bfcl_parallel_zip": "Schema-aware function-call routing with explicit handling of parallel 'respectively' calls.",
    "rmdia_schema": "Compact schema-first decoding for tasks where strict output contract dominates.",
    "rmdia_silent": "Minimal direct answer route when metadata indicates an easy evidence bridge.",
    "rmdia_verify": "Silent two-pass candidate plus verifier route for inference-sensitive cases.",
    "rmdia_mhop_yesno_guard": "Null-aware yes/no guard for MultiHopRAG over-answering risks.",
    "rmdia_contrast": "Compact contrastive candidate elimination for narrative reasoning.",
}


def route_key(task: dict[str, Any]) -> str:
    """Return the observable metadata key used by the router."""

    benchmark = str(task.get("benchmark", ""))
    if benchmark == "musr":
        return str(task.get("subdomain") or "_default")
    if benchmark == "multihop_rag":
        return str(task.get("question_type") or "_default")
    if benchmark == "bfcl":
        return "_default"
    if benchmark == "livecodebench_output":
        return "_default"
    return "_default"


def select_route(task: dict[str, Any]) -> RouteSpec:
    """Select the MDia route for one task."""

    benchmark = str(task.get("benchmark", ""))
    if benchmark not in ROUTE_MAP:
        raise ValueError(f"Unsupported benchmark: {benchmark}")
    key = route_key(task)
    route = ROUTE_MAP[benchmark].get(key) or ROUTE_MAP[benchmark]["_default"]
    return RouteSpec(
        benchmark=benchmark,
        route=route,
        key=key,
        reason=ROUTE_REASONS.get(route, "Benchmark-specific MDia route."),
    )

