#!/usr/bin/env python3
"""Run MDia-Routed-v2 on a JSONL task file."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mdia.client import chat_completion  # noqa: E402
from mdia.evaluate import evaluate_prediction  # noqa: E402
from mdia.io_utils import read_jsonl  # noqa: E402
from mdia.prompts import build_prompt  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Task JSONL path.")
    parser.add_argument("--output", required=True, help="Output JSONL path.")
    parser.add_argument("--model", required=True, help="OpenAI-compatible model id.")
    parser.add_argument("--api-base", default=None, help="API base URL. Defaults to MDIA_API_BASE or SiliconFlow.")
    parser.add_argument("--api-key-env", default="MDIA_API_KEY", help="Environment variable containing the API key.")
    parser.add_argument("--limit", type=int, default=None, help="Optional maximum number of tasks.")
    parser.add_argument("--dry-run-prompts", action="store_true", help="Write prompts without calling the API.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tasks = read_jsonl(args.input)
    if args.limit is not None:
        tasks = tasks[: args.limit]
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as handle:
        for idx, task in enumerate(tasks, 1):
            prompt, max_tokens, route = build_prompt(task)
            started = time.time()
            if args.dry_run_prompts:
                response = {"ok": True, "content": "", "usage": {}, "dry_run_prompt": prompt}
            else:
                response = chat_completion(
                    args.model,
                    prompt,
                    api_base=args.api_base,
                    api_key_env=args.api_key_env,
                    max_tokens=max_tokens,
                )
            elapsed = round(time.time() - started, 3)
            content = str(response.get("content", ""))
            eval_row = evaluate_prediction(task, content) if not args.dry_run_prompts else {"success": None, "parse_ok": None}
            usage = response.get("usage", {}) if isinstance(response.get("usage"), dict) else {}
            payload = {
                "created_at": utc_now(),
                "model": args.model,
                "benchmark": task.get("benchmark"),
                "task_id": task.get("task_id"),
                "route": route.route,
                "route_key": route.key,
                "success": eval_row.get("success"),
                "parse_ok": eval_row.get("parse_ok"),
                "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                "completion_tokens": int(usage.get("completion_tokens") or 0),
                "total_tokens": int(usage.get("total_tokens") or 0),
                "elapsed_sec": elapsed,
                "prediction": eval_row.get("prediction"),
                "content": content,
                "error": response.get("error"),
            }
            if args.dry_run_prompts:
                payload["prompt"] = prompt
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            handle.flush()
            print(f"[{idx}/{len(tasks)}] {task.get('benchmark')} {task.get('task_id')} route={route.route}", flush=True)


if __name__ == "__main__":
    main()

