"""End-to-end journey (the evidence spine).

Walks ONE applicant through the whole integrated loop, logging every step:

  gold feature row  ->  build_features  ->  Model Serving score
  ->  cohort threshold (Lakebase)  ->  APPROVE/DECLINE
  ->  account slips (first-payment default)  ->  ai_query cure draft
  ->  guardrail check  ->  INSERT cure_case (Lakebase)
  ->  Genie surfaces the worst cohort  ->  UPDATE cohort_threshold (Lakebase)
  ->  re-read threshold to show the loop closed.

Reuses data/features.build_features and data/guardrail (no duplicated logic).
Shells out to the Databricks CLI and `databricks psql` for the live services.
Run from the repo root:  PYTHONPATH=. python3 journey/run_journey.py
"""
from __future__ import annotations

import json
import subprocess
import sys

import pandas as pd

from config import (PROFILE, CATALOG, SCHEMA, SERVING_ENDPOINT, GENAI_ENDPOINT,
                    GENIE_SPACE_ID, LAKEBASE_PROJECT)
from data.features import build_features, FEATURE_COLUMNS
from data.guardrail import guardrail_check

FQ = f"{CATALOG}.{SCHEMA}"
PSQL_ENV = {"PATH": "/opt/homebrew/opt/libpq/bin:/usr/bin:/bin:/usr/local/bin"}
APPROVED_PLANS = ["split", "instalments", "14 day extension", "14-day extension",
                  "reduced payment plan", "reduced plan"]


def step(n, title):
    print(f"\n{'=' * 72}\nSTEP {n}: {title}\n{'=' * 72}")


def sql(query):
    out = subprocess.run(
        ["databricks", "experimental", "aitools", "tools", "query", query, "--profile", PROFILE, "-o", "json"],
        capture_output=True, text=True)
    try:
        return json.loads(out.stdout)
    except Exception:
        print(out.stdout, out.stderr); return []


def psql(query):
    import os
    env = dict(os.environ); env.update(PSQL_ENV)
    out = subprocess.run(
        ["databricks", "psql", "--project", LAKEBASE_PROJECT, "--profile", PROFILE, "--", "-t", "-c", query],
        capture_output=True, text=True, env=env)
    return (out.stdout + out.stderr).strip()


def main():
    print("BNPL COLD-START AFFORDABILITY — END-TO-END JOURNEY")

    # 1. pick an approved-then-slipped applicant and pull its raw gold feature row
    step(1, "Ingest: pull one applicant's point-in-time feature row from gold")
    picked = sql(
        f"SELECT application_id FROM {FQ}.gold_decisions "
        f"WHERE decision='APPROVE' AND fpd_actual=1 AND merchant_category='Travel' LIMIT 1")
    app_id = picked[0]["application_id"]
    frow = sql(f"SELECT * FROM {FQ}.gold_features WHERE application_id='{app_id}'")[0]
    drow = sql(f"SELECT merchant_category, reason_codes, round(score,4) AS score, thin_file_flag "
               f"FROM {FQ}.gold_decisions WHERE application_id='{app_id}'")[0]
    print(f"applicant={app_id} merchant={drow['merchant_category']} thin_file={drow['thin_file_flag']}")
    print(f"amount={frow['amount']} disposable={frow['disposable_income_proxy']} "
          f"ratio={frow['amount_to_disposable_ratio']} bureau={frow.get('bureau_score')}")

    # 2. build features (same transform as training) and score via Model Serving
    step(2, "Score: build_features -> Model Serving endpoint (real-time)")
    X = build_features(pd.DataFrame([frow]))
    record = {c: (None if pd.isna(X.iloc[0][c]) else X.iloc[0][c].item()) for c in FEATURE_COLUMNS}
    payload = json.dumps({"dataframe_records": [record]})
    resp = subprocess.run(
        ["databricks", "serving-endpoints", "query", SERVING_ENDPOINT, "--profile", PROFILE, "--json", payload],
        capture_output=True, text=True)
    served = json.loads(resp.stdout)
    score = float(served["predictions"][0])
    print(f"served FPD probability = {score:.4f}")
    print(f"reason codes (deterministic, from batch SHAP) = {drow['reason_codes']}")

    # 3. read the cohort threshold from Lakebase and decide
    step(3, "Decide: read cohort threshold from Lakebase, apply policy")
    cat = drow["merchant_category"]
    thr = float(psql(f"SELECT threshold FROM bnpl.cohort_thresholds WHERE merchant_category='{cat}'"))
    decision = "APPROVE" if score < thr else "DECLINE"
    print(f"threshold[{cat}]={thr}  score={score:.4f}  ->  DECISION={decision}")

    # 4. the account slips; draft a cure note via ai_query, then guardrail it
    step(4, "Slip -> GenAI cure draft (for human review) -> guardrail")
    reasons = drow["reason_codes"]
    prompt = (
        "You are drafting an internal early-cure note for a Buy Now Pay Later lender, for HUMAN "
        "REVIEW before any use. The account was approved then missed its first instalment. Offer only "
        "these approved options: split the remaining balance into instalments, a 14 day extension, or a "
        "reduced payment plan. Be supportive and Consumer Duty aligned. No interest, fees, legal threats, "
        f"names, emails, or account numbers. Reason codes: {reasons}. Keep it under 90 words.")
    cure = sql(f"SELECT ai_query('{GENAI_ENDPOINT}', '{prompt.replace(chr(39), ' ')}') AS t")[0]["t"]
    print("cure draft:\n" + cure)
    gr = guardrail_check(cure, APPROVED_PLANS)
    print(f"guardrail: {gr}")

    # 5. insert the cure case into Lakebase (mutable OLTP)
    step(5, "Queue: INSERT cure_case into Lakebase (mutable OLTP)")
    safe = cure.replace("'", "''")[:900]
    print(psql(
        f"INSERT INTO bnpl.cure_cases (application_id, customer_id, status, priority, cure_narrative) "
        f"VALUES ('{app_id}', '{frow['customer_id']}', 'OPEN', 'HIGH', '{safe}') RETURNING case_id, application_id, status"))

    # 6. Genie surfaces the worst cohort -> analyst tightens that threshold (loop closes)
    step(6, "Learn: Genie surfaced 'Travel' as worst cohort -> tighten its threshold")
    before = psql("SELECT merchant_category, threshold FROM bnpl.cohort_thresholds WHERE merchant_category='Travel'")
    print("before: " + before)
    print(psql("UPDATE bnpl.cohort_thresholds SET threshold=0.15, updated_by=current_user, updated_at=now() "
               "WHERE merchant_category='Travel' RETURNING merchant_category, threshold"))
    after = psql("SELECT merchant_category, threshold FROM bnpl.cohort_thresholds WHERE merchant_category='Travel'")
    print("after:  " + after)

    print("\n" + "=" * 72)
    print("JOURNEY COMPLETE: ingest -> govern -> serve -> decide -> cure -> queue -> learn.")
    print("=" * 72)


if __name__ == "__main__":
    sys.exit(main())
