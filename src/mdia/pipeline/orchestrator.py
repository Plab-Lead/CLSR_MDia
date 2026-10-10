"""End-to-end orchestration and immutable split/run manifests."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mdia.pipeline.execution import ControllerRouter, DialectRouter, RunArtifacts, run
from mdia.pipeline.io import (
    artifact_checksum,
    immutable_write,
    read_json,
    write_json_atomic,
    write_jsonl_atomic,
)
from mdia.pipeline.lifecycle import (
    CardEvolver,
    CardFactory,
    ChatProvider,
    DatasetAdapter,
    Evaluator,
    ProviderMap,
    collect,
    create,
    evolve,
    profile,
    select,
)
from mdia.reporting import build_report
from mdia.rules.validation import EvidenceInput, validate_rules
from mdia.schemas import (
    DataSplit,
    DialectCard,
    DialectProfile,
    JsonValue,
    RouteBudget,
    RuleResult,
    RuleSpec,
    RunManifest,
    TaskRecord,
    TraceRecord,
    stable_digest,
    task_manifest_digest,
)


@dataclass(frozen=True)
class PipelineLayout:
    root: Path
    splits: Path
    dialects: Path
    profiles: Path
    selection: Path
    execution: Path
    rules: Path

    @classmethod
    def create(cls, root: str | Path) -> PipelineLayout:
        run_root = Path(root)
        layout = cls(
            root=run_root,
            splits=run_root / "splits",
            dialects=run_root / "dialects",
            profiles=run_root / "profiles",
            selection=run_root / "selection",
            execution=run_root / "execution",
            rules=run_root / "rules",
        )
        for directory in (
            layout.root,
            layout.splits,
            layout.dialects,
            layout.profiles,
            layout.selection,
            layout.execution,
            layout.rules,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        return layout


@dataclass(frozen=True)
class PipelineArtifacts:
    layout: PipelineLayout
    traces: tuple[TraceRecord, ...]
    evolved_cards: tuple[DialectCard, ...]
    evolution_profiles: tuple[DialectProfile, ...]
    router_profiles: tuple[DialectProfile, ...]
    frozen_bank: tuple[DialectCard, ...]
    execution: RunArtifacts
    rule_results: tuple[RuleResult, ...]
    manifest: RunManifest
    report_path: Path


class _ManifestAdapter:
    def __init__(self, records: Mapping[DataSplit, Sequence[TaskRecord]]) -> None:
        self._records = records

    def load(self, split: DataSplit) -> Iterable[TaskRecord]:
        return tuple(self._records.get(split, ()))


def freeze_splits(adapter: DatasetAdapter, output_dir: str | Path) -> dict[DataSplit, list[TaskRecord]]:
    """Materialize each split once and reject identity overlap before any calls."""

    directory = Path(output_dir)
    records: dict[DataSplit, list[TaskRecord]] = {}
    owner: dict[str, DataSplit] = {}
    for split in DataSplit:
        items = list(adapter.load(split))
        if len({item.task_id for item in items}) != len(items):
            raise ValueError(f"{split.value} manifest contains duplicate task IDs")
        for item in items:
            if item.split is not split:
                raise ValueError(f"adapter returned {item.split.value} from load({split.value})")
            previous = owner.get(item.task_id)
            if previous is not None:
                raise ValueError(f"task {item.task_id} appears in both {previous.value} and {split.value}")
            owner[item.task_id] = split
        records[split] = items
        immutable_write(
            directory / f"{split.value}.json",
            {
                "split": split.value,
                "content_hash": task_manifest_digest(items),
                "records": items,
            },
        )
    return records


def _section(config: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = config.get(key, {})
    return value if isinstance(value, Mapping) else {}


def _checksums(root: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if (
            not path.is_file()
            or path.name in {"manifest.json", "SHA256SUMS.json"}
            or path.name.startswith(".")
        ):
            continue
        checksums[path.relative_to(root).as_posix()] = artifact_checksum(path)
    return checksums


def validate_existing_run(root: str | Path, config_hash: str | None = None) -> RunManifest | None:
    """Reject config drift or mutation of artifacts covered by an existing manifest."""

    run_root = Path(root)
    manifest_path = run_root / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = RunManifest.model_validate(read_json(manifest_path))
    if config_hash is not None and manifest.config_hash != config_hash:
        raise ValueError("the existing run uses a different config hash; choose a new run_id or --run-dir")
    for relative, expected in manifest.artifact_checksums.items():
        path = run_root / relative
        if not path.is_file():
            raise ValueError(f"resume artifact listed by the manifest is missing: {relative}")
        if artifact_checksum(path) != expected:
            raise ValueError(f"resume artifact checksum mismatch: {relative}")
    return manifest


def _manifest(
    *,
    root: Path,
    config: Mapping[str, Any],
    splits: Mapping[DataSplit, Sequence[TaskRecord]],
    bank: Sequence[DialectCard],
    code_revision: str,
    provider_revision: str,
    model_revisions: Mapping[str, str],
    seeds: Mapping[str, int],
    config_hash: str | None = None,
    created_at: datetime | None = None,
) -> RunManifest:
    return RunManifest(
        run_id=root.name,
        created_at=created_at or datetime.now(timezone.utc),
        code_revision=code_revision,
        config_hash=config_hash or stable_digest(config),
        provider_revision=provider_revision,
        model_revisions=dict(model_revisions),
        seeds=dict(seeds),
        split_hashes={split: task_manifest_digest(records) for split, records in splits.items()},
        candidate_pool=tuple(card.dialect_id for card in bank),
        artifact_checksums=_checksums(root),
        metadata={
            "pipeline": "mdia",
            "clsr_special_case": bool(config.get("preset") == "clsr"),
            "selection_evidence": "validation_only",
        },
    )


def run_pipeline(
    adapter: DatasetAdapter,
    providers: ProviderMap | ChatProvider,
    evaluator: Evaluator,
    router: DialectRouter,
    *,
    run_dir: str | Path,
    budget: RouteBudget,
    config: Mapping[str, Any] | None = None,
    config_hash: str | None = None,
    speaker_providers: ProviderMap | ChatProvider | None = None,
    listener_providers: ProviderMap | ChatProvider | None = None,
    card_factory: CardFactory | None = None,
    evolver: CardEvolver | None = None,
    controller_router: ControllerRouter | None = None,
    controller_profile: Mapping[str, Any] | None = None,
    judge_provider: ChatProvider | None = None,
    rule_evidence: EvidenceInput | None = None,
    rule_specs: Sequence[RuleSpec] | None = None,
    discussion_summaries: Sequence[str] = (),
    code_revision: str = "unknown",
    provider_revision: str = "unspecified",
    model_revisions: Mapping[str, str] | None = None,
    seed: int = 0,
    resume: bool = True,
) -> PipelineArtifacts:
    """Run the complete offline-capable eight-stage pipeline."""

    settings: Mapping[str, Any] = dict(config or {})
    settings_hash = settings.get("_config_hash")
    if settings_hash is not None and not isinstance(settings_hash, str):
        raise ValueError("config['_config_hash'] must be a SHA-256 string")
    if config_hash is not None and settings_hash is not None and config_hash != settings_hash:
        raise ValueError("config_hash disagrees with config['_config_hash']")
    effective_config_hash = config_hash or settings_hash
    if effective_config_hash is not None and re.fullmatch(r"[0-9a-f]{64}", effective_config_hash) is None:
        raise ValueError("config_hash must be a lowercase SHA-256 hex digest")
    speakers = speaker_providers or providers
    listeners = listener_providers or providers
    create_settings = _section(settings, "create")
    evolve_settings = _section(settings, "evolve")
    profile_settings = _section(settings, "profile")
    select_settings = _section(settings, "select")
    layout = PipelineLayout.create(run_dir)
    existing_manifest = validate_existing_run(layout.root, effective_config_hash)
    created_at = existing_manifest.created_at if existing_manifest is not None else None
    split_records = freeze_splits(adapter, layout.splits)
    frozen_adapter = _ManifestAdapter(split_records)

    traces = collect(
        frozen_adapter,
        speakers,
        evaluator,
        output_path=layout.root / "direct_traces.jsonl",
        resume=resume,
        max_tokens=int(_section(settings, "collect").get("max_tokens", 2048)),
        temperature=float(_section(settings, "collect").get("temperature", 0.0)),
        seed=seed,
    )
    initial_cards = create(
        traces,
        top_k=int(create_settings.get("top_k", 1)),
        speaker_diversity=bool(create_settings.get("speaker_diversity", False)),
        creator_ids=tuple(str(item) for item in create_settings.get("creator_ids", ())),
        card_factory=card_factory,
        output_path=layout.dialects / "generation-000.json",
    )
    validation_cache: dict[tuple[str, ...], list[DialectProfile]] = {}

    def generation_profiles(cards: Sequence[DialectCard]) -> list[DialectProfile]:
        key = tuple(card.dialect_id for card in cards)
        if key not in validation_cache:
            generation = cards[0].generation
            validation_cache[key] = profile(
                split_records[DataSplit.EVOLUTION_VALIDATION],
                cards,
                listeners,
                evaluator,
                split=DataSplit.EVOLUTION_VALIDATION,
                output_path=layout.profiles / f"evolution_generation-{generation:03d}.jsonl",
                max_tokens=int(profile_settings.get("max_tokens", 2048)),
                temperature=float(profile_settings.get("temperature", 0.0)),
                seed=seed,
                token_penalty=float(profile_settings.get("token_penalty", 0.0001)),
                parse_failure_penalty=float(profile_settings.get("parse_failure_penalty", 0.25)),
            )
        return validation_cache[key]

    def generation_score(cards: Sequence[DialectCard]) -> float:
        profiles = generation_profiles(cards)
        utilities = [item.utility for item in profiles if item.utility is not None]
        return sum(utilities) / len(utilities) if utilities else 0.0

    initial_profiles = generation_profiles(initial_cards)
    validation_failures: list[dict[str, JsonValue]] = [
        {
            "split": DataSplit.EVOLUTION_VALIDATION.value,
            "task_id": observation.task_id,
            "dialect_id": item.dialect_id,
            "listener_id": item.listener_id,
            "parse_failure": observation.parse_failure,
        }
        for item in initial_profiles
        for observation in item.observations
        if not observation.correct or observation.parse_failure
    ]
    evolved_cards = evolve(
        initial_cards,
        validation_failures=(
            validation_failures if bool(evolve_settings.get("include_failure_summaries", True)) else ()
        ),
        discussion_summaries=discussion_summaries,
        max_generations=int(evolve_settings.get("max_generations", 1)),
        patience=int(evolve_settings.get("patience", 1)),
        min_delta=float(evolve_settings.get("min_delta", 0.0)),
        enable_horizontal_borrowing=bool(evolve_settings.get("horizontal_borrowing", True)),
        output_dir=layout.dialects,
        evolver=evolver,
        score_generation=generation_score,
        resume=resume,
    )
    evolution_profiles = generation_profiles(evolved_cards)
    write_jsonl_atomic(layout.profiles / "evolution_validation.jsonl", evolution_profiles)
    frozen_bank = select(
        evolved_cards,
        evolution_profiles,
        min_support=int(select_settings.get("min_support", 1)),
        max_cards=int(select_settings["max_cards"]) if select_settings.get("max_cards") is not None else None,
        minimum_speakers=int(select_settings.get("minimum_speakers", 1)),
        pareto_metrics=tuple(
            str(item)
            for item in select_settings.get("pareto_metrics", ("accuracy", "tokens", "parse_failures"))
        ),
        diversity_key=str(select_settings.get("diversity_key", "creator_id"))
        if select_settings.get("diversity_key") is not None
        else None,
        output_path=layout.selection / "frozen_dialect_bank.json",
    )
    router_profiles = profile(
        split_records[DataSplit.ROUTER_VALIDATION],
        frozen_bank,
        listeners,
        evaluator,
        split=DataSplit.ROUTER_VALIDATION,
        output_path=layout.profiles / "router_validation.jsonl",
        max_tokens=int(profile_settings.get("max_tokens", 2048)),
        temperature=float(profile_settings.get("temperature", 0.0)),
        seed=seed,
        token_penalty=float(profile_settings.get("token_penalty", 0.0001)),
        parse_failure_penalty=float(profile_settings.get("parse_failure_penalty", 0.25)),
    )
    execution = run(
        split_records[DataSplit.TEST],
        frozen_bank,
        router,
        listeners,
        evaluator,
        profiles=router_profiles,
        budget=budget,
        output_dir=layout.execution,
        controller_router=controller_router,
        controller_profile=controller_profile,
        judge_provider=judge_provider,
        temperature=float(_section(settings, "run").get("temperature", 0.0)),
        seed=seed,
        resume=resume,
    )
    rules_settings = _section(settings, "rules")
    if rules_settings.get("enabled", True) is False:
        rule_results: list[RuleResult] = []
        write_json_atomic(
            layout.rules / "results.json",
            {
                "enabled": False,
                "reason": "rule validation is disabled by the active preset",
                "n_rules": 0,
                "records": [],
            },
        )
    else:
        rule_results = validate_rules(
            rule_evidence or {},
            specs=rule_specs,
            output_dir=layout.rules,
            seed=int(rules_settings.get("seed", seed)),
            iterations=int(rules_settings.get("iterations", 4000)),
            alpha=float(rules_settings.get("alpha", 0.05)),
        )

    draft = _manifest(
        root=layout.root,
        config=settings,
        splits=split_records,
        bank=frozen_bank,
        code_revision=code_revision,
        provider_revision=provider_revision,
        model_revisions=model_revisions or {},
        seeds={"pipeline": seed},
        config_hash=effective_config_hash,
        created_at=created_at,
    )
    write_json_atomic(layout.root / "manifest.json", draft)
    report_path = build_report(layout.root)
    manifest = _manifest(
        root=layout.root,
        config=settings,
        splits=split_records,
        bank=frozen_bank,
        code_revision=code_revision,
        provider_revision=provider_revision,
        model_revisions=model_revisions or {},
        seeds={"pipeline": seed},
        config_hash=effective_config_hash,
        created_at=created_at,
    )
    write_json_atomic(layout.root / "manifest.json", manifest)
    return PipelineArtifacts(
        layout=layout,
        traces=tuple(traces),
        evolved_cards=tuple(evolved_cards),
        evolution_profiles=tuple(evolution_profiles),
        router_profiles=tuple(router_profiles),
        frozen_bank=tuple(frozen_bank),
        execution=execution,
        rule_results=tuple(rule_results),
        manifest=manifest,
        report_path=report_path,
    )


__all__ = [
    "PipelineArtifacts",
    "PipelineLayout",
    "freeze_splits",
    "run_pipeline",
    "validate_existing_run",
]
