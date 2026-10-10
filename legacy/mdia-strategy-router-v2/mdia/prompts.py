"""Prompt construction for MDia-Routed-v2."""

from __future__ import annotations

from typing import Any

from .routing import RouteSpec, select_route


def trim_text(text: Any, max_chars: int) -> str:
    text = str(text)
    if len(text) <= max_chars:
        return text
    head = max_chars // 2
    tail = max_chars - head
    return text[:head].rstrip() + "\n...[middle truncated]...\n" + text[-tail:].lstrip()


def compact_choices(task: dict[str, Any]) -> str:
    return "\n".join(f"{i}. {choice}" for i, choice in enumerate(task.get("choices", [])))


def compact_evidence(task: dict[str, Any]) -> str:
    lines = []
    for idx, ev in enumerate(task.get("evidence", []), 1):
        if isinstance(ev, dict):
            lines.append(f"[D{idx}] {ev.get('source', '')} | {ev.get('title', '')} | fact: {ev.get('fact', '')}")
        else:
            lines.append(f"[D{idx}] {ev}")
    return "\n".join(lines)


def tool_schema_text(functions: list[dict[str, Any]]) -> str:
    lines = []
    for fn in functions:
        params = fn.get("parameters", {})
        props = params.get("properties", {}) if isinstance(params, dict) else {}
        required = params.get("required", []) if isinstance(params, dict) else []
        args = []
        for name, spec in props.items():
            typ = spec.get("type", "any") if isinstance(spec, dict) else "any"
            mark = "*" if name in required else ""
            enum = spec.get("enum") if isinstance(spec, dict) else None
            enum_text = f" enum={enum}" if enum else ""
            args.append(f"{name}{mark}:{typ}{enum_text}")
        lines.append(f"- {fn.get('name')}({', '.join(args)}): {fn.get('description', '')}")
    return "\n".join(lines)


def route_directive(route: str, benchmark: str, task: dict[str, Any]) -> str:
    """Return the compact route instruction used before the benchmark prompt."""

    if route == "rmdia_schema":
        return (
            "Route by schema first. Identify required output keys, solve silently, "
            "then emit only the minimal valid JSON object. No rationale, markdown, or extra fields."
        )
    if route == "rmdia_silent":
        return (
            "Use MDia silently: P=parse inputs; R=route to benchmark skill; C=compute candidate; "
            "V=verify against constraints; X=emit final JSON only. Do not reveal P/R/C/V."
        )
    if route == "rmdia_verify":
        return (
            "Use a two-pass silent verifier. First produce a candidate internally; second check it "
            "against the narrative, evidence, tools, or input. Revise if any mismatch. Emit only final JSON."
        )
    if route == "rmdia_contrast":
        return (
            "Use contrastive MDia silently: compare the top two plausible candidates, reject the one "
            "violating a constraint, then emit only the surviving final JSON."
        )
    if route == "rmdia_bfcl_parallel_zip" and benchmark == "bfcl":
        return (
            "BFCL parallel route. If the request gives multiple entities and corresponding values with "
            "words like respectively, zip them by order and emit one separate tool call per pair. "
            "Include schema defaults and optional empty/default arguments when natural."
        )
    if route == "rmdia_mhop_yesno_guard" and benchmark == "multihop_rag":
        return (
            "MultiHop comparison route. For yes/no comparison questions, answer Yes only when every "
            "clause is directly supported by the evidence. For null_query, answer exactly "
            "'Insufficient information.'."
        )
    return "Use schema-first routed MDia. Solve silently and emit only the minimal valid JSON object."


def build_prompt(task: dict[str, Any], route_spec: RouteSpec | None = None) -> tuple[str, int, RouteSpec]:
    """Build one benchmark prompt and return ``(prompt, max_tokens, route_spec)``."""

    route_spec = route_spec or select_route(task)
    benchmark = route_spec.benchmark
    route = route_spec.route
    directive = route_directive(route, benchmark, task)

    if benchmark == "musr":
        context = trim_text(task.get("context", ""), 8000)
        max_tokens = 110
        return (
            f"""{directive}

Task: multiple-choice narrative reasoning.

Narrative:
{context}

Question:
{task.get('question', '')}

Choices:
{compact_choices(task)}

Return exactly: {{"answer_index": 0, "answer": "choice text"}}
""",
            max_tokens,
            route_spec,
        )

    if benchmark == "multihop_rag":
        max_tokens = 80
        return (
            f"""{directive}

Task: answer using only provided evidence.

Question type: {task.get('question_type', '')}

Question:
{task.get('question', '')}

Evidence:
{compact_evidence(task)}

Return exactly: {{"answer": "short answer"}}
""",
            max_tokens,
            route_spec,
        )

    if benchmark == "bfcl":
        max_tokens = 240
        return (
            f"""{directive}

Task: function call extraction.

User request:
{task.get('question', '')}

Available functions:
{tool_schema_text(task.get('functions', []))}

Rules:
- Use only exact function names from Available functions.
- Include every required argument if the user provides or implies it.
- Do not invent unsupported functions or arguments.
- If no call is needed, use [].
- Include optional parameters when the schema gives a default or an empty/default value is natural.
- For words such as respectively, pair the first entity with the first value, second entity with second value, and so on.

Return exactly: {{"tool_calls":[{{"name":"function.name","arguments":{{"arg":"value"}}}}]}}
""",
            max_tokens,
            route_spec,
        )

    if benchmark == "livecodebench_output":
        max_tokens = 120
        return (
            f"""{directive}

Task: predict exact stdout for the given programming problem input.

Problem:
{task.get('question_title', '')}
{task.get('question', '')}

Input:
{task.get('test_input', '')}

Rules:
- Output must match stdout exactly after normalization of trailing whitespace.
- If there are multiple lines, encode them with newline characters in the JSON string.

Return exactly: {{"output": "exact stdout"}}
""",
            max_tokens,
            route_spec,
        )

    raise ValueError(f"Unsupported benchmark: {benchmark}")

