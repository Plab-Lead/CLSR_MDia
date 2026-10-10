from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from mdia.schemas import (
    Completion,
    CompletionRequest,
    DataSplit,
    DialectCard,
    DialectProfile,
    ProfileObservation,
    TaskRecord,
)


def make_task(
    name: str,
    *,
    split: DataSplit = DataSplit.TEST,
    query: str | None = None,
    gold: Any = "A",
    metadata: Mapping[str, Any] | None = None,
) -> TaskRecord:
    return TaskRecord(
        task_id=name,
        split=split,
        query=query or f"Question {name}?",
        gold=gold,
        metadata=dict(metadata or {"benchmark": "toy"}),
    )


def make_card(
    creator: str,
    *,
    generation: int = 0,
    suffix: str = "base",
    parents: Sequence[str] = (),
    task_tags: Sequence[str] = ("toy",),
) -> DialectCard:
    return DialectCard(
        generation=generation,
        parent_ids=tuple(parents),
        creator_id=creator,
        speaker_ids=(creator,),
        task_tags=tuple(task_tags),
        symbol_inventory=f"V-{suffix}",
        grammar=f"G-{suffix}",
        reasoning_operators=f"O-{suffix}",
        usage_rules=f"R-{suffix}",
        empirical_profile={"profiled": 0.0},
        input_contract="public task only",
        output_contract="one answer",
        fallback="answer directly",
    )


def make_profile(
    card: DialectCard,
    listener: str,
    *,
    correct: Sequence[bool] = (True, True),
    tokens: Sequence[int] = (5, 5),
    split: DataSplit = DataSplit.ROUTER_VALIDATION,
    utility: float | None = None,
) -> DialectProfile:
    assert len(correct) == len(tokens)
    observations = tuple(
        ProfileObservation(task_id=f"profile-{card.creator_id}-{index}", correct=ok, completion_tokens=cost)
        for index, (ok, cost) in enumerate(zip(correct, tokens, strict=True))
    )
    return DialectProfile(
        dialect_id=card.dialect_id,
        listener_id=listener,
        split=split,
        observations=observations,
        utility=utility,
    )


class MemoryAdapter:
    def __init__(self, records: Mapping[DataSplit, Sequence[TaskRecord]]) -> None:
        self.records = {split: tuple(items) for split, items in records.items()}

    def load(self, split: DataSplit) -> tuple[TaskRecord, ...]:
        return self.records.get(split, ())


@dataclass
class RecordingProvider:
    answers: Mapping[str, str] | None = None
    default: str = "A"
    completion_tokens: int = 1
    prompt_tokens: int = 2
    cost: float = 0.01
    latency_ms: float = 3.0
    model: str = "fixture-model"
    revision: str = "fixture-v1"
    provider_id: str = "fixture"

    def __post_init__(self) -> None:
        self.requests: list[CompletionRequest] = []

    def complete(self, request: CompletionRequest) -> Completion:
        self.requests.append(request)
        dialect_id = str(request.metadata.get("dialect_id", "raw"))
        text = (self.answers or {}).get(dialect_id, self.default)
        return Completion(
            request_id=request.request_id,
            text=text,
            model=request.model,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            cost=self.cost,
            latency_ms=self.latency_ms,
        )


class OverspendingProvider(RecordingProvider):
    def complete(self, request: CompletionRequest) -> Completion:
        self.requests.append(request)
        return Completion(
            request_id=request.request_id,
            text=self.default,
            model=request.model,
            completion_tokens=request.max_tokens + 1,
        )
