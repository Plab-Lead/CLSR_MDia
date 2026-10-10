"""Validated, immutable data contracts shared by the MDia pipeline.

The distinction between :class:`TaskRecord` and :class:`TaskView` is a
deliberate leakage boundary: routers and providers receive the public view,
while only evaluators receive the record containing the gold answer.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, PrivateAttr, field_validator, model_validator

SCHEMA_VERSION = "1.0"
_ID_PREFIX = re.compile(r"^[a-z][a-z0-9_-]*$")
_PRIVATE_TASK_KEYS = frozenset(
    {
        "answer",
        "expected",
        "expected_answer",
        "expected_output",
        "gold",
        "gold_answer",
        "gold_index",
        "gold_label",
        "label",
        "reference_answer",
        "solution",
        "target",
    }
)


def _canonical_value(value: Any) -> JsonValue:
    """Convert supported Python values to a deterministic JSON value."""

    if isinstance(value, BaseModel):
        return _canonical_value(value.model_dump(mode="json", exclude_none=False))
    if isinstance(value, Enum):
        return _canonical_value(value.value)
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, datetime):
        normalized = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return normalized.isoformat().replace("+00:00", "Z")
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        canonical_items = [_canonical_value(item) for item in value]
        return sorted(canonical_items, key=lambda item: canonical_json(item))
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite floating-point values cannot be hashed")
        return value
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Serialize ``value`` as stable UTF-8 JSON."""

    return json.dumps(
        _canonical_value(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def stable_digest(value: Any) -> str:
    """Return a full SHA-256 hex digest for a canonical value."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def stable_id(prefix: str, value: Any, *, length: int = 20) -> str:
    """Build a readable, content-addressed identifier."""

    if not _ID_PREFIX.fullmatch(prefix):
        raise ValueError("ID prefix must start with a lowercase letter and contain only [a-z0-9_-]")
    if length < 12 or length > 64:
        raise ValueError("stable ID length must be between 12 and 64")
    return f"{prefix}-{stable_digest(value)[:length]}"


def is_private_task_key(key: str) -> bool:
    """Return whether a metadata key conventionally carries held-out gold."""

    return key.strip().casefold() in _PRIVATE_TASK_KEYS


def public_task_metadata(metadata: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """Recursively remove reserved gold-bearing keys from task metadata."""

    def scrub(value: JsonValue) -> JsonValue:
        if isinstance(value, dict):
            return {key: scrub(item) for key, item in value.items() if not is_private_task_key(key)}
        if isinstance(value, list):
            return [scrub(item) for item in value]
        return value

    return {key: scrub(value) for key, value in metadata.items() if not is_private_task_key(key)}


class MDiaModel(BaseModel):
    """Base model for on-disk public contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class DataSplit(str, Enum):
    INDUCTION = "induction"
    EVOLUTION_VALIDATION = "evolution_validation"
    ROUTER_VALIDATION = "router_validation"
    TEST = "test"


class RouteMode(str, Enum):
    SINGLE = "single"
    AGGREGATE = "aggregate"
    COMPOSE = "compose"
    ABSTAIN = "abstain"
    RAW_FALLBACK = "raw_fallback"


class AggregationMethod(str, Enum):
    MAJORITY = "majority"
    WEIGHTED = "weighted"
    SCORE = "score"
    JUDGE = "judge"


class RuleSupport(str, Enum):
    FULL = "full"
    STRONG = "strong"
    PARTIAL = "partial"
    WEAK = "weak"
    BOUNDARY = "boundary"
    UNSUPPORTED = "unsupported"


class RuleExecutionStatus(str, Enum):
    EVALUATED = "evaluated"
    NOT_EVALUATED = "not_evaluated"
    ERROR = "error"


class TaskView(MDiaModel):
    """Gold-free task projection accepted by pre-prediction components."""

    task_id: str = Field(min_length=1)
    split: DataSplit
    query: str = Field(min_length=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    public_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("metadata")
    @classmethod
    def _metadata_has_no_gold(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if public_task_metadata(value) != value:
            raise ValueError("TaskView metadata contains reserved gold fields")
        return value


class TaskRecord(MDiaModel):
    task_id: str = ""
    split: DataSplit
    query: str = Field(min_length=1)
    gold: JsonValue | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    content_hash: str = ""

    @field_validator("query")
    @classmethod
    def _query_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query cannot be blank")
        return value

    @model_validator(mode="after")
    def _derive_identity(self) -> TaskRecord:
        public = {
            "split": self.split.value,
            "query": self.query,
            "metadata": public_task_metadata(self.metadata),
        }
        expected_id = stable_id("task", public)
        full = {
            "split": self.split.value,
            "query": self.query,
            "metadata": self.metadata,
            "task_id": self.task_id or expected_id,
            "gold": self.gold,
        }
        expected_hash = stable_digest(full)
        if self.content_hash and self.content_hash != expected_hash:
            raise ValueError("content_hash does not match task content")
        object.__setattr__(self, "task_id", self.task_id or expected_id)
        object.__setattr__(self, "content_hash", expected_hash)
        return self

    def to_view(self) -> TaskView:
        metadata = public_task_metadata(self.metadata)
        public = {
            "task_id": self.task_id,
            "split": self.split.value,
            "query": self.query,
            "metadata": metadata,
        }
        return TaskView(
            task_id=self.task_id,
            split=self.split,
            query=self.query,
            metadata=metadata,
            public_digest=stable_digest(public),
        )


class ChatMessage(MDiaModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None


class CompletionRequest(MDiaModel):
    request_id: str = ""
    model: str = Field(min_length=1)
    messages: tuple[ChatMessage, ...] = Field(min_length=1)
    max_tokens: int = Field(default=512, gt=0)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    stop: tuple[str, ...] = ()
    seed: int | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _derive_request_id(self) -> CompletionRequest:
        payload = {
            "model": self.model,
            "messages": self.messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stop": self.stop,
            "seed": self.seed,
            "metadata": self.metadata,
        }
        object.__setattr__(self, "request_id", self.request_id or stable_id("request", payload))
        return self

    @property
    def replay_key(self) -> str:
        return self.request_id


class Completion(MDiaModel):
    request_id: str = Field(min_length=1)
    text: str
    model: str = Field(min_length=1)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    finish_reason: str = "stop"
    latency_ms: float = Field(default=0.0, ge=0.0)
    cost: float = Field(default=0.0, ge=0.0)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class EvaluationRecord(MDiaModel):
    evaluation_id: str = ""
    task_id: str = Field(min_length=1)
    evaluator_id: str = Field(min_length=1)
    output: str
    parsed_output: JsonValue | None = None
    correct: bool | None = None
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    parse_failure: bool = False
    official: bool = False
    diagnostic: bool = True
    metrics: dict[str, float] = Field(default_factory=dict)
    details: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _derive_evaluation_id(self) -> EvaluationRecord:
        payload = {
            "task_id": self.task_id,
            "evaluator_id": self.evaluator_id,
            "output": self.output,
            "parsed_output": self.parsed_output,
        }
        object.__setattr__(self, "evaluation_id", self.evaluation_id or stable_id("evaluation", payload))
        return self


class TraceRecord(MDiaModel):
    trace_id: str = ""
    task_id: str = Field(min_length=1)
    split: DataSplit
    speaker_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    output: str
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    correct: bool | None = None
    evaluator_id: str | None = None
    parse_failure: bool = False
    latency_ms: float = Field(default=0.0, ge=0.0)
    cost: float = Field(default=0.0, ge=0.0)
    request_id: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _derive_trace_id(self) -> TraceRecord:
        payload = {
            "task_id": self.task_id,
            "split": self.split.value,
            "speaker_id": self.speaker_id,
            "model_id": self.model_id,
            "output": self.output,
            "request_id": self.request_id,
        }
        object.__setattr__(self, "trace_id", self.trace_id or stable_id("trace", payload))
        return self


class DialectCard(MDiaModel):
    """Machine dialect specification ``D = (V, G, O, R, rho)``."""

    dialect_id: str = ""
    specification_digest: str = ""
    generation: int = Field(ge=0)
    parent_ids: tuple[str, ...] = ()
    creator_id: str = Field(min_length=1)
    speaker_ids: tuple[str, ...] = Field(min_length=1)
    source_trace_ids: tuple[str, ...] = ()
    task_tags: tuple[str, ...] = ()
    symbol_inventory: str = Field(min_length=1, description="V: finite symbols and their meanings")
    grammar: str = Field(min_length=1)
    reasoning_operators: str = Field(min_length=1, description="O: reusable reasoning transformations")
    usage_rules: str = Field(min_length=1, description="R: validity, use, and avoidance rules")
    empirical_profile: dict[str, float] = Field(
        min_length=1,
        description="rho: empirical accuracy, cost, failure, transfer, and compatibility statistics",
    )
    profile_ids: tuple[str, ...] = ()
    input_contract: str = Field(min_length=1)
    output_contract: str = Field(min_length=1)
    fallback: str = Field(min_length=1)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _derive_card_identity(self) -> DialectCard:
        specification = {
            "symbol_inventory": self.symbol_inventory,
            "grammar": self.grammar,
            "reasoning_operators": self.reasoning_operators,
            "usage_rules": self.usage_rules,
            "input_contract": self.input_contract,
            "output_contract": self.output_contract,
            "fallback": self.fallback,
            "task_tags": sorted(self.task_tags),
        }
        expected_digest = stable_digest(specification)
        if self.specification_digest and self.specification_digest != expected_digest:
            raise ValueError("specification_digest does not match dialect specification")
        identity = {
            "specification_digest": expected_digest,
            "generation": self.generation,
            "parent_ids": sorted(self.parent_ids),
            "creator_id": self.creator_id,
            "speaker_ids": sorted(self.speaker_ids),
        }
        expected_id = stable_id("dialect", identity)
        if self.dialect_id and self.dialect_id != expected_id:
            raise ValueError("dialect_id does not match dialect identity")
        object.__setattr__(self, "specification_digest", expected_digest)
        object.__setattr__(self, "dialect_id", expected_id)
        return self


class ProfileObservation(MDiaModel):
    task_id: str = Field(min_length=1)
    correct: bool
    completion_tokens: int = Field(ge=0)
    parse_failure: bool = False
    latency_ms: float = Field(default=0.0, ge=0.0)
    cost: float = Field(default=0.0, ge=0.0)
    score: float | None = Field(default=None, ge=0.0, le=1.0)


class DialectProfile(MDiaModel):
    profile_id: str = ""
    dialect_id: str = Field(min_length=1)
    listener_id: str = Field(min_length=1)
    split: DataSplit
    task_tag: str | None = None
    observations: tuple[ProfileObservation, ...] = ()
    n_items: int = Field(default=0, ge=0)
    accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    mean_completion_tokens: float = Field(default=0.0, ge=0.0)
    parse_failure_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    mean_latency_ms: float = Field(default=0.0, ge=0.0)
    mean_cost: float = Field(default=0.0, ge=0.0)
    confidence_interval: tuple[float, float] = (0.0, 1.0)
    utility: float | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _derive_profile(self) -> DialectProfile:
        if self.observations:
            n_items = len(self.observations)
            if self.n_items not in (0, n_items):
                raise ValueError("n_items must equal the number of observations")
            accuracy = sum(item.correct for item in self.observations) / n_items
            mean_tokens = sum(item.completion_tokens for item in self.observations) / n_items
            parse_rate = sum(item.parse_failure for item in self.observations) / n_items
            mean_latency = sum(item.latency_ms for item in self.observations) / n_items
            mean_cost = sum(item.cost for item in self.observations) / n_items
            object.__setattr__(self, "n_items", n_items)
            object.__setattr__(self, "accuracy", accuracy)
            object.__setattr__(self, "mean_completion_tokens", mean_tokens)
            object.__setattr__(self, "parse_failure_rate", parse_rate)
            object.__setattr__(self, "mean_latency_ms", mean_latency)
            object.__setattr__(self, "mean_cost", mean_cost)
        low, high = self.confidence_interval
        if not 0.0 <= low <= high <= 1.0:
            raise ValueError("confidence_interval must satisfy 0 <= low <= high <= 1")
        identity = {
            "dialect_id": self.dialect_id,
            "listener_id": self.listener_id,
            "split": self.split.value,
            "task_tag": self.task_tag,
            "task_ids": [item.task_id for item in self.observations],
        }
        object.__setattr__(self, "profile_id", self.profile_id or stable_id("profile", identity))
        return self


class RouteBudget(MDiaModel):
    token_budget: int = Field(gt=0)
    max_steps: int = Field(default=1, gt=0)
    consumed_tokens: int = Field(default=0, ge=0)
    minimum_utility: float | None = None

    @model_validator(mode="after")
    def _consumption_within_budget(self) -> RouteBudget:
        if self.consumed_tokens > self.token_budget:
            raise ValueError("consumed_tokens cannot exceed token_budget")
        return self

    @property
    def remaining_tokens(self) -> int:
        return self.token_budget - self.consumed_tokens


class DialectRoutePlan(MDiaModel):
    route_id: str = ""
    task_id: str = Field(min_length=1)
    router_id: str = Field(min_length=1)
    listener_id: str = Field(min_length=1)
    mode: RouteMode
    dialect_ids: tuple[str, ...] = ()
    specification_digests: tuple[str, ...] = ()
    aggregation: AggregationMethod | None = None
    weights: tuple[float, ...] = ()
    utility_scores: dict[str, float] = Field(default_factory=dict)
    estimated_tokens: int = Field(default=0, ge=0)
    token_budget: int = Field(gt=0)
    max_steps: int = Field(gt=0)
    stop_reason: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_route(self) -> DialectRoutePlan:
        count = len(self.dialect_ids)
        if len(set(self.dialect_ids)) != count:
            raise ValueError("dialect_ids must be unique")
        if len(self.specification_digests) != count:
            raise ValueError("each routed dialect must have a specification digest")
        if self.weights and len(self.weights) != count:
            raise ValueError("weights must align with dialect_ids")
        if any(weight < 0 for weight in self.weights):
            raise ValueError("route weights cannot be negative")
        required_steps = count + int(self.aggregation is AggregationMethod.JUDGE)
        if required_steps > self.max_steps:
            raise ValueError("max_steps cannot execute all selected dialects and aggregation steps")
        if self.estimated_tokens > self.token_budget:
            raise ValueError("estimated_tokens cannot exceed token_budget")
        if self.mode is RouteMode.SINGLE and count != 1:
            raise ValueError("single mode requires exactly one dialect")
        if self.mode in (RouteMode.AGGREGATE, RouteMode.COMPOSE) and count < 2:
            raise ValueError(f"{self.mode.value} mode requires at least two dialects")
        if self.mode is RouteMode.AGGREGATE and self.aggregation is None:
            raise ValueError("aggregate mode requires an aggregation method")
        if self.mode is not RouteMode.AGGREGATE and self.aggregation is not None:
            raise ValueError("aggregation is valid only in aggregate mode")
        if self.aggregation is AggregationMethod.WEIGHTED:
            if not self.weights or not math.isclose(sum(self.weights), 1.0, rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError("weighted aggregation requires weights summing to one")
        elif self.weights:
            raise ValueError("weights are valid only for weighted aggregation")
        if self.mode in (RouteMode.ABSTAIN, RouteMode.RAW_FALLBACK) and count:
            raise ValueError(f"{self.mode.value} mode cannot select dialects")
        if self.mode in (RouteMode.ABSTAIN, RouteMode.RAW_FALLBACK) and not self.stop_reason:
            raise ValueError(f"{self.mode.value} mode requires a stop_reason")
        identity = {
            "task_id": self.task_id,
            "router_id": self.router_id,
            "listener_id": self.listener_id,
            "mode": self.mode.value,
            "dialect_ids": self.dialect_ids,
            "specification_digests": self.specification_digests,
            "aggregation": self.aggregation,
            "token_budget": self.token_budget,
            "max_steps": self.max_steps,
        }
        object.__setattr__(self, "route_id", self.route_id or stable_id("route", identity))
        return self


class ControllerRoutePlan(MDiaModel):
    route_id: str = ""
    router_id: str = Field(min_length=1)
    controller_family: str = Field(min_length=1)
    answer_contract: str = Field(min_length=1)
    metadata_key: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    estimated_tokens: int = Field(default=0, ge=0)
    token_budget: int = Field(gt=0)
    stop_reason: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _derive_route_id(self) -> ControllerRoutePlan:
        if self.estimated_tokens > self.token_budget:
            raise ValueError("estimated_tokens cannot exceed token_budget")
        payload = {
            "router_id": self.router_id,
            "controller_family": self.controller_family,
            "answer_contract": self.answer_contract,
            "metadata_key": self.metadata_key,
            "token_budget": self.token_budget,
        }
        object.__setattr__(self, "route_id", self.route_id or stable_id("controller-route", payload))
        return self


class RuleSpec(MDiaModel):
    rule_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    title: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    manuscript_support: RuleSupport
    eligible_records: str = Field(min_length=1)
    unit_of_analysis: str = Field(min_length=1)
    features: tuple[str, ...] = Field(min_length=1)
    statistic: str = Field(min_length=1)
    direction: Literal["positive", "negative", "two_sided", "noninferior", "descriptive"]
    threshold: float | None = None
    test_type: Literal["paired_bootstrap", "permutation", "regression", "descriptive"]
    evidence_stream: str = Field(min_length=1)
    exceptions: tuple[str, ...] = ()
    routing_implication: str = Field(min_length=1)
    proxy: bool = False


class RuleResult(MDiaModel):
    result_id: str = ""
    rule_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    status: RuleExecutionStatus
    manuscript_support: RuleSupport
    n_units: int = Field(default=0, ge=0)
    estimate: float | None = None
    confidence_interval: tuple[float, float] | None = None
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    adjusted_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    passed: bool | None = None
    reason: str | None = None
    evidence_artifacts: tuple[str, ...] = ()
    proxy: bool = False
    details: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_rule_result(self) -> RuleResult:
        if self.status is RuleExecutionStatus.NOT_EVALUATED and not self.reason:
            raise ValueError("not_evaluated results require a reason")
        if self.status is not RuleExecutionStatus.EVALUATED and self.passed is not None:
            raise ValueError("only evaluated results may set passed")
        payload = {"rule_id": self.rule_id, "status": self.status.value, "evidence": self.evidence_artifacts}
        object.__setattr__(self, "result_id", self.result_id or stable_id("rule-result", payload))
        return self


class RunManifest(MDiaModel):
    schema_version: str = SCHEMA_VERSION
    run_id: str = Field(min_length=1)
    created_at: datetime
    code_revision: str = Field(min_length=1)
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_revision: str = Field(min_length=1)
    model_revisions: dict[str, str] = Field(default_factory=dict)
    seeds: dict[str, int] = Field(default_factory=dict)
    split_hashes: dict[DataSplit, str] = Field(default_factory=dict)
    candidate_pool: tuple[str, ...] = ()
    artifact_checksums: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    _source_path: Path | None = PrivateAttr(default=None)

    @field_validator("created_at")
    @classmethod
    def _created_at_is_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        return value

    @field_validator("split_hashes", "artifact_checksums")
    @classmethod
    def _hashes_are_sha256(cls, value: Mapping[Any, str]) -> Mapping[Any, str]:
        for digest in value.values():
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("manifest hashes must be lowercase SHA-256 hex digests")
        return value


def task_manifest_digest(records: Sequence[TaskRecord]) -> str:
    """Hash an immutable task manifest without depending on file ordering."""

    identities = sorted((record.task_id, record.content_hash) for record in records)
    return stable_digest(identities)


__all__ = [
    "AggregationMethod",
    "ChatMessage",
    "Completion",
    "CompletionRequest",
    "ControllerRoutePlan",
    "DataSplit",
    "DialectCard",
    "DialectProfile",
    "DialectRoutePlan",
    "EvaluationRecord",
    "JsonValue",
    "ProfileObservation",
    "RouteBudget",
    "RouteMode",
    "RuleExecutionStatus",
    "RuleResult",
    "RuleSpec",
    "RuleSupport",
    "RunManifest",
    "SCHEMA_VERSION",
    "TaskRecord",
    "TaskView",
    "TraceRecord",
    "canonical_json",
    "is_private_task_key",
    "public_task_metadata",
    "stable_digest",
    "stable_id",
    "task_manifest_digest",
]
