# Task 7 — GenAI affordability narrative + guardrail (execution evidence)

Run 2026-09-16. One `ai_query` call to `databricks-claude-haiku-4-5`, tokenised
input (no PII) + the model's deterministic reason codes. Output is a draft for
human review, constrained to approved options.

## Endpoint sanity

```
SELECT ai_query('databricks-claude-haiku-4-5', 'Reply with exactly: PONG') -> "PONG"
```

## Input facts (tokenised, no PII)

```
case ref CASE-7F3A; account APPROVED at checkout then missed first instalment;
model FPD probability at approval 0.28; reason codes: Low disposable income,
Irregular or unstable income pattern, No credit-bureau history (thin file);
requested amount 180 GBP; merchant category Fashion; thin file yes.
```

## ai_query output

```
# SECTION 1: AFFORDABILITY ASSESSMENT NARRATIVE

At approval, the affordability model indicated elevated risk with an FPD probability
of 0.28, reflecting concerns identified during underwriting: low disposable income,
an irregular or unstable income pattern, and absence of credit-bureau history limiting
verification capability. The applicant proceeded to purchase and missed the first
instalment, confirming the model's risk indicators were material to repayment capacity.
The combination of thin-file status and income volatility suggests genuine affordability
constraints rather than engagement failure. Early intervention with flexible repayment
options is appropriate to support sustainable resolution.

---

# SECTION 2: EARLY CURE OUTREACH DRAFT

**Subject: Let's find a payment option that works for you**

We've noticed the first payment on your recent purchase wasn't completed. We understand
that money can be tight sometimes, and we'd like to help you get back on track in a way
that suits your situation.

You have three options available:
- **Spread it out**: Split your remaining balance into smaller instalments over a longer period
- **Breathing room**: Take a 14-day extension to your next payment date
- **Reduced plan**: Move to a reduced payment schedule that eases the pressure now

Please get in touch at your earliest convenience so we can discuss which option works best
for you. We're here to help.
```

## Guardrail results (data/guardrail.py)

Real output:
```
{"ok": true, "violations": []}
```

Non-compliant control ("...legal action and send bailiffs. Contact john.doe@example.com. We guarantee approval..."):
```
{"ok": false, "violations": [
  "non-compliant phrase matched /legal action/",
  "non-compliant phrase matched /bailiff/",
  "non-compliant phrase matched /guarantee/",
  "possible PII leak (email address or long numeric id)",
  "references no approved payment option"]}
```

The model authors the narrative; the reason codes come from the model (SHAP), not
the LLM; and the guardrail is the gate before any human sees the draft.
