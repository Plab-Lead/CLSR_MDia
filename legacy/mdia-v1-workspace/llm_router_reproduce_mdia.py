#!/usr/bin/env python3
"""
LLM-router reproduction script for CLSR / MDia (LSF-v1).

This script implements the paper-style LLM-router discussed in the camera-ready
revision: profile-aware category pruning -> compact protocol planning ->
deterministic execution over existing LSFs -> accuracy/token evaluation.

Recommended location in the repository:
    LSF_MDia/LSF-v1/llm_router_reproduce_mdia.py

Core design choices covered here:
  1. LSF card format:
       [ID] TAG | perf:<acc>/<tok> | IO | STOP
  2. Two-stage router:
       Stage 1: category routing, C:<category-list>
       Stage 2: protocol planning,
           M:<mode>;L:<lsf-list>;R:<round-spec>;K:<n>;A:<agg>;S:<stop>
  3. Execution modes:
       M:S  single LSF
       M:A  multi-LSF aggregation
       M:C  implicit multi-LSF composition
  4. Reproducibility:
       - deterministic DSL parser and validator;
       - heuristic fallback when the router output is invalid;
       - optional validation profiling for each candidate LSF;
       - JSONL records for every test item and a summary JSON.

The script follows the existing LSF-v1 style: it uses an OpenAI-compatible
chat-completion client and defaults to the SiliconFlow endpoint.

Example quick run from LSF-v1:

    export SILICONFLOW_API_KEY="YOUR_KEY"
    python llm_router_reproduce_mdia.py \
        --data_card gpqa \
        --lsf_dir lsf_evolve_records/gpqa \
        --max_lsf 12 \
        --profile_n 20 \
        --max_num_test 100 \
        --inference_model Qwen/Qwen3.5-35B-A3B \
        --router_model Qwen/Qwen3.5-9B \
        --judge_model Qwen/Qwen3.5-9B \
        --run_baseline

Notes:
  - If the local repository stores evolved LSFs under `evolve_records/` rather than
    `lsf_evolve_records/`, pass `--lsf_dir evolve_records/<benchmark>`.
  - If `llm_utils.load_data` or `llm_utils.eval_llmOutputs` is unavailable, the
    script still runs in `--demo` mode on a tiny built-in dataset.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import statistics
import string
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from openai import OpenAI
except Exception as exc:  # pragma: no cover
    OpenAI = None  # type: ignore

try:
    import llm_utils.load_data as load_ds
except Exception:  # pragma: no cover
    load_ds = None  # type: ignore

try:
    import llm_utils.eval_llmOutputs as eval_llm
except Exception:  # pragma: no cover
    eval_llm = None  # type: ignore


# -----------------------------
# Data structures
# -----------------------------

CATEGORY_CODES = [
    "ALG", "GEO", "NUM", "MATH", "PHY", "CHEM", "BIO", "MED", "CS",
    "QA", "HIS", "LAW", "ECO", "SOC", "SCI", "COMMON", "GEN",
]

CATEGORY_HINTS = {
    "ALG": ["equation", "solve", "linear", "polynomial", "algebra", "variable"],
    "GEO": ["geometry", "triangle", "circle", "angle", "area", "perimeter"],
    "NUM": ["arithmetic", "calculate", "number", "percent", "ratio"],
    "MATH": ["proof", "math", "integer", "modulo", "sequence", "combinatorics"],
    "PHY": ["force", "mass", "velocity", "acceleration", "energy", "physics"],
    "CHEM": ["reaction", "molecule", "acid", "base", "chemistry"],
    "BIO": ["cell", "gene", "protein", "biology", "organism"],
    "CS": ["algorithm", "code", "program", "complexity", "data structure"],
    "QA": ["who", "what", "when", "where", "which", "why", "how"],
    "HIS": ["history", "year", "war", "king", "president", "dynasty"],
    "LAW": ["law", "legal", "court", "contract"],
    "ECO": ["economy", "market", "price", "demand", "supply"],
    "SCI": ["science", "experiment", "hypothesis"],
    "COMMON": ["commonsense", "daily", "practical"],
    "GEN": [],
}

MODE_SET = {"S", "A", "C"}
AGG_SET = {"none", "mv", "sc", "w", "judge"}


@dataclass
class LSFCard:
    lsf_id: str
    category: str
    tag: str
    acc: float
    tok: int
    io: str
    stop: str
    spec: str
    source_file: str = ""
    source_index: int = -1

    def to_router_line(self) -> str:
        return (
            f"[{self.lsf_id}] {self.tag} | perf:{self.acc:.2f}/{int(self.tok)} | "
            f"out:{self.io} | stop:{self.stop}"
        )


@dataclass
class RouterPlan:
    mode: str
    lsf_ids: List[str]
    round_spec: str
    k: int
    agg: str
    stop: str
    raw: str = ""
    source: str = "llm"

    def to_dsl(self) -> str:
        return (
            f"M:{self.mode};L:{','.join(self.lsf_ids)};R:{self.round_spec};"
            f"K:{self.k};A:{self.agg};S:{self.stop}"
        )


@dataclass
class SolverOutput:
    text: str
    completion_tokens: int
    prompt_tokens: int
    reasoning_tokens: int = 0
    role: str = "solver"
    lsf_id: str = ""


# -----------------------------
# Utility functions
# -----------------------------


def now_id(n: int = 5) -> str:
    return "".join(random.choice(string.ascii_letters + string.digits) for _ in range(n))


def count_approx_tokens(text: str) -> int:
    # A conservative fallback when API usage is unavailable.
    # English-ish token approximation: roughly 4 chars per token.
    return max(1, int(math.ceil(len(text) / 4)))


def ensure_client(api_key: Optional[str], base_url: str):
    if OpenAI is None:
        raise RuntimeError("openai package is not installed. Run: pip install openai")
    key = api_key or os.getenv("SILICONFLOW_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "Missing API key. Set SILICONFLOW_API_KEY or OPENAI_API_KEY, "
            "or pass --api_key."
        )
    return OpenAI(api_key=key, base_url=base_url)


def chat_completion(
    client,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 512,
    enable_thinking: bool = False,
    thinking_budget: int = 4096,
    retries: int = 3,
    retry_sleep: float = 2.0,
) -> SolverOutput:
    last_error = None
    for attempt in range(retries):
        try:
            extra_body = {"enable_thinking": bool(enable_thinking)}
            if enable_thinking:
                extra_body["thinking_budget"] = int(thinking_budget)
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body=extra_body,
            )
            text = resp.choices[0].message.content or ""
            usage = getattr(resp, "usage", None)
            comp = int(getattr(usage, "completion_tokens", count_approx_tokens(text)) or 0)
            prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
            reasoning = 0
            try:
                details = getattr(usage, "completion_tokens_details", None)
                reasoning = int(getattr(details, "reasoning_tokens", 0) or 0)
            except Exception:
                reasoning = 0
            return SolverOutput(text=text, completion_tokens=comp, prompt_tokens=prompt, reasoning_tokens=reasoning)
        except Exception as exc:  # pragma: no cover
            last_error = exc
            time.sleep(retry_sleep * (attempt + 1))
    raise RuntimeError(f"Chat-completion failed after {retries} retries: {last_error}")


def load_dataset(data_card: str, demo: bool = False) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if demo or load_ds is None:
        train = [
            {"query": "Solve 2x+3=11.", "label": "4", "cot_content": "2x=8 so x=4."},
            {"query": "A 2 kg mass is pulled with 10 N on a frictionless surface. Find acceleration.", "label": "5", "cot_content": "a=F/m=10/2=5."},
        ]
        test = [
            {"query": "Solve 3x-6=12.", "label": "6"},
            {"query": "A 4 kg object has force 20 N. What is acceleration?", "label": "5"},
        ]
        return train, test
    return load_ds.load_cleanDS(_dataCard=data_card)


def normalize_answer(text: str) -> str:
    text = text.strip()
    # Prefer explicit final-answer markers.
    patterns = [
        r"final\s*answer\s*[:：]\s*([^\n]+)",
        r"answer\s*[:：]\s*([^\n]+)",
        r"####\s*([^\n]+)",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.I)
        if m:
            text = m.group(1).strip()
            break
    # Keep numbers / choices compactly.
    text = text.replace("$", "")
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" .。\n\t")
    return text.lower()


def simple_correctness(test_item: Dict[str, Any], pred: str) -> int:
    label = str(test_item.get("label", "")).strip()
    if not label:
        return 0
    p = normalize_answer(pred)
    l = normalize_answer(label)
    if not l:
        return 0
    return int(p == l or l in p.split() or l in p[-20:])


def evaluate_output(test_item: Dict[str, Any], pred: str, client=None, judge_model: str = "") -> Dict[str, Any]:
    # Use the repository evaluator when available; otherwise fallback to exact-ish match.
    if eval_llm is not None and client is not None and judge_model:
        try:
            raw = eval_llm.eval_output(test_item, pred, client, judge_model)
            parsed = eval(raw) if isinstance(raw, str) else raw
            if isinstance(parsed, dict) and "isCorr" in parsed:
                return parsed
        except Exception:
            pass
    return {"isCorr": simple_correctness(test_item, pred), "eval_note": "fallback_exactish"}


# -----------------------------
# LSF loading and profiling
# -----------------------------


def infer_category_from_path(path: Path, data_card: str) -> str:
    s = f"{path.parent.name}/{path.name}/{data_card}".lower()
    if any(k in s for k in ["math", "gsm", "aime"]):
        return "MATH"
    if "gpqa" in s or "sci" in s:
        return "SCI"
    if "hotpot" in s:
        return "QA"
    if "mmlu" in s:
        return "GEN"
    return "GEN"


def summarize_tag(spec: str, category: str) -> str:
    low = spec.lower()
    if any(w in low for w in ["equation", "algebra", "solve"]):
        return "algebra/solve"
    if any(w in low for w in ["unit", "physics", "force", "mechanics"]):
        return "physics/equation"
    if any(w in low for w in ["decompose", "sub-question", "evidence"]):
        return "qa/decompose"
    if any(w in low for w in ["proof", "theorem", "lemma"]):
        return "math/proof"
    return f"{category.lower()}/compact"


def load_lsf_specs(lsf_dir: str, data_card: str, max_lsf: int = 16, ev_id: Optional[int] = None) -> List[LSFCard]:
    root = Path(lsf_dir)
    if not root.exists():
        raise FileNotFoundError(f"LSF directory does not exist: {lsf_dir}")
    paths = sorted(root.glob("*.json"))
    cards: List[LSFCard] = []
    for path in paths:
        if len(cards) >= max_lsf:
            break
        try:
            with path.open("r", encoding="utf-8") as f:
                obj = json.load(f)
        except Exception:
            continue
        records: List[Any]
        if isinstance(obj, list):
            records = obj
        elif isinstance(obj, dict) and "records" in obj and isinstance(obj["records"], list):
            records = obj["records"]
        else:
            records = [obj]

        idxs: List[int]
        if ev_id is not None and 0 <= ev_id < len(records):
            idxs = [ev_id]
        else:
            idxs = [len(records) - 1]
        for idx in idxs:
            rec = records[idx]
            if not isinstance(rec, dict):
                continue
            spec = rec.get("cur_lsf") or rec.get("lsf") or rec.get("LSF") or rec.get("spec")
            if not spec or not isinstance(spec, str):
                continue
            cat = infer_category_from_path(path, data_card)
            lsf_id = f"{cat}{len(cards)+1}"
            cards.append(
                LSFCard(
                    lsf_id=lsf_id,
                    category=cat,
                    tag=summarize_tag(spec, cat),
                    acc=0.50,
                    tok=max(16, min(512, count_approx_tokens(spec) // 8)),
                    io="ans,brief",
                    stop="ans",
                    spec=spec,
                    source_file=str(path),
                    source_index=idx,
                )
            )
            if len(cards) >= max_lsf:
                break
    if not cards:
        raise RuntimeError(f"No valid LSF specs found in {lsf_dir}")
    return cards


def solve_with_lsf_prompt(cur_lsf: str, cur_query: str, prev_state: str = "") -> str:
    state_block = ""
    if prev_state.strip():
        state_block = f"""
Previous symbolic state from an earlier LSF stage:
<STATE>
{prev_state}
</STATE>
"""
    return f"""
You are given a fixed Language Symbolism Framework (LSF). Your task is to solve the query using this LSF as faithfully and efficiently as possible.

Primary objective: minimize generated tokens while preserving correctness.

Rules:
- Treat the LSF as fixed.
- Do NOT redesign, explain, extend, or rename the LSF.
- Do NOT restate the query.
- Do NOT provide long explanations.
- Use the least latent reasoning necessary for correctness.
- End with a compact line in the form: Final answer: <answer>

Current LSF:
<LSF_SPEC>
{cur_lsf}
</LSF_SPEC>
{state_block}
Test query:
<QUERY>
{cur_query}
</QUERY>
""".strip()


def profile_lsf_cards(
    cards: List[LSFCard],
    train_ds: List[Dict[str, Any]],
    client,
    inference_model: str,
    judge_model: str,
    profile_n: int,
    seed: int,
    temperature: float,
    enable_thinking: bool,
) -> List[LSFCard]:
    if profile_n <= 0:
        return cards
    rng = random.Random(seed)
    sample = rng.sample(train_ds, min(profile_n, len(train_ds)))
    for card in cards:
        corr = 0
        toks: List[int] = []
        for item in sample:
            out = chat_completion(
                client=client,
                model=inference_model,
                messages=[{"role": "user", "content": solve_with_lsf_prompt(card.spec, item["query"])}],
                temperature=temperature,
                max_tokens=768,
                enable_thinking=enable_thinking,
            )
            ev = evaluate_output(item, out.text, client=client, judge_model=judge_model)
            corr += int(ev.get("isCorr", 0))
            toks.append(out.completion_tokens or count_approx_tokens(out.text))
        card.acc = corr / max(1, len(sample))
        card.tok = int(statistics.median(toks)) if toks else card.tok
        # A lightweight update of the tag based on observed profile.
        if card.acc >= 0.75 and card.tok <= 80:
            card.tag = f"{card.tag}/high-utility"
        elif card.tok <= 60:
            card.tag = f"{card.tag}/low-cost"
        elif card.acc < 0.45:
            card.tag = f"{card.tag}/risky"
    return cards


# -----------------------------
# Router prompts and DSL parser
# -----------------------------


def category_router_prompt(query: str) -> str:
    return f"""
You are an LSF category router.
Given the query, output exactly one line in the format:

C:<category-list>

where <category-list> contains one or two comma-separated category codes chosen from:
{', '.join(CATEGORY_CODES)}

Use a broad backup category when the query is ambiguous.
Do not output explanations.

Query:
{query}
""".strip()


def protocol_router_prompt(query: str, cards: Sequence[LSFCard], token_budget: int) -> str:
    card_lines = "\n".join(c.to_router_line() for c in cards)
    return f"""
You are an LSF protocol router.
Given the query and available LSF cards, choose the cheapest reasoning protocol that is likely to preserve correctness.

Output exactly one line in the following DSL:
M:<mode>;L:<lsf-list>;R:<round-spec>;K:<n>;A:<agg>;S:<stop>

Allowed modes:
- M:S means single-LSF direct answer.
- M:A means multi-LSF aggregation.
- M:C means implicit LSF composition.

Rules:
- Use only LSF IDs that appear in the cards.
- Prefer M:S when one high-accuracy low-token LSF is enough.
- Use M:A when independent LSF redundancy is likely to improve correctness.
- Use M:C when the problem needs staged symbolic processing, such as domain formulation followed by algebraic solving.
- Keep K small; use K:1 by default and K:2 only if aggregation is useful.
- A must be one of: none, mv, sc, w, judge.
- The expected generated-token budget is approximately {token_budget}.
- Do not output explanations or any text outside the plan line.

Available LSF cards:
{card_lines}

Query:
{query}
""".strip()


def parse_category_output(text: str) -> List[str]:
    m = re.search(r"C\s*:\s*([A-Z, ]+)", text.strip())
    if not m:
        return []
    cats = [c.strip().upper() for c in m.group(1).split(",") if c.strip()]
    return [c for c in cats if c in CATEGORY_CODES][:2]


def heuristic_category(query: str) -> List[str]:
    low = query.lower()
    scores = []
    for cat, words in CATEGORY_HINTS.items():
        score = sum(1 for w in words if w in low)
        if score > 0:
            scores.append((score, cat))
    if not scores:
        # Questions beginning with wh-words are often QA-like; otherwise use GEN.
        if re.search(r"\b(who|what|when|where|which|why|how)\b", low):
            return ["QA", "GEN"]
        return ["GEN"]
    scores.sort(reverse=True)
    return [c for _, c in scores[:2]]


def parse_router_plan(text: str) -> Optional[RouterPlan]:
    raw = text.strip().splitlines()[0].strip() if text.strip() else ""
    # Sometimes models wrap in backticks; remove them.
    raw = raw.strip("` ")
    fields: Dict[str, str] = {}
    for part in raw.split(";"):
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        fields[k.strip().upper()] = v.strip()
    try:
        mode = fields["M"].upper()
        ids = [x.strip() for x in fields["L"].split(",") if x.strip()]
        round_spec = fields.get("R", "1")
        k = int(fields.get("K", "1"))
        agg = fields.get("A", "none").lower()
        stop = fields.get("S", "ans")
        return RouterPlan(mode=mode, lsf_ids=ids, round_spec=round_spec, k=k, agg=agg, stop=stop, raw=raw)
    except Exception:
        return None


def validate_plan(plan: RouterPlan, available_ids: Sequence[str]) -> bool:
    avail = set(available_ids)
    if plan.mode not in MODE_SET:
        return False
    if not plan.lsf_ids or any(x not in avail for x in plan.lsf_ids):
        return False
    if plan.k < 1 or plan.k > 5:
        return False
    if plan.agg not in AGG_SET:
        return False
    if plan.mode == "S" and len(plan.lsf_ids) != 1:
        return False
    if plan.mode == "S" and plan.agg != "none":
        return False
    if plan.mode == "A" and len(plan.lsf_ids) < 2:
        return False
    if plan.mode == "C":
        stages = [s.strip() for s in plan.round_spec.split(">") if s.strip()]
        if len(stages) < 2:
            return False
        if any(s not in avail for s in stages):
            return False
    return True


def heuristic_plan(cards: Sequence[LSFCard], query: str, token_budget: int) -> RouterPlan:
    # Cost-aware fallback. Sort by empirical utility.
    def utility(c: LSFCard) -> float:
        return c.acc - 0.20 * min(c.tok / max(1, token_budget), 3.0)

    ranked = sorted(cards, key=utility, reverse=True)
    best = ranked[0]
    low = query.lower()
    hard = any(w in low for w in ["prove", "derive", "multi", "explain", "why", "complex", "except", "not"])
    math_phys = any(w in low for w in ["force", "mass", "acceleration", "equation", "solve"])

    if math_phys and len(ranked) >= 2:
        # Try a staged domain->algebra plan when categories differ or tags are complementary.
        phy = next((c for c in ranked if c.category == "PHY" or "physics" in c.tag), None)
        alg = next((c for c in ranked if c.category in {"ALG", "MATH"} or "algebra" in c.tag), None)
        if phy and alg and phy.lsf_id != alg.lsf_id:
            return RouterPlan("C", [phy.lsf_id, alg.lsf_id], f"{phy.lsf_id}>{alg.lsf_id}", 1, "none", "ans", source="heuristic")

    if best.acc >= 0.70 and best.tok <= token_budget * 0.65 and not hard:
        return RouterPlan("S", [best.lsf_id], "1", 1, "none", "ans", source="heuristic")

    if len(ranked) >= 2:
        chosen = ranked[: min(3, len(ranked))]
        return RouterPlan("A", [c.lsf_id for c in chosen], "1", 1 if token_budget < 160 else 2, "mv", "ans", source="heuristic")

    return RouterPlan("S", [best.lsf_id], "1", 1, "none", "ans", source="heuristic")


# -----------------------------
# Router and execution
# -----------------------------


def route_query(
    query: str,
    all_cards: Sequence[LSFCard],
    client,
    router_model: str,
    token_budget: int,
    use_llm_router: bool = True,
    router_temperature: float = 0.0,
) -> Tuple[List[str], List[LSFCard], RouterPlan, List[SolverOutput]]:
    router_outputs: List[SolverOutput] = []

    if use_llm_router:
        cat_out = chat_completion(
            client=client,
            model=router_model,
            messages=[{"role": "user", "content": category_router_prompt(query)}],
            temperature=router_temperature,
            max_tokens=32,
            enable_thinking=False,
        )
        cat_out.role = "category_router"
        router_outputs.append(cat_out)
        cats = parse_category_output(cat_out.text) or heuristic_category(query)
    else:
        cats = heuristic_category(query)

    cand = [c for c in all_cards if c.category in cats]
    # Include GEN as broad backup, and avoid empty candidate sets.
    if len(cand) < 2:
        extra = [c for c in all_cards if c.category == "GEN" and c not in cand]
        cand.extend(extra[: max(0, 3 - len(cand))])
    if not cand:
        cand = list(all_cards)

    # To keep router prompt compact, expose only top candidates by utility.
    cand = sorted(cand, key=lambda c: (c.acc, -c.tok), reverse=True)[:12]
    available_ids = [c.lsf_id for c in cand]

    plan: Optional[RouterPlan] = None
    if use_llm_router:
        for _ in range(2):
            plan_out = chat_completion(
                client=client,
                model=router_model,
                messages=[{"role": "user", "content": protocol_router_prompt(query, cand, token_budget)}],
                temperature=router_temperature,
                max_tokens=96,
                enable_thinking=False,
            )
            plan_out.role = "protocol_router"
            router_outputs.append(plan_out)
            plan = parse_router_plan(plan_out.text)
            if plan and validate_plan(plan, available_ids):
                break
            plan = None

    if plan is None:
        plan = heuristic_plan(cand, query, token_budget)

    return cats, cand, plan, router_outputs


def majority_vote_text(outputs: Sequence[str]) -> str:
    if not outputs:
        return ""
    norm_to_first: Dict[str, str] = {}
    counts: Dict[str, int] = {}
    for out in outputs:
        n = normalize_answer(out)
        norm_to_first.setdefault(n, out)
        counts[n] = counts.get(n, 0) + 1
    best_norm = sorted(counts.items(), key=lambda kv: (-kv[1], len(kv[0])))[0][0]
    return norm_to_first[best_norm]


def judge_aggregate_prompt(query: str, outputs: Sequence[str]) -> str:
    blocks = []
    for i, out in enumerate(outputs):
        blocks.append(f"Candidate {i+1}:\n{out}")
    return f"""
You are an answer aggregator. Select the most likely correct final answer from candidate LSF outputs.
Return only one compact final answer line: Final answer: <answer>

Query:
{query}

Candidates:
{chr(10).join(blocks)}
""".strip()


def execute_plan(
    query: str,
    plan: RouterPlan,
    cards_by_id: Dict[str, LSFCard],
    client,
    inference_model: str,
    aggregator_model: str,
    temperature: float,
    enable_thinking: bool,
) -> Tuple[str, List[SolverOutput]]:
    outputs: List[SolverOutput] = []

    def call_solver(card: LSFCard, prev_state: str = "") -> SolverOutput:
        out = chat_completion(
            client=client,
            model=inference_model,
            messages=[{"role": "user", "content": solve_with_lsf_prompt(card.spec, query, prev_state)}],
            temperature=temperature,
            max_tokens=1024,
            enable_thinking=enable_thinking,
        )
        out.role = "solver"
        out.lsf_id = card.lsf_id
        return out

    if plan.mode == "S":
        card = cards_by_id[plan.lsf_ids[0]]
        out = call_solver(card)
        outputs.append(out)
        return out.text, outputs

    if plan.mode == "A":
        candidate_texts: List[str] = []
        for lsf_id in plan.lsf_ids:
            card = cards_by_id[lsf_id]
            for _ in range(max(1, plan.k)):
                out = call_solver(card)
                outputs.append(out)
                candidate_texts.append(out.text)
        if plan.agg in {"mv", "sc", "w"}:
            final = majority_vote_text(candidate_texts)
            if final:
                return final, outputs
        agg_out = chat_completion(
            client=client,
            model=aggregator_model,
            messages=[{"role": "user", "content": judge_aggregate_prompt(query, candidate_texts)}],
            temperature=0.0,
            max_tokens=128,
            enable_thinking=False,
        )
        agg_out.role = "aggregator"
        outputs.append(agg_out)
        return agg_out.text, outputs

    if plan.mode == "C":
        stages = [s.strip() for s in plan.round_spec.split(">") if s.strip()]
        state = ""
        last_text = ""
        for sid in stages:
            card = cards_by_id[sid]
            out = call_solver(card, prev_state=state)
            outputs.append(out)
            last_text = out.text
            state = out.text
        return last_text, outputs

    raise ValueError(f"Unknown mode: {plan.mode}")


# -----------------------------
# Baseline prompts
# -----------------------------


def cot_prompt(query: str) -> str:
    return f"""
Solve the following problem carefully. Provide concise reasoning and end with:
Final answer: <answer>

Problem:
{query}
""".strip()


def run_cot_baseline(
    item: Dict[str, Any],
    client,
    model: str,
    judge_model: str,
    temperature: float,
    enable_thinking: bool,
) -> Dict[str, Any]:
    out = chat_completion(
        client=client,
        model=model,
        messages=[{"role": "user", "content": cot_prompt(item["query"])}],
        temperature=temperature,
        max_tokens=2048,
        enable_thinking=enable_thinking,
    )
    ev = evaluate_output(item, out.text, client=client, judge_model=judge_model)
    return {
        "raw_output": out.text,
        "completion_tokens": out.completion_tokens,
        "prompt_tokens": out.prompt_tokens,
        "reasoning_tokens": out.reasoning_tokens,
        **ev,
    }


# -----------------------------
# Main experiment loop
# -----------------------------


def select_test_items(test_ds: List[Dict[str, Any]], max_num_test: int, offset: int, seed: int) -> List[Tuple[int, Dict[str, Any]]]:
    if max_num_test <= 0 or max_num_test >= len(test_ds):
        return list(enumerate(test_ds[offset:], start=offset))
    step = max(1, len(test_ds) // max_num_test)
    ids = list(range(offset, len(test_ds), step))[:max_num_test]
    return [(i, test_ds[i]) for i in ids]


def summarize_records(records: List[Dict[str, Any]], prefix: str) -> Dict[str, Any]:
    if not records:
        return {f"{prefix}_n": 0, f"{prefix}_acc": 0.0, f"{prefix}_avg_completion_tokens": 0.0}
    acc = sum(int(r.get("isCorr", 0)) for r in records) / len(records)
    toks = sum(int(r.get("completion_tokens", 0)) for r in records) / len(records)
    router_toks = sum(int(r.get("router_completion_tokens", 0)) for r in records) / len(records)
    solver_toks = sum(int(r.get("solver_completion_tokens", 0)) for r in records) / len(records)
    return {
        f"{prefix}_n": len(records),
        f"{prefix}_acc": acc,
        f"{prefix}_avg_completion_tokens": toks,
        f"{prefix}_avg_router_tokens": router_toks,
        f"{prefix}_avg_solver_tokens": solver_toks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce CLSR/MDia LLM-router over evolved LSFs.")
    parser.add_argument("--data_card", default="gpqa", choices=["mmlu-pro", "gpqa", "gsm8k", "math500", "aime", "sci-qa", "hotpot-qa"])
    parser.add_argument("--lsf_dir", default="lsf_evolve_records/gpqa")
    parser.add_argument("--out_dir", default="routed_lsf_preds/llm_router_reproduce")
    parser.add_argument("--max_lsf", type=int, default=12)
    parser.add_argument("--ev_id", type=int, default=None)
    parser.add_argument("--profile_n", type=int, default=16, help="Number of training items used to profile each LSF; 0 disables profiling.")
    parser.add_argument("--max_num_test", type=int, default=100)
    parser.add_argument("--test_offset", type=int, default=0)
    parser.add_argument("--token_budget", type=int, default=220)
    parser.add_argument("--api_key", default=None)
    parser.add_argument("--base_url", default="https://api.siliconflow.cn/v1")
    parser.add_argument("--inference_model", default="Qwen/Qwen3.5-35B-A3B")
    parser.add_argument("--router_model", default="Qwen/Qwen3.5-9B")
    parser.add_argument("--aggregator_model", default="Qwen/Qwen3.5-9B")
    parser.add_argument("--judge_model", default="Qwen/Qwen3.5-9B")
    parser.add_argument("--temperature", type=float, default=0.4)
    parser.add_argument("--router_temperature", type=float, default=0.0)
    parser.add_argument("--enable_thinking", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--use_heuristic_router", action="store_true", help="Disable LLM router and use deterministic cost-aware heuristic router.")
    parser.add_argument("--run_baseline", action="store_true", help="Also run a standard concise CoT baseline for comparison.")
    parser.add_argument("--demo", action="store_true", help="Use tiny built-in demo dataset. Requires --lsf_dir unless --make_demo_lsf is set.")
    parser.add_argument("--make_demo_lsf", action="store_true", help="Create two tiny demo LSFs in a temporary output directory.")
    args = parser.parse_args()

    random.seed(args.seed)

    client = ensure_client(args.api_key, args.base_url)
    train_ds, test_ds = load_dataset(args.data_card, demo=args.demo)

    if args.make_demo_lsf:
        demo_dir = Path(args.out_dir) / "demo_lsf_records"
        demo_dir.mkdir(parents=True, exist_ok=True)
        demo_specs = [
            {"cur_lsf": "ALG-MINI: use eq->isolate->ans. Output only Final answer."},
            {"cur_lsf": "PHY-MINI: map quantities to formula, substitute, unit-check, then Final answer."},
        ]
        with (demo_dir / "demo_lsf.json").open("w", encoding="utf-8") as f:
            json.dump(demo_specs, f, indent=2)
        args.lsf_dir = str(demo_dir)

    cards = load_lsf_specs(args.lsf_dir, args.data_card, max_lsf=args.max_lsf, ev_id=args.ev_id)
    cards = profile_lsf_cards(
        cards=cards,
        train_ds=train_ds,
        client=client,
        inference_model=args.inference_model,
        judge_model=args.judge_model,
        profile_n=args.profile_n,
        seed=args.seed,
        temperature=args.temperature,
        enable_thinking=args.enable_thinking,
    )
    cards_by_id = {c.lsf_id: c for c in cards}

    run_id = f"{args.data_card}_{datetime.now().strftime('%m%d_%H%M%S')}_{now_id()}"
    out_dir = Path(args.out_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "lsf_cards.json").open("w", encoding="utf-8") as f:
        json.dump([asdict(c) | {"router_line": c.to_router_line()} for c in cards], f, indent=2, ensure_ascii=False)

    routed_records: List[Dict[str, Any]] = []
    baseline_records: List[Dict[str, Any]] = []
    test_items = select_test_items(test_ds, args.max_num_test, args.test_offset, args.seed)

    print(f"[INFO] data={args.data_card} n_test={len(test_items)} n_lsf={len(cards)} out={out_dir}")
    print("[INFO] Top router cards:")
    for c in sorted(cards, key=lambda x: (x.acc, -x.tok), reverse=True)[:5]:
        print("  ", c.to_router_line())

    for local_i, (test_id, item) in enumerate(test_items, start=1):
        query = item["query"]
        cats, cand, plan, router_outs = route_query(
            query=query,
            all_cards=cards,
            client=client,
            router_model=args.router_model,
            token_budget=args.token_budget,
            use_llm_router=not args.use_heuristic_router,
            router_temperature=args.router_temperature,
        )
        final_text, exec_outs = execute_plan(
            query=query,
            plan=plan,
            cards_by_id=cards_by_id,
            client=client,
            inference_model=args.inference_model,
            aggregator_model=args.aggregator_model,
            temperature=args.temperature,
            enable_thinking=args.enable_thinking,
        )
        ev = evaluate_output(item, final_text, client=client, judge_model=args.judge_model)
        router_tokens = sum(o.completion_tokens for o in router_outs)
        solver_tokens = sum(o.completion_tokens for o in exec_outs)
        rec = {
            "test_id": test_id,
            "query": query,
            "label": item.get("label", ""),
            "categories": cats,
            "candidate_lsf_ids": [c.lsf_id for c in cand],
            "plan": asdict(plan),
            "final_output": final_text,
            "router_outputs": [asdict(o) for o in router_outs],
            "execution_outputs": [asdict(o) for o in exec_outs],
            "router_completion_tokens": router_tokens,
            "solver_completion_tokens": solver_tokens,
            "completion_tokens": router_tokens + solver_tokens,
            **ev,
        }
        routed_records.append(rec)

        if args.run_baseline:
            b = run_cot_baseline(
                item=item,
                client=client,
                model=args.inference_model,
                judge_model=args.judge_model,
                temperature=args.temperature,
                enable_thinking=args.enable_thinking,
            )
            b.update({"test_id": test_id, "query": query, "label": item.get("label", "")})
            baseline_records.append(b)

        if local_i % 10 == 0 or local_i == len(test_items):
            rs = summarize_records(routed_records, "routed")
            msg = (
                f"[PROGRESS] {local_i}/{len(test_items)} "
                f"routed_acc={rs['routed_acc']:.3f} "
                f"routed_tok={rs['routed_avg_completion_tokens']:.1f}"
            )
            if baseline_records:
                bs = summarize_records(baseline_records, "cot")
                msg += f" cot_acc={bs['cot_acc']:.3f} cot_tok={bs['cot_avg_completion_tokens']:.1f}"
            print(msg)

        # Incremental writes for crash safety.
        with (out_dir / "routed_records.jsonl").open("w", encoding="utf-8") as f:
            for r in routed_records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        if baseline_records:
            with (out_dir / "cot_baseline_records.jsonl").open("w", encoding="utf-8") as f:
                for r in baseline_records:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary: Dict[str, Any] = {
        "run_id": run_id,
        "data_card": args.data_card,
        "inference_model": args.inference_model,
        "router_model": args.router_model,
        "judge_model": args.judge_model,
        "lsf_dir": args.lsf_dir,
        "num_lsf": len(cards),
        "profile_n": args.profile_n,
        "token_budget": args.token_budget,
        "use_llm_router": not args.use_heuristic_router,
        **summarize_records(routed_records, "routed"),
    }
    if baseline_records:
        summary.update(summarize_records(baseline_records, "cot"))
        cot_tok = summary.get("cot_avg_completion_tokens", 0.0)
        routed_tok = summary.get("routed_avg_completion_tokens", 0.0)
        summary["token_reduction_x_vs_cot"] = (cot_tok / routed_tok) if routed_tok else None
        summary["acc_delta_vs_cot"] = summary.get("routed_acc", 0.0) - summary.get("cot_acc", 0.0)

    with (out_dir / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n[SUMMARY]")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"[SAVED] {out_dir}")


if __name__ == "__main__":
    main()
