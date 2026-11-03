# Benchmark comparisons

Counts are paired on the stated cohort. Change in tokens uses recorded native input plus generation. Intervals are the archived, unadjusted group-paired 95% intervals; a dash means none was supplied for this contrast. The accompanying [scope and methods](README.md) describe exposure, accounting and the controls.

| Benchmark · receiver | Procedure vs comparator | Questions / groups | Correct | Gain (pp) | 95% interval (pp) | Total tokens | Other controls (correct, same cohort) |
|---|---|---:|---:|---:|---:|---:|---|
| GPQA · DeepSeek-V4-Pro | Typed bound vs Paired English | 256 / 256 | 182 / 168 | +5.47 | +0.39, +10.55 | +0.46% | raw 2048: 179; obligation english: 177 |
| MultiHop-RAG · DeepSeek-V4-Pro | Selective evidence vs Paired English | 256 / 256 | 206 / 190 | +6.25 | +3.13, +9.77 | +2.69% | flat terminal: 205 |
| MultiHop-RAG · Qwen3.6-35B-A3B | Typed query vs Paired English | 256 / 256 | 214 / 174 | +15.63 | — | -0.82% | TALE EP reimplementation: 221; schema only 8192: 221 |
| AIME · DeepSeek-V4-Flash | Counting equivalence vs Paired English | 60 / 60 | 29 / 20 | +15.00 | — | +3.88% | raw 8192: 34; parent 8192: 34 |
| CRUXEval · GLM-5.2 | Selective literal integrity vs Raw CoT (2048) | 256 / 256 | 241 / 229 | +4.69 | +0.39, +8.98 | +16.41% | English piece trace: 237 |
| CRUXEval · GLM-5.2 | Model-authored module bank vs Paired English bank | 192 / 192 | 183 / 173 | +5.21 | +2.08, +8.85 | +1.52% | Retained parent: 183 |
| BFCL · Kimi-K2.7-Code | GEPA procedure vs Optimized English | 192 / 192 | 183 / 165 | +9.38 | +4.69, +14.06 | +72.15% | direct 2048: 185; schema only 8192: 186 |
| BFCL · Kimi-K2.6 | GEPA procedure vs Optimized English | 192 / 192 | 187 / 181 | +3.13 | +0.00, +6.25 | +53.78% | direct 2048: 189; schema only 8192: 186 |
| BFCL · DeepSeek-V4-Pro | GEPA procedure vs Optimized English | 192 / 192 | 180 / 174 | +3.13 | -1.56, +7.81 | +113.54% | direct 2048: 182; schema only 8192: 180; sot 8192: 185 |
| BFCL · Qwen3.6-35B-A3B | GEPA procedure vs Optimized English | 192 / 192 | 180 / 178 | +1.04 | -2.60, +4.69 | +54.82% | direct 2048: 179; schema only 8192: 180; raw 2048: 181; raw 8192: 181; parent 8192: 181 |
| MATH (Level 5) · DeepSeek-V4-Flash | Derive and substitute vs Paired English | 56 / 56 | 46 / 43 | +5.36 | -5.36, +16.07 | +0.40% | raw 2048: 51; raw 8192: 52; schema only 2048: 49 |
| LiveCodeBench · DeepSeek-V4-Flash | Symbolic procedure vs Lexical procedure | 256 / 104 | 233 / 226 | +2.73 | -0.80, +6.32 | -6.04% | sot 8192: 234; raw 2048: 226; natural 2048: 236; raw 8192: 230 |
| MMLU-Pro · Qwen3.6-35B-A3B | Compiled card vs Raw CoT (2048) | 256 / 256 | 196 / 195 | +0.39 | -3.13, +3.91 | -18.66% | raw 8192: 216; natural 2048: 198 |
| FOLIO · DeepSeek-V4-Flash | Contrastive card R1 vs Raw CoT (2048) | 204 / 73 | 156 / 144 | +5.88 | +0.99, +10.58 | +129.46% | natural 2048: 157 |
| MuSR · Qwen3.6-35B-A3B | GEPA procedure vs Raw CoT (2048) | 257 / 128 | 166 / 152 | +5.45 | -1.24, +12.10 | +26.49% | natural 2048: 176 |
| BBEH · DeepSeek-V4-Flash | Contrastive card R2 vs Raw CoT (2048) | 256 / 256 | 81 / 75 | +2.34 | -3.52, +8.20 | +10.99% | raw 8192: 88; natural 2048: 83 |
