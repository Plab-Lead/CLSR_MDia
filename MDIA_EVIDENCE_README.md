# MDia benchmark results — 5 October 2026

MDia delivers useful accuracy–generated-token tradeoffs through reusable task-specific machine dialects. This release includes benchmark results across **five benchmarks and three LLM families**, complete numerical comparator panels, and deterministic offline reproduction.

This is an additive research snapshot for [LSF_MDia](https://github.com/pzqpzq/LSF_MDia), prepared against public commit **7235a1724dfe47d116461549c014baf9e32a67b2**.

## Demonstrated gains

| Benchmark / receiver | Cases | Correct: MDia / comparator | Generated-token saving | Comparator |
|---|---:|---:|---:|---|
| GPQA / GLM-5.3 | 256 | 194 / 180 | 16.45% | Paired English formulation |
| BFCL / Qwen3.6-35B-A3B | 192 | 181 / 177 | 65.31% | English, 8192-token cap |
| MultiHop-RAG / DeepSeek-V4-Flash | 256 | 172 / 167 | 60.29% | Sketch-of-Thought, 8192-token cap |
| LiveCodeBench / DeepSeek-V4-Flash | 256 cases in 104 groups | 230 / 230 | 15.19% | Raw CoT, 8192-token cap |
| CRUXEval / DeepSeek-V4-Flash | 256 | 242 / 242 | 21.55% | Paired English formulation |

Savings use native generated tokens per case. Input usage is reported separately in every numerical table; both TALE stages are included in its accounting. Equal correct counts describe the observed cohort.

The Qwen BFCL common-cohort panel is especially broad: its MDia parent has a better observed accuracy/generated-token point than **11 of 13 labelled baseline points**, spanning six baseline families. The full panel contains all seven registered baseline families and all 18 logical points per receiver. Its paired saving against English is **65.31%**, with an ordinary whole-group bootstrap interval of **60.63–69.41%**.

The release also preserves the original BFCL 256-case result, the Qwen CRUXEval 48-case result, and the DeepSeek-V4-Pro GPQA compact-profile tradeoff. A further completed Flash CRUXEval common-192 comparison records **182/192 correct for both paired formulations** and **23.01% generated-token saving**, with an ordinary interval of **13.81–32.78%**.

![MDia accuracy–generated-token comparisons](artifacts/research/20261005/results/POSITIVE_FRONTIERS.png)

## Reproduce in one command

Use Python 3.11 or newer (tested with Python 3.12.14). From the repository root:

```bash
python3 -m venv .venv-evidence
source .venv-evidence/bin/activate
python -m pip install -r requirements-evidence.lock.txt
python scripts/reproduce_mdia_release.py --output runs/mdia-evidence-20261005
```

Choose a fresh output directory. The script checks the release hashes, recomputes case-level aggregates, paired intervals and two-/three-dimensional frontiers, compares them with saved numerical references, exports complete comparison tables, and draws the figure. It makes **zero API calls**.

For a dependency-free integrity check:

```bash
python scripts/verify_mdia_release.py
```

## What is included

- Seven curated paired settings across five benchmarks, four named backbones and three families: GLM, Qwen and DeepSeek. Flash and Pro are two DeepSeek backbones.
- The full 55-point Flash 256-case comparison table across MultiHop-RAG, LiveCodeBench and CRUXEval.
- All 36 BFCL common-192 points and 34 paired contrasts.
- All 36 CRUXEval common-192 points and 52 paired contrasts.
- All 303 supplied baseline summary rows across 14 source panels.
- 16,576 case-policy observation rows for the seven curated pairs and the two common-192 panels, with original group identifiers, native costs, parse flags, aliases and source digests.
- Native policy identities, generic serving-spec examples, source provenance, fixed seeds and expected numerical outputs.

Observation rows and overlapping cohorts are not independent tasks or replications. The [protocol](docs/evidence-release-20261005.md) maps these inventories and their reproduction modes.

## Research scope

All supplied variants and comparator points remain in the numerical record. The comparisons use the registered task forms: GPQA multiple choice, BFCL AST function-call correctness, MultiHop-RAG reasoning over provided evidence, LiveCodeBench output prediction, and CRUXEval native input/output prediction.

This snapshot reproduces scalar arithmetic, whole-group pairing, frontiers and layout. The repository's canonical dataset/provider workflow supplies the separate route for new inference with independently acquired benchmark inputs. See [data sources](artifacts/research/20261005/protocols/DATA_SOURCES.json).

## Building future versions

These results motivate receiver-specific dialect profiles, compact procedural state, task-native contracts and budget-aware profile selection. Persistent, versioned serving specifications make those extensions concrete: future versions can add receiver profiles, larger fixed cohorts and new dialects while retaining the same accounting and comparison protocol.

Start with the [artifact index](artifacts/research/20261005/README.md), [reproduction protocol](docs/evidence-release-20261005.md), and [result tables](artifacts/research/20261005/results/POSITIVE_RESULTS.md).
