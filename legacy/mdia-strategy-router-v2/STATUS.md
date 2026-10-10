# Status: metadata strategy/controller router

**Status:** archived diagnostic package, noncanonical.

This tree was formerly `LSF-v2/`. Its old version name caused a semantic collision: it is not a newer implementation of evolved-LSF routing. It selects a handcrafted reasoning/controller family from observable benchmark metadata and then applies a strict answer contract.

## What its router does

`mdia/routing.py` maps benchmark and subtype metadata to route names such as schema-first, verification, contrastive, or null-aware strategies. `mdia/prompts.py` translates the selected controller into an internal prompt and parser-facing answer contract. The route output does **not** contain a stable evolved dialect-card ID or specification digest.

In canonical terminology this is a `ControllerRouter`, not the primary `DialectRouter`.

## Expected inputs

- task JSONL in one of the documented legacy benchmark-specific shapes;
- `configs/route_map.json`;
- an OpenAI-compatible endpoint and runtime key in `MDIA_API_KEY`; and
- benchmark-appropriate evaluation data when scoring is requested.

## Known limitations

- Routes are handcrafted strategies rather than created/evolved LSF cards.
- The lightweight evaluators are diagnostic and are not substitutes for official benchmark harnesses.
- Included CSV/JSONL files are selected historical snapshots. Their old README claims are not revalidated by the canonical pipeline and must not be generalized to paper reproduction.
- The package has no shared canonical split, dialect-bank, or run-manifest contract.
- The private `MDia-v2` workspace contains broader controller sweeps and a 100-rule registry; it also contains private operations/configuration material and was not copied.

The canonical root package may apply controller routing as an optional layer **in addition to** concrete-card routing, and records the two decisions separately.
