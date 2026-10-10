# Reproduction and data policy

“The pipeline runs” and “a paper result was reproduced” are different claims. This project uses three explicit reproduction tiers.

## Tier 1: offline fixture

Purpose: verify installation, schemas, split isolation, card lifecycle, routing modes, rule execution, and deterministic provenance without network access.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
mdia pipeline --config configs/toy_mdia.yaml
pytest
```

The replay provider and toy tasks are redistributable fixtures. They demonstrate behavior; their metrics are not research evidence.

## Tier 2: adapter run

Purpose: apply the canonical contract to a new dataset/model. Supply a licensed dataset adapter, provider configuration, evaluator, and new immutable split manifests. Start from the closest configuration, but assign a new run ID and do not label the output a manuscript reproduction.

Before publishing, report model/provider revision, evaluator type, seeds, split/content hashes, candidate bank, selected route policy, complete item counts, token-accounting convention, and failures.

## Tier 3: paper protocol

Purpose: reproduce a named manuscript table or analysis. In addition to Tier 2, this requires the exact paper configuration and artifact release:

- benchmark versions and official licenses;
- exact immutable partition manifests;
- model and provider revisions;
- dialect bank/candidate-pool manifest;
- evaluator and parser versions;
- generation and route-selection seeds;
- rule registry and statistical implementation version; and
- SHA-256 checksums for every source artifact.

If any required component is unavailable, describe the result as a partial reproduction or adapter run. Do not substitute a different row, task count, evaluator, or evidence stream silently.

## Evidence separation

Reports must keep these sections distinct:

1. **Held-out performance:** a frozen policy evaluated on test records; the only stream for final accuracy/cost claims.
2. **Split-validation routing:** route selection frozen on `router_validation`, evaluated on a disjoint set; evidence for selection behavior.
3. **Mechanism/proxy analysis:** transfer matrices, model profiles, rule validation, or source-removal analysis; evidence for interpretation, not a held-out gain.

Cached leave-one-source or “cross-generation” calculations are labelled `proxy` unless live generation and parent/influence records are present in the run.

## Evaluators

Use an official benchmark harness adapter when making an official benchmark claim. Lightweight exact-match, regex, normalized-string, or LLM-judge evaluators are **diagnostic** unless the benchmark specifies them. Store the raw response, parser result, evaluator result, evaluator identity/version, and parse failure separately.

The final report must show excluded/incomplete rows rather than filling them from another protocol. Counts must match the run manifest.

## Determinism and provenance

A repeatable run fixes:

- code revision and schema version;
- normalized config hash;
- provider/model revision;
- Python/dependency environment;
- all random/decoding seeds;
- partition content hashes;
- card IDs/specification digests;
- frozen validation profiles and candidate pool; and
- evaluator and rule-registry versions.

Provider APIs can drift even when their public model name does not. A deterministic card/route choice does not guarantee byte-identical hosted-model output; report the provider revision and time window.

## Release assets

Git contains only redistributable toy fixtures and compact example outputs. Publish large sanitized artifacts as versioned GitHub Release assets, for example:

```text
mdia-v1.0.0-artifacts/
  MANIFEST.sha256
  RUN_MANIFEST.json
  README.md
  normalized_records.jsonl.zst
  dialect_bank.json
  rule_results.json
```

The release README must name the originating code tag, license/redistribution status, removed fields, expected counts, and verification command:

```bash
shasum -a 256 -c MANIFEST.sha256
```

Do not publish restricted benchmark text, provider-private prompts, full API payload logs, account metadata, API usage ledgers, machine-specific paths, or credentials. A task manifest may contain stable IDs and content hashes without containing the restricted text itself.

## Credentials and remote-derived material

- Store credentials only in local environment variables; `.env` is ignored by Git.
- Never add secrets to YAML/JSON/Python, shell history, job files, logs, or release artifacts.
- Scan the working tree and Git history before release.
- Credentials discovered in private research workspaces must be rotated by their owner before any artifact from that workspace is published. Removing a key from the newest commit is not rotation.
- Inspect remote material read-only, copy only the minimum artifact needed, and run credential/path scans before adding it to Git.

The recovered legacy meta-LSF prompt bank followed this process; its status file records the checksum. No other private remote artifact is bundled merely because it informed the design.

## Redistribution checklist

Before release:

- confirm every fixture/artifact license;
- search for secrets and private paths in tracked files and Git history;
- inspect JSONL for prompt/context/gold leakage and command-like generated text;
- verify SHA-256 manifests;
- run the offline pipeline from a clean clone;
- run unit, leakage, CLSR, MDia, and regression tests; and
- verify documentation links and citation metadata.
