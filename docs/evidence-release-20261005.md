# MDia benchmark reproduction protocol

This additive snapshot accompanies public MDia commit **7235a1724dfe47d116461549c014baf9e32a67b2**. Its scripts live beside the canonical implementation and read only the research files under `artifacts/research/20261005`.

## Run and verify

```bash
python -m pip install -r requirements-evidence.lock.txt
python scripts/verify_mdia_release.py
python scripts/reproduce_mdia_release.py --output runs/mdia-evidence-20261005
python -m unittest discover -s tests -p 'test_evidence_release.py'
```

The reproduction command requires a new output directory, verifies every manifest member before arithmetic, and blocks Python socket connections. It preserves the included input files. The lock file records the tested numerical environment; `requirements-evidence.txt` describes the broader supported dependency range.

## Evidence inventories

| Inventory | Case-policy rows | Numerical reproduction |
|---|---:|---|
| Seven curated paired settings | 2,752 | Both sides, aggregates and seven whole-group contrasts |
| BFCL common-192, Qwen and Pro | 6,912 | 36 points, 34 contrasts, two-/three-dimensional frontiers |
| CRUXEval common-192, Flash and Qwen | 6,912 | 36 points, 52 contrasts, two-/three-dimensional frontiers |

These sum to **16,576 observation rows**. Cohorts can overlap; policy rows, source panels and logical aliases retain their original identities.

The separately supplied baseline summary inventory has **14 panels / 303 rows**. The curated frontier inventory has **eight panels / 149 labelled points**, including the complete **55-point Flash 256-case block**. Summary tables are exported from hash-verified aggregate source files; case-level recomputation covers the inventories in the table above.

## Native accounting and pairing

Generated usage includes native reasoning once. Input usage is separate. TALE includes estimator and solver stages. Cost availability is carried explicitly through whole-cost means, contrasts and frontier classification. Logical labels that share a physical receipt remain marked as aliases. Original source-field presence and separately derived provenance are retained.

The seven curated pairs use 10,000 PCG64 whole-group bootstrap draws, seeds 20261001 through 20261007, and sorted opaque group/case identifiers. LiveCodeBench preserves its 104 original problem groups across 256 cases and uses case-weighted whole-group resampling.

BFCL common-192 uses 10,000 PCG64 draws with seed **20261003** in the original `group_order`. CRUXEval common-192 uses 10,000 PCG64 draws with seed **20261002**, with its supplied backbone-specific order mapping. These are ordinary descriptive intervals for the recorded cohorts; the source campaign permitted test-set variant development. Original grades and registered parse flags are used directly.

## Outputs

The command writes:

- `POSITIVE_RESULTS.csv` and `POSITIVE_RESULTS.md`: seven curated paired settings.
- `FLASH256_ALL_POINTS.csv`: the three-benchmark 55-point source block.
- `ALL_BASELINE_PANELS.csv`: all 303 supplied summary rows.
- `ALL_CURATED_FRONTIER_POINTS.csv`: all 149 curated source points.
- `CORE_AGGREGATES.json`, `CORE_PAIRED.json` and `CORE_FRONTIERS.json`.
- `BFCL192_ALL_POINTS.csv`, `BFCL192_POINTS.json`, `BFCL192_PAIRED.json` and `BFCL192_FRONTIERS.json`.
- `CRUX192_ALL_POINTS.csv`, `CRUX192_POINTS.json`, `CRUX192_PAIRED.json` and `CRUX192_FRONTIERS.json`.
- `POSITIVE_FRONTIERS.png` and `POSITIVE_FRONTIERS.svg`.
- `VALIDATION.json`: checksum count, numerical comparisons, runtime versions and offline execution status.

The BFCL plot uses the complete Qwen common-192 panel. The other four plotted benchmarks use their complete curated 256-case source panels. Input usage sets marker size; blue stars identify the retained MDia profiles. Numerical tables retain every source point and its cost-availability fields.

## Serving specifications and provenance

`protocols/native_policies.json` records ten original policy identities and their native decoding parameters. `protocols/serving_spec_examples.json` contains ten generic author-owned served-specification examples with content and source-file digests. Examples illustrate the reusable instruction format; each example retains its own registry identity. Numerical rows are linked by opaque policy, task, group and source-review identities.

`protocols/SOURCE_PROVENANCE.json` pins the reviewed packet origins and exact scalar source bytes. `protocols/ACCOUNTING.json` defines units, seeds and interval interpretation. `protocols/DATA_SOURCES.json` links the original benchmark sources.

New inference uses separately acquired benchmark inputs, registered wrappers/scorers and provider access through the canonical MDia workflow. The included command needs only the numerical exports and runs entirely offline.

## Future profile development

A new receiver profile can carry a versioned serving specification, an explicit task contract, a fixed whole-group cohort and symmetric native budgets. Recording all comparator arms, input/generated usage and per-task aliases makes future profiles directly comparable with this snapshot.

Code uses the repository's MIT license. Benchmark inputs are acquired separately under their original terms.
