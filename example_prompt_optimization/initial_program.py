"""Baseline candidate prompt program for the OpenEvolve Prompt Optimization Lab.

OpenEvolve mutates ONLY the code between `# EVOLVE-BLOCK-START` and `# EVOLVE-BLOCK-END`.
The evaluator calls `build_messages(ticket_text)` for every support ticket in the
benchmark dataset and sends those messages directly to the target Gemini model.
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


def build_messages(ticket_text: str) -> List[Dict[str, str]]:
    """Construct the chat completion messages list for a given ticket.

    Evolution can improve this function by:
      1. Refining SYSTEM_PROMPT with exact taxonomy definitions & decision rules
      2. Adding few-shot (user/assistant) demonstration pairs for tricky edge cases
      3. Enforcing strict JSON schema & type rules (e.g. float numbers vs strings, null handling)
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
