from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from mdia.schemas import (
    AggregationMethod,
    DataSplit,
    DialectRoutePlan,
    RouteBudget,
    RouteMode,
    RunManifest,
    TaskRecord,
    TaskView,
    canonical_json,
    stable_digest,
    stable_id,
    task_manifest_digest,
)
from tests.support import make_card


def test_stable_ids_are_canonical_and_order_independent() -> None:
    left = {"b": [2, 1], "a": {"z", "x"}}
    right = {"a": {"x", "z"}, "b": [2, 1]}
    assert canonical_json(left) == canonical_json(right)
    assert stable_digest(left) == stable_digest(right)
    assert stable_id("task", left) == stable_id("task", right)
    with pytest.raises(ValueError, match="prefix"):
        stable_id("Bad", left)


def test_task_identity_is_public_but_content_hash_covers_gold() -> None:
    common = {
        "split": DataSplit.INDUCTION,
        "query": "Choose one",
        "metadata": {"difficulty": "easy", "gold_answer": "metadata-secret"},
    }
    first = TaskRecord(gold="A", **common)
    second = TaskRecord(gold="B", **common)
    third = TaskRecord(
        gold="A",
        split=DataSplit.INDUCTION,
        query="Choose one",
        metadata={"difficulty": "easy", "gold_answer": "different-private-value"},
    )

    assert first.task_id == second.task_id == third.task_id
    assert first.content_hash != second.content_hash
    assert first.content_hash != third.content_hash
    assert task_manifest_digest([first, second]) == task_manifest_digest([second, first])


def test_task_view_removes_gold_and_rejects_direct_gold_metadata() -> None:
    task = TaskRecord(
        task_id="gold-boundary",
        split=DataSplit.TEST,
        query="Do not leak",
        gold="secret-answer",
        metadata={
            "gold_answer": "also-secret",
            "benchmark": "toy",
            "nested": {"label": "nested-secret", "safe": "visible"},
        },
    )
    view = task.to_view()
    assert view.metadata == {"benchmark": "toy", "nested": {"safe": "visible"}}
    assert "secret" not in view.model_dump_json()

    with pytest.raises(ValidationError, match="reserved gold"):
        TaskView(
            task_id="bad",
            split=DataSplit.TEST,
            query="bad",
            metadata={"label": "A"},
            public_digest="0" * 64,
        )
    with pytest.raises(ValidationError, match="reserved gold"):
        TaskView(
            task_id="bad-nested",
            split=DataSplit.TEST,
            query="bad",
            metadata={"nested": {"target": "A"}},
            public_digest="0" * 64,
        )


def test_dialect_identity_covers_specification_and_lifecycle() -> None:
    card = make_card("speaker-a")
    same = make_card("speaker-a")
    changed_spec = make_card("speaker-a", suffix="changed")
    next_generation = make_card("speaker-a", generation=1, parents=(card.dialect_id,))

    assert card.dialect_id == same.dialect_id
    assert card.specification_digest == same.specification_digest
    assert card.specification_digest != changed_spec.specification_digest
    assert card.dialect_id != next_generation.dialect_id

    profiled_payload = card.model_dump(mode="json")
    profiled_payload["empirical_profile"] = {"profiled": 1.0, "validation_accuracy": 0.75}
    profiled_payload["profile_ids"] = ["profile-validation"]
    profiled = type(card).model_validate(profiled_payload)
    assert profiled.dialect_id == card.dialect_id
    assert profiled.specification_digest == card.specification_digest
    assert set(profiled.model_fields_set) >= {
        "symbol_inventory",
        "grammar",
        "reasoning_operators",
        "usage_rules",
        "empirical_profile",
    }

    payload = card.model_dump(mode="json")
    payload["grammar"] = "tampered"
    with pytest.raises(ValidationError, match="specification_digest"):
        type(card).model_validate(payload)


def test_route_schema_enforces_modes_digests_weights_and_budget() -> None:
    first = make_card("a")
    second = make_card("b")
    route = DialectRoutePlan(
        task_id="task",
        router_id="router",
        listener_id="listener",
        mode=RouteMode.AGGREGATE,
        dialect_ids=(first.dialect_id, second.dialect_id),
        specification_digests=(first.specification_digest, second.specification_digest),
        aggregation=AggregationMethod.WEIGHTED,
        weights=(0.25, 0.75),
        estimated_tokens=8,
        token_budget=10,
        max_steps=2,
    )
    duplicate = DialectRoutePlan.model_validate(route.model_dump(mode="json"))
    assert duplicate.route_id == route.route_id

    with pytest.raises(ValidationError, match="exactly one"):
        DialectRoutePlan(
            task_id="task",
            router_id="router",
            listener_id="listener",
            mode=RouteMode.SINGLE,
            dialect_ids=(),
            specification_digests=(),
            token_budget=10,
            max_steps=1,
        )
    with pytest.raises(ValidationError, match="summing to one"):
        route.model_copy(update={"weights": (0.2, 0.2)}).model_validate(
            {**route.model_dump(mode="json"), "weights": [0.2, 0.2]}
        )
    with pytest.raises(ValidationError, match="cannot exceed"):
        RouteBudget(token_budget=5, consumed_tokens=6)


def test_run_manifest_requires_timezone_and_sha256_hashes() -> None:
    valid = {
        "run_id": "run",
        "created_at": "2026-07-30T00:00:00Z",
        "code_revision": "abc",
        "config_hash": "a" * 64,
        "provider_revision": "fixture",
        "split_hashes": {"test": "b" * 64},
        "artifact_checksums": {"x": "c" * 64},
    }
    assert RunManifest.model_validate(valid).created_at.tzinfo is not None
    with pytest.raises(ValidationError, match="timezone"):
        RunManifest.model_validate({**valid, "created_at": datetime(2026, 7, 30)})
    with pytest.raises(ValidationError, match="SHA-256"):
        RunManifest.model_validate({**valid, "artifact_checksums": {"x": "bad"}})
