# Legacy history and migration

Before the 1.0 rebuild, three folders were presented as v0, v1, and v2. That numbering suggested a linear succession even though the folders represented different research questions and two different kinds of routing.

## What changed

| Old name | New archive | Interpretation |
|---|---|---|
| `LSF-v0-draft` | `legacy/clsr-v0-workspace` | Early homogeneous CLSR creation/evolution workspace |
| `LSF-v1` | `legacy/mdia-v1-workspace` | Heterogeneous creation/evolution and concrete evolved-LSF routing |
| `LSF-v2` | `legacy/mdia-strategy-router-v2` | Metadata-to-handcrafted-controller routing for format-sensitive tasks |

The pre-migration Git state is preserved by tag `pre-mdia-reorg-2026-07-30`. Git moves retain file history. Tracked `.pyc` and `.DS_Store` files were removed after the snapshot.

Each archive has a `STATUS.md` that lists its role, expected inputs, known limitations, and why it is not canonical. Historical READMEs and outputs remain for auditability, but the status file and root documentation control interpretation.

## Router terminology

The MDia-v1 prototype used evolved LSF material during inference. This became the canonical `DialectRouter`, whose output must name real cards in a frozen bank.

The former v2 package used benchmark/subtype metadata to choose handcrafted schema, verification, contrastive, or evidence-guard strategies. This became the optional `ControllerRouter`, whose output names a controller/answer contract rather than an evolved card.

This distinction addresses the confusion recorded in GitHub issue [#4](https://github.com/pzqpzq/LSF_MDia/issues/4).

## Recovered CLSR input

The v0 scripts referenced `meta_prompts/meta_LSFs_v2.json`, which was not previously present. A minimal read-only recovery from the private FlatSymbolism workspace is now archived at:

```text
legacy/clsr-v0-workspace/meta_prompts/meta_LSFs_v2.json
```

The file was parsed and scanned for credential/private-path patterns before inclusion. Its checksum is recorded in the v0 status file. This resolves GitHub issue [#6](https://github.com/pzqpzq/LSF_MDia/issues/6) for historical inspection, not the larger reproducibility gaps of the v0 workspace.

## Remote research provenance

The rebuild was informed by read-only inspection of three private research areas:

- `MDia-v1`, for heterogeneous lifecycle scripts, concrete-card routing, coverage, checkpoint, and resume behavior;
- `MDia-NMI-Jun1`, for normalized event archives, profile/transfer analysis, evidence-stream separation, split-router validation, and statistics; and
- `MDia-v2`, for controller-routing experiments and the complete rule registry.

No private workspace was modified. Scripts, operational logs, API ledgers, provider configuration, benchmark copies, and credentials were not copied into the canonical release.

## How to use the archive

- Cite it only as provenance for the historical code path.
- Do not import its modules into canonical experiments.
- Do not treat filenames as stable IDs or split manifests.
- Do not execute command-like strings found inside generated prediction JSON.
- Do not quote historical selected slices as current or official results without canonical re-evaluation.
- Confirm benchmark licensing before reusing any example text.

For new work, use the root CLI and configs. For conceptual comparison, see [Paper-to-code map](paper-to-code.md).
