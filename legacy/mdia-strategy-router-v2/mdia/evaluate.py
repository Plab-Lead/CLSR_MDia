"""Lightweight parsers and evaluators for the four public benchmark formats."""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def normalize_answer(text: Any) -> str:
    text = str(text).strip().lower()
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"[^a-z0-9.+#_ -]+", " ", text)
    return normalize_space(text)


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        obj = json.loads(cleaned)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(cleaned[start : end + 1])
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def evaluate_musr(task: dict[str, Any], content: str) -> dict[str, Any]:
    obj = parse_json_object(content)
    pred_idx = obj.get("answer_index")
    if isinstance(pred_idx, str):
        match = re.search(r"-?\d+", pred_idx)
        pred_idx = int(match.group(0)) if match else None
    pred_answer = str(obj.get("answer", content))
    gold_idx = task.get("gold_index")
    gold_answer = task.get("gold_answer", "")
    success = pred_idx == gold_idx or normalize_answer(gold_answer) in normalize_answer(pred_answer)
    return {"success": bool(success), "parse_ok": bool(obj), "prediction": pred_idx if pred_idx is not None else pred_answer}


def evaluate_multihop(task: dict[str, Any], content: str) -> dict[str, Any]:
    obj = parse_json_object(content)
    pred = str(obj.get("answer", content))
    gold = str(task.get("gold_answer", ""))
    n_pred = normalize_answer(pred)
    n_gold = normalize_answer(gold)
    success = bool(n_gold) and (n_gold == n_pred or n_gold in n_pred or n_pred in n_gold)
    return {"success": success, "parse_ok": bool(obj), "prediction": pred}


def norm_value(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return normalize_answer(value)


def normalize_calls(calls: Any) -> list[dict[str, Any]]:
    if not isinstance(calls, list):
        return []
    out = []
    for call in calls:
        if not isinstance(call, dict):
            continue
        name = str(call.get("name", "")).strip()
        args = call.get("arguments", {})
        if not isinstance(args, dict):
            args = {}
        out.append({"name": name, "arguments": {str(k): norm_value(v) for k, v in args.items()}})
    return sorted(out, key=lambda item: (item["name"], json.dumps(item["arguments"], sort_keys=True)))


def gold_options_to_calls(gold: Any) -> list[dict[str, Any]]:
    calls = []
    if not isinstance(gold, list):
        return calls
    for item in gold:
        if not isinstance(item, dict):
            continue
        for name, args in item.items():
            norm_args = {}
            if isinstance(args, dict):
                for key, values in args.items():
                    if isinstance(values, list):
                        norm_args[key] = [norm_value(value) for value in values]
                    else:
                        norm_args[key] = [norm_value(values)]
            calls.append({"name": str(name), "arguments": norm_args})
    return calls


def evaluate_bfcl(task: dict[str, Any], content: str) -> dict[str, Any]:
    obj = parse_json_object(content)
    pred_calls = normalize_calls(obj.get("tool_calls", []))
    gold_calls = gold_options_to_calls(task.get("gold", []))
    pred_names = [call["name"] for call in pred_calls]
    gold_names = [call["name"] for call in gold_calls]
    function_ok = Counter(pred_names) == Counter(gold_names)
    arg_ok = function_ok and len(pred_calls) == len(gold_calls)
    if arg_ok:
        for pred, gold in zip(pred_calls, sorted(gold_calls, key=lambda item: item["name"])):
            for key, allowed_values in gold["arguments"].items():
                if key not in pred["arguments"] or pred["arguments"][key] not in allowed_values:
                    arg_ok = False
                    break
            if not arg_ok:
                break
    success = bool(gold_calls) and function_ok and arg_ok
    return {
        "success": success,
        "parse_ok": bool(obj),
        "function_ok": function_ok,
        "argument_ok": arg_ok,
        "prediction": pred_calls,
    }


def normalize_stdout(text: Any) -> str:
    text = str(text).strip()
    text = text.replace("\\r\\n", "\n").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def evaluate_lcb(task: dict[str, Any], content: str) -> dict[str, Any]:
    obj = parse_json_object(content)
    pred = obj.get("output", content)
    success = normalize_stdout(pred) == normalize_stdout(task.get("gold_output", ""))
    return {"success": success, "parse_ok": bool(obj), "prediction": pred}


EVALUATORS = {
    "musr": evaluate_musr,
    "multihop_rag": evaluate_multihop,
    "bfcl": evaluate_bfcl,
    "livecodebench_output": evaluate_lcb,
}


def has_gold(task: dict[str, Any]) -> bool:
    benchmark = task.get("benchmark")
    if benchmark == "musr":
        return "gold_index" in task or "gold_answer" in task
    if benchmark == "multihop_rag":
        return "gold_answer" in task
    if benchmark == "bfcl":
        return "gold" in task
    if benchmark == "livecodebench_output":
        return "gold_output" in task
    return False


def evaluate_prediction(task: dict[str, Any], content: str) -> dict[str, Any]:
    benchmark = str(task.get("benchmark", ""))
    if benchmark not in EVALUATORS:
        raise ValueError(f"Unsupported benchmark: {benchmark}")
    if not has_gold(task):
        obj = parse_json_object(content)
        return {"success": None, "parse_ok": bool(obj), "prediction": obj or content}
    return EVALUATORS[benchmark](task, content)

