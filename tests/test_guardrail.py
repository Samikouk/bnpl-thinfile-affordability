"""Tests for the GenAI cure-draft guardrail.

The guardrail makes the LLM output safe to show: it flags non-compliant /
threatening language, possible PII leaks, and drafts that reference no approved
payment option. Drafts are for human review; the guardrail is the gate.
"""
from data.guardrail import guardrail_check

ALLOWED = ["split into instalments", "14-day extension", "reduced payment plan"]


def test_clean_message_passes():
    txt = ("Hi, we noticed a missed payment. We can help: split into instalments, "
           "or take a 14-day extension. Reply and we'll set it up. Interest-free, as always.")
    r = guardrail_check(txt, ALLOWED)
    assert r["ok"] and r["violations"] == []


def test_threatening_language_flagged():
    txt = "Pay immediately or we will take legal action and send bailiffs to your home."
    r = guardrail_check(txt, ALLOWED)
    assert not r["ok"]
    assert any("legal action" in v for v in r["violations"])


def test_pii_leak_flagged():
    txt = "Email john.doe@example.com to arrange to split into instalments."
    r = guardrail_check(txt, ALLOWED)
    assert not r["ok"]
    assert any("PII" in v for v in r["violations"])


def test_ungrounded_offer_flagged():
    txt = "We can offer you a special one-time deal today only."
    r = guardrail_check(txt, ALLOWED)
    assert not r["ok"]
    assert any("approved payment option" in v for v in r["violations"])
