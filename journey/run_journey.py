"""End-to-end journey (the evidence spine).

Walks ONE applicant through the whole integrated loop, logging every step:

  scored decision (served from Lakebase, OLTP latency)
  ->  cohort threshold (Lakebase)  ->  APPROVE/DECLINE
  ->  account slips (first-payment default)  ->  ai_query cure draft
  ->  guardrail check  ->  INSERT cure_case (Lakebase)
  ->  Genie surfaced the worst cohort  ->  UPDATE cohort_threshold (Lakebase)
  ->  re-read threshold to show the loop closed.

The FPD model (UC-registered `bnpl_fpd_samk.demo.fpd_model`) produces the score;
it is materialised to gold_decisions and synced to Lakebase `public.decisions`,
which is the low-latency serving path the console reads. Reuses data/guardrail.
Run from the repo root:  PYTHONPATH=. python3 journey/run_journey.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

from config import PROFILE, CATALOG, SCHEMA, GENAI_ENDPOINT, LAKEBASE_PROJECT
from data.guardrail import guardrail_check

FQ = f"{CATALOG}.{SCHEMA}"
APPROVED_PLANS = ["split", "instalments", "14 day extension", "14-day extension",
                  "reduced payment plan", "reduced plan"]
ENV = dict(os.environ); ENV["PATH"] = "/opt/homebrew/opt/libpq/bin:" + ENV.get("PATH", "")


def step(n, title):
    print(f"\n{'=' * 74}\nSTEP {n}: {title}\n{'=' * 74}")


def sql(query):
    out = subprocess.run(
        ["databricks", "experimental", "aitools", "tools", "query", query, "--profile", PROFILE, "-o", "json"],
        capture_output=True, text=True)
    try:
        return json.loads(out.stdout)
    except Exception:
        print(out.stdout, out.stderr); return []


_BANNER = ("Connecting to", "Project:", "Branch:", "Endpoint:")


def psql(*args):
    base = ["databricks", "psql", "--project", LAKEBASE_PROJECT, "--profile", PROFILE, "--"]
    out = subprocess.run(base + list(args), capture_output=True, text=True, env=ENV)
    return "\n".join(l for l in (out.stdout + out.stderr).splitlines()
                     if l.strip() and not l.startswith(_BANNER))


def main():
    print("BNPL COLD-START AFFORDABILITY — END-TO-END JOURNEY")

    # 1. pick an approved-then-slipped Travel applicant from the synced decisions (Lakebase)
    step(1, "Serve: read a scored decision from Lakebase (public.decisions)")
    pick = psql("-t", "-A", "-F", "|", "-c",
                "SELECT application_id, merchant_category, ROUND(score::numeric,4), reason_codes "
                "FROM public.decisions WHERE decision='APPROVE' AND fpd_actual=1 "
                "AND merchant_category='Travel' ORDER BY score DESC LIMIT 1")
    app_id, cat, score, reasons = pick.split("|", 3)
    score = float(score)
    print(f"applicant={app_id}  merchant={cat}  score={score}")
    print(f"reason codes (deterministic, model SHAP): {reasons}")

    # 2. serving latency: warm decision lookup by key (second query = connection already open)
    step(2, "Serving latency: warm Lakebase decision lookup by application_id")
    print(psql("-c", "\\timing on",
               "-c", f"SELECT 1 FROM public.decisions WHERE application_id='{app_id}'",
               "-c", f"SELECT application_id, ROUND(score::numeric,4) AS score, decision "
                     f"FROM public.decisions WHERE application_id='{app_id}'"))

    # 3. read the cohort threshold from Lakebase and decide
    step(3, "Decide: read cohort threshold from Lakebase, apply policy")
    thr = float(psql("-t", "-A", "-c",
                     f"SELECT threshold FROM bnpl.cohort_thresholds WHERE merchant_category='{cat}'"))
    decision = "APPROVE" if score < thr else "DECLINE"
    print(f"threshold[{cat}]={thr}  score={score}  ->  DECISION={decision}")

    # 4. account slips; draft a cure note via ai_query, then guardrail it
    step(4, "Slip -> GenAI cure draft (for human review) -> guardrail")
    prompt = (
        "You are drafting an internal early-cure note for a Buy Now Pay Later lender, for HUMAN "
        "REVIEW before any use. The account was approved then missed its first instalment. Offer only "
        "these approved options: split the remaining balance into instalments, a 14 day extension, or a "
        "reduced payment plan. Be supportive and Consumer Duty aligned. No interest, fees, legal threats, "
        f"names, emails, or account numbers. Reason codes: {reasons}. Keep it under 80 words.")
    cure = sql(f"SELECT ai_query('{GENAI_ENDPOINT}', '{prompt}') AS t")[0]["t"]
    print("cure draft:\n" + cure)
    print(f"guardrail: {guardrail_check(cure, APPROVED_PLANS)}")

    # 5. insert the cure case into Lakebase (mutable OLTP)
    step(5, "Queue: INSERT cure_case into Lakebase (mutable OLTP)")
    safe = cure.replace("'", "''")[:900]
    print(psql("-c",
               f"INSERT INTO bnpl.cure_cases (application_id, status, priority, cure_narrative) "
               f"VALUES ('{app_id}', 'OPEN', 'HIGH', '{safe}') "
               f"RETURNING case_id, application_id, status, priority"))

    # 6. Genie surfaced the worst cohort -> analyst tightens that threshold (loop closes)
    step(6, "Learn: Genie surfaced 'Travel' as worst cohort (7.36%) -> tighten threshold")
    print("before: " + psql("-t", "-A", "-c",
                            "SELECT merchant_category||' '||threshold FROM bnpl.cohort_thresholds WHERE merchant_category='Travel'"))
    print(psql("-c", "UPDATE bnpl.cohort_thresholds SET threshold=0.15, updated_by=current_user, "
                     "updated_at=now() WHERE merchant_category='Travel' RETURNING merchant_category, threshold"))
    print("after:  " + psql("-t", "-A", "-c",
                            "SELECT merchant_category||' '||threshold FROM bnpl.cohort_thresholds WHERE merchant_category='Travel'"))

    print(f"\n{'=' * 74}")
    print("JOURNEY COMPLETE: serve -> decide -> slip -> cure -> queue -> learn -> re-threshold.")
    print("=" * 74)


if __name__ == "__main__":
    sys.exit(main())
