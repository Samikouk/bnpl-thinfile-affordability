"""Guardrail for the GenAI cure-draft output.

Every draft is for human review; this check is the automated gate that runs
first. It flags:
  - non-compliant / threatening collections language (FCA Consumer Duty,
    FDCPA-style concerns),
  - possible PII leakage (email address or long numeric id in the text),
  - drafts that reference none of the approved payment options (ungrounded
    offers the LLM may have invented).
"""
from __future__ import annotations

import re

# Threatening or non-compliant collections language.
BANNED_PATTERNS = [
    r"legal action",
    r"\bcourt\b",
    r"bailiff",
    r"debt collector",
    r"we will report you",
    r"guarantee",
    r"\bapr\b",
    r"waive",
    r"write[- ]?off",
]

# Crude PII detectors: an email address, or a long digit run (card / account).
PII_PATTERNS = [
    r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}",
    r"\b\d{12,}\b",
]


def guardrail_check(text: str, allowed_plans: list[str]) -> dict:
    """Return {"ok": bool, "violations": [str]} for a cure-draft string."""
    t = (text or "").lower()
    violations: list[str] = []

    for pat in BANNED_PATTERNS:
        if re.search(pat, t):
            violations.append(f"non-compliant phrase matched /{pat}/")

    for pat in PII_PATTERNS:
        if re.search(pat, t):
            violations.append("possible PII leak (email address or long numeric id)")
            break

    if allowed_plans and not any(p.lower() in t for p in allowed_plans):
        violations.append("references no approved payment option")

    return {"ok": len(violations) == 0, "violations": violations}
