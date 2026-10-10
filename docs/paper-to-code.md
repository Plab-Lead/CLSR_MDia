# Paper-to-code map

This release treats [`papers/MDia_Jul17.pdf`](../papers/MDia_Jul17.pdf) as the method contract and [CLSR](https://arxiv.org/abs/2606.29354) as the homogeneous special case.

## MDia methods

| Manuscript concept | Canonical implementation |
|---|---|
| Section 4.1, eight-stage workflow | `collect`, `create`, `evolve`, `profile`, `select`, `run`, `validate-rules`, and `report` |
| Section 4.2, partitions and metadata | Immutable split manifests and gold-free `TaskView` routing boundary |
| Section 4.3, model population/profile features | Provider/model revisions plus validation-derived listener/speaker profiles |
| Section 4.4, `D = (V,G,O,R,rho)` | Validated `DialectCard` with lifecycle provenance and specification digest |
| Section 4.5, high-leverage traces | Per-item evaluator-correct Top-K by completion tokens, optionally speaker-diverse |
| Section 4.6, inheritance, borrowing, archive | Parent-linked generation checkpoints and normalized event records |
| Sections 4.7-4.9, routing and cost | Separate controller/card route plans, profile utility, budgets, aggregation, and complete generated-token accounting |
| Section 4.10, rule validation | 100-rule registry, declared evidence/statistic, execution status, and family-wise correction |
| Section 4.11, provenance | Evidence-stream separation, evaluator versions, source IDs, counts, and checksums |

The code uses a dedicated `select` command between profiling and test routing. This makes the manuscript's validation-only freezing step observable instead of hiding it inside the route command.

## CLSR relationship

CLSR creates and evolves reusable symbolic protocols and selects, aggregates, or composes concrete LSFs at inference time. MDia extends the same lifecycle by making the source speaker, target listener, heterogeneous model profile, transfer asymmetry, and archive history first-class variables.

| Dimension | CLSR preset | MDia preset |
|---|---|---|
| Community | One backbone/model community | Heterogeneous model families/profiles |
| Card lifecycle | Create, evolve, select | Create, inherit, borrow, profile, select |
| Primary router | Concrete LSF cards | Concrete LSF cards using listener/task profiles |
| Ecology analysis | Disabled | Speaker-listener transfer and publicness/openness/resistance |
| Cross-family rule claims | Out of scope | Eligible when evidence requirements are met |

The archived v0 scripts are early CLSR provenance; the supported CLSR implementation is `configs/clsr.yaml` plus the root package.

## Evidence streams and claims

The manuscript intentionally uses three non-interchangeable streams:

| Stream | Scientific question | Canonical report section |
|---|---|---|
| Held-out performance | Does the frozen MDia workflow improve the accuracy/cost frontier? | Final test metrics |
| Split-validation routing | Can validation evidence select a route without using evaluation outcomes? | Route-selection audit |
| Mechanism/proxy analysis | How do dialects transfer, which rules match, and what source influence is visible? | Profiles, rules, proxy analyses |

Do not average a transfer-matrix cell with a held-out routed result or cite a validation support label as a new test-set gain. The root README quotes only the manuscript-grounded statement that 19 rules received full or strong support in the paper's audited archive.

## Provenance of the rebuild

The public design was informed by three private research workspaces without copying their scripts or operational material:

- `MDia-v1`: heterogeneous creation/evolution, concrete-LSF execution, coverage inventories, and resume-oriented experiment behavior;
- `MDia-NMI-Jun1`: normalized archive, transfer/profile tables, split-router audit, statistical reports, and analysis provenance; and
- `MDia-v2`: format-sensitive controller experiments and the 100-rule registry.

The canonical implementation recreates the scientifically relevant behavior behind clean contracts. Private logs, credentials, API ledgers, benchmark copies, and machine-specific paths remain excluded.

## Legacy ambiguity resolved

- GitHub issue [#4](https://github.com/pzqpzq/LSF_MDia/issues/4) concerned what “v2 routing” selected. The answer is now explicit: the archived former v2 selects handcrafted controllers, while `DialectRouter` selects concrete evolved cards.
- GitHub issue [#6](https://github.com/pzqpzq/LSF_MDia/issues/6) concerned the missing `meta_LSFs_v2.json`. A sanitized historical copy is present under the archived CLSR workspace with its checksum and status documented.

Historical result files remain evidence provenance only. A number becomes a current release result only when a canonical run manifest, compatible evaluator, complete count, and source checksum support it.
