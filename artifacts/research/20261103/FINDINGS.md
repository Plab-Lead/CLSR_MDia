# Where the differences arise

These paired analyses concern supplied procedures, recorded outputs and evaluator decisions on exposed cohorts.

| QA comparison | Both answers extractable | Only procedure correct / only English correct among those pairs | Net gain outside those pairs |
|---|---:|---:|---:|
| GPQA · DeepSeek-V4-Pro | 255/256 | 30 / 15 | -1 |
| MultiHop-RAG · DeepSeek-V4-Pro | 256/256 | 19 / 3 | +0 |
| MultiHop-RAG · Qwen3.6-35B-A3B | 256/256 | 48 / 8 | +0 |
| AIME · DeepSeek-V4-Flash | 36/60 | 7 / 2 | +4 |

On both MultiHop deployments, the whole margin occurred among pairs with extractable answers. On AIME, extraction also contributed. These observations locate score differences in the outputs; they do not identify a change in internal reasoning.

| Stronger English comparison | Correct (procedure / English) | Accuracy 95% interval (pp) | Change in recorded total tokens |
|---|---:|---:|---:|
| GPQA · obligation english | 182 / 177 | -3.13, +7.42 | -27.47% |
| MultiHop-RAG · flat terminal | 206 / 205 | -3.13, +4.30 | -10.59% |

Both paired intervals for the accuracy difference against these stronger English controls include zero.

## Recipient and output format

| Reference | Additional GEPA gain on Kimi-K2.7-Code relative to Kimi-K2.6 (pp) | Exact paired bootstrap 95% interval (pp) |
|---|---:|---:|
| optimized English | +6.25 | +1.04, +11.46 |
| Direct | +0.00 | -3.13, +3.13 |

On Code, 15 of 21 procedure-only wins contained the same proposed calls as English but differed in output format. This held for 10/10 procedure-only wins on parallel calls. Both optimized procedures were written in English. These wins locate a difference at the output contract.

DeepSeek and Qwen each recovered 4 of the 8 tasks both English controls missed. The observed overlap was 2; the expected overlap conditional on the two recovery counts was 2.

## Subgroup and instruction effects

On MATH Level 5, derive-and-substitute solved 46 questions and English solved 43. The other 200 questions gave 186 versus 189, yielding a full-panel tie at 232/256.

On LiveCodeBench, the symbolic / lexical counts were 233 / 226 with ordinary-English reasoning instructions and 225 / 230 with machine-dialect instructions. The interaction was -4.69 pp (archived 95% interval -9.84 to +0.39). The procedures differ in wording and length as well as notation.

## Construction history

Before construction, GLM and Qwen delivered different instructions on 55/192 groups. After construction, they differed on 23/192. GLM changed to match Qwen on 32 groups. Matched English had the same transition counts. Equality here means identical instruction text.

## Comparison scope

On the 64 CRUX groups added to the selective-integrity panel, the procedure solved 59 and English piece trace solved 64. The 192- and 256-group panels overlap.

The MuSR question-based baseline replay combined two fixed controls for 182/257 correct. Its components were chosen retrospectively; this was not an online router.

Across the four full panels with same-cap Raw comparisons (FOLIO, MuSR, BBEH and MMLU-Pro), 4 of 10 compatible registered contrasts favored the procedure. Their named positive comparisons appear in the table. The breadth count represents benchmarks; it is not a win rate or a fully crossed family-by-benchmark design.

## Reading an action from a working note

A calibration on synthetic tasks measured how often the same reader found a single explicitly tagged choice. The two information conditions used 16 notes per model. Counts below refer to readable choices, not benchmark accuracy.

| Native model | Full-information tagged / notes | Local-information tagged / notes |
|---|---:|---:|
| GLM-5.2 | 2/16 | 0/16 |
| Qwen3.6-35B-A3B | 16/16 | 7/16 |
| Kimi-K2.6 | 5/16 | 0/16 |

Two further Qwen calibrations compared strict parsing with a frozen renderer on the same model responses.

| Calibration | Full: strict / rendered correct | Local: strict / rendered correct | Cases per condition |
|---|---:|---:|---:|
| C9 | 6 / 15 | 0 / 0 | 16 |
| C11a | 10 / 16 | 2 / 2 | 16 |

Rendering made existing choices scoreable. These small calibrations measure answer delivery; they do not test transmission between agents and are outside the benchmark count.
