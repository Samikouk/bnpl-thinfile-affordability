# Databricks notebook source
# MAGIC %md
# MAGIC # GenAI affordability narrative + early-cure draft (for human review)
# MAGIC One `ai_query` call to a Claude endpoint. Input is tokenised (no PII) plus the
# MAGIC model's deterministic reason codes. Output is a draft for a human agent to review,
# MAGIC constrained to approved options, then checked by `data/guardrail.py`.

# COMMAND ----------
ENDPOINT = "databricks-claude-haiku-4-5"

# In production the facts come from a gold_decisions / cure_cases row (tokenised).
prompt = (
    "You are drafting internal documentation for a Buy Now Pay Later lender, for HUMAN "
    "REVIEW before any use. Do not contact the customer directly. Using only the facts, "
    "write two short sections. Section 1 titled AFFORDABILITY ASSESSMENT NARRATIVE for the "
    "audit file, 3 to 4 sentences, explaining the risk using the reason codes. Section 2 "
    "titled EARLY CURE OUTREACH DRAFT for a human agent to review, offering only these "
    "approved options: split the remaining balance into instalments, a 14 day extension, or "
    "a reduced payment plan. Keep it supportive and Consumer Duty aligned. Do not invent "
    "interest, fees, or legal threats. Do not include any customer name, email, or account "
    "number. FACTS (no PII): case ref CASE-7F3A; account was APPROVED at checkout then missed "
    "the first instalment; model FPD probability at approval 0.28; reason codes are Low "
    "disposable income, Irregular or unstable income pattern, and No credit-bureau history "
    "(thin file); requested amount 180 GBP; merchant category Fashion; thin file yes."
)

narrative = spark.sql(
    "SELECT ai_query(:ep, :p) AS narrative",
    args={"ep": ENDPOINT, "p": prompt},
).collect()[0]["narrative"]
print(narrative)

# COMMAND ----------
# MAGIC %md ## Guardrail (data/guardrail.py) — the automated gate before any human sees it

# COMMAND ----------
import re

BANNED = [r"legal action", r"\bcourt\b", r"bailiff", r"debt collector",
          r"we will report you", r"guarantee", r"\bapr\b", r"waive", r"write[- ]?off"]
PII = [r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", r"\b\d{12,}\b"]
ALLOWED = ["split", "instalments", "14 day extension", "14-day extension", "reduced payment plan", "reduced plan"]


def guardrail_check(text):
    t = (text or "").lower()
    v = [f"non-compliant phrase /{p}/" for p in BANNED if re.search(p, t)]
    if any(re.search(p, t) for p in PII):
        v.append("possible PII leak")
    if not any(a.lower() in t for a in ALLOWED):
        v.append("references no approved payment option")
    return {"ok": not v, "violations": v}


print(guardrail_check(narrative))
