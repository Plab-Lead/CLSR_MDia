"""Validated configuration loading for reproducible MDia runs."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, JsonValue, PrivateAttr, model_validator

from .schemas import SCHEMA_VERSION, AggregationMethod, DataSplit, RouteMode, stable_digest


class ConfigError(ValueError):
    """Raised when a configuration file cannot be loaded safely."""


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class DatasetConfig(ConfigModel):
    adapter: Literal["jsonl"] = "jsonl"
    path: Path | None = None
    split_paths: dict[DataSplit, Path] = Field(default_factory=dict)
    id_field: str = "task_id"
    split_field: str = "split"
    query_field: str = "query"
    gold_field: str = "gold"
    metadata_field: str = "metadata"
    strict_split_isolation: bool = True

    @model_validator(mode="after")
    def _has_one_source_style(self) -> DatasetConfig:
        if (self.path is None) == (not self.split_paths):
            raise ValueError("dataset must define exactly one of path or split_paths")
        return self


class ProviderConfig(ConfigModel):
    kind: Literal["replay", "openai_compatible"]
    model: str = Field(min_length=1)
    revision: str = "unspecified"
    replay_path: Path | None = None
    replay_default_text: str | None = None
    base_url: str | None = None
    api_key_env: str = "MDIA_API_KEY"
    max_tokens: int = Field(default=512, gt=0)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    timeout_seconds: float = Field(default=120.0, gt=0.0)
    retries: int = Field(default=2, ge=0, le=10)
    seed: int | None = None

    @model_validator(mode="after")
    def _kind_specific_fields(self) -> ProviderConfig:
        if self.kind == "replay" and self.replay_path is None and self.replay_default_text is None:
            raise ValueError("replay provider requires replay_path or replay_default_text")
        if self.kind == "openai_compatible":
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.api_key_env):
                raise ValueError("api_key_env must be the name of an environment variable")
            if self.replay_path is not None or self.replay_default_text is not None:
                raise ValueError("OpenAI-compatible provider cannot use replay settings")
            if self.base_url is not None:
                parsed = urlsplit(self.base_url)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    raise ValueError("base_url must be an absolute HTTP(S) URL")
                if parsed.username is not None or parsed.password is not None:
                    raise ValueError("base_url cannot contain credentials; use api_key_env")
        return self


class EvaluatorConfig(ConfigModel):
    kind: Literal["exact_match", "diagnostic"] = "exact_match"
    evaluator_id: str = "exact-match-v1"
    case_sensitive: bool = False
    strip: bool = True
    normalize_whitespace: bool = True
    json_field: str | None = None
    official: bool = False


class CommunityConfig(ConfigModel):
    preset: Literal["mdia", "clsr"] = "mdia"
    creators: tuple[str, ...] = Field(min_length=1)
    speakers: tuple[str, ...] = Field(min_length=1)
    listeners: tuple[str, ...] = Field(min_length=1)
    homogeneous: bool = False

    @model_validator(mode="after")
    def _validate_preset(self) -> CommunityConfig:
        if self.preset == "clsr" and not self.homogeneous:
            raise ValueError("the CLSR preset must declare homogeneous=true")
        if self.preset == "clsr" and len(set((*self.creators, *self.speakers, *self.listeners))) != 1:
            raise ValueError("the CLSR preset must use one backbone across creators, speakers, and listeners")
        return self


class CreationConfig(ConfigModel):
    top_k_per_task: int = Field(default=3, gt=0)
    enforce_speaker_diversity: bool = True
    minimum_correct_traces: int = Field(default=1, gt=0)


class EvolutionConfig(ConfigModel):
    max_generations: int = Field(default=3, ge=0)
    saturation_patience: int = Field(default=1, gt=0)
    minimum_improvement: float = Field(default=0.0, ge=0.0)
    inherit_previous_generation: Literal[True] = True
    enable_horizontal_borrowing: bool = True
    include_failure_summaries: bool = True


class SelectionConfig(ConfigModel):
    minimum_support: int = Field(default=1, gt=0)
    max_cards: int = Field(default=8, gt=0)
    minimum_speakers: int = Field(default=1, gt=0)
    pareto_metrics: tuple[Literal["accuracy", "tokens", "parse_failures", "latency", "cost"], ...] = (
        "accuracy",
        "tokens",
    )
    enforce_creator_diversity: bool = True

    @model_validator(mode="after")
    def _validate_pareto_metrics(self) -> SelectionConfig:
        if not self.pareto_metrics:
            raise ValueError("pareto_metrics cannot be empty")
        if len(set(self.pareto_metrics)) != len(self.pareto_metrics):
            raise ValueError("pareto_metrics cannot contain duplicates")
        return self


class RoutingConfig(ConfigModel):
    policy: Literal["utility", "fixed_single"] = "utility"
    mode: RouteMode = RouteMode.SINGLE
    aggregation: AggregationMethod | None = None
    token_budget: int = Field(default=1024, gt=0)
    max_steps: int = Field(default=1, gt=0)
    max_dialects: int = Field(default=3, gt=0)
    fixed_dialect_id: str | None = None
    accuracy_weight: float = Field(default=1.0, ge=0.0)
    token_penalty: float = Field(default=0.001, ge=0.0)
    parse_failure_penalty: float = Field(default=0.25, ge=0.0)
    latency_penalty: float = Field(default=0.0, ge=0.0)
    cost_penalty: float = Field(default=0.0, ge=0.0)
    raw_fallback_when_unroutable: bool = True
    minimum_utility: float | None = None

    @model_validator(mode="after")
    def _validate_routing_policy(self) -> RoutingConfig:
        if self.mode is RouteMode.AGGREGATE and self.aggregation is None:
            raise ValueError("aggregate routing requires an aggregation method")
        if self.mode is not RouteMode.AGGREGATE and self.aggregation is not None:
            raise ValueError("aggregation can only be set for aggregate routing")
        if self.policy == "fixed_single":
            if self.mode is not RouteMode.SINGLE:
                raise ValueError("fixed_single policy requires mode=single")
            if not self.fixed_dialect_id:
                raise ValueError("fixed_single policy requires fixed_dialect_id")
        if self.mode in (RouteMode.AGGREGATE, RouteMode.COMPOSE) and self.max_dialects < 2:
            raise ValueError(f"{self.mode.value} mode requires max_dialects >= 2")
        if self.mode in (RouteMode.AGGREGATE, RouteMode.COMPOSE) and self.max_steps < 2:
            raise ValueError(f"{self.mode.value} mode requires max_steps >= 2")
        if self.aggregation is AggregationMethod.JUDGE and self.max_steps < 3:
            raise ValueError("judge aggregation requires at least two dialect steps and one judge step")
        return self


class ControllerConfig(ConfigModel):
    enabled: bool = False
    routes: dict[str, dict[str, str]] = Field(default_factory=dict)
    key_fields: dict[str, str] = Field(default_factory=dict)
    default_controller: str | None = None
    estimated_overhead: dict[str, int] = Field(default_factory=dict)
    reasons: dict[str, str] = Field(default_factory=dict)
    answer_contracts: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_controller(self) -> ControllerConfig:
        if any(value < 0 for value in self.estimated_overhead.values()):
            raise ValueError("controller estimated_overhead values cannot be negative")
        if self.enabled and not self.routes and self.default_controller is None:
            raise ValueError("an enabled controller requires routes or default_controller")
        return self


class RulesConfig(ConfigModel):
    enabled: bool = True
    registry_path: Path | None = None
    familywise_fdr: float = Field(default=0.05, gt=0.0, lt=1.0)
    bootstrap_samples: int = Field(default=2000, gt=0)
    permutation_samples: int = Field(default=2000, gt=0)
    seed: int | None = None


class RunConfig(ConfigModel):
    schema_version: str = SCHEMA_VERSION
    run_id: str | None = None
    seed: int = 0
    output_dir: Path = Path("runs")
    dataset: DatasetConfig
    provider: ProviderConfig
    evaluator: EvaluatorConfig = EvaluatorConfig()
    community: CommunityConfig
    creation: CreationConfig = CreationConfig()
    evolution: EvolutionConfig = EvolutionConfig()
    selection: SelectionConfig = SelectionConfig()
    routing: RoutingConfig = RoutingConfig()
    controller: ControllerConfig = ControllerConfig()
    rules: RulesConfig = RulesConfig()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    _source_path: Path | None = PrivateAttr(default=None)

    @model_validator(mode="after")
    def _schema_and_preset_consistency(self) -> RunConfig:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"unsupported schema_version {self.schema_version!r}; expected {SCHEMA_VERSION!r}"
            )
        if self.community.preset == "clsr" and self.rules.enabled:
            raise ValueError(
                "CLSR disables cross-family sociolinguistic rule analysis; set rules.enabled=false"
            )
        return self

    @property
    def config_hash(self) -> str:
        return stable_digest(self.model_dump(mode="json", exclude={"run_id"}))

    @property
    def source_path(self) -> Path | None:
        return self._source_path

    def resolve_path(self, path: Path) -> Path:
        """Resolve a configured path relative to its configuration file."""

        if path.is_absolute():
            return path
        base = self._source_path.parent if self._source_path is not None else Path.cwd()
        return (base / path).resolve()


def _load_yaml_or_json(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml
    except ImportError:
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError(
                "PyYAML is unavailable; use JSON syntax in the .yaml file or install the declared PyYAML dependency"
            ) from exc
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc


def load_config(path: str | os.PathLike[str]) -> RunConfig:
    """Load and validate a YAML (or JSON-formatted YAML) run configuration."""

    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ConfigError(f"configuration file does not exist: {source}")
    raw = _load_yaml_or_json(source)
    if not isinstance(raw, dict):
        raise ConfigError("configuration root must be a mapping")
    config = RunConfig.model_validate(raw)
    config._source_path = source
    return config


def load_config_data(data: dict[str, Any], *, source_path: Path | None = None) -> RunConfig:
    """Validate an already parsed configuration (useful for tests and embedding)."""

    config = RunConfig.model_validate(data)
    if source_path is not None:
        config._source_path = source_path.expanduser().resolve()
    return config


__all__ = [
    "CommunityConfig",
    "ConfigError",
    "ControllerConfig",
    "CreationConfig",
    "DatasetConfig",
    "EvaluatorConfig",
    "EvolutionConfig",
    "ProviderConfig",
    "RoutingConfig",
    "RulesConfig",
    "RunConfig",
    "SelectionConfig",
    "load_config",
    "load_config_data",
]
