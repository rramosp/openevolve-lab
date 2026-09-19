"""Exercise 1 Student Workspace: Manual Prompt Engineering Attempt.

In Exercise 1, your goal is to beat `initial_program.py` BY HAND before we use
OpenEvolve to automate the optimization loop.

Workflow:
  1. Inspect the baseline prompt and a single ticket evaluation:
       python3 test_harness.py --inspect-ticket TCK-001 initial_program.py
  2. Run the full baseline benchmark scorecard:
       python3 test_harness.py initial_program.py
  3. Edit `SYSTEM_PROMPT` and/or `build_messages(ticket_text)` below to fix the
     failure modes you discovered (e.g., list allowed labels, warn about sarcasm,
     handle resolved false alarms, specify float vs null rules, or add a few-shot example).
  4. Evaluate your hand-crafted prompt and compare it side-by-side with the baseline:
       python3 test_harness.py --compare initial_program.py manual_prompt_attempt.py
"""

from typing import Dict, List


# EVOLVE-BLOCK-START
SYSTEM_PROMPT = """You are a customer support triage assistant.
Read the user's support ticket and return a JSON object with:
- intent_labels: list of categories
- urgency: P0, P1, P2, or P3
- sentiment: positive, neutral, negative, or critical_negative
- extracted_entities: object with account_or_invoice_id and monetary_amount_usd
- requires_human_escalation: true or false
"""

x="""
TODO (Exercise 1): Improve this prompt by hand! Consider:
  1. Listing the exact 10 allowed `intent_labels` from dataset.py so the LLM doesn't guess.
  2. Explaining how to classify sarcastic praise during outages (e.g., "10/10 engineering!").
  3. Explaining what to do when a ticket says an issue was a false alarm / already resolved.
  4. Specifying that output must be raw JSON (no ```json markdown fences) and null for missing values.
"""


def build_messages(ticket_text: str) -> List[Dict[str, str]]:
    """Construct the chat completion messages list for a given ticket.

    You can also add few-shot (user/assistant) example turns here!
    """
    return [
        {"role": "system", "content": SYSTEM_PROMPT.strip()},
        {"role": "user", "content": f"Ticket:\n{ticket_text}"},
    ]
# EVOLVE-BLOCK-END


if __name__ == "__main__":
    sample_ticket = (
        "Oh bravo, truly 10/10 engineering! Our production cluster on account ACC-90412 "
        "just vaporized 36 hours of customer transaction tables."
    )
    msgs = build_messages(sample_ticket)
    total_chars = sum(len(m["content"]) for m in msgs)
    print(f"Rendered {len(msgs)} messages ({total_chars} chars, ~{total_chars // 4} tokens):")
    for m in msgs:
        print(f"\n--- [{m['role'].upper()}] ---\n{m['content']}")
