# Extending datasets, providers, evaluators, and routers

Extensions must preserve stable identities, split isolation, gold-data boundaries, and provenance. The offline fixture is the reference integration test.

## Dataset adapter

Implement:

```python
DatasetAdapter.load(split) -> Iterable[TaskRecord]
```

For each record:

- derive a stable item ID from a source-native ID or canonical content;
- assign exactly one of `induction`, `evolution_validation`, `router_validation`, or `test`;
- put only pre-generation fields in query/observable metadata;
- keep gold answers and evaluator-only metadata in protected fields; and
- record source version, license, and content hash.

Never infer partitions from mutable file ordering. If source text cannot be redistributed, commit only a manifest of stable IDs/hashes and loading instructions.

## Chat provider

Implement:

```python
ChatProvider.complete(request) -> Completion
```

The request boundary must accept a gold-free task view plus the selected card/controller context. The completion should preserve provider/model revision, raw response, finish status, prompt/completion tokens where available, latency, estimated cost, and deterministic/replay metadata.

Credentials come from environment variables named by provider configuration. Do not serialize resolved keys into requests, manifests, exceptions, or logs. A provider must never read evaluator-only task fields.

## Evaluator

Implement:

```python
Evaluator.evaluate(task, output) -> EvaluationRecord
```

Parse and scoring are explicit steps. Record parse failure independently from incorrectness, retain the canonical parsed answer, and version the evaluator. Label a local evaluator `diagnostic` unless it wraps or exactly follows the benchmark's official harness.

The evaluator is the only extension that receives protected gold data, and only after generation completes.

## Dialect router

Implement:

```python
DialectRouter.route(task_view, listener_profile, bank, budget) -> DialectRoutePlan
```

A valid plan:

- references only concrete cards in the supplied frozen bank;
- includes each stable card ID and matching specification digest;
- names `single`, `aggregate`, `compose`, or `abstain/raw-fallback` mode;
- names a real aggregation algorithm when applicable;
- fixes the generated-token/call/round budget and stopping rule; and
- records the validation/profile evidence used to choose the route.

Route scoring may use query text, observable task metadata, listener profiles, frozen validation statistics, and budget information. It may not use gold labels, test outcomes, or candidate-answer feedback before the plan is fixed.

If you add an aggregator, implement and test it as a distinct algorithm. Do not expose several policy names that call the same code path.

## Controller router

Implement:

```python
ControllerRouter.route(task_metadata, listener_profile, budget) -> ControllerRoutePlan
```

This optional layer selects an answer-contract/controller family such as schema-first, evidence-guarded, contrastive, or verifier-rich. Its output is not an evolved dialect-card ID. If both routers are enabled, write both plans to the event record and account for all generated controller/router tokens.

## Dialect synthesis/evolution

New synthesis logic must emit all components of `D = (V,G,O,R,rho)` plus provenance, parents, task tags, I/O contract, fallback, and digest. Evolution receives only the previous generation, permitted validation evidence, and recorded discussion summaries. Write atomic generation checkpoints so interruption can resume without duplicating or silently skipping a generation.

## Configuration and tests

Add a focused config preset rather than hard-coded paths or model switches. Validation should reject unknown splits, missing provider/evaluator registrations, empty creator/listener sets, impossible budgets, and route modes incompatible with the bank.

Every extension should add tests for:

- schema round trips and stable IDs;
- split/gold leakage;
- deterministic replay behavior;
- token and failure accounting;
- card/bank referential integrity;
- budget and stopping enforcement; and
- at least one end-to-end fixture path.

For a paper-facing adapter, also test official evaluator parity and document dataset/model licenses in [Reproduction and data policy](reproduction.md).
