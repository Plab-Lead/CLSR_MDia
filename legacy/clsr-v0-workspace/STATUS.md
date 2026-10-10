# Status: CLSR v0 research workspace

**Status:** archived, incomplete, noncanonical.

This tree was formerly `LSF-v0-draft/`. It contains early scripts for creating, evolving, evaluating, and selecting Language Symbolism Frameworks in the homogeneous-agent setting that became CLSR.

## Historical role

- `evolve-PLL-v1.py` evolves prompt-language/LSF candidates from previously selected examples.
- `eval-evolvePLL-v1.py` evaluates raw and LSF-conditioned outputs.
- `get_evolved_samples_v1.py` ranks saved runs using correctness and token counts.
- `llm_utils/` contains local model, dataset, and evaluator helpers.
- `meta_prompts/meta_LSFs_v2.json` is the recovered level-0 through level-9 meta-LSF prompt bank expected by the evolution/evaluation scripts.

The recovered prompt bank was copied read-only from the corresponding file in the private FlatSymbolism research workspace on 2026-07-30. It parses as JSON, contains no detected credential or private absolute-path patterns, and has SHA-256:

```text
0ad8f6b5bea37c37eef18ee95ffef4fbd1f3b8650a1b66af3feaf49295d9ccba
```

Its inclusion resolves the missing-input problem for historical inspection, but it does not make this workspace a reproducible release.

## Expected inputs

The scripts expect local Hugging Face dataset mirrors, local model checkpoints, generated candidate directories such as `PLLs/`, `PLL-preds-record/`, and `evoluted_Samples/`, plus the Python dependencies imported directly by the scripts. Most of those artifacts are intentionally not committed.

## Known limitations

- Dataset and model paths are hard-coded placeholders and must not be treated as portable configuration.
- The scripts use module-level experiment switches rather than a validated CLI/config schema.
- The complete generation/evaluation directory graph and dependency lock are absent.
- Partitions, stable card identities, selection provenance, and leakage controls do not meet the canonical MDia contract.
- The recovered prompt bank is a historical input, not a canonical MDia dialect bank.

Use `configs/clsr.yaml` with the root CLI for the supported homogeneous special case.
