# Data Notes

`selected_routed_outputs.jsonl` contains only the compact selected MDia-Routed-v2 rows used for the final frontier result. It omits full prompts, full benchmark contexts, gold answers, API keys, usage ledgers, remote paths, and logs.

`baseline_overall.csv` contains aggregate raw/raw CoT/SoT/CoD/original-MDia baselines across the five model families.

`mdia_routed_v2_official_win.csv` contains the final strict official-win rows.

`accuracy_token_frontier.csv` combines baselines and MDia-Routed-v2 for plotting accuracy vs. completion tokens.

`selected_outputs_summary.csv` is regenerated from `selected_routed_outputs.jsonl` with `scripts/summarize_frontier.py`.
