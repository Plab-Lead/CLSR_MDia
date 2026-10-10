# Pipeline and artifacts

The canonical CLI implements the eight stages in Section 4.1 of the MDia manuscript. The public stage names separate lifecycle operations that older scripts mixed together.

## Partition contract

| Partition | Permitted use | Forbidden use |
|---|---|---|
| `induction` | Collect direct traces and create generation 0 | Profile, select, or report held-out performance |
| `evolution_validation` | Evaluate/update generations and decide saturation | Tune from test outcomes |
| `router_validation` | Build profiles, compare route policies, and freeze route settings | Generate cards or select from test feedback |
| `test` | Execute a frozen bank/policy and evaluate final predictions | Change cards, generations, profiles, or routes |

Every item has a stable ID and content hash. A manifest is immutable after the run starts; changing content creates a different run.

## 1. Collect direct responses

```bash
mdia collect --config configs/toy_mdia.yaml
```

Each configured speaker answers induction tasks without an LSF. The output records provider/model revision, decoding seed, raw and parsed text, evaluator result, completion tokens, latency, and cost. Gold data are visible only to the evaluator after generation.

## 2. Create generation 0

```bash
mdia create --config configs/toy_mdia.yaml
```

For each induction item, MDia filters to evaluator-correct traces from the configured creator community and selects the Top-K lowest-completion-token traces. When speaker diversity is enabled, one high-performing speaker cannot fill every slot. The offline reference factory deterministically turns each selected trace into a schema-valid card; research adapters can inject a semantic `CardFactory` backed by a creator model. Both produce persistent cards with:

```text
symbols + grammar/schema + operators + validity/usage rules + empirical profile
```

Cards receive content-derived stable IDs, generation `0`, creator/speaker provenance, task tags, I/O contract, fallback, and a specification digest.

## 3. Evolve

```bash
mdia evolve --config configs/toy_mdia.yaml
```

Each update receives the previous card, selected validation successes/failures, and a recorded cross-agent discussion summary. Parent links distinguish vertical inheritance from horizontal borrowing. After every generation, MDia writes an atomic checkpoint with inputs, candidates, selection evidence, and hashes.

The stopping rule is validation saturation: the configured utility fails to improve by the required margin for the configured patience. Test results are never a stop signal.

## 4. Profile speaker-listener transfer

```bash
mdia profile --config configs/toy_mdia.yaml
```

Every candidate speaker dialect is executed by each configured listener on validation items. Per-item records support:

- accuracy or benchmark score;
- completion tokens;
- parse failures;
- latency and estimated monetary cost;
- confidence intervals and minimum support; and
- task-conditioned utility.

Diagonal cells are self-dialect use; off-diagonal cells are foreign transfer. These validation-style matrices are mechanism evidence and are not averaged into held-out route performance.

## 5. Select and freeze

```bash
mdia select --config configs/toy_mdia.yaml
```

Selection uses only validation profiles. It enforces minimum support, removes dominated accuracy/cost/parse-risk points, applies configured diversity constraints, and writes a frozen bank manifest. Filename order and test-set accuracy are never fallbacks.

The frozen manifest records the candidate pool, selected IDs/digests, selection policy, profile/evaluator versions, split hashes, and artifact checksums.

## 6. Route, execute, and evaluate

```bash
mdia run --config configs/toy_mdia.yaml
```

The router receives only a gold-free task view, listener profile, frozen validation statistics, and a budget. It returns one of:

- `single`: execute one concrete card;
- `aggregate`: execute several cards independently and combine them with the named majority, weighted, score-based, or judge algorithm;
- `compose`: execute an ordered planner/solver/verifier-style card sequence with bounded rounds;
- `abstain/raw-fallback`: avoid a predicted mismatch and use the configured raw-answer policy.

Every selected card ID and digest must resolve to the frozen bank. The route plan fixes maximum generated tokens, calls/rounds, stop rule, and fallback before execution. The optional controller choice is stored separately from concrete card IDs.

Token cost counts every dialect-conditioned solver completion and any generated judge/aggregation completion. The built-in router is deterministic and therefore generates no planning tokens; an injected model-backed router must record its own overhead. Prompt tokens are retained separately for cache-aware analysis even when the enforced budget and headline cost use completion tokens.

## 7. Validate rules

```bash
mdia validate-rules --config configs/toy_mdia.yaml
```

Validators consume the evidence stream declared by each rule and produce an evidence-linked `RuleResult`. Missing fields, insufficient support, or absent paper thresholds produce `not_evaluated`, not an inferred score. Statistical p-values are corrected within each of the seven rule families. See [Rule validation](rules.md).

## 8. Report

```bash
mdia report --config configs/toy_mdia.yaml
```

The report separates:

1. held-out final performance;
2. split-validation route selection; and
3. validation-style mechanism/proxy analysis.

Every value links back to a run artifact, evaluator version, count, and checksum. Cached leave-one-source analyses are labelled `proxy` unless the run contains live evolution provenance.

## End-to-end command

```bash
mdia pipeline --config configs/toy_mdia.yaml
```

The orchestration command validates or resumes each stage in order. A successful run includes, logically, the following artifact groups (exact nested filenames are indexed by `RunManifest`):

```text
runs/<run_id>/
  manifest.json
  report.md
  splits/{induction,evolution_validation,router_validation,test}.json
  direct_traces.jsonl
  dialects/generation-*.json
  profiles/{evolution_validation,router_validation}.jsonl
  selection/frozen_dialect_bank.json
  execution/{route_plans,predictions,evaluations}.jsonl
  execution/token_accounting.json
  rules/{registry,results}.json
```

To publish an artifact bundle, copy only redistributable records, remove restricted task text and private operational fields, write a SHA-256 manifest, and link the bundle to the originating run manifest.
