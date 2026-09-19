"""Benchmark dataset for the OpenEvolve Prompt Optimization Lab.

Task: Multi-Label Enterprise Support Ticket Triage & Structured JSON Extraction.

Every example tests specific failure modes that naive prompts get wrong:
  1. `sarcasm_outage`: Sarcastic praise masking catastrophic outages or data loss.
  2. `multi_intent`: Compound tickets containing 2-3 distinct intents simultaneously.
  3. `resolved_negation`: Mentions of billing/outages that are explicitly resolved or negated.
  4. `security_pii`: Implicit credential leaks, unauthorized access, or GDPR erasure requests.
  5. `entity_edge_cases`: Tricky invoice IDs, currency strings ("$1,250.50 USD"), or missing values (`null`).
  6. `benign_routine`: Standard low-priority inquiries where escalation MUST be `false`.

Allowed Schema:
{
  "intent_labels": list[str],  # Subset of ALLOWED_INTENT_LABELS
  "urgency": "P0" | "P1" | "P2" | "P3",
  "sentiment": "positive" | "neutral" | "negative" | "critical_negative",
  "extracted_entities": {
    "account_or_invoice_id": str | None,
    "monetary_amount_usd": float | None
  },
  "requires_human_escalation": bool
}
"""

from typing import Any, Dict, List

ALLOWED_INTENT_LABELS = [
    "outage",
    "data_loss",
    "billing_dispute",
    "refund_request",
    "security_incident",
    "privacy_gdpr_request",
    "account_access",
    "feature_request",
    "documentation_request",
    "general_feedback",
]

ALLOWED_URGENCY = ["P0", "P1", "P2", "P3"]
ALLOWED_SENTIMENT = ["positive", "neutral", "negative", "critical_negative"]


BENCHMARK_EXAMPLES: List[Dict[str, Any]] = [
    # --- Category 1: Sarcasm & Passive-Aggressive Outages (Naive prompts predict 'positive'!) ---
    {
        "id": "TCK-001",
        "category": "sarcasm_outage",
        "ticket_text": (
            "Oh bravo, truly 10/10 engineering! Our production cluster on account ACC-90412 "
            "just vaporized 36 hours of customer transaction tables right in the middle of our "
            "Series B investor demo. Couldn't have asked for a more thrilling Tuesday morning!"
        ),
        "expected": {
            "intent_labels": ["data_loss", "outage"],
            "urgency": "P0",
            "sentiment": "critical_negative",
            "extracted_entities": {
                "account_or_invoice_id": "ACC-90412",
                "monetary_amount_usd": None,
            },
            "requires_human_escalation": True,
        },
    },
    {
        "id": "TCK-002",
        "category": "sarcasm_outage",
        "ticket_text": (
            "Just wanted to send a huge thank you to whoever pushed the midnight update. "
            "Every single API call on tenant ORG-4410 now returns HTTP 503 and we're losing "
            "roughly $4,500.00 an hour in checkout volume. Stellar job team, keep it up!"
        ),
        "expected": {
            "intent_labels": ["outage"],
            "urgency": "P0",
            "sentiment": "critical_negative",
            "extracted_entities": {
                "account_or_invoice_id": "ORG-4410",
                "monetary_amount_usd": 4500.0,
            },
            "requires_human_escalation": True,
        },
    },
    {
        "id": "TCK-003",
        "category": "sarcasm_outage",
        "ticket_text": (
            "Super cool how your new billing engine charged our corporate card THREE times "
            "for invoice INV-2026-778 ($1,299.50 each time, total $3,898.50 overcharged if you "
            "count the extra $2,599.00 taken). I love explaining surprise charges to our CFO! "
            "Reverse the duplicate $2,599.00 immediately."
        ),
        "expected": {
            "intent_labels": ["billing_dispute", "refund_request"],
            "urgency": "P1",
            "sentiment": "negative",
            "extracted_entities": {
                "account_or_invoice_id": "INV-2026-778",
                "monetary_amount_usd": 2599.0,
            },
            "requires_human_escalation": True,
        },
    },

    # --- Category 2: Multi-Intent / Compound Tickets (Naive prompts miss secondary labels) ---
    {
        "id": "TCK-004",
        "category": "multi_intent",
        "ticket_text": (
            "Hi support, two urgent items for workspace WSP-3319: First, an ex-employee whose "
            "laptop was stolen still appears to have active session tokens hitting our webhook "
            "logs from an unfamiliar IP in Bucharest. Second, we were billed $850.00 on that "
            "compromised seat yesterday—please refund that $850.00 charge and revoke all tokens."
        ),
        "expected": {
            "intent_labels": ["security_incident", "account_access", "refund_request"],
            "urgency": "P0",
            "sentiment": "critical_negative",
            "extracted_entities": {
                "account_or_invoice_id": "WSP-3319",
                "monetary_amount_usd": 850.0,
            },
            "requires_human_escalation": True,
        },
    },
    {
        "id": "TCK-005",
        "category": "multi_intent",
        "ticket_text": (
            "Under EU GDPR Article 17, I formally request complete permanent erasure of all personal "
            "data associated with account ACC-11802. Also, since I cancelled within the 14-day "
            "cooling-off window, please issue a full refund of my annual payment of $240.00."
        ),
        "expected": {
            "intent_labels": ["privacy_gdpr_request", "refund_request"],
            "urgency": "P1",
            "sentiment": "neutral",
            "extracted_entities": {
                "account_or_invoice_id": "ACC-11802",
                "monetary_amount_usd": 240.0,
            },
            "requires_human_escalation": True,
        },
    },
    {
        "id": "TCK-006",
        "category": "multi_intent",
        "ticket_text": (
            "Our SSO SAML certificate expired this morning and 120 engineers are locked out of "
            "account ENT-5501. While you help us reset the IdP metadata, could you also point us "
            "to the documentation page for SCIM automated group provisioning?"
        ),
        "expected": {
            "intent_labels": ["account_access", "documentation_request"],
            "urgency": "P1",
            "sentiment": "negative",
            "extracted_entities": {
                "account_or_invoice_id": "ENT-5501",
                "monetary_amount_usd": None,
            },
            "requires_human_escalation": True,
        },
    },

    # --- Category 3: Resolved / Negated Mentions (Trap: keywords like 'outage'/'double charge' appear!) ---
    {
        "id": "TCK-007",
        "category": "resolved_negation",
        "ticket_text": (
            "False alarm on our earlier panic! We thought there was a database outage and a "
            "$999.00 double charge on invoice INV-5520, but our internal accounting and ops teams "
            "confirmed everything is working 100% fine and the charge was our staging account. "
            "No action or refund needed—could you just send over the PDF tax receipt for INV-5520?"
        ),
        "expected": {
            "intent_labels": ["documentation_request"],
            "urgency": "P3",
            "sentiment": "positive",
            "extracted_entities": {
                "account_or_invoice_id": "INV-5520",
                "monetary_amount_usd": 999.0,
            },
            "requires_human_escalation": False,
        },
    },
    {
        "id": "TCK-008",
        "category": "resolved_negation",
        "ticket_text": (
            "We are NOT experiencing any downtime or data loss, and we do NOT want a refund. "
            "We just wanted to let your product team know that the new dark-mode analytics dashboard "
            "on account ACC-7721 is awesome! One small wish: please add CSV export for weekly cohorts."
        ),
        "expected": {
            "intent_labels": ["general_feedback", "feature_request"],
            "urgency": "P3",
            "sentiment": "positive",
            "extracted_entities": {
                "account_or_invoice_id": "ACC-7721",
                "monetary_amount_usd": None,
            },
            "requires_human_escalation": False,
        },
    },
    {
        "id": "TCK-009",
        "category": "resolved_negation",
        "ticket_text": (
            "Quick follow-up on account ACC-3094: my colleague solved the login issue by clearing "
            "her browser cookies, so please close any lock-out investigation. Everything is working "
            "smoothly now—just wanted to say thanks for your quick auto-responder links!"
        ),
        "expected": {
            "intent_labels": ["general_feedback"],
            "urgency": "P3",
            "sentiment": "positive",
            "extracted_entities": {
                "account_or_invoice_id": "ACC-3094",
                "monetary_amount_usd": None,
            },
            "requires_human_escalation": False,
        },
    },

    # --- Category 4: Implicit Security / Privacy Incidents ---
    {
        "id": "TCK-010",
        "category": "security_pii",
        "ticket_text": (
            "Hello, while inspecting the public GraphQL response payload for our storefront "
            "(account ACC-6612), I noticed that unauthenticated queries return full plaintext "
            "email addresses and last-4 SSN digits of other merchants' customers. Please advise."
        ),
        "expected": {
            "intent_labels": ["security_incident", "privacy_gdpr_request"],
            "urgency": "P0",
            "sentiment": "critical_negative",
            "extracted_entities": {
                "account_or_invoice_id": "ACC-6612",
                "monetary_amount_usd": None,
            },
            "requires_human_escalation": True,
        },
    },
    {
        "id": "TCK-011",
        "category": "security_pii",
        "ticket_text": (
            "Someone changed the recovery email and 2FA phone number on my master admin account "
            "ADM-0098 at 3:14 AM UTC without my authorization, and initiated a $12,400.00 wire "
            "payout. Lock the account and freeze the transfer right now!"
        ),
        "expected": {
            "intent_labels": ["security_incident", "account_access"],
            "urgency": "P0",
            "sentiment": "critical_negative",
            "extracted_entities": {
                "account_or_invoice_id": "ADM-0098",
                "monetary_amount_usd": 12400.0,
            },
            "requires_human_escalation": True,
        },
    },
    {
        "id": "TCK-012",
        "category": "security_pii",
        "ticket_text": (
            "Pursuant to California Consumer Privacy Act (CCPA), please provide a machine-readable "
            "export of all telemetry and personal identifiers collected for user account USR-88210 "
            "over the past 12 months."
        ),
        "expected": {
            "intent_labels": ["privacy_gdpr_request"],
            "urgency": "P2",
            "sentiment": "neutral",
            "extracted_entities": {
                "account_or_invoice_id": "USR-88210",
                "monetary_amount_usd": None,
            },
            "requires_human_escalation": True,
        },
    },

    # --- Category 5: Tricky Entity & Billing Edge Cases ---
    {
        "id": "TCK-013",
        "category": "entity_edge_cases",
        "ticket_text": (
            "Invoice INV-99104 shows a line item of $1,750.25 for Enterprise Support, "
            "whereas our signed order form states $1,250.00. Please adjust the invoice "
            "or credit the $500.25 discrepancy before our net-30 due date next week."
        ),
        "expected": {
            "intent_labels": ["billing_dispute"],
            "urgency": "P2",
            "sentiment": "negative",
            "extracted_entities": {
                "account_or_invoice_id": "INV-99104",
                "monetary_amount_usd": 500.25,
            },
            "requires_human_escalation": True,
        },
    },
    {
        "id": "TCK-014",
        "category": "entity_edge_cases",
        "ticket_text": (
            "We accidentally purchased 15 Pro seats instead of 5 on invoice INV-40219 ten minutes "
            "ago. Could you cancel the 10 extra seats and refund the $490.00 difference?"
        ),
        "expected": {
            "intent_labels": ["refund_request", "billing_dispute"],
            "urgency": "P2",
            "sentiment": "neutral",
            "extracted_entities": {
                "account_or_invoice_id": "INV-40219",
                "monetary_amount_usd": 490.0,
            },
            "requires_human_escalation": True,
        },
    },
    {
        "id": "TCK-015",
        "category": "entity_edge_cases",
        "ticket_text": (
            "Hi team, our nightly ETL pipeline on workspace WSP-7102 failed to write 4 partitions "
            "after your storage maintenance window, and those 4 partitions appear permanently missing "
            "from our bucket snapshot."
        ),
        "expected": {
            "intent_labels": ["data_loss"],
            "urgency": "P0",
            "sentiment": "critical_negative",
            "extracted_entities": {
                "account_or_invoice_id": "WSP-7102",
                "monetary_amount_usd": None,
            },
            "requires_human_escalation": True,
        },
    },

    # --- Category 6: Routine Low-Priority Inquiries (Must NOT escalate!) ---
    {
        "id": "TCK-016",
        "category": "benign_routine",
        "ticket_text": (
            "Where can I find the OpenAPI 3.1 specification or Swagger JSON file for your v2 "
            "webhooks endpoint? No account ID needed, just evaluating the platform."
        ),
        "expected": {
            "intent_labels": ["documentation_request"],
            "urgency": "P3",
            "sentiment": "neutral",
            "extracted_entities": {
                "account_or_invoice_id": None,
                "monetary_amount_usd": None,
            },
            "requires_human_escalation": False,
        },
    },
    {
        "id": "TCK-017",
        "category": "benign_routine",
        "ticket_text": (
            "It would be really helpful if the CLI tool supported `--format=parquet` when exporting "
            "audit logs from account ACC-5012. Thanks for considering!"
        ),
        "expected": {
            "intent_labels": ["feature_request"],
            "urgency": "P3",
            "sentiment": "positive",
            "extracted_entities": {
                "account_or_invoice_id": "ACC-5012",
                "monetary_amount_usd": None,
            },
            "requires_human_escalation": False,
        },
    },
    {
        "id": "TCK-018",
        "category": "benign_routine",
        "ticket_text": (
            "Hi, I need to update my team member's role from Viewer to Editor in organization ORG-2201, "
            "but the role dropdown is grayed out on my screen. I am currently an Org Admin."
        ),
        "expected": {
            "intent_labels": ["account_access"],
            "urgency": "P2",
            "sentiment": "neutral",
            "extracted_entities": {
                "account_or_invoice_id": "ORG-2201",
                "monetary_amount_usd": None,
            },
            "requires_human_escalation": False,
        },
    },
]

# Fast Stage-1 Canary Subset (5 diverse examples covering each major failure mode)
STAGE1_CANARY_IDS = {"TCK-001", "TCK-004", "TCK-007", "TCK-010", "TCK-016"}
STAGE1_EXAMPLES = [ex for ex in BENCHMARK_EXAMPLES if ex["id"] in STAGE1_CANARY_IDS]
