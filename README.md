# Machine Dialectology (MDia)

MDia studies which parts of a reasoning procedure one language model can express in a form that another can use. A reusable *dialect card* specifies the vocabulary, grammar, operations and answer format of a procedure. MDia records the card’s author, its construction history and its performance with each tested receiver. Symbolic cards, English procedures and direct solvers can then be compared by both answer accuracy and the number of tokens the receiver generates.

[Benchmark results](#benchmark-results-and-reproduction) · [Quickstart](#quickstart) · [Pipeline](#canonical-pipeline) · [Documentation](#documentation) · [Citation](#citation)

[![MDia framework: dialect construction, speaker–listener transfer and inference](assets/readme/pipeline-Jul15-v0.png)](assets/readme/pipeline-Jul15-v0.png)

## Benchmark results and reproduction

Across four reasoning benchmarks, MDia procedures matched or exceeded the named reference’s observed accuracy while generating fewer tokens. Each row compares the same model on the same questions. **Generation saved** is the percentage reduction in native output tokens relative to the named reference, including reasoning tokens where the provider reports them.

<!-- mdia-paired-efficiency:start -->

| Benchmark · model | MDia procedure vs reference | Questions / groups | Reference accuracy | MDia accuracy | Generated tokens per question (ref → MDia) | Generation saved |
|---|---|---:|---:|---:|---:|---:|
| CRUXEval · Qwen3.6-35B-A3B | Fixed specialist C2 vs Raw CoT (2048) | 96 / 96 | 94.79% | 94.79% | 606.60 → 272.43 | 55.09% |
| GPQA · DeepSeek-V4-Pro | Typed bound vs Adapted English (obligations) | 256 / 256 | 69.14% | 71.09% | 593.74 → 336.55 | 43.32% |
| MultiHop-RAG · Qwen3.6-35B-A3B | Typed query vs Paired English | 256 / 256 | 67.97% | 83.59% | 11.97 → 9.03 | 24.58% |
| CRUXEval · DeepSeek-V4-Flash | Python state vs Paired English | 256 / 256 | 94.53% | 94.53% | 181.89 → 142.70 | 21.55% |
| CRUXEval · GLM-5.2 | Selective literal integrity vs English piece trace | 256 / 256 | 92.58% | 94.14% | 90.02 → 72.40 | 19.57% |
| GPQA · GLM-5.3 | Obligation card vs Paired English | 256 / 256 | 70.31% | 75.78% | 1,070.52 → 894.40 | 16.45% |
| LiveCodeBench (output prediction) · DeepSeek-V4-Flash | Symbolic procedure vs Lexical procedure | 256 / 104 | 88.28% | 91.02% | 279.59 → 267.23 | 4.42% |

<!-- mdia-paired-efficiency:end -->

The table includes all pairs in the comparison inventory that matched or exceeded reference accuracy and reduced both generation and combined input-plus-output usage, with at least 96 whole groups and no reported gaps in token usage on either arm. The panels were available during development, so matching accuracy describes the observed panel. The detailed results give paired uncertainty and distinguish smaller panels, incomplete accounting and cases where longer inputs outweighed shorter outputs. [Paired results and accounting](artifacts/research/token-efficiency-v1/RESULTS.md)

On GPQA with GLM-5.3, the obligation card reduced generation by 16.45% while accuracy rose from 70.31% to 75.78%. The paired 95% interval for the accuracy difference was +0.78 to +10.16 percentage points. On Qwen MultiHop-RAG, the typed query reached 83.59% against paired English at 67.97%, with 24.58% less generation. TALE and schema each reached 86.33% on that panel. The Qwen CRUXEval comparison evaluates a fixed specialist. A matched baseline router reached 96.88% on the same questions. [October comparator panels](artifacts/research/20261005/results/ALL_BASELINE_PANELS.csv) · [November comparisons](artifacts/research/20261103/COMPARISONS.md)

The wider collection covers 11 benchmarks and four native model families. It also distinguishes changes in the proposed answer from changes in how the answer reaches the evaluator. On Kimi-K2.7-Code BFCL, for example, 71.43% of the tasks solved only by the GEPA procedure contained the same proposed tool calls as the optimized English control. [Benchmark collection](artifacts/research/20261103/README.md) · [Paired analyses](artifacts/research/20261103/FINDINGS.md)

Reproduce the efficiency table offline with Python 3.10 or later.

```sh
python3 -B scripts/reproduce_mdia_token_efficiency.py --check
python3 -B scripts/reproduce_mdia_token_efficiency.py --output runs/mdia-token-efficiency
```

The first command verifies the README table and the published results against their numerical sources. The second exports the table, arm-level token sums and an audit of all 32 comparisons to a new or empty directory. [Efficiency data](artifacts/research/token-efficiency-v1/output-savings.csv) · [October reproduction package](MDIA_EVIDENCE_README.md) · [November reproduction guide](artifacts/research/20261103/README.md)

## Quickstart

Run the deterministic example with Python 3.10 or later:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
mdia pipeline --config configs/toy_mdia.yaml
```

The [toy task set](examples/toy/) and replay provider exercise the entire lifecycle without credentials. The run writes a manifest, card generations, transfer profiles, a frozen bank, route decisions, predictions and an accounting report. A [complete example](artifacts/example/README.md) shows the output layout.

## Canonical pipeline

A speaker specifies a procedure; a listener uses it to solve a task. The stored card binds the symbols and operators to an explicit input/output contract. Two cards with similar vocabulary can lead to different predictions, and the same card can behave differently with another listener. MDia stores those measurements separately from the card text.

| Stage | What the system records |
|---|---|
| Collect and create | Direct traces on the induction partition and the first generation of cards |
| Evolve | Each generation's source cards, edits, borrowing and validation evidence |
| Profile and select | Receiver-specific accuracy, tokens and parse outcomes; the frozen bank |
| Run | The selected card or fallback, the model response, the evaluated answer and token accounting |
| Validate and report | Evidence-linked rule evaluations, routing decisions and held-out performance |

The [pipeline guide](docs/pipeline.md) defines the separate induction, evolution-validation, router-validation and test partitions. The [card and provider interfaces](docs/extending.md) support additional datasets and receivers. **CLSR** is the homogeneous-agent configuration of the same framework; see [the CLSR preset](configs/clsr.yaml).

## Routing semantics

A dialect router selects concrete cards by their frozen identifiers. A controller router selects an answer procedure, such as producing a schema or performing a verification step. Route plans distinguish using a single card, aggregating candidates, composing stages and falling back to a fixed solver. The resulting record makes it possible to compare selection against the same solver used on its own. The [architecture guide](docs/architecture.md) defines these interfaces.

## Documentation

| Resource | Contents |
|---|---|
| [Accuracy and native token use](artifacts/research/token-efficiency-v1/RESULTS.md) | Paired accuracy, generation savings and serving-token accounting |
| [Benchmark evidence and methods](artifacts/research/20261103/README.md) | Paired comparisons, exposure, group structure, serving and construction accounting |
| [October numerical release](docs/evidence-release-20261005.md) | Accuracy and generation-token frontiers, original settings and reproduction instructions |
| [Reproduction and data policy](docs/reproduction.md) | Offline verification, adapter experiments and historical inference protocols |
| [Paper-to-code map](docs/paper-to-code.md) | Manuscript concepts and their supported implementation |
| [Rule validation](docs/rules.md) | Evidence streams, statistical tests and interpretation |
| [Legacy implementations](legacy/README.md) | Earlier CLSR and MDia workspaces from the original `pzqpzq/LSF_MDia` repository |

## Citation

Use [CITATION.cff](CITATION.cff) to cite the software. The [MDia manuscript](papers/MDia_Jul17.pdf) presents the framework. For CLSR, cite Zhengqi Pei, Qingming Huang and Shuhui Wang, [*When LLMs Develop Languages: Symbolic Communication for Efficient Multi-Agent Reasoning*](https://arxiv.org/abs/2606.29354), ICML 2026.

Code is released under the [MIT License](LICENSE). Benchmark data and model weights retain their original licenses. For reproducibility questions, include the configuration, model revision, evaluator and smallest redistributable example. Academic correspondence: `peizhengqi22@mails.ucas.ac.cn`; industry collaborations: `peizhengqi@chipflow.net`.
