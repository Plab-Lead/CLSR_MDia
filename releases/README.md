# MDia benchmark release — 5 October 2026

Download [mdia-results-20261005.zip](mdia-results-20261005.zip) and verify it against [the SHA-256 checksum](mdia-results-20261005.zip.sha256). This additive package contains the benchmark tables, numerical records, serving-specification examples and deterministic reproduction scripts.

The files are also available directly in the repository. Start with [the results overview](../MDIA_EVIDENCE_README.md) and [the reproduction protocol](../docs/evidence-release-20261005.md).

## Use the package

Extract the archive into the root of an MDia checkout, or clone this repository and use its included files. With Python 3.11 or newer:

```bash
python3 -m venv .venv-evidence
source .venv-evidence/bin/activate
python -m pip install -r requirements-evidence.lock.txt
python scripts/verify_mdia_release.py
python scripts/reproduce_mdia_release.py --output runs/mdia-results-20261005
```

Use a fresh output directory. The script recomputes case-level aggregates, whole-group paired intervals and frontiers, validates the saved numerical references, and exports complete tables and PNG/SVG figures. The command runs offline without API credentials.

The reference presentation lives under [artifacts/research/20261005/results/](../artifacts/research/20261005/results/). The full comparison data include the Flash 256 three-benchmark block and BFCL/CRUXEval common-192 panels. Native generated and input tokens are reported separately.

MDia is the general framework for new experiments and applications. Its dataset/provider interfaces and versioned dialect cards support adding receiver profiles, task-native contracts and budgeted routing policies. See [Extending MDia](../docs/extending.md).

## Repository integration

The benchmark assets build on public commit 7235a1724dfe47d116461549c014baf9e32a67b2. The supported source implementation retains version 1.0.0; this release adds measured results, numerical scripts and documentation.

Code follows the repository's MIT license. Obtain benchmark inputs separately from their original sources when running new inference.
