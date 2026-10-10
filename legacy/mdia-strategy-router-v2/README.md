> **Archived research snapshot.** Read [`STATUS.md`](STATUS.md) before using this folder. Its router selects handcrafted metadata-conditioned controller strategies; it does not retrieve evolved LSF cards. Included result claims have not been revalidated by the canonical root pipeline.

# Historical MDia strategy/controller router (formerly “MDia-Routed-v2”)

This folder is a sanitized, GitHub-ready core release for MDia-Routed-v2. It contains the method implementation, a lightweight runner, compact evaluator utilities, and representative output data showing the accuracy-token frontier advantage on four supplementary benchmarks.

The package is intentionally smaller than the full experiment workspace. It excludes ablation sweeps, remote-server logs, API usage ledgers, full prompts, full benchmark contexts, and credentials.

## Contents

```text
mdia_routed_v2_release/
  mdia/
    routing.py          # Observable metadata router.
    prompts.py          # MDia-Routed-v2 prompt builder.
    client.py           # OpenAI-compatible API client using env vars.
    evaluate.py         # Lightweight task evaluators.
    io_utils.py         # JSONL/CSV helpers.
  scripts/
    run_mdia_routed.py  # Run MDia-Routed-v2 on a JSONL task file.
    summarize_frontier.py
  configs/
    route_map.json
    model_config.example.json
  data/
    baseline_overall.csv
    mdia_routed_v2_official_win.csv
    accuracy_token_frontier.csv
    selected_outputs_summary.csv
    selected_routed_outputs.jsonl
    DATA_NOTES.md
  requirements.txt
```

## Method Summary

MDia-Routed-v2 treats MDia as a routed dialect controller. Instead of using one fixed MDia prompt for every task, it selects a compact internal reasoning route from observable benchmark metadata, then emits only the minimal JSON answer object.

The router does not use task IDs, gold labels, or model outputs.

| Benchmark | Metadata key | Route |
|---|---|---|
| BFCL v3 | benchmark-level route | `rmdia_bfcl_parallel_zip` |
| LiveCodeBench-output | benchmark-level route | `rmdia_schema` |
| MultiHopRAG | `comparison_query` | `rmdia_silent` |
| MultiHopRAG | `inference_query` | `rmdia_verify` |
| MultiHopRAG | `null_query` | `rmdia_mhop_yesno_guard` |
| MuSR | `murder_mystery` | `rmdia_contrast` |
| MuSR | `object_placements` | `rmdia_contrast` |
| MuSR | `team_allocation` | `rmdia_schema` |

Route intuitions:

- `rmdia_bfcl_parallel_zip`: schema-aware function calling with explicit handling for parallel "respectively" requests.
- `rmdia_schema`: compact schema-first decoding for strict output tasks.
- `rmdia_silent`: minimal direct-answer route for simple evidence bridges.
- `rmdia_verify`: silent candidate generation plus short verification.
- `rmdia_mhop_yesno_guard`: null-aware yes/no guard for MultiHopRAG.
- `rmdia_contrast`: compact contrastive candidate elimination for narrative reasoning.

## Main Frontier Result

Strict official-win means MDia-Routed-v2 has higher accuracy than the best baseline and fewer mean completion tokens than the lowest-token baseline.

| Benchmark | n | MDia-Routed-v2 accuracy | Best baseline accuracy | MDia-Routed-v2 completion tokens | Lowest baseline completion tokens | Win |
|---|---:|---:|---:|---:|---:|---|
| BFCL v3 | 75 | 72.00% | 62.67% | 36.2 | 54.4 | yes |
| LiveCodeBench-output | 40 | 22.50% | 20.00% | 24.2 | 75.1 | yes |
| MultiHopRAG | 60 | 96.67% | 90.00% | 7.8 | 11.2 | yes |
| MuSR | 60 | 55.00% | 51.67% | 36.0 | 51.1 | yes |

The plotting-ready table is `data/accuracy_token_frontier.csv`.

## Representative Data

The data folder includes only compact representative artifacts:

- `baseline_overall.csv`: aggregate raw, raw CoT, SoT, CoD, and original non-routed MDia results across five model families.
- `mdia_routed_v2_official_win.csv`: final strict official-win table for MDia-Routed-v2.
- `accuracy_token_frontier.csv`: combined baseline and MDia-Routed-v2 points for accuracy-token frontier plots.
- `selected_outputs_summary.csv`: summary regenerated from `selected_routed_outputs.jsonl` using `scripts/summarize_frontier.py`.
- `selected_routed_outputs.jsonl`: selected MDia-Routed-v2 row-level outputs only, stripped of full prompts, contexts, gold answers, API keys, usage ledgers, remote paths, and logs.

The selected routed-output JSONL has fields such as:

```json
{
  "benchmark": "bfcl",
  "model": "Qwen/Qwen3.5-9B",
  "task_id": "bfcl_...",
  "method": "MDia-Routed-v2",
  "route": "rmdia_bfcl_parallel_zip",
  "route_key": "_default",
  "success": true,
  "parse_ok": true,
  "completion_tokens": 36,
  "prediction": "...",
  "model_output": "..."
}
```

## Task JSONL Format for Reproduction

`scripts/run_mdia_routed.py` expects one task per JSONL line. The required fields depend on the benchmark.

MuSR:

```json
{"task_id":"musr_0","benchmark":"musr","subdomain":"object_placements","context":"...","question":"...","choices":["A","B","C"],"gold_index":0,"gold_answer":"A"}
```

MultiHopRAG:

```json
{"task_id":"mhop_0","benchmark":"multihop_rag","question_type":"comparison_query","question":"...","evidence":[{"source":"...","title":"...","fact":"..."}],"gold_answer":"..."}
```

BFCL v3:

```json
{"task_id":"bfcl_0","benchmark":"bfcl","category":"parallel","question":"...","functions":[{"name":"tool.name","description":"...","parameters":{"type":"object","properties":{},"required":[]}}],"gold":[]}
```

LiveCodeBench-output:

```json
{"task_id":"lcb_0","benchmark":"livecodebench_output","difficulty":"easy","question_title":"...","question":"...","test_input":"...","gold_output":"..."}
```

Gold fields are optional for generation. If gold fields are absent, the runner will still write predictions and parse status, but `success` is set to `null`.

## Running

The core code uses only the Python standard library.

```bash
cd mdia_routed_v2_release
export MDIA_API_KEY="your_api_key_here"
export MDIA_API_BASE="https://api.siliconflow.cn/v1"

python scripts/run_mdia_routed.py \
  --input path/to/tasks.jsonl \
  --output runs/mdia_routed_v2_outputs.jsonl \
  --model Qwen/Qwen3.5-9B
```

To inspect prompts without calling an API:

```bash
python scripts/run_mdia_routed.py \
  --input path/to/tasks.jsonl \
  --output runs/dry_run_prompts.jsonl \
  --model Qwen/Qwen3.5-9B \
  --dry-run-prompts
```

To summarize compact outputs:

```bash
python scripts/summarize_frontier.py \
  --outputs data/selected_routed_outputs.jsonl \
  --baseline-csv data/baseline_overall.csv \
  --out-csv runs/selected_outputs_summary.csv
```

## Security and Sanitization

This package should not contain:

- API keys.
- Hugging Face tokens.
- SSH credentials.
- Remote-server paths.
- API usage ledgers.
- Full experiment logs.

Credentials must be supplied at runtime through environment variables such as `MDIA_API_KEY`.

## Scope Notes

- The included LiveCodeBench setting is an output-prediction diagnostic based on public test cases, not full pass@1 code generation.
- The route map was selected from the official-slice exploratory sweep. For broad generalization claims, run a fresh held-out validation slice using the same route map.
- This release focuses on method reproducibility and representative frontier data. Full ablation scripts and long-running sweep machinery are intentionally omitted.
