## Benchmark results and reproduction

The October 2026 release provides measured MDia receiver profiles across **five benchmarks and three LLM families: GLM, Qwen and DeepSeek**. Reusable dialects encode task-relevant obligations, function-call procedures, evidence links, compact code state and Python execution state.

| Benchmark / receiver | Cases | Comparator | Correct: MDia / comparator | Generated tokens per case: MDia / comparator | Generated-token saving |
|---|---:|---|---:|---:|---:|
| GPQA / GLM-5.3 | 256 | Paired English formulation | **194 / 180** | 894.398 / 1,070.523 | **16.45%** |
| BFCL / Qwen3.6-35B-A3B | 192 | English, 8192-token cap | **181 / 177** | 81.380 / 234.583 | **65.31%** |
| MultiHop-RAG / DeepSeek-V4-Flash | 256 | Sketch-of-Thought, 8192-token cap | **172 / 167** | 10.953 / 27.586 | **60.29%** |
| LiveCodeBench / DeepSeek-V4-Flash | 256 cases / 104 problem groups | Raw CoT, 8192-token cap | **230 / 230** | 251.520 / 296.566 | **15.19%** |
| CRUXEval / DeepSeek-V4-Flash | 256 | Paired English formulation | **242 / 242** | 142.695 / 181.887 | **21.55%** |

Savings refer to native **generated tokens**, including native reasoning once. Native input usage is reported separately in the complete tables, and TALE accounting includes both estimator and solver stages. Correct counts describe the recorded cohort. The BFCL row uses the source Qwen parent profile and a new common-cohort English comparison.

In the Qwen BFCL common-192 panel, the MDia parent improves the observed accuracy/generated-token point over **11 of 13 baseline points**, spanning six baseline families. All seven registered baseline families remain in the full panel. The English comparison's generated-token saving has an ordinary whole-group bootstrap interval of **60.63–69.41%**.

![MDia accuracy–generated-token comparison panels](artifacts/research/20261005/results/POSITIVE_FRONTIERS.png)

### Reproduce the released tables and figures

Clone this repository, use **Python 3.11+** (tested with Python 3.12.14), and run:

```bash
python3 -m venv .venv-evidence
source .venv-evidence/bin/activate
python -m pip install -r requirements-evidence.lock.txt
python scripts/verify_mdia_release.py
python scripts/reproduce_mdia_release.py --output runs/mdia-results-20261005
```

Choose a fresh output directory. The command verifies the file manifest, recomputes aggregates, whole-group paired intervals and accuracy/generated/input frontiers, checks the saved numerical references, and exports the tables and PNG/SVG figure. It runs offline without API credentials. `VALIDATION.json` records the checks and runtime versions.

The package contains **16,576 case-policy observation rows**, the complete **55-point Flash 256-case block**, all **36 BFCL common-192 points / 34 contrasts**, all **36 CRUXEval common-192 points / 52 contrasts**, and **303 baseline summary rows**. Original cohort and logical alias identities remain available throughout the numerical records.

- [Results overview and instructions](MDIA_EVIDENCE_README.md)
- [Full BFCL common-192 table](artifacts/research/20261005/results/BFCL192_ALL_POINTS.csv)
- [Full Flash 256-case table](artifacts/research/20261005/results/FLASH256_ALL_POINTS.csv)
- [Full CRUXEval common-192 table](artifacts/research/20261005/results/CRUX192_ALL_POINTS.csv)
- [Paired settings and separate input accounting](artifacts/research/20261005/results/POSITIVE_RESULTS.md)
- [Reproduction protocol, seeds and source mapping](docs/evidence-release-20261005.md)
- [Download the versioned package](https://github.com/pzqpzq/LSF_MDia/raw/refs/tags/mdia-results-20261005/releases/mdia-results-20261005.zip)

These commands reproduce the numerical analyses and presentation from the released scalar records. For new model inference, acquire the benchmark inputs from their original sources and use the dataset/provider interfaces in [Extending MDia](https://github.com/pzqpzq/LSF_MDia/blob/mdia-results-20261005/docs/extending.md).
