# Paired accuracy and native token use

The comparison inventory contains 32 named contrasts. In 22, the procedure matched or exceeded its reference's observed accuracy and used fewer output tokens. 10 also used fewer recorded input-plus-output tokens. Several comparisons reuse the same questions or procedures, which limits their independence.

## Lower output and total token use

Every row below meets both token criteria on at least 96 whole groups, with zero prior unknown-usage indicators reported for either arm. Generation saved is the percentage reduction in native output tokens relative to the named reference. Generation includes reasoning tokens where the provider reports them.

| Benchmark · model | MDia procedure vs reference | Questions / groups | Reference accuracy | MDia accuracy | Generated tokens per question (ref → MDia) | Generation saved |
|---|---|---:|---:|---:|---:|---:|
| CRUXEval · Qwen3.6-35B-A3B | Fixed specialist C2 vs Raw CoT (2048) | 96 / 96 | 94.79% | 94.79% | 606.60 → 272.43 | 55.09% |
| GPQA · DeepSeek-V4-Pro | Typed bound vs Adapted English (obligations) | 256 / 256 | 69.14% | 71.09% | 593.74 → 336.55 | 43.32% |
| MultiHop-RAG · Qwen3.6-35B-A3B | Typed query vs Paired English | 256 / 256 | 67.97% | 83.59% | 11.97 → 9.03 | 24.58% |
| CRUXEval · DeepSeek-V4-Flash | Python state vs Paired English | 256 / 256 | 94.53% | 94.53% | 181.89 → 142.70 | 21.55% |
| CRUXEval · GLM-5.2 | Selective literal integrity vs English piece trace | 256 / 256 | 92.58% | 94.14% | 90.02 → 72.40 | 19.57% |
| GPQA · GLM-5.3 | Obligation card vs Paired English | 256 / 256 | 70.31% | 75.78% | 1,070.52 → 894.40 | 16.45% |
| LiveCodeBench (output prediction) · DeepSeek-V4-Flash | Symbolic procedure vs Lexical procedure | 256 / 104 | 88.28% | 91.02% | 279.59 → 267.23 | 4.42% |

The Qwen CRUXEval row evaluates a fixed specialist. The matched baseline router reached 96.88% on the same panel. For GLM-5.2, the combined CRUXEval estimate includes 64 additional groups on which English reached 100.00% and MDia reached 92.19%. On GPQA, the archived GLM-5.3 schema control reached 77.34%. On Qwen MultiHop-RAG, TALE and schema each reached 86.33%. The natural-language LiveCodeBench control reached 92.19%. The displayed LiveCodeBench pair holds the ordinary-English reasoning frame fixed.

## Smaller panels and incomplete attempt accounting

The following pairs also meet both observed token criteria. The Qwen transfer panel has 48 groups. On MultiHop-RAG Pro the procedure has one prior attempt with unknown usage. On MMLU-Pro the Raw CoT reference has one. Their totals cover recorded usage.

| Benchmark · model | MDia procedure vs reference | Questions / groups | Reference accuracy | MDia accuracy | Generated tokens per question (ref → MDia) | Generation saved |
|---|---|---:|---:|---:|---:|---:|
| CRUXEval · Qwen (transfer panel) | Python state vs Original English | 48 / 48 | 91.67% | 95.83% | 274.15 → 199.88 | 27.09% |
| MMLU-Pro · Qwen3.6-35B-A3B | Compiled card vs Raw CoT (2048) | 256 / 256 | 76.17% | 76.56% | 1,033.05 → 687.07 | 33.49% |
| MultiHop-RAG · DeepSeek-V4-Pro | Selective evidence vs Flat-terminal English | 256 / 256 | 80.08% | 80.47% | 7.61 → 6.87 | 9.80% |

## Shorter generations with greater total token use

In these pairs, the additional input tokens outweighed the reduction in generation. The MATH Level 5 subgroup was chosen after inspecting outcomes. The BFCL GEPA comparisons use two English procedures.

| Benchmark · model | MDia procedure vs reference | Questions / groups | Reference accuracy | MDia accuracy | Generated tokens per question (ref → MDia) | Generation saved |
|---|---|---:|---:|---:|---:|---:|
| BBEH · DeepSeek-V4-Flash | Contrastive card R2 vs Raw CoT (2048) | 256 / 256 | 29.30% | 31.64% | 1,034.52 → 997.77 | 3.55% |
| BFCL · Kimi-K2.6 | GEPA procedure vs Optimized English | 192 / 192 | 94.27% | 97.40% | 213.17 → 43.58 | 79.55% |
| BFCL · Kimi-K2.7-Code | GEPA procedure vs Optimized English | 192 / 192 | 85.94% | 95.31% | 247.27 → 205.56 | 16.87% |
| BFCL · Qwen3.6-35B-A3B | Parent card (8192) vs Direct (8192) | 256 / 256 | 94.14% | 94.53% | 94.00 → 82.91 | 11.80% |
| BFCL · Qwen3.6-35B-A3B | GEPA procedure vs Optimized English | 192 / 192 | 92.71% | 93.75% | 248.46 → 95.45 | 61.58% |
| CRUXEval · GLM-5.2 | Selective literal integrity vs Raw CoT (2048) | 256 / 256 | 89.45% | 94.14% | 134.61 → 72.40 | 46.21% |
| CRUXEval · GLM-5.2 | Model-authored module bank vs Paired English bank | 192 / 192 | 90.10% | 95.31% | 81.20 → 72.86 | 10.27% |
| GPQA · DeepSeek-V4-Pro | Typed bound vs Raw CoT (2048) | 256 / 256 | 69.92% | 71.09% | 397.38 → 336.55 | 15.31% |
| LiveCodeBench (output prediction) · DeepSeek-V4-Flash | Compiled card (2048) vs Raw CoT (8192) | 256 / 104 | 89.84% | 89.84% | 296.57 → 251.52 | 15.19% |
| MATH (Level 5) · DeepSeek-V4-Flash | Derive and substitute vs Paired English | 56 / 56 | 76.79% | 82.14% | 418.57 → 413.30 | 1.26% |
| MultiHop-RAG · DeepSeek-V4-Flash | Parent card (8192) vs Sketch-of-Thought (8192) | 256 / 256 | 65.23% | 67.19% | 27.59 → 10.95 | 60.29% |
| MultiHop-RAG · DeepSeek-V4-Pro | Selective evidence vs Paired English | 256 / 256 | 74.22% | 80.47% | 7.18 → 6.87 | 4.40% |

## Sources and interpretation

The inventory includes the seven October core pairs, all 16 November comparisons, the seven metered QA companion controls and two archived CRUXEval comparisons (C2 and C6). Each comparison uses the same questions on both sides. Benchmark panels were development-exposed and contrasts were selected retrospectively. Generated tokens per question is the output subtotal divided by the question count. Generation saved is 100 × (reference output − procedure output) / reference output, computed from integer subtotals before rounding. The CSV lists raw token sums by arm, group counts, prior unknown-usage indicators and available unadjusted paired 95% accuracy intervals. A blank interval or usage field means unavailable. Formal equivalence would require a prespecified accuracy margin and a paired equivalence analysis. The token totals cover serving and exclude construction. Charges and latency require separate accounting. See the October baseline panels and the November comparison and serving tables under `artifacts/research/20261005` and `artifacts/research/20261103` in the repository. [Generation savings data](output-savings.csv)

From the repository root, run the following with Python 3.10 or later. The first command verifies the input digests, the README table and the published numerical outputs. The second writes those outputs, a standalone README table and the full comparison inventory to a new or empty directory.

~~~sh
python3 -B scripts/reproduce_mdia_token_efficiency.py --check
python3 -B scripts/reproduce_mdia_token_efficiency.py --output runs/mdia-token-efficiency
~~~

The seven October comparisons are re-paired by case and whole group. The November records supply paired counts and arm-level token sums. The scalar supplement in `artifacts/research/token-efficiency-v1/supplement.json` supplies the two additional CRUXEval pairs and QA control accounting. Its exporter, `scripts/export_mdia_token_efficiency_sources.py`, verifies those values against four archived reports identified by SHA-256.
