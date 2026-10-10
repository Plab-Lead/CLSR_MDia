# MDia reproducibility report

> This report separates held-out task performance, validation-only routing evidence, and mechanism/proxy rule evidence.

## Run identity

| Field | Value |
|---|---|
| Run ID | `example` |
| Schema | `1.0` |
| Code revision | `mdia-v1.0.0-example` |
| Provider revision | `synthetic-v1` |
| Config hash | `ef838d21a1375510c5803208c620d6c4805b6040576ecd01e76bec4471c51c3a` |

## Held-out or router-validation execution

- Predictions: 2
- Scored evaluations: 2
- Accuracy: 1.000
- Parse-failure rate: 0.000
- Official evaluations: 0; diagnostic evaluations: 2
- Completion tokens: 2
- Prompt tokens: 0
- Recorded cost: 0.000000

### Route modes

| Mode | Tasks |
|---|---:|
| single | 2 |

## Validation-only dialect evidence

- Frozen cards: 4
- Transfer profiles: 8
- Card and route choice must be derived from evolution-validation or router-validation profiles, never test outcomes.

## Machine-sociolinguistic rules

- Registry results: 100
- Evaluated now: 0
- Not evaluated now: 100
- Current tests passing after within-family BH correction: 0/0
- Results labelled as fixed-archive/cross-generation proxies: 15

The manuscript support labels below are provenance, not results inferred from this run:

| Manuscript support | Rules |
|---|---:|
| full | 6 |
| strong | 13 |
| partial | 17 |
| weak | 44 |
| boundary | 16 |
| unsupported | 4 |

## Artifact integrity

| Artifact | SHA-256 |
|---|---|
| `execution/evaluations.jsonl` | `7eaa75795eb553f568152fec51b64d73e49f4e7f2aeb61b3fadda757cf21d75b` |
| `execution/predictions.jsonl` | `9ac144c365d866a416903f6e7da8e3a0755eae7e9f1f3ec141fe819d09927e4a` |
| `execution/route_plans.jsonl` | `a2828e21ace655fb9a9af0d775a569c9f58dedc25773ba731982a87a58c23d14` |
| `execution/token_accounting.json` | `d52e085ea83d444dc2cac28ebd0b4440419a52a160ac571b077e83b1b5e333db` |
| `manifest.json` | `454300c328ee7a542b992dab1b55fc09a6f52be6ca0727af1b92bacea332fa0f` |
| `profiles/evolution_validation.jsonl` | `8266c9cbd3a5df4585302abd1792fe0f402a0255c235dbffa996e0116384f8cc` |
| `rules/results.json` | `e56848e237d3a541e8b8b443c93694d0e481114c52c5b2c860767622da36830a` |
| `selection/frozen_dialect_bank.json` | `32419cc785a8ab7500d80eca1a3591232b8fa81713a9d96a106e075c4132c3b2` |

## Interpretation guardrails

- Diagnostic evaluators are not official benchmark scores.
- A `not_evaluated` rule has no current evidentiary result; its manuscript label must not be substituted as one.
- Fixed-archive leave-one-source and cached cross-generation analyses remain proxies unless live evolution records are supplied.
