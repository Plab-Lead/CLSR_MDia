# Complete offline example

This directory is the committed output of:

```bash
MDIA_CODE_REVISION=mdia-v1.0.0-example mdia pipeline \
  --config configs/toy_mdia.yaml \
  --run-dir artifacts/example
```

The tasks and replay outputs are synthetic and redistributable under the fixture license in
[`examples/toy/DATA_LICENSE.json`](../../examples/toy/DATA_LICENSE.json). Results verify the software
contract only: the exact-match scores are diagnostic, and the 100 `not_evaluated` rule records correctly
show that this fixture supplies no paper-scale sociolinguistic evidence.

Use `manifest.json` for schema, configuration, split, model, seed, candidate-pool, and artifact hashes.
