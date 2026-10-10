"""Creation, evolution, profiling, and validation-only selection stages."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol, TypeAlias, cast

from mdia.pipeline.io import read_json, read_jsonl, write_json_atomic, write_jsonl_atomic
from mdia.schemas import (
    ChatMessage,
    Completion,
    CompletionRequest,
    DataSplit,
    DialectCard,
    DialectProfile,
    EvaluationRecord,
    JsonValue,
    ProfileObservation,
    TaskRecord,
    TraceRecord,
    canonical_json,
    stable_digest,
)


class DatasetAdapter(Protocol):
    def load(self, split: DataSplit) -> Iterable[TaskRecord]: ...


class ChatProvider(Protocol):
    def complete(self, request: CompletionRequest) -> Completion: ...


class Evaluator(Protocol):
    def evaluate(self, task: TaskRecord, output: str) -> EvaluationRecord: ...


ProviderMap: TypeAlias = Mapping[str, ChatProvider]
CardFactory: TypeAlias = Callable[[TraceRecord], DialectCard | Mapping[str, Any]]
CardEvolver: TypeAlias = Callable[[DialectCard, Mapping[str, JsonValue]], DialectCard | Mapping[str, Any]]


VALIDATION_SPLITS = frozenset({DataSplit.EVOLUTION_VALIDATION, DataSplit.ROUTER_VALIDATION})


def _provider_model(provider: ChatProvider, fallback: str) -> str:
    for attribute in ("model_id", "model", "provider_id"):
        value = getattr(provider, attribute, None)
        if isinstance(value, str) and value:
            return value
    return fallback


def _provider_map(providers: ProviderMap | ChatProvider) -> dict[str, ChatProvider]:
    if isinstance(providers, Mapping):
        if not providers:
            raise ValueError("at least one provider is required")
        return dict(providers)
    identifier = _provider_model(providers, "speaker")
    return {identifier: providers}


def _require_split(
    record: TaskRecord | TraceRecord, expected: set[DataSplit] | frozenset[DataSplit], stage: str
) -> None:
    if record.split not in expected:
        allowed = ", ".join(sorted(split.value for split in expected))
        raise ValueError(f"{stage} accepts only {allowed}; got {record.split.value}")


def _task_tags(task: TaskRecord) -> tuple[str, ...]:
    raw = task.metadata.get("task_tags", task.metadata.get("task_tag", task.metadata.get("benchmark", ())))
    if isinstance(raw, str):
        return (raw,) if raw else ()
    if isinstance(raw, list):
        return tuple(sorted(str(item) for item in raw if str(item)))
    return ()


def collect(
    adapter: DatasetAdapter,
    providers: ProviderMap | ChatProvider,
    evaluator: Evaluator,
    *,
    split: DataSplit = DataSplit.INDUCTION,
    output_path: str | Path | None = None,
    resume: bool = True,
    max_tokens: int = 2048,
    temperature: float = 0.0,
    seed: int = 0,
) -> list[TraceRecord]:
    """Collect direct answers without exposing gold fields to providers.

    The induction split is a hard contract.  Resume is keyed by task and
    speaker, and the complete JSONL is replaced atomically after every answer.
    """

    if split is not DataSplit.INDUCTION:
        raise ValueError("collect is restricted to the induction split")
    provider_by_speaker = _provider_map(providers)
    target = Path(output_path) if output_path is not None else None
    traces: list[TraceRecord] = []
    if resume and target is not None and target.exists():
        traces = [TraceRecord.model_validate(row) for row in read_jsonl(target)]
        for trace in traces:
            _require_split(trace, {DataSplit.INDUCTION}, "collect resume")
    completed = {(trace.task_id, trace.speaker_id) for trace in traces}

    tasks = list(adapter.load(split))
    if len({task.task_id for task in tasks}) != len(tasks):
        raise ValueError("induction manifest contains duplicate task IDs")
    for task in tasks:
        _require_split(task, {DataSplit.INDUCTION}, "collect")
        view = task.to_view()
        for speaker_id, provider in sorted(provider_by_speaker.items()):
            if (task.task_id, speaker_id) in completed:
                continue
            model_id = _provider_model(provider, speaker_id)
            request = CompletionRequest(
                model=model_id,
                messages=(
                    ChatMessage(
                        role="system",
                        content="Answer the task directly and finish with a clear final answer.",
                    ),
                    ChatMessage(role="user", content=view.query),
                ),
                max_tokens=max_tokens,
                temperature=temperature,
                seed=seed,
                metadata={
                    "stage": "collect",
                    "task_id": view.task_id,
                    "public_digest": view.public_digest,
                    "speaker_id": speaker_id,
                },
            )
            completion = provider.complete(request)
            evaluation = evaluator.evaluate(task, completion.text)
            trace = TraceRecord(
                task_id=task.task_id,
                split=task.split,
                speaker_id=speaker_id,
                model_id=completion.model,
                output=completion.text,
                prompt_tokens=completion.prompt_tokens,
                completion_tokens=completion.completion_tokens,
                correct=evaluation.correct,
                evaluator_id=evaluation.evaluator_id,
                parse_failure=evaluation.parse_failure,
                latency_ms=completion.latency_ms,
                cost=completion.cost,
                request_id=completion.request_id,
                metadata={"task_tags": list(_task_tags(task)), "diagnostic": evaluation.diagnostic},
            )
            traces.append(trace)
            completed.add((task.task_id, speaker_id))
            if target is not None:
                write_jsonl_atomic(target, traces)
    return traces


def select_top_k_traces(
    traces: Sequence[TraceRecord],
    *,
    top_k: int,
    speaker_diversity: bool = False,
) -> list[TraceRecord]:
    """Choose correct, parseable, lowest-token traces independently per item."""

    if top_k <= 0:
        raise ValueError("top_k must be positive")
    by_task: dict[str, list[TraceRecord]] = defaultdict(list)
    for trace in traces:
        _require_split(trace, {DataSplit.INDUCTION}, "create")
        if trace.correct is True and not trace.parse_failure:
            by_task[trace.task_id].append(trace)

    selected: list[TraceRecord] = []
    for task_id in sorted(by_task):
        ranked = sorted(
            by_task[task_id],
            key=lambda item: (item.completion_tokens, item.prompt_tokens, item.speaker_id, item.trace_id),
        )
        if not speaker_diversity:
            selected.extend(ranked[:top_k])
            continue
        chosen: list[TraceRecord] = []
        used_speakers: set[str] = set()
        for trace in ranked:
            if trace.speaker_id not in used_speakers:
                chosen.append(trace)
                used_speakers.add(trace.speaker_id)
                if len(chosen) == top_k:
                    break
        if len(chosen) < top_k:
            chosen_ids = {trace.trace_id for trace in chosen}
            chosen.extend(trace for trace in ranked if trace.trace_id not in chosen_ids)
        selected.extend(chosen[:top_k])
    return selected


def _default_card(trace: TraceRecord) -> DialectCard:
    task_tags_raw = trace.metadata.get("task_tags", [])
    task_tags = tuple(str(value) for value in task_tags_raw) if isinstance(task_tags_raw, list) else ()
    return DialectCard(
        generation=0,
        creator_id=trace.speaker_id,
        speaker_ids=(trace.speaker_id,),
        source_trace_ids=(trace.trace_id,),
        task_tags=task_tags,
        symbol_inventory="Use stable, short names and define every nonstandard symbol before reuse.",
        grammar="Express premises, transformations, checks, and the final answer in an explicit order.",
        reasoning_operators=f"Reusable transformations inferred from successful source {trace.trace_id}:\n{trace.output}",
        usage_rules="Use the shortest complete derivation; retain bindings and verification whenever omission could change correctness.",
        empirical_profile={
            "profiled": 0.0,
            "source_correct": 1.0,
            "source_completion_tokens": float(trace.completion_tokens),
            "source_parse_failure": float(trace.parse_failure),
        },
        input_contract="Read only the supplied task and public task metadata; never assume access to a gold answer.",
        output_contract="Return a human-readable final answer that satisfies the task's declared answer format.",
        fallback="If the dialect is ambiguous or unsafe, stop using it and answer directly in plain language.",
        metadata={"creation": "correct_low_token_trace", "source_model": trace.model_id},
    )


def _card_from_factory(trace: TraceRecord, factory: CardFactory | None) -> DialectCard:
    value = _default_card(trace) if factory is None else factory(trace)
    if isinstance(value, DialectCard):
        card = value
    else:
        card = DialectCard.model_validate(value)
    if card.generation != 0:
        raise ValueError("create card factories must return generation-0 cards")
    if trace.trace_id not in card.source_trace_ids:
        raise ValueError("created cards must retain their source trace ID")
    return card


def create(
    traces: Sequence[TraceRecord],
    *,
    top_k: int = 1,
    speaker_diversity: bool = False,
    creator_ids: Sequence[str] | None = None,
    card_factory: CardFactory | None = None,
    output_path: str | Path | None = None,
) -> list[DialectCard]:
    """Create deterministic generation-0 cards from selected direct traces."""

    allowed_creators = set(creator_ids or ())
    eligible_traces = traces
    if allowed_creators and card_factory is None:
        eligible_traces = [trace for trace in traces if trace.speaker_id in allowed_creators]
    selected = select_top_k_traces(eligible_traces, top_k=top_k, speaker_diversity=speaker_diversity)
    cards_by_id: dict[str, DialectCard] = {}
    for trace in selected:
        card = _card_from_factory(trace, card_factory)
        if allowed_creators and card.creator_id not in allowed_creators:
            raise ValueError(f"card creator {card.creator_id!r} is outside the configured creator community")
        cards_by_id[card.dialect_id] = card
    cards = [cards_by_id[key] for key in sorted(cards_by_id)]
    if not cards and allowed_creators:
        raise ValueError(
            "no eligible creator traces produced cards; configure creators as speakers or inject a CardFactory"
        )
    if output_path is not None:
        write_json_atomic(
            output_path,
            {
                "generation": 0,
                "selection": {
                    "top_k": top_k,
                    "speaker_diversity": speaker_diversity,
                    "creator_ids": sorted(allowed_creators),
                },
                "records": cards,
            },
        )
    return cards


def _validated_failures(failures: Sequence[Mapping[str, JsonValue]]) -> list[dict[str, JsonValue]]:
    normalized: list[dict[str, JsonValue]] = []
    for failure in failures:
        split = failure.get("split")
        if split not in {item.value for item in VALIDATION_SPLITS}:
            raise ValueError("evolution failures must come from a validation split")
        normalized.append(dict(failure))
    return normalized


def _default_evolve_card(
    card: DialectCard,
    peer: DialectCard | None,
    *,
    generation: int,
    context: Mapping[str, JsonValue],
) -> DialectCard:
    payload = card.model_dump(mode="json")
    payload.pop("dialect_id", None)
    payload.pop("specification_digest", None)
    payload["generation"] = generation
    parents = [card.dialect_id]
    if peer is not None and peer.dialect_id != card.dialect_id:
        parents.append(peer.dialect_id)
    payload["parent_ids"] = parents
    metadata = dict(cast(dict[str, JsonValue], payload.get("metadata", {})))
    metadata.update(
        {
            "evolution_mode": "inheritance_with_borrowing" if len(parents) > 1 else "vertical_inheritance",
            "evolution_context_digest": stable_digest(context),
        }
    )
    payload["metadata"] = metadata
    payload["usage_rules"] = (
        f"{card.usage_rules}\nGeneration {generation} retains the parent contract; "
        "validation failures and discussion summaries are recorded in provenance for an explicit evolver to repair."
    )
    payload["empirical_profile"] = {"profiled": 0.0, "generation": float(generation)}
    payload["profile_ids"] = []
    return DialectCard.model_validate(payload)


def _checkpoint_generation(path: Path) -> int:
    try:
        return int(path.stem.split("-")[-1])
    except ValueError as exc:
        raise ValueError(f"invalid generation checkpoint name: {path.name}") from exc


def _load_generation(path: Path) -> tuple[int, list[DialectCard], float | None, int]:
    value = read_json(path)
    if not isinstance(value, dict) or not isinstance(value.get("records"), list):
        raise ValueError(f"malformed generation checkpoint: {path}")
    generation = int(value.get("generation", _checkpoint_generation(path)))
    if generation != _checkpoint_generation(path):
        raise ValueError(f"checkpoint generation does not match filename: {path}")
    cards = [DialectCard.model_validate(row) for row in value["records"]]
    if any(card.generation != generation for card in cards):
        raise ValueError(f"checkpoint contains cards from another generation: {path}")
    score_raw = value.get("validation_score")
    score = float(score_raw) if score_raw is not None else None
    saturation_count = int(value.get("saturation_count", 0))
    return generation, cards, score, saturation_count


def evolve(
    cards: Sequence[DialectCard],
    *,
    validation_failures: Sequence[Mapping[str, JsonValue]] = (),
    discussion_summaries: Sequence[str] = (),
    max_generations: int = 1,
    patience: int = 1,
    min_delta: float = 0.0,
    enable_horizontal_borrowing: bool = True,
    output_dir: str | Path,
    evolver: CardEvolver | None = None,
    score_generation: Callable[[Sequence[DialectCard]], float] | None = None,
    resume: bool = True,
) -> list[DialectCard]:
    """Evolve cards with atomic checkpoints and validation-based saturation.

    Without ``score_generation`` there is no evidentiary basis for early
    stopping, so all requested generations are run.  The default evolver is a
    provenance-preserving reference implementation; research runs should pass
    a semantic evolver backed by their configured provider.
    """

    if max_generations < 0:
        raise ValueError("max_generations cannot be negative")
    if patience <= 0:
        raise ValueError("patience must be positive")
    if min_delta < 0:
        raise ValueError("min_delta cannot be negative")
    if not cards:
        raise ValueError("at least one card is required")
    failures = _validated_failures(validation_failures)
    summaries = [summary for summary in discussion_summaries if summary.strip()]
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    current = sorted(cards, key=lambda card: card.dialect_id)
    start_generation = current[0].generation
    if any(card.generation != start_generation for card in current):
        raise ValueError("input cards must belong to a single generation")
    best_score: float | None = score_generation(current) if score_generation is not None else None
    saturation_count = 0

    checkpoints = sorted(directory.glob("generation-*.json"), key=_checkpoint_generation)
    if not resume:
        for checkpoint in checkpoints:
            if _checkpoint_generation(checkpoint) > start_generation:
                checkpoint.unlink()
        checkpoints = [
            checkpoint for checkpoint in checkpoints if _checkpoint_generation(checkpoint) <= start_generation
        ]
    if resume and checkpoints:
        last_generation, loaded, loaded_score, loaded_saturation = _load_generation(checkpoints[-1])
        if last_generation >= start_generation:
            current = loaded
            start_generation = last_generation
            best_score = (
                loaded_score
                if loaded_score is not None or score_generation is None
                else score_generation(loaded)
            )
            saturation_count = loaded_saturation

    if not checkpoints or _checkpoint_generation(checkpoints[-1]) < start_generation:
        write_json_atomic(
            directory / f"generation-{start_generation:03d}.json",
            {
                "generation": start_generation,
                "validation_score": best_score,
                "saturation_count": saturation_count,
                "records": current,
            },
        )

    final_generation = cards[0].generation + max_generations
    for generation in range(start_generation + 1, final_generation + 1):
        context: dict[str, JsonValue] = {
            "generation": generation,
            "validation_failures": cast(JsonValue, failures),
            "discussion_summaries": cast(JsonValue, summaries),
            "previous_generation_ids": cast(JsonValue, [card.dialect_id for card in current]),
        }
        next_cards: list[DialectCard] = []
        for index, card in enumerate(current):
            peer = (
                current[(index + 1) % len(current)]
                if enable_horizontal_borrowing and len(current) > 1
                else None
            )
            if evolver is None:
                evolved = _default_evolve_card(card, peer, generation=generation, context=context)
            else:
                raw = evolver(card, context)
                evolved = raw if isinstance(raw, DialectCard) else DialectCard.model_validate(raw)
            if evolved.generation != generation:
                raise ValueError("evolver returned a card with the wrong generation")
            if card.dialect_id not in evolved.parent_ids:
                raise ValueError("evolved cards must retain vertical inheritance from their direct parent")
            next_cards.append(evolved)
        current = sorted(
            {card.dialect_id: card for card in next_cards}.values(), key=lambda card: card.dialect_id
        )

        score = score_generation(current) if score_generation is not None else None
        if score is not None:
            if not math.isfinite(score):
                raise ValueError("generation validation score must be finite")
            if best_score is None or score > best_score + min_delta:
                best_score = score
                saturation_count = 0
            else:
                saturation_count += 1
        write_json_atomic(
            directory / f"generation-{generation:03d}.json",
            {
                "generation": generation,
                "validation_score": score,
                "best_validation_score": best_score,
                "saturation_count": saturation_count,
                "records": current,
            },
        )
        if score_generation is not None and saturation_count >= patience:
            break
    return current


def binomial_confidence_interval(
    successes: int, total: int, *, z: float = 1.959963984540054
) -> tuple[float, float]:
    """Wilson score interval for binary per-item correctness."""

    if total <= 0:
        return (0.0, 1.0)
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    margin = z * math.sqrt((proportion * (1.0 - proportion) + z * z / (4.0 * total)) / total) / denominator
    return (max(0.0, center - margin), min(1.0, center + margin))


def _dialect_system_prompt(card: DialectCard) -> str:
    return (
        "Apply this machine dialect as an internal reasoning and answer contract. "
        "If it is unsafe or unclear, follow its fallback.\n"
        f"V symbol inventory: {card.symbol_inventory}\n"
        f"G grammar: {card.grammar}\n"
        f"O reasoning operators: {card.reasoning_operators}\n"
        f"R validity and usage rules: {card.usage_rules}\n"
        f"rho empirical profile: {canonical_json(card.empirical_profile)}\n"
        f"Input contract: {card.input_contract}\n"
        f"Output contract: {card.output_contract}\n"
        f"Fallback: {card.fallback}"
    )


def profile(
    tasks: Sequence[TaskRecord],
    cards: Sequence[DialectCard],
    providers: ProviderMap | ChatProvider,
    evaluator: Evaluator,
    *,
    split: DataSplit,
    output_path: str | Path | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.0,
    seed: int = 0,
    token_penalty: float = 0.0001,
    parse_failure_penalty: float = 0.25,
) -> list[DialectProfile]:
    """Measure the complete speaker-card by listener transfer matrix."""

    if split not in VALIDATION_SPLITS:
        raise ValueError("profile is restricted to evolution_validation or router_validation")
    provider_by_listener = _provider_map(providers)
    for task in tasks:
        _require_split(task, {split}, "profile")
    if len({task.task_id for task in tasks}) != len(tasks):
        raise ValueError("profile tasks contain duplicate task IDs")

    profiles: list[DialectProfile] = []
    for card in sorted(cards, key=lambda item: item.dialect_id):
        for listener_id, provider in sorted(provider_by_listener.items()):
            observations: list[ProfileObservation] = []
            tags_by_task: dict[str, tuple[str, ...]] = {}
            for task in tasks:
                view = task.to_view()
                request = CompletionRequest(
                    model=_provider_model(provider, listener_id),
                    messages=(
                        ChatMessage(role="system", content=_dialect_system_prompt(card)),
                        ChatMessage(role="user", content=view.query),
                    ),
                    max_tokens=max_tokens,
                    temperature=temperature,
                    seed=seed,
                    metadata={
                        "stage": "profile",
                        "task_id": view.task_id,
                        "public_digest": view.public_digest,
                        "dialect_id": card.dialect_id,
                        "specification_digest": card.specification_digest,
                        "listener_id": listener_id,
                    },
                )
                completion = provider.complete(request)
                evaluation = evaluator.evaluate(task, completion.text)
                if evaluation.correct is None:
                    raise ValueError("profile evaluators must return item-level correctness")
                observations.append(
                    ProfileObservation(
                        task_id=task.task_id,
                        correct=evaluation.correct,
                        completion_tokens=completion.completion_tokens,
                        parse_failure=evaluation.parse_failure,
                        latency_ms=completion.latency_ms,
                        cost=completion.cost,
                        score=evaluation.score,
                    )
                )
                tags_by_task[task.task_id] = _task_tags(task)
            successes = sum(observation.correct for observation in observations)
            mean_tokens = (
                sum(observation.completion_tokens for observation in observations) / len(observations)
                if observations
                else 0.0
            )
            parse_rate = (
                sum(observation.parse_failure for observation in observations) / len(observations)
                if observations
                else 0.0
            )
            accuracy = successes / len(observations) if observations else 0.0
            conditioned: dict[str, JsonValue] = {}
            all_tags = sorted({tag for tags in tags_by_task.values() for tag in tags})
            for tag in all_tags:
                subset = [item for item in observations if tag in tags_by_task[item.task_id]]
                conditioned[tag] = {
                    "n_items": len(subset),
                    "accuracy": sum(item.correct for item in subset) / len(subset),
                    "mean_completion_tokens": sum(item.completion_tokens for item in subset) / len(subset),
                    "parse_failure_rate": sum(item.parse_failure for item in subset) / len(subset),
                }
            profiles.append(
                DialectProfile(
                    dialect_id=card.dialect_id,
                    listener_id=listener_id,
                    split=split,
                    observations=tuple(observations),
                    confidence_interval=binomial_confidence_interval(successes, len(observations)),
                    utility=accuracy - token_penalty * mean_tokens - parse_failure_penalty * parse_rate,
                    metadata={
                        "specification_digest": card.specification_digest,
                        "task_conditioned": conditioned,
                        "token_penalty": token_penalty,
                        "parse_failure_penalty": parse_failure_penalty,
                    },
                )
            )
    if output_path is not None:
        write_jsonl_atomic(output_path, profiles)
    return profiles


ProfileSummary: TypeAlias = tuple[int, float, float, float, float, float, float]


def _profile_summary(profiles: Sequence[DialectProfile]) -> ProfileSummary:
    observations = [item for profile in profiles for item in profile.observations]
    if not observations:
        return (0, 0.0, math.inf, 1.0, math.inf, math.inf, -math.inf)
    n_items = len(observations)
    accuracy = sum(item.correct for item in observations) / n_items
    tokens = sum(item.completion_tokens for item in observations) / n_items
    parse_rate = sum(item.parse_failure for item in observations) / n_items
    latency = sum(item.latency_ms for item in observations) / n_items
    cost = sum(item.cost for item in observations) / n_items
    utilities = [profile.utility for profile in profiles if profile.utility is not None]
    utility = sum(utilities) / len(utilities) if utilities else accuracy
    return (n_items, accuracy, tokens, parse_rate, latency, cost, utility)


def _dominates(left: ProfileSummary, right: ProfileSummary, metrics: Sequence[str]) -> bool:
    positions = {"accuracy": 1, "tokens": 2, "parse_failures": 3, "latency": 4, "cost": 5}
    comparisons: list[tuple[float, float, bool]] = []
    for metric in metrics:
        position = positions[metric]
        comparisons.append((left[position], right[position], metric == "accuracy"))
    weak = all(
        left_value >= right_value if maximize else left_value <= right_value
        for left_value, right_value, maximize in comparisons
    )
    strict = any(
        left_value > right_value if maximize else left_value < right_value
        for left_value, right_value, maximize in comparisons
    )
    return weak and strict


def select(
    cards: Sequence[DialectCard],
    profiles: Sequence[DialectProfile],
    *,
    min_support: int = 1,
    max_cards: int | None = None,
    minimum_speakers: int = 1,
    pareto_metrics: Sequence[str] = ("accuracy", "tokens", "parse_failures"),
    diversity_key: str | None = "creator_id",
    output_path: str | Path | None = None,
) -> list[DialectCard]:
    """Freeze a validation-selected Pareto bank with optional source diversity."""

    if min_support <= 0:
        raise ValueError("min_support must be positive")
    if max_cards is not None and max_cards <= 0:
        raise ValueError("max_cards must be positive when set")
    if minimum_speakers <= 0:
        raise ValueError("minimum_speakers must be positive")
    if max_cards is not None and minimum_speakers > max_cards:
        raise ValueError("minimum_speakers cannot exceed max_cards")
    supported_metrics = {"accuracy", "tokens", "parse_failures", "latency", "cost"}
    if not pareto_metrics or any(metric not in supported_metrics for metric in pareto_metrics):
        raise ValueError("pareto_metrics must contain supported accuracy/resource metrics")
    for item in profiles:
        if item.split not in VALIDATION_SPLITS:
            raise ValueError("select accepts validation profiles only")
    cards_by_id = {card.dialect_id: card for card in cards}
    if len(cards_by_id) != len(cards):
        raise ValueError("candidate bank contains duplicate dialect IDs")
    grouped: dict[str, list[DialectProfile]] = defaultdict(list)
    for item in profiles:
        if item.dialect_id not in cards_by_id:
            raise ValueError(f"profile references unknown dialect: {item.dialect_id}")
        if item.task_tag is None:
            grouped[item.dialect_id].append(item)
    summaries = {
        dialect_id: _profile_summary(items)
        for dialect_id, items in grouped.items()
        if _profile_summary(items)[0] >= min_support
    }
    pareto_ids = [
        dialect_id
        for dialect_id, summary in summaries.items()
        if not any(
            other_id != dialect_id and _dominates(other_summary, summary, pareto_metrics)
            for other_id, other_summary in summaries.items()
        )
    ]
    ranked = sorted(
        pareto_ids,
        key=lambda dialect_id: (
            -summaries[dialect_id][6],
            -summaries[dialect_id][1],
            summaries[dialect_id][2],
            summaries[dialect_id][3],
            dialect_id,
        ),
    )
    if max_cards is not None and diversity_key:
        diverse: list[str] = []
        seen: set[str] = set()
        for dialect_id in ranked:
            card = cards_by_id[dialect_id]
            if diversity_key == "creator_id":
                value = card.creator_id
            elif diversity_key == "speaker_id":
                value = card.speaker_ids[0]
            else:
                raw = card.metadata.get(diversity_key, "")
                value = str(raw)
            if value not in seen:
                seen.add(value)
                diverse.append(dialect_id)
                if len(diverse) == max_cards:
                    break
        if len(diverse) < max_cards:
            diverse.extend(dialect_id for dialect_id in ranked if dialect_id not in set(diverse))
        ranked = diverse
    if max_cards is not None:
        ranked = ranked[:max_cards]
    selected: list[DialectCard] = []
    for dialect_id in ranked:
        card = cards_by_id[dialect_id]
        support, accuracy, tokens, parse_rate, latency, cost, utility = summaries[dialect_id]
        profile_ids = tuple(sorted(item.profile_id for item in grouped[dialect_id]))
        payload = card.model_dump(mode="json")
        payload["empirical_profile"] = {
            "profiled": 1.0,
            "validation_support": float(support),
            "validation_accuracy": accuracy,
            "validation_mean_completion_tokens": tokens,
            "validation_parse_failure_rate": parse_rate,
            "validation_mean_latency_ms": latency,
            "validation_mean_cost": cost,
            "validation_utility": utility,
        }
        payload["profile_ids"] = list(profile_ids)
        selected.append(DialectCard.model_validate(payload))
    selected_speakers = {speaker for card in selected for speaker in card.speaker_ids}
    if len(selected_speakers) < minimum_speakers:
        raise ValueError("the validation-selected Pareto bank cannot satisfy the configured minimum_speakers")
    if output_path is not None:
        write_json_atomic(
            output_path,
            {
                "selection_basis": "validation_only_pareto",
                "validation_splits": sorted({profile.split.value for profile in profiles}),
                "min_support": min_support,
                "max_cards": max_cards,
                "minimum_speakers": minimum_speakers,
                "pareto_metrics": list(pareto_metrics),
                "diversity_key": diversity_key,
                "candidate_pool": sorted(cards_by_id),
                "records": selected,
                "profile_summary": {
                    key: {
                        "n_items": value[0],
                        "accuracy": value[1],
                        "mean_completion_tokens": value[2],
                        "parse_failure_rate": value[3],
                        "mean_latency_ms": value[4],
                        "mean_cost": value[5],
                        "utility": value[6],
                    }
                    for key, value in sorted(summaries.items())
                },
            },
        )
    return selected


__all__ = [
    "CardEvolver",
    "CardFactory",
    "ChatProvider",
    "DatasetAdapter",
    "Evaluator",
    "ProviderMap",
    "VALIDATION_SPLITS",
    "binomial_confidence_interval",
    "collect",
    "create",
    "evolve",
    "profile",
    "select",
    "select_top_k_traces",
]
