"""Standalone Test, Inspection & Comparison Harness for the OpenEvolve Prompt Optimization Lab.

Usage examples:
  # 1. Inspect the rendered prompt & structural stats (no API call required):
  python3 test_harness.py --show-prompt initial_program.py

  # 2. Trace a single ticket end-to-end (prompt -> live LLM output -> gold JSON -> grading):
  python3 test_harness.py --inspect-ticket TCK-001 initial_program.py

  # 3. Evaluate a prompt program on the full 18-ticket benchmark:
  python3 test_harness.py initial_program.py

  # 4. Fast 5-ticket Stage-1 canary evaluation:
  python3 test_harness.py --stage1 initial_program.py

  # 5. Side-by-side comparison of baseline vs hand-crafted or evolved prompt:
  python3 test_harness.py --compare initial_program.py manual_prompt_attempt.py
"""

import argparse
import json
import os
import sys

from dataset import BENCHMARK_EXAMPLES
from evaluator import (
    _extract_prompt_stats,
    _get_api_key,
    _load_candidate_module,
    _parse_json_response,
    _score_single_example,
    evaluate,
    evaluate_stage1,
)


def _print_prompt_inspection(program_path: str) -> None:
    """Display the exact rendered prompt messages and structural statistics."""
    module = _load_candidate_module(program_path)
    prompt_chars, est_tokens, few_shot_count = _extract_prompt_stats(module)
    sample_ticket = BENCHMARK_EXAMPLES[0]["ticket_text"]
    messages = module.build_messages(sample_ticket)

    print("=" * 78)
    print(f"PROMPT STRUCTURE INSPECTION: {program_path}")
    print("=" * 78)
    print(f"  Static Prompt Length     : {int(prompt_chars)} chars")
    print(f"  Estimated Prompt Tokens  : {est_tokens:.1f} tokens")
    print(f"  Few-Shot Example Turns   : {int(few_shot_count)} turns")
    print(f"  Total Messages per Call  : {len(messages)} messages")
    print("-" * 78)
    for idx, msg in enumerate(messages):
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")
        print(f"[Message {idx + 1} | role={role}]")
        print(content)
        print("-" * 78)


def _print_single_ticket_walkthrough(program_path: str, ticket_id: str) -> None:
    """Trace one support ticket through build_messages -> Gemini -> rubric grader."""
    matching = [ex for ex in BENCHMARK_EXAMPLES if ex["id"].upper() == ticket_id.upper()]
    if not matching:
        valid_ids = ", ".join(ex["id"] for ex in BENCHMARK_EXAMPLES)
        print(f"ERROR: Unknown ticket ID {ticket_id!r}. Valid IDs: {valid_ids}", file=sys.stderr)
        sys.exit(1)

    example = matching[0]
    module = _load_candidate_module(program_path)
    messages = module.build_messages(example["ticket_text"])
    api_key = _get_api_key()
    scored = _score_single_example(api_key, module, example)
    parsed_pred, clean_json = _parse_json_response(scored["raw_output"])

    print("=" * 78)
    print(f"SINGLE-TICKET EVALUATION WALKTHROUGH: {example['id']} (category={example['category']})")
    print(f"Program Path: {program_path}")
    print("=" * 78)

    print("\n1. INPUT SUPPORT TICKET:")
    print("-" * 78)
    print(example["ticket_text"])

    print("\n2. MESSAGES SENT TO GEMINI (`build_messages(ticket_text)`):")
    print("-" * 78)
    for idx, msg in enumerate(messages):
        print(f"  [{idx + 1}] role={msg.get('role')!r}:")
        for line in str(msg.get("content", "")).splitlines():
            print(f"      {line}")

    print("\n3. RAW MODEL OUTPUT FROM GEMINI:")
    print("-" * 78)
    if scored["raw_output"]:
        print(scored["raw_output"])
    else:
        err_msg = "; ".join(scored.get("field_errors", [])) or "Empty response returned by model"
        print(f"[NO RAW OUTPUT — {err_msg}]")

    print("\n4. EXPECTED GOLD JSON vs. PARSED MODEL JSON:")
    print("-" * 78)
    print("Expected Gold JSON:")
    print(json.dumps(example["expected"], indent=2))
    print("\nParsed Model JSON:")
    print(json.dumps(parsed_pred, indent=2))

    print("\n5. FIELD-BY-FIELD RUBRIC GRADING:")
    print("-" * 78)
    print(f"  Clean Raw JSON (no ``` fences) : {'PASS' if clean_json else 'FAIL (wrapped in markdown fences)'}")
    print(f"  Intent Multi-Label F1 Score    : {scored['label_f1'] * 100:6.2f}%")
    print(f"  Urgency Match                  : {'PASS' if scored['urgency_ok'] == 1.0 else 'FAIL'}")
    print(f"  Sentiment Match                : {'PASS' if scored['sentiment_ok'] == 1.0 else 'FAIL'}")
    print(f"  Entity Extraction Match        : {scored['entity_ok'] * 100:6.2f}%")
    print(f"  Human Escalation Flag Match    : {'PASS' if scored['escalation_ok'] == 1.0 else 'FAIL'}")
    print(f"  100% Exact Ticket Match        : {'YES' if scored['exact_match'] == 1.0 else 'NO'}")
    if scored["field_errors"]:
        print("\n  Specific Discrepancies Detected:")
        for err in scored["field_errors"]:
            print(f"    * {err}")
    print("=" * 78)


def _print_single_report(title: str, program_path: str, result) -> None:
    metrics = result.metrics
    artifacts = result.artifacts

    print("=" * 74)
    print(f"PROMPT EVALUATION REPORT: {title}")
    print(f"Program Path : {program_path}")
    print("=" * 74)
    print(f"  Combined Fitness Score     : {metrics['combined_score']:.4f}")
    print(f"  Raw Quality Score          : {metrics['raw_quality_score']:.4f}")
    print(f"  100% Exact Ticket Match    : {metrics['exact_match_rate'] * 100:6.2f}%")
    print(f"  Intent Multi-Label F1      : {metrics['label_f1'] * 100:6.2f}%")
    print(f"  Urgency Accuracy (P0-P3)   : {metrics['urgency_accuracy'] * 100:6.2f}%")
    print(f"  Sentiment Accuracy         : {metrics['sentiment_accuracy'] * 100:6.2f}%")
    print(f"  Entity Extraction Accuracy : {metrics['entity_accuracy'] * 100:6.2f}%")
    print(f"  Escalation Flag Accuracy   : {metrics['escalation_accuracy'] * 100:6.2f}%")
    print(f"  Clean JSON Validity Rate   : {metrics['json_validity_rate'] * 100:6.2f}%")
    print("-" * 74)
    print("  MAP-Elites Structural Coordinates:")
    print(f"    prompt_char_length       : {int(metrics['prompt_char_length'])} chars")
    print(f"    estimated_prompt_tokens  : {metrics['estimated_prompt_tokens']:.1f} tokens")
    print(f"    few_shot_count           : {int(metrics['few_shot_count'])} turns")
    print(f"    eval_time_sec            : {metrics['eval_time_sec']:.2f} s")
    print("-" * 74)

    if "category_accuracy_summary" in artifacts:
        print(artifacts["category_accuracy_summary"])
        print("-" * 74)

    if "failure_cases_report" in artifacts:
        print("Top Diagnostic Failure Cases:")
        print(artifacts["failure_cases_report"])
    print("=" * 74)


def _print_comparison_report(path_a: str, res_a, path_b: str, res_b) -> None:
    ma = res_a.metrics
    mb = res_b.metrics

    print("\n" + "=" * 78)
    print("SIDE-BY-SIDE PROMPT COMPARISON")
    print(f"  Prompt A (Baseline) : {path_a}")
    print(f"  Prompt B (Candidate): {path_b}")
    print("=" * 78)
    print(f"{'Metric':<30} | {'Prompt A':>12} | {'Prompt B':>12} | {'Delta (B - A)':>14}")
    print("-" * 78)

    rows = [
        ("combined_score", False),
        ("raw_quality_score", False),
        ("exact_match_rate", True),
        ("label_f1", True),
        ("urgency_accuracy", True),
        ("sentiment_accuracy", True),
        ("entity_accuracy", True),
        ("escalation_accuracy", True),
        ("json_validity_rate", True),
        ("prompt_char_length", False),
        ("estimated_prompt_tokens", False),
        ("few_shot_count", False),
    ]
    for key, is_pct in rows:
        va = ma.get(key, 0.0)
        vb = mb.get(key, 0.0)
        diff = vb - va
        if is_pct:
            print(f"{key:<30} | {va * 100:11.2f}% | {vb * 100:11.2f}% | {diff * 100:+13.2f}%")
        else:
            print(f"{key:<30} | {va:12.2f} | {vb:12.2f} | {diff:+14.2f}")
    print("=" * 78)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect, evaluate, or compare prompt programs.")
    parser.add_argument(
        "program",
        nargs="?",
        default="initial_program.py",
        help="Path to candidate prompt program (default: initial_program.py)",
    )
    parser.add_argument(
        "--show-prompt",
        action="store_true",
        help="Inspect the rendered prompt messages and token stats (no API key required)",
    )
    parser.add_argument(
        "--inspect-ticket",
        metavar="TICKET_ID",
        help="Trace a single ticket end-to-end (e.g. --inspect-ticket TCK-001)",
    )
    parser.add_argument(
        "--stage1",
        action="store_true",
        help="Run fast Stage-1 canary evaluation (5 tickets) instead of full benchmark",
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("PROMPT_A_PY", "PROMPT_B_PY"),
        help="Evaluate and compare two prompt programs side-by-side",
    )
    args = parser.parse_args()

    if args.show_prompt:
        _print_prompt_inspection(args.program)
        return

    if not os.environ.get("OPENAI_API_KEY"):
        print(
            "ERROR: OPENAI_API_KEY is not set in your shell environment.\n"
            "Please export your API key first:\n"
            "  export OPENAI_API_KEY='your-api-key'",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.inspect_ticket:
        _print_single_ticket_walkthrough(args.program, args.inspect_ticket)
        return

    eval_fn = evaluate_stage1 if args.stage1 else evaluate

    if args.compare:
        path_a, path_b = args.compare
        print(f"Evaluating Prompt A ({path_a})...")
        res_a = eval_fn(path_a)
        print(f"Evaluating Prompt B ({path_b})...")
        res_b = eval_fn(path_b)
        _print_single_report("PROMPT A (BASELINE)", path_a, res_a)
        _print_single_report("PROMPT B (CANDIDATE)", path_b, res_b)
        _print_comparison_report(path_a, res_a, path_b, res_b)
    else:
        res = eval_fn(args.program)
        label = "STAGE-1 CANARY (5 TICKETS)" if args.stage1 else "FULL BENCHMARK (18 TICKETS)"
        _print_single_report(label, args.program, res)


if __name__ == "__main__":
    main()
