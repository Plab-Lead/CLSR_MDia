"""Command-line entry point for the canonical MDia lifecycle."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mdia import __version__
from mdia.config import ConfigError, RunConfig, load_config
from mdia.datasets import JsonlDatasetAdapter
from mdia.evaluation import Evaluator, build_evaluator
from mdia.pipeline import (
    PipelineLayout,
    build_report,
    collect,
    create,
    evolve,
    freeze_splits,
    profile,
    run,
    run_pipeline,
    select,
    validate_existing_run,
    validate_rules,
)
from mdia.pipeline.io import (
    artifact_checksum,
    read_json,
    read_jsonl,
    read_models,
    write_json_atomic,
)
from mdia.providers import ChatProvider, build_provider
from mdia.routing import MetadataControllerRouter, UtilityDialectRouter
from mdia.schemas import (
    DataSplit,
    DialectCard,
    DialectProfile,
    JsonValue,
    RouteBudget,
    RuleSpec,
    RunManifest,
    TraceRecord,
)

STAGES = (
    "collect",
    "create",
    "evolve",
    "profile",
    "select",
    "run",
    "validate-rules",
    "report",
    "pipeline",
)


@dataclass(frozen=True)
class Runtime:
    config: RunConfig
    run_dir: Path
    layout: PipelineLayout
    adapter: JsonlDatasetAdapter
    speaker_providers: dict[str, ChatProvider]
    listener_providers: dict[str, ChatProvider]
    evaluator: Evaluator


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mdia",
        description="Create, evolve, profile, select, and route machine dialects.",
    )
    parser.add_argument("--version", action="version", version=f"mdia {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    descriptions = {
        "collect": "Collect heterogeneous direct-answer traces.",
        "create": "Create generation-0 concrete LSF cards.",
        "evolve": "Evolve cards through inheritance and borrowing.",
        "profile": "Measure speaker-dialect to listener transfer on validation data.",
        "select": "Freeze a validation-selected dialect bank.",
        "run": "Route frozen dialects, execute them, and score held-out predictions.",
        "validate-rules": "Validate the declared sociolinguistic rules.",
        "report": "Build the reproducibility report.",
        "pipeline": "Run the complete eight-stage workflow.",
    }
    for command in STAGES:
        child = subparsers.add_parser(command, help=descriptions[command], description=descriptions[command])
        child.add_argument(
            "--config", required=True, type=Path, help="Validated YAML or JSON run configuration."
        )
        child.add_argument("--run-dir", type=Path, help="Override the configured run directory.")
        child.add_argument(
            "--no-resume",
            action="store_true",
            help="Do not reuse compatible stage checkpoints.",
        )
        if command == "validate-rules":
            child.add_argument(
                "--evidence",
                type=Path,
                help="Optional JSON rule-evidence mapping; missing evidence remains not_evaluated.",
            )
    return parser


def _provider_map(config: RunConfig, model_ids: Sequence[str]) -> dict[str, ChatProvider]:
    base_dir = config.source_path.parent if config.source_path is not None else Path.cwd()
    return {
        model_id: build_provider(config.provider.model_copy(update={"model": model_id}), base_dir=base_dir)
        for model_id in dict.fromkeys(model_ids)
    }


def _runtime(config_path: Path, run_dir_override: Path | None) -> Runtime:
    config = load_config(config_path)
    configured_root = config.resolve_path(config.output_dir)
    run_id = config.run_id or f"mdia-{config.config_hash[:12]}"
    run_dir = (
        run_dir_override.expanduser().resolve() if run_dir_override is not None else configured_root / run_id
    )
    base_dir = config.source_path.parent if config.source_path is not None else Path.cwd()
    validate_existing_run(run_dir, config.config_hash)
    return Runtime(
        config=config,
        run_dir=run_dir,
        layout=PipelineLayout.create(run_dir),
        adapter=JsonlDatasetAdapter(config.dataset, base_dir=base_dir),
        speaker_providers=_provider_map(config, config.community.speakers),
        listener_providers=_provider_map(config, config.community.listeners),
        evaluator=build_evaluator(config.evaluator),
    )


def _settings(config: RunConfig) -> dict[str, Any]:
    """Translate the public RunConfig into the pipeline's narrow stage knobs."""

    return {
        "_config_hash": config.config_hash,
        "schema_version": config.schema_version,
        "preset": config.community.preset,
        "collect": {
            "max_tokens": config.provider.max_tokens,
            "temperature": config.provider.temperature,
        },
        "create": {
            "top_k": config.creation.top_k_per_task,
            "speaker_diversity": config.creation.enforce_speaker_diversity,
            "creator_ids": list(config.community.creators),
        },
        "evolve": {
            "max_generations": config.evolution.max_generations,
            "patience": config.evolution.saturation_patience,
            "min_delta": config.evolution.minimum_improvement,
            "inherit_previous_generation": config.evolution.inherit_previous_generation,
            "horizontal_borrowing": config.evolution.enable_horizontal_borrowing,
            "include_failure_summaries": config.evolution.include_failure_summaries,
        },
        "profile": {
            "max_tokens": config.provider.max_tokens,
            "temperature": config.provider.temperature,
            "token_penalty": config.routing.token_penalty,
            "parse_failure_penalty": config.routing.parse_failure_penalty,
        },
        "select": {
            "min_support": config.selection.minimum_support,
            "max_cards": config.selection.max_cards,
            "minimum_speakers": config.selection.minimum_speakers,
            "pareto_metrics": list(config.selection.pareto_metrics),
            "diversity_key": "creator_id" if config.selection.enforce_creator_diversity else None,
        },
        "routing": config.routing.model_dump(mode="json"),
        "controller": config.controller.model_dump(mode="json"),
        "run": {"temperature": config.provider.temperature},
        "rules": {
            "enabled": config.rules.enabled,
            "iterations": max(config.rules.bootstrap_samples, config.rules.permutation_samples),
            "alpha": config.rules.familywise_fdr,
            "seed": config.rules.seed if config.rules.seed is not None else config.seed,
        },
        "metadata": config.metadata,
    }


def _budget(config: RunConfig) -> RouteBudget:
    return RouteBudget(token_budget=config.routing.token_budget, max_steps=config.routing.max_steps)


def _router(runtime: Runtime) -> UtilityDialectRouter:
    return UtilityDialectRouter(runtime.config.routing, listener_id=runtime.config.community.listeners[0])


def _controller_router(runtime: Runtime) -> MetadataControllerRouter | None:
    config = runtime.config.controller
    if not config.enabled:
        return None
    return MetadataControllerRouter(
        routes=config.routes or None,
        key_fields=config.key_fields or None,
        default_controller=config.default_controller,
        estimated_overhead=config.estimated_overhead,
        reasons=config.reasons,
        answer_contracts=config.answer_contracts,
    )


def _code_revision() -> str:
    override = os.environ.get("MDIA_CODE_REVISION")
    if override:
        return override
    root = Path(__file__).resolve().parents[2]
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return f"{revision}+dirty" if dirty else revision
    except (OSError, subprocess.CalledProcessError):
        return "working-tree"


def _latest_generation(layout: PipelineLayout) -> Path:
    candidates = sorted(layout.dialects.glob("generation-*.json"))
    if not candidates:
        raise FileNotFoundError("no dialect generation exists; run `mdia create` first")
    return candidates[-1]


def _frozen_bank(layout: PipelineLayout) -> list[DialectCard]:
    path = layout.selection / "frozen_dialect_bank.json"
    if not path.exists():
        raise FileNotFoundError("no frozen dialect bank exists; run `mdia select` first")
    return read_models(path, DialectCard)


def _artifact_checksums(root: Path) -> dict[str, str]:
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


def _write_manifest(runtime: Runtime, candidate_pool: Sequence[DialectCard] = ()) -> RunManifest:
    split_hashes = {split: runtime.adapter.manifest_hash(split) for split in DataSplit}
    manifest_path = runtime.run_dir / "manifest.json"
    created_at = datetime.now(timezone.utc)
    if manifest_path.exists():
        existing = RunManifest.model_validate(read_json(manifest_path))
        created_at = existing.created_at
    models = tuple(dict.fromkeys((*runtime.config.community.speakers, *runtime.config.community.listeners)))
    manifest = RunManifest(
        run_id=runtime.run_dir.name,
        created_at=created_at,
        code_revision=_code_revision(),
        config_hash=runtime.config.config_hash,
        provider_revision=runtime.config.provider.revision,
        model_revisions={model_id: runtime.config.provider.revision for model_id in models},
        seeds={"pipeline": runtime.config.seed},
        split_hashes=split_hashes,
        candidate_pool=tuple(card.dialect_id for card in candidate_pool),
        artifact_checksums=_artifact_checksums(runtime.run_dir),
        metadata={
            "pipeline": "mdia",
            "preset": runtime.config.community.preset,
            "clsr_special_case": runtime.config.community.preset == "clsr",
            "selection_evidence": "validation_only",
        },
    )
    write_json_atomic(manifest_path, manifest)
    return manifest


def _ensure_splits(runtime: Runtime) -> None:
    freeze_splits(runtime.adapter, runtime.layout.splits)


def _read_rule_specs(runtime: Runtime) -> list[RuleSpec] | None:
    configured = runtime.config.rules.registry_path
    if configured is None:
        return None
    return read_models(runtime.config.resolve_path(configured), RuleSpec)


def _read_evidence(path: Path | None) -> Any:
    if path is None:
        return {}
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"rule evidence does not exist: {resolved}")
    return json.loads(resolved.read_text(encoding="utf-8"))


def _disabled_rules(runtime: Runtime) -> None:
    runtime.layout.rules.mkdir(parents=True, exist_ok=True)
    write_json_atomic(
        runtime.layout.rules / "results.json",
        {
            "enabled": False,
            "preset": runtime.config.community.preset,
            "reason": "Cross-family ecology and sociolinguistic-rule analysis is disabled by this preset.",
            "n_rules": 0,
            "records": [],
        },
    )


def _execute_stage(args: argparse.Namespace) -> Path:
    runtime = _runtime(args.config, args.run_dir)
    config = runtime.config
    resume = not args.no_resume
    _ensure_splits(runtime)

    if args.command == "collect":
        collect(
            runtime.adapter,
            runtime.speaker_providers,
            runtime.evaluator,
            output_path=runtime.run_dir / "direct_traces.jsonl",
            resume=resume,
            max_tokens=config.provider.max_tokens,
            temperature=config.provider.temperature,
            seed=config.seed,
        )
        _write_manifest(runtime)
        return runtime.run_dir / "direct_traces.jsonl"

    if args.command == "create":
        trace_path = runtime.run_dir / "direct_traces.jsonl"
        if not trace_path.exists():
            raise FileNotFoundError("direct traces are missing; run `mdia collect` first")
        traces = [TraceRecord.model_validate(row) for row in read_jsonl(trace_path)]
        cards = create(
            traces,
            top_k=config.creation.top_k_per_task,
            speaker_diversity=config.creation.enforce_speaker_diversity,
            creator_ids=config.community.creators,
            output_path=runtime.layout.dialects / "generation-000.json",
        )
        if len(cards) < config.creation.minimum_correct_traces:
            raise ValueError("too few correct direct traces to satisfy creation.minimum_correct_traces")
        _write_manifest(runtime, cards)
        return runtime.layout.dialects / "generation-000.json"

    if args.command == "evolve":
        cards = read_models(_latest_generation(runtime.layout), DialectCard)
        validation_cache: dict[tuple[str, ...], list[DialectProfile]] = {}

        def generation_profiles(candidates: Sequence[DialectCard]) -> list[DialectProfile]:
            key = tuple(card.dialect_id for card in candidates)
            if key not in validation_cache:
                generation = candidates[0].generation
                validation_cache[key] = profile(
                    runtime.adapter.load(DataSplit.EVOLUTION_VALIDATION),
                    candidates,
                    runtime.listener_providers,
                    runtime.evaluator,
                    split=DataSplit.EVOLUTION_VALIDATION,
                    output_path=(runtime.layout.profiles / f"evolution_generation-{generation:03d}.jsonl"),
                    max_tokens=config.provider.max_tokens,
                    temperature=config.provider.temperature,
                    seed=config.seed,
                    token_penalty=config.routing.token_penalty,
                    parse_failure_penalty=config.routing.parse_failure_penalty,
                )
            return validation_cache[key]

        def generation_score(candidates: Sequence[DialectCard]) -> float:
            utilities = [item.utility for item in generation_profiles(candidates) if item.utility is not None]
            return sum(utilities) / len(utilities) if utilities else 0.0

        initial_profiles = generation_profiles(cards)
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
        evolved = evolve(
            cards,
            validation_failures=(validation_failures if config.evolution.include_failure_summaries else ()),
            max_generations=config.evolution.max_generations,
            patience=config.evolution.saturation_patience,
            min_delta=config.evolution.minimum_improvement,
            enable_horizontal_borrowing=config.evolution.enable_horizontal_borrowing,
            output_dir=runtime.layout.dialects,
            score_generation=generation_score,
            resume=resume,
        )
        _write_manifest(runtime, evolved)
        return _latest_generation(runtime.layout)

    if args.command == "profile":
        cards = read_models(_latest_generation(runtime.layout), DialectCard)
        profiles = profile(
            runtime.adapter.load(DataSplit.EVOLUTION_VALIDATION),
            cards,
            runtime.listener_providers,
            runtime.evaluator,
            split=DataSplit.EVOLUTION_VALIDATION,
            output_path=runtime.layout.profiles / "evolution_validation.jsonl",
            max_tokens=config.provider.max_tokens,
            temperature=config.provider.temperature,
            seed=config.seed,
            token_penalty=config.routing.token_penalty,
            parse_failure_penalty=config.routing.parse_failure_penalty,
        )
        _write_manifest(runtime, cards)
        if not profiles:
            raise ValueError("profiling produced no listener-card observations")
        return runtime.layout.profiles / "evolution_validation.jsonl"

    if args.command == "select":
        cards = read_models(_latest_generation(runtime.layout), DialectCard)
        profile_path = runtime.layout.profiles / "evolution_validation.jsonl"
        if not profile_path.exists():
            raise FileNotFoundError("evolution-validation profiles are missing; run `mdia profile` first")
        profiles = read_models(profile_path, DialectProfile)
        bank = select(
            cards,
            profiles,
            min_support=config.selection.minimum_support,
            max_cards=config.selection.max_cards,
            minimum_speakers=config.selection.minimum_speakers,
            pareto_metrics=config.selection.pareto_metrics,
            diversity_key="creator_id" if config.selection.enforce_creator_diversity else None,
            output_path=runtime.layout.selection / "frozen_dialect_bank.json",
        )
        if not bank:
            raise ValueError("validation selection produced an empty dialect bank")
        _write_manifest(runtime, bank)
        return runtime.layout.selection / "frozen_dialect_bank.json"

    if args.command == "run":
        bank = _frozen_bank(runtime.layout)
        router_profiles = profile(
            runtime.adapter.load(DataSplit.ROUTER_VALIDATION),
            bank,
            runtime.listener_providers,
            runtime.evaluator,
            split=DataSplit.ROUTER_VALIDATION,
            output_path=runtime.layout.profiles / "router_validation.jsonl",
            max_tokens=config.provider.max_tokens,
            temperature=config.provider.temperature,
            seed=config.seed,
            token_penalty=config.routing.token_penalty,
            parse_failure_penalty=config.routing.parse_failure_penalty,
        )
        run(
            runtime.adapter.load(DataSplit.TEST),
            bank,
            _router(runtime),
            runtime.listener_providers,
            runtime.evaluator,
            profiles=router_profiles,
            budget=_budget(config),
            output_dir=runtime.layout.execution,
            controller_router=_controller_router(runtime),
            temperature=config.provider.temperature,
            seed=config.seed,
            resume=resume,
        )
        _write_manifest(runtime, bank)
        return runtime.layout.execution / "predictions.jsonl"

    if args.command == "validate-rules":
        bank = (
            _frozen_bank(runtime.layout)
            if (runtime.layout.selection / "frozen_dialect_bank.json").exists()
            else []
        )
        if not config.rules.enabled:
            _disabled_rules(runtime)
        else:
            validate_rules(
                _read_evidence(args.evidence),
                specs=_read_rule_specs(runtime),
                output_dir=runtime.layout.rules,
                seed=config.rules.seed if config.rules.seed is not None else config.seed,
                iterations=max(config.rules.bootstrap_samples, config.rules.permutation_samples),
                alpha=config.rules.familywise_fdr,
            )
        _write_manifest(runtime, bank)
        return runtime.layout.rules / "results.json"

    if args.command == "report":
        bank = (
            _frozen_bank(runtime.layout)
            if (runtime.layout.selection / "frozen_dialect_bank.json").exists()
            else []
        )
        _write_manifest(runtime, bank)
        report_path = build_report(runtime.run_dir)
        _write_manifest(runtime, bank)
        return report_path

    artifacts = run_pipeline(
        runtime.adapter,
        runtime.listener_providers,
        runtime.evaluator,
        _router(runtime),
        speaker_providers=runtime.speaker_providers,
        listener_providers=runtime.listener_providers,
        run_dir=runtime.run_dir,
        budget=_budget(config),
        config=_settings(config),
        config_hash=config.config_hash,
        rule_specs=_read_rule_specs(runtime),
        controller_router=_controller_router(runtime),
        code_revision=_code_revision(),
        provider_revision=config.provider.revision,
        model_revisions={
            model_id: config.provider.revision
            for model_id in dict.fromkeys((*config.community.speakers, *config.community.listeners))
        },
        seed=config.seed,
        resume=resume,
    )
    return artifacts.report_path


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        output = _execute_stage(args)
    except (ConfigError, FileNotFoundError, OSError, ValueError, RuntimeError) as exc:
        print(f"mdia: error: {exc}", file=sys.stderr)
        return 2
    print(f"MDia {args.command} complete: {output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
