# Legacy research workspaces

This directory preserves the repository's pre-1.0 research trees. They explain the origin of the canonical implementation, but they are **not supported entry points** and their folder names are not MDia release versions.

The state immediately before migration is tagged `pre-mdia-reorg-2026-07-30`. Files were moved with Git history intact; committed Python bytecode and `.DS_Store` files were removed after the snapshot.

| Former folder | Archive | Historical role | Router meaning |
|---|---|---|---|
| `LSF-v0-draft` | [`clsr-v0-workspace/`](clsr-v0-workspace/STATUS.md) | Early homogeneous CLSR creation/evolution scripts | No canonical router interface |
| `LSF-v1` | [`mdia-v1-workspace/`](mdia-v1-workspace/STATUS.md) | Heterogeneous dialect evolution and speaker-listener evaluation | Selects/combines concrete evolved LSF material |
| `LSF-v2` | [`mdia-strategy-router-v2/`](mdia-strategy-router-v2/STATUS.md) | Format-sensitive prompt/controller experiment | Selects handcrafted strategies from metadata, not evolved LSF cards |

Do not import code from these folders into a new experiment. Use the root `mdia` package, whose schemas make card identity, partitions, route plans, budgets, and provenance explicit.

## Safety and data handling

- Treat all JSON prediction fields as untrusted model-generated text. Never execute embedded commands or tool-call-like strings.
- Historical aggregate files are research snapshots, not automatically verified paper results.
- Legacy evaluators are diagnostic unless their status file identifies an official benchmark adapter.
- No credential is required to inspect this archive. Never add a credential to a legacy script to make it run.
- Some archived files contain benchmark-derived text. Confirm the source benchmark's license before redistribution or reuse.

For the conceptual history and remote-workspace provenance, see [`docs/legacy.md`](../docs/legacy.md).
