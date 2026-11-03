# MDia benchmark evidence · 3 November 2026

This collection measures how a reusable procedure changes a native model's answer on the same questions. It covers 16 procedure–comparator settings across 11 benchmarks and four model families. DeepSeek contributes Pro and Flash deployments; the two Kimi deployments belong to one family. Questions recur across receivers, procedures and nested cohorts. The number of settings is not a count of independent replications.

[Benchmark comparisons](COMPARISONS.md) · [Findings on answer delivery and construction](FINDINGS.md) · [Accuracy data](comparisons.csv) · [Serving data](serving.csv) · [Source statistics](records.json)

## Reproduce the analysis

From the repository root, using Python 3.10 or later:

```sh
python3 scripts/reproduce_mdia_evidence_20261103.py --check
python3 scripts/reproduce_mdia_evidence_20261103.py --output runs/mdia-20261103
```

The second command requires an empty or new output directory and writes two Markdown tables and two CSV files. The first checks the SHA-256 manifest and compares all four regenerated files byte for byte. Both use only the Python standard library. They perform numerical reproduction from aggregate records: no benchmark downloads, provider credentials, model inference, task execution or rescoring.

## Reading the comparisons

**Accuracy.** The numerator is the number of correct answers under the original evaluator. Gain is 100 × (procedure correct − comparator correct) / number of questions, in percentage points. The paired counts record procedure only, comparator only, both correct and both incorrect. They reconstruct both marginals for 14 comparisons; the two GLM CRUX comparisons use the complete published arm marginals. The GLM bank was model-authored and manually screened. Its retained parent had identical per-case correctness. BFCL's GEPA candidate and paired English control both used English; their instructions differed in content.

**Cohorts.** These are exposed development comparisons, including contrasts chosen after the scores were available. They describe performance against the comparator named on each row. The MATH row is the 56-question Level 5 subgroup of a 256-question panel; [the complement and full result](FINDINGS.md) give its scope. All four BFCL deployments share 192 tasks. The MultiHop deployments share 256 questions. LiveCodeBench is an **output-prediction** evaluation: 256 queries from 104 programs. FOLIO has 204 questions from 73 premise sets; MuSR has 257 from 128 stories. Public tasks and model-generated code are never executed by this analysis.

**Uncertainty.** The table carries through the original unadjusted, group-paired 95% intervals where reported. They are conditional on exposed cohorts, and selection across contrasts is not adjusted. Historical bootstrap resamples cannot be reconstructed from arm totals alone. For the separate BFCL difference between deployments, the released joint win/tie/loss tables *are* sufficient: the reproducer computes the exact empirical whole-task bootstrap distribution by integer convolution, including the sensitivity to changing the reference from optimized English to Direct. The explanatory QA counts likewise reconcile each disjoint extraction stratum and the earlier/added cohorts against the full panel.

**Accounting.** Total-token change is 100 × (procedure tokens / comparator tokens − 1), with tokens equal to the recorded native input plus generation, including reported reasoning. The Kimi-Code GEPA procedure, for example, generated fewer tokens but used more input; its total was 72.15% higher than optimized English. [Serving data](serving.csv) report the two token fields and the original latency statistic and coverage separately. MultiHop/Pro has one earlier procedure attempt with unknown usage; FOLIO and MMLU-Pro have one such Raw attempt each. Zero reported unknown attempts does not certify an invoice. A blank cost, latency or coverage cell means unavailable. Latency sums are not wall time. Do not add repeated logical rows across settings to infer campaign expenditure.

**Construction.** The two BFCL GEPA searches each used 192 metric evaluations and six proposals. Including compatible predecessor seed activity, the candidate and English construction families recorded 198 and 186 physical attempts, respectively. These are shared construction costs across deployments. The GLM module bank has six recorded constructor calls (22,857 input and 3,265 generated tokens); historical adaptation and human design time are not fully metered. Three synthetic calibrations in the [findings](FINDINGS.md) have separate native call, token and latency accounting in the source statistics. They do not contribute benchmarks to the accuracy table.

## Numerical provenance

`records.json` contains only scalar counts, cohort summaries, native settings where identified, and checksums of the source reports. It includes the 32 serving arms used by the 16 comparisons, companion control counts and separate diagnostic data. A null recipe on the pooled selective-integrity row means there is no unified recipe record in that aggregate. Routes, raw responses, task identifiers, benchmark inputs, reference answers and billing records are not inputs to this release. The [reproduction policy](../../../docs/reproduction.md) distinguishes reproducing a numerical analysis from running an exact historical inference protocol.
