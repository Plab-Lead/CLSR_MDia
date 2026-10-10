# Sociolinguistic rule validation

The 100-rule bank is a falsifiable inventory of machine-sociolinguistic hypotheses, not a list of axioms. A rule connects a social concept such as openness, publicness, teaching, resistance, compression fragility, code-switching, or archive survival to measurable MDia event records.

## Seven families

| Family | Rule IDs | Manuscript taxonomy |
|---|---|---|
| A | R001-R015 | Receiver/listener rules |
| B | R016-R030 | Speaker/publicness rules |
| C | R031-R045 | Task-conditioned rules |
| D | R046-R060 | Compression/redundancy rules |
| E | R061-R075 | Routing/code-switching rules |
| F | R076-R090 | Archive/evolution rules |
| G | R091-R100 | Robustness, scale, and deployment rules |

The registry publishes all 100 entries, including negative and boundary results.

## Rule contract

Every `RuleSpec` declares:

- stable rule ID and family;
- hypothesis and predicted direction;
- eligible record predicate and minimum support;
- unit of analysis;
- required features;
- statistic and test type;
- paper-defined threshold;
- evidence stream;
- known exceptions; and
- routing implication.

A validator may use a paired per-item bootstrap, a permutation test, or a declared regression model as appropriate to the hypothesis. It cannot replace a missing threshold or feature with an undocumented heuristic. Multiple-testing p-values are adjusted with Benjamini-Hochberg **within each of the seven families**.

## Two independent status axes

The registry preserves the manuscript's empirical support label:

```text
full | strong | partial | weak | boundary | unsupported
```

That label describes the manuscript archive and should be read as evidence strength within that archive, not a universal law.

Each current run separately records whether the rule was executable and what it found. If data, minimum support, threshold, or a required statistic is absent, the execution result is `not_evaluated`. The package never converts `not_evaluated` into the manuscript label and never treats a legacy heuristic support score as revalidated evidence.

## Evidence streams

Rules declare exactly one primary evidence stream:

- held-out final performance;
- split-validation route-selection evidence; or
- validation-style transfer/mechanism evidence.

These streams are not interchangeable. Speaker-listener transfer profiles do not become held-out route gains, and a cached leave-one-source analysis does not become live cross-generational evolution. The latter is labelled `proxy` unless the run contains the relevant live card generations, parentage, and source events.

## Manuscript-grounded headline

The MDia manuscript reports full or strong support for 19 rules in its audited archive. The root README highlights only this supported subset and representative themes documented by the paper: listener-openness asymmetry, public-dialect asymmetry, weak-speaker teaching, foreign-dialect risk, route simplicity, task-aware routing, parser-compatible compactness, answer-contract compression, cost-aware selection, audit-friendly finalization, strict tool/RAG contracts, and negative-transfer guards.

This repository does not claim that an offline toy run reproduces those 19 results. A current report must show its own evidence counts, statistic, confidence interval/effect, raw and adjusted p-values where applicable, execution status, and source artifact IDs.

## Reporting requirements

The detailed rule report contains every rule, including:

- manuscript support label and scope note;
- current execution status;
- eligible and excluded counts;
- evidence stream and artifact checksums;
- statistic, effect/direction, uncertainty, and adjusted significance;
- exceptions or failure reason; and
- routing implication, treated as a soft feature unless the paper and current run justify a hard guard.

Only `full` and `strong` manuscript findings belong in a headline summary. `partial`, `weak`, `boundary`, `unsupported`, and `not_evaluated` outcomes remain visible in the full report so the theory can be corrected rather than selectively reported.

## Routing use

Supported rules may change a route score or activate a conservative guard. Examples include lowering scores for a foreign dialect with measured negative-transfer risk, avoiding ultra-compact cards for a compression-fragile listener, preferring task-conditioned over global choices, or abstaining when profile mismatch is high.

Rule-aware routing cannot inspect the target answer and cannot update the frozen test policy from test outcomes. For high-stakes tasks, parser validity, stability, and negative-transfer checks should gate deployment independently of average utility.
