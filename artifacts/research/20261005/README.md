# MDia numerical evidence snapshot

The [release overview](../../../MDIA_EVIDENCE_README.md) presents the demonstrated gains across five benchmarks and three LLM families. This directory contains the numerical inputs and expected outputs for deterministic offline reproduction.

```text
data/core/        Seven curated paired settings and complete source summary panels
data/bfcl192/     All 36 common-192 points as scalar observation rows
data/crux192/     All 36 common-192 points as scalar observation rows
expected/        Saved numerical references
protocols/       Source digests, native accounting and generic serving specifications
results/         Verified tables, intervals, frontiers and figure
```

Run from the repository root:

```bash
python scripts/reproduce_mdia_release.py --output runs/mdia-evidence-20261005
```

The release manifest checksums the scripts, documentation, inputs and saved outputs. All supplied comparator points and logical aliases stay in the data. Native generated usage includes reasoning once; input usage is reported separately.

The files contain scalar measurements, opaque identifiers and generic method specifications. Original benchmark inputs are obtained from the sources listed in [DATA_SOURCES.json](protocols/DATA_SOURCES.json).

See the [protocol](../../../docs/evidence-release-20261005.md), [result tables](results/POSITIVE_RESULTS.md), [BFCL common-192 panel](results/BFCL192_ALL_POINTS.csv) and [CRUXEval common-192 panel](results/CRUX192_ALL_POINTS.csv).
