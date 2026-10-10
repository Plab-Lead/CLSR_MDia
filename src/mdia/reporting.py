"""Build an auditable Markdown summary from versioned MDia run artifacts."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from mdia.pipeline.io import artifact_checksum


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    return rows


def _records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.suffix == ".jsonl":
        return _read_jsonl(path)
    value = _read_json(path)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict) and isinstance(value.get("records"), list):
        return [item for item in value["records"] if isinstance(item, dict)]
    return []


def _find(run_dir: Path, relative_candidates: tuple[str, ...]) -> Path | None:
    for relative in relative_candidates:
        candidate = run_dir / relative
        if candidate.exists():
            return candidate
    return None


def _format_number(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def build_report(run_dir: str | Path, output_path: str | Path | None = None) -> Path:
    """Build ``report.md`` without conflating held-out and mechanism evidence."""

    root = Path(run_dir)
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"run directory does not exist: {root}")
    target = Path(output_path) if output_path is not None else root / "report.md"

    manifest_path = root / "manifest.json"
    manifest = _read_json(manifest_path) if manifest_path.exists() else {}
    if not isinstance(manifest, dict):
        manifest = {}
    evaluation_path = _find(root, ("execution/evaluations.jsonl", "evaluations.jsonl"))
    prediction_path = _find(root, ("execution/predictions.jsonl", "predictions.jsonl"))
    route_path = _find(root, ("execution/route_plans.jsonl", "route_plans.jsonl"))
    accounting_path = _find(root, ("execution/token_accounting.json", "token_accounting.json"))
    rules_path = _find(root, ("rules/results.json", "rule_results.json"))
    bank_path = _find(root, ("selection/frozen_dialect_bank.json", "frozen_dialect_bank.json"))
    profile_path = _find(root, ("profiles/evolution_validation.jsonl", "profiles.jsonl"))

    evaluations = _records(evaluation_path) if evaluation_path is not None else []
    predictions = _records(prediction_path) if prediction_path is not None else []
    routes = _records(route_path) if route_path is not None else []
    rule_results = _records(rules_path) if rules_path is not None else []
    bank = _records(bank_path) if bank_path is not None else []
    profiles = _records(profile_path) if profile_path is not None else []
    accounting = _read_json(accounting_path) if accounting_path is not None else {}
    if not isinstance(accounting, dict):
        accounting = {}

    scored = [row for row in evaluations if isinstance(row.get("correct"), bool)]
    correct = sum(bool(row["correct"]) for row in scored)
    parse_failures = sum(bool(row.get("parse_failure")) for row in evaluations)
    official = sum(bool(row.get("official")) for row in evaluations)
    route_modes = Counter(str(row.get("mode", "unknown")) for row in routes)
    execution_status = Counter(str(row.get("status", "unknown")) for row in rule_results)
    manuscript_support = Counter(str(row.get("manuscript_support", "unknown")) for row in rule_results)
    evaluated_rules = [row for row in rule_results if row.get("status") == "evaluated"]
    passed_rules = sum(row.get("passed") is True for row in evaluated_rules)
    proxy_rules = sum(bool(row.get("proxy")) for row in rule_results)

    lines = [
        "# MDia reproducibility report",
        "",
        "> This report separates held-out task performance, validation-only routing evidence, and mechanism/proxy rule evidence.",
        "",
        "## Run identity",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Run ID | `{manifest.get('run_id', root.name)}` |",
        f"| Schema | `{manifest.get('schema_version', 'unknown')}` |",
        f"| Code revision | `{manifest.get('code_revision', 'unknown')}` |",
        f"| Provider revision | `{manifest.get('provider_revision', 'unknown')}` |",
        f"| Config hash | `{manifest.get('config_hash', 'unknown')}` |",
        "",
        "## Held-out or router-validation execution",
        "",
    ]
    if evaluations:
        accuracy = correct / len(scored) if scored else 0.0
        parse_rate = parse_failures / len(evaluations)
        lines.extend(
            [
                f"- Predictions: {len(predictions)}",
                f"- Scored evaluations: {len(scored)}",
                f"- Accuracy: {_format_number(accuracy)}",
                f"- Parse-failure rate: {_format_number(parse_rate)}",
                f"- Official evaluations: {official}; diagnostic evaluations: {len(evaluations) - official}",
                f"- Completion tokens: {int(accounting.get('completion_tokens', 0))}",
                f"- Prompt tokens: {int(accounting.get('prompt_tokens', 0))}",
                f"- Recorded cost: {_format_number(float(accounting.get('cost', 0.0)), 6)}",
            ]
        )
    else:
        lines.append("No execution evaluations were found.")
    lines.extend(["", "### Route modes", ""])
    if route_modes:
        lines.extend(["| Mode | Tasks |", "|---|---:|"])
        lines.extend(f"| {mode} | {count} |" for mode, count in sorted(route_modes.items()))
    else:
        lines.append("No route plans were found.")

    lines.extend(
        [
            "",
            "## Validation-only dialect evidence",
            "",
            f"- Frozen cards: {len(bank)}",
            f"- Transfer profiles: {len(profiles)}",
            "- Card and route choice must be derived from evolution-validation or router-validation profiles, never test outcomes.",
            "",
            "## Machine-sociolinguistic rules",
            "",
        ]
    )
    if rule_results:
        lines.extend(
            [
                f"- Registry results: {len(rule_results)}",
                f"- Evaluated now: {execution_status.get('evaluated', 0)}",
                f"- Not evaluated now: {execution_status.get('not_evaluated', 0)}",
                f"- Current tests passing after within-family BH correction: {passed_rules}/{len(evaluated_rules)}",
                f"- Results labelled as fixed-archive/cross-generation proxies: {proxy_rules}",
                "",
                "The manuscript support labels below are provenance, not results inferred from this run:",
                "",
                "| Manuscript support | Rules |",
                "|---|---:|",
            ]
        )
        for support in ("full", "strong", "partial", "weak", "boundary", "unsupported"):
            lines.append(f"| {support} | {manuscript_support.get(support, 0)} |")
    else:
        lines.append("No rule-validation results were found.")

    artifact_paths = [
        path
        for path in (
            manifest_path,
            evaluation_path,
            prediction_path,
            route_path,
            accounting_path,
            rules_path,
            bank_path,
            profile_path,
        )
        if path is not None and path.exists()
    ]
    lines.extend(["", "## Artifact integrity", ""])
    if artifact_paths:
        lines.extend(["| Artifact | SHA-256 |", "|---|---|"])
        for path in sorted(set(artifact_paths)):
            lines.append(f"| `{path.relative_to(root).as_posix()}` | `{artifact_checksum(path)}` |")
    else:
        lines.append("No canonical artifacts were found.")
    lines.extend(
        [
            "",
            "## Interpretation guardrails",
            "",
            "- Diagnostic evaluators are not official benchmark scores.",
            "- A `not_evaluated` rule has no current evidentiary result; its manuscript label must not be substituted as one.",
            "- Fixed-archive leave-one-source and cached cross-generation analyses remain proxies unless live evolution records are supplied.",
            "",
        ]
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


report = build_report


__all__ = ["build_report", "report"]
