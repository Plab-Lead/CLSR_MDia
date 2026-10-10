# Paper-scale configurations

This directory is reserved for immutable, versioned configurations that reproduce a specific manuscript table or figure. Paper configurations must name exact dataset revisions, model/provider revisions, split-manifest hashes, seeds, evaluator versions, and external artifact checksums.

The repository intentionally does not ship a misleading “paper config” containing private server paths or unavailable benchmark assets. Add a configuration here only after its referenced manifests and redistributable release artifacts have passed the release-hygiene checks described in `docs/reproduction.md`.
