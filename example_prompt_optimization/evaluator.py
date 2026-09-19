"""Live Gemini API Evaluator for the OpenEvolve Prompt Optimization Lab.

Evaluates candidate prompt programs (`build_messages(ticket_text)`) against the
benchmark dataset using live Gemini API calls via the OpenAI-compatible endpoint.

Key OpenEvolve features demonstrated:
  1. Cascade Evaluation (`evaluate_stage1` -> `evaluate_stage2`):
     Quickly filters syntax errors or low-performing prompts on 5 canary tickets
     before spending API tokens on the full 18-ticket benchmark.
  2. Continuous MAP-Elites Features (`prompt_char_length`, `estimated_prompt_tokens`,
     `few_shot_count`):
     Allows MAP-Elites to maintain diverse prompt strategies across the
     accuracy-vs-token-budget Pareto frontier.
  3. Rich Diagnostic Artifacts (`failure_cases_report`, `category_accuracy_summary`):
     Feeds concrete misclassified examples back into OpenEvolve's mutation prompt
     when `prompt.include_artifacts: true` is enabled in `config.yaml`.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import importlib.util
import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Tuple

import urllib.error
import urllib.request

try:
    import openai
except ImportError:
    openai = None  # type: ignore[assignment]

# Ensure local directory is importable when invoked by OpenEvolve worker subprocesses
_LAB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LAB_DIR not in sys.path:
    sys.path.insert(0, _LAB_DIR)

from dataset import (  # noqa: E402
    ALLOWED_INTENT_LABELS,
    BENCHMARK_EXAMPLES,
    STAGE1_EXAMPLES,
)

try:
    from openevolve.evaluation_result import EvaluationResult
except ImportError:
    # Lightweight fallback if run outside openevolve for standalone inspection
    class EvaluationResult:  # type: ignore[no-redef]
        def __init__(self, metrics: Dict[str, float], artifacts: Dict[str, str] = None):
            self.metrics = metrics
            self.artifacts = artifacts or {}


TARGET_API_BASE = os.environ.get(
    "OPENAI_COMPATIBLE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
)
TARGET_MODEL = os.environ.get("MODEL", "gemini-3.5-flash-lite")
MAX_WORKERS = int(os.environ.get("EVAL_MAX_WORKERS", "8"))


def _get_api_key() -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        api_key = api_key.strip().strip("'\"")
    if not api_key:
        raise RuntimeError(
            "Missing API key. Please set OPENAI_API_KEY in your shell environment:\n"
            "  export OPENAI_API_KEY='your-api-key'"
        )
    return api_key


def _call_chat_completions(messages: List[Dict[str, str]], api_key: str) -> str:
    """Call OpenAI-compatible chat completions endpoint via SDK or stdlib urllib."""
    if openai is not None:
        client = openai.OpenAI(
            api_key=api_key, base_url=TARGET_API_BASE, timeout=30.0, max_retries=2
        )
        response = client.chat.completions.create(
            model=TARGET_MODEL,
            messages=messages,
            temperature=0.0,
            max_tokens=2048,
        )
        return response.choices[0].message.content or ""

    url = TARGET_API_BASE.rstrip("/") + "/chat/completions"
    payload = json.dumps(
        {
            "model": TARGET_MODEL,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 2048,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"] or ""
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"HTTP {e.code} calling model {TARGET_MODEL} at {url}: {error_body}"
        ) from e


def _load_candidate_module(program_path: str):
    spec = importlib.util.spec_from_file_location("candidate_prompt_module", program_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load candidate program from {program_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "build_messages") or not callable(module.build_messages):
        raise AttributeError("Candidate program must define `build_messages(ticket_text: str)`")
    return module


def _extract_prompt_stats(module) -> Tuple[float, float, float]:
    """Compute static prompt length, token estimate, and few-shot turn count."""
    sentinel_text = "__TICKET_PLACEHOLDER__"
    msgs = module.build_messages(sentinel_text)
    if not isinstance(msgs, list) or not msgs:
        raise ValueError("build_messages(ticket_text) must return a non-empty list of dicts")

    total_chars = 0
    for m in msgs:
        content = str(m.get("content", ""))
        total_chars += len(content.replace(sentinel_text, ""))

    prompt_char_length = float(total_chars)
    estimated_tokens = round(prompt_char_length / 4.0, 1)
    # Count assistant messages prior to the final user query as few-shot examples
    few_shot_count = float(sum(1 for m in msgs[:-1] if m.get("role") == "assistant"))
    return prompt_char_length, estimated_tokens, few_shot_count


def _parse_json_response(raw_text: str) -> Tuple[Dict[str, Any], bool]:
    """Parse JSON from model output; track whether clean JSON was returned without fences."""
    stripped = raw_text.strip()
    is_clean_json = False
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed, True
    except json.JSONDecodeError:
        pass

    # Fallback: strip ```json ... ``` markdown fences if present
    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fenced_match:
        try:
            parsed = json.loads(fenced_match.group(1))
            if isinstance(parsed, dict):
                return parsed, is_clean_json
        except json.JSONDecodeError:
            pass

    return {}, False


def _score_single_example(
    api_key: str, module, example: Dict[str, Any]
) -> Dict[str, Any]:
    """Run one support ticket through the candidate prompt and score every field."""
    ticket_id = example["id"]
    category = example["category"]
    ticket_text = example["ticket_text"]
    expected = example["expected"]

    try:
        messages = module.build_messages(ticket_text)
        raw_output = _call_chat_completions(messages, api_key)
    except Exception as exc:
        return {
            "id": ticket_id,
            "category": category,
            "json_valid": 0.0,
            "clean_json": 0.0,
            "label_f1": 0.0,
            "urgency_ok": 0.0,
            "sentiment_ok": 0.0,
            "entity_ok": 0.0,
            "escalation_ok": 0.0,
            "exact_match": 0.0,
            "field_errors": [f"API/Execution error: {exc}"],
            "raw_output": "",
        }

    pred, clean_json = _parse_json_response(raw_output)
    json_valid = 1.0 if pred else 0.0
    field_errors: List[str] = []

    if not pred:
        return {
            "id": ticket_id,
            "category": category,
            "json_valid": 0.0,
            "clean_json": 0.0,
            "label_f1": 0.0,
            "urgency_ok": 0.0,
            "sentiment_ok": 0.0,
            "entity_ok": 0.0,
            "escalation_ok": 0.0,
            "exact_match": 0.0,
            "field_errors": [f"Invalid JSON output: {raw_output[:140]!r}"],
            "raw_output": raw_output,
        }

    if not clean_json:
        field_errors.append("Output wrapped in markdown code fences instead of raw JSON")

    # 1. Multi-label intent F1
    exp_labels = set(expected["intent_labels"])
    raw_pred_labels = pred.get("intent_labels", [])
    pred_labels = set(raw_pred_labels) if isinstance(raw_pred_labels, list) else set()
    invalid_labels = pred_labels - set(ALLOWED_INTENT_LABELS)
    if invalid_labels:
        field_errors.append(f"Hallucinated non-taxonomy labels: {sorted(invalid_labels)}")

    tp = len(exp_labels & pred_labels)
    precision = tp / len(pred_labels) if pred_labels else 0.0
    recall = tp / len(exp_labels) if exp_labels else 0.0
    label_f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    if label_f1 < 1.0:
        field_errors.append(
            f"intent_labels: expected {sorted(exp_labels)}, got {sorted(pred_labels)}"
        )

    # 2. Urgency accuracy
    pred_urgency = pred.get("urgency")
    urgency_ok = 1.0 if pred_urgency == expected["urgency"] else 0.0
    if not urgency_ok:
        field_errors.append(f"urgency: expected {expected['urgency']!r}, got {pred_urgency!r}")

    # 3. Sentiment accuracy
    pred_sentiment = pred.get("sentiment")
    sentiment_ok = 1.0 if pred_sentiment == expected["sentiment"] else 0.0
    if not sentiment_ok:
        field_errors.append(
            f"sentiment: expected {expected['sentiment']!r}, got {pred_sentiment!r}"
        )

    # 4. Extracted entities accuracy (ID + numeric monetary amount)
    pred_entities = pred.get("extracted_entities")
    if not isinstance(pred_entities, dict):
        pred_entities = {}
    exp_entities = expected["extracted_entities"]

    pred_id = pred_entities.get("account_or_invoice_id")
    exp_id = exp_entities["account_or_invoice_id"]
    id_ok = 1.0 if pred_id == exp_id else 0.0
    if not id_ok:
        field_errors.append(f"account_or_invoice_id: expected {exp_id!r}, got {pred_id!r}")

    pred_amt = pred_entities.get("monetary_amount_usd")
    exp_amt = exp_entities["monetary_amount_usd"]
    if exp_amt is None:
        amt_ok = 1.0 if pred_amt is None else 0.0
    else:
        amt_ok = (
            1.0
            if isinstance(pred_amt, (int, float))
            and not isinstance(pred_amt, bool)
            and abs(float(pred_amt) - float(exp_amt)) < 0.01
            else 0.0
        )
    if not amt_ok:
        field_errors.append(f"monetary_amount_usd: expected {exp_amt!r}, got {pred_amt!r}")

    entity_ok = 0.5 * id_ok + 0.5 * amt_ok

    # 5. Escalation accuracy
    pred_esc = pred.get("requires_human_escalation")
    exp_esc = expected["requires_human_escalation"]
    escalation_ok = (
        1.0 if isinstance(pred_esc, bool) and pred_esc == exp_esc else 0.0
    )
    if not escalation_ok:
        field_errors.append(
            f"requires_human_escalation: expected {exp_esc!r}, got {pred_esc!r}"
        )

    exact_match = (
        1.0
        if (
            label_f1 == 1.0
            and urgency_ok == 1.0
            and sentiment_ok == 1.0
            and entity_ok == 1.0
            and escalation_ok == 1.0
            and clean_json
        )
        else 0.0
    )

    return {
        "id": ticket_id,
        "category": category,
        "json_valid": json_valid,
        "clean_json": 1.0 if clean_json else 0.0,
        "label_f1": label_f1,
        "urgency_ok": urgency_ok,
        "sentiment_ok": sentiment_ok,
        "entity_ok": entity_ok,
        "escalation_ok": escalation_ok,
        "exact_match": exact_match,
        "field_errors": field_errors,
        "raw_output": raw_output,
    }


def _evaluate_examples(program_path: str, examples: List[Dict[str, Any]]) -> EvaluationResult:
    """Evaluate a candidate prompt program on a list of examples and build artifacts."""
    start_time = time.time()
    try:
        module = _load_candidate_module(program_path)
        prompt_chars, est_tokens, few_shot_count = _extract_prompt_stats(module)
    except Exception as exc:
        return EvaluationResult(
            metrics={
                "combined_score": 0.0,
                "exact_match_rate": 0.0,
                "label_f1": 0.0,
                "urgency_accuracy": 0.0,
                "sentiment_accuracy": 0.0,
                "entity_accuracy": 0.0,
                "escalation_accuracy": 0.0,
                "json_validity_rate": 0.0,
                "prompt_char_length": 0.0,
                "estimated_prompt_tokens": 0.0,
                "few_shot_count": 0.0,
            },
            artifacts={
                "failure_cases_report": f"Program failed to load or build messages: {exc}"
            },
        )

    api_key = _get_api_key()
    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(_score_single_example, api_key, module, ex): ex["id"]
            for ex in examples
        }
        for fut in as_completed(futures):
            results.append(fut.result())

    results.sort(key=lambda r: r["id"])
    n = float(len(results))

    label_f1 = sum(r["label_f1"] for r in results) / n
    urgency_acc = sum(r["urgency_ok"] for r in results) / n
    sentiment_acc = sum(r["sentiment_ok"] for r in results) / n
    entity_acc = sum(r["entity_ok"] for r in results) / n
    escalation_acc = sum(r["escalation_ok"] for r in results) / n
    exact_match_rate = sum(r["exact_match"] for r in results) / n
    json_validity_rate = sum(r["json_valid"] for r in results) / n
    clean_json_rate = sum(r["clean_json"] for r in results) / n

    # Weighted quality score across all 5 extraction tasks + clean JSON bonus
    raw_quality_score = (
        0.30 * label_f1
        + 0.20 * urgency_acc
        + 0.15 * sentiment_acc
        + 0.15 * entity_acc
        + 0.15 * escalation_acc
        + 0.05 * clean_json_rate
    )

    # Mild token bloat regularizer: no penalty up to 1,200 tokens (~4,800 chars),
    # then a gentle linear penalty so evolution prefers concise, high-signal prompts.
    token_penalty = max(0.0, (est_tokens - 1200.0) * 0.00005)
    combined_score = max(0.0, round(raw_quality_score - token_penalty, 4))

    # Build per-category breakdown artifact
    category_buckets: Dict[str, List[float]] = {}
    for r in results:
        category_buckets.setdefault(r["category"], []).append(r["exact_match"])
    cat_lines = ["Per-Category Exact Match Rates:"]
    for cat, vals in sorted(category_buckets.items()):
        cat_lines.append(f"  - {cat}: {sum(vals)}/{len(vals)} ({100.0 * sum(vals) / len(vals):.1f}%)")

    # Build concrete failure cases report artifact (top 6 failing examples)
    failure_lines = []
    failing_examples = [r for r in results if r["field_errors"]]
    for r in failing_examples[:6]:
        failure_lines.append(f"[{r['id']} | category={r['category']}]")
        for err in r["field_errors"]:
            failure_lines.append(f"  * {err}")

    failure_report = (
        "\n".join(failure_lines)
        if failure_lines
        else "All evaluated tickets matched 100% with zero errors!"
    )

    elapsed_sec = round(time.time() - start_time, 2)

    return EvaluationResult(
        metrics={
            "combined_score": combined_score,
            "raw_quality_score": round(raw_quality_score, 4),
            "exact_match_rate": round(exact_match_rate, 4),
            "label_f1": round(label_f1, 4),
            "urgency_accuracy": round(urgency_acc, 4),
            "sentiment_accuracy": round(sentiment_acc, 4),
            "entity_accuracy": round(entity_acc, 4),
            "escalation_accuracy": round(escalation_acc, 4),
            "json_validity_rate": round(json_validity_rate, 4),
            "prompt_char_length": prompt_chars,
            "estimated_prompt_tokens": est_tokens,
            "few_shot_count": few_shot_count,
            "eval_time_sec": elapsed_sec,
        },
        artifacts={
            "category_accuracy_summary": "\n".join(cat_lines),
            "failure_cases_report": failure_report,
        },
    )


def evaluate_stage1(program_path: str) -> EvaluationResult:
    """Stage 1 Cascade Gate: fast evaluation on 5 diverse canary examples."""
    return _evaluate_examples(program_path, STAGE1_EXAMPLES)


def evaluate_stage2(program_path: str) -> EvaluationResult:
    """Stage 2 Full Benchmark: complete evaluation across all 18 tricky tickets."""
    return _evaluate_examples(program_path, BENCHMARK_EXAMPLES)


def evaluate(program_path: str) -> EvaluationResult:
    """Default entry point when cascade evaluation is disabled."""
    return _evaluate_examples(program_path, BENCHMARK_EXAMPLES)
