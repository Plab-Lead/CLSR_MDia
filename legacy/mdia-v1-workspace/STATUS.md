# Status: MDia v1 research workspace

**Status:** archived research provenance, partially runnable only with missing private inputs, noncanonical.

This tree was formerly `LSF-v1/`. It is the important conceptual bridge from homogeneous CLSR to MDia: multiple model families create and execute dialects, saved generation records preserve evolution, and the router works with concrete evolved LSFs.

## Historical role

- `evolve_LSF_apr21.py` bootstraps and evolves LSF text from correct, concise heterogeneous traces.
- `eval_LSFs_apr21.py` runs dialect-conditioned evaluation.
- `llm_router_reproduce_mdia.py` contains the later experimental concrete-LSF routing path.
- `lsf_evolve_records/` contains selected evolution snapshots.
- `raw_llm_preds/`, `single_lsf_preds/`, and `routed_lsf_preds/` contain representative saved outputs.

The private `MDia-v1` workspace also contains larger run inventories, job lists, partial/resume logs, and coverage reports. Those private operations files were inspected for behavior but were not copied into this public archive.

## Expected inputs

The evolution and evaluation scripts expect local dataset mirrors, `rawLLM-preds-record/` and other generated result trees, model/provider access, and environment-specific dependencies. Only a small provenance sample is committed here.

## Known limitations

- Two early scripts reference external `API_key`/`API_KEY` variables and hard-coded experiment choices; no secret is included.
- Local dataset paths and implicit filename metadata are not portable interfaces.
- The archived records do not constitute complete immutable induction, evolution-validation, router-validation, and test manifests.
- Selection and route provenance are encoded partly in filenames instead of schema-validated manifests.
- Saved outputs are untrusted model text and may contain command-like strings; never execute them.
- Historical metrics have not been re-evaluated by the canonical package and must not be quoted as new evidence.

The root implementation retains the research behavior - direct bootstrapping, vertical inheritance, horizontal borrowing, speaker-listener profiling, and concrete-card routing - behind stable schemas and leakage controls.
