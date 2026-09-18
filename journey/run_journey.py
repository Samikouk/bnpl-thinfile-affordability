"""End-to-end journey (the evidence spine).

Walks ONE applicant through the integrated loop:

  historical APPROVE in Lakebase (why the account could slip)
  ->  first-payment default
  ->  ai_query cure draft + guardrail
  ->  INSERT cure_case
  ->  Genie-surfaced worst cohort (Travel)
  ->  UPDATE cohort_thresholds
  ->  re-apply operational policy (score vs new threshold) so the loop closes.

Does not re-label the historical checkout in the middle of the slip story.
SQL literals are escaped; application_id is validated. Reuses data.guardrail
and data.policy.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

from config import PROFILE, GENAI_ENDPOINT, LAKEBASE_PROJECT
from data.guardrail import guardrail_check
from data.policy import TIGHTENED_TRAVEL_THRESHOLD, decide
APPROVED_PLANS = ["split", "instalments", "14 day extension", "14-day extension",
                  "reduced payment plan", "reduced plan"]
ENV = dict(os.environ); ENV["PATH"] = "/opt/homebrew/opt/libpq/bin:" + ENV.get("PATH", "")
_APP_ID_RE = re.compile(r"^A\d+$")
_BANNER = ("Connecting to", "Project:", "Branch:", "Endpoint:")


def step(n, title):
    print(f"\n{'=' * 74}\nSTEP {n}: {title}\n{'=' * 74}")


def sql_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def sql(query: str):
    out = subprocess.run(
        ["databricks", "experimental", "aitools", "tools", "query", query, "--profile", PROFILE, "-o", "json"],
        capture_output=True, text=True)
    try:
        return json.loads(out.stdout)
    except Exception:
        print(out.stdout, out.stderr); return []


def psql(*args):
    base = ["databricks", "psql", "--project", LAKEBASE_PROJECT, "--profile", PROFILE, "--"]
    out = subprocess.run(base + list(args), capture_output=True, text=True, env=ENV)
    return "\n".join(l for l in (out.stdout + out.stderr).splitlines()
                     if l.strip() and not l.startswith(_BANNER))


def require_app_id(app_id: str) -> str:
    app_id = app_id.strip()
    if not _APP_ID_RE.match(app_id):
        raise ValueError(f"unexpected application_id: {app_id!r}")
    return app_id


def main():
    print("BNPL COLD-START AFFORDABILITY — END-TO-END JOURNEY")

    step(1, "Serve: historical APPROVE that later slipped (Lakebase public.decisions)")
    preferred = psql("-t", "-A", "-F", "|", "-c",
                "SELECT d.application_id, d.merchant_category, ROUND(d.score::numeric,4), "
                "d.decision, d.reason_codes, t.threshold "
                "FROM public.decisions d "
                "JOIN bnpl.cohort_thresholds t ON t.merchant_category = d.merchant_category "
                "WHERE d.fpd_actual = 1 AND d.merchant_category = 'Travel' "
                "AND d.decision = 'APPROVE' "
                "AND d.score < t.threshold "
                "AND d.score >= 0.15 "
                "ORDER BY d.score DESC LIMIT 1")
    pick = preferred.strip()
    if pick.count("|") < 5:
        print("no borderline row under the current cohort cut; falling back to an historical APPROVE (85% snapshot)")
        pick = psql("-t", "-A", "-F", "|", "-c",
                    "SELECT d.application_id, d.merchant_category, ROUND(d.score::numeric,4), "
                    "d.decision, d.reason_codes, t.threshold "
                    "FROM public.decisions d "
                    "JOIN bnpl.cohort_thresholds t ON t.merchant_category = d.merchant_category "
                    "WHERE d.fpd_actual = 1 AND d.merchant_category = 'Travel' "
                    "AND d.decision = 'APPROVE' "
                    "AND d.score >= 0.15 "
                    "ORDER BY d.score ASC LIMIT 1").strip()
    parts = pick.strip().split("|")
    if len(parts) < 6:
        raise SystemExit(f"no borderline Travel FPD row in (0.15, current threshold]: {pick!r}")
    app_id, cat, score_s, historical, reasons, thr_s = (p.strip() for p in parts[:6])
    app_id = require_app_id(app_id)
    score = float(score_s)
    historical_thr = float(thr_s)
    print(f"applicant={app_id}  merchant={cat}  score={score}")
    print(f"historical decision={historical}  threshold_then={historical_thr}  (kept as history)")
    print(f"reason codes (deterministic, model SHAP): {reasons}")

    step(2, "Serving latency: warm Lakebase decision lookup by application_id")
    aid = sql_literal(app_id)
    print(psql("-c", "\\timing on",
               "-c", f"SELECT 1 FROM public.decisions WHERE application_id={aid}",
               "-c", f"SELECT application_id, ROUND(score::numeric,4) AS score, decision "
                     f"FROM public.decisions WHERE application_id={aid}"))

    step(3, "Slip is on the historical APPROVE — do not re-decide the original checkout")
    print(f"account slipped (fpd_actual=1) after historical {historical} at threshold {historical_thr}.")
    print("Policy is re-applied only after the analyst write-back (step 6).")

    step(4, "Slip -> GenAI cure draft (for human review) -> guardrail")
    prompt = (
        "You are drafting an internal early-cure note for a Buy Now Pay Later lender, for HUMAN "
        "REVIEW before any use. The account was approved then missed its first instalment. Offer only "
        "these approved options: split the remaining balance into instalments, a 14 day extension, or a "
        "reduced payment plan. Be supportive and Consumer Duty aligned. No interest, fees, legal threats, "
        f"names, emails, or account numbers. Reason codes: {reasons}. Keep it under 80 words."
    )
    prompt_sql = sql_literal(prompt)
    endpoint_sql = sql_literal(GENAI_ENDPOINT)
    rows = sql(f"SELECT ai_query({endpoint_sql}, {prompt_sql}) AS t")
    cure = rows[0]["t"] if rows else ""
    print("cure draft:\n" + cure)
    print(f"guardrail: {guardrail_check(cure, APPROVED_PLANS)}")

    step(5, "Queue: INSERT cure_case into Lakebase (mutable OLTP)")
    narrative = sql_literal(cure[:900])
    print(psql("-c",
               f"INSERT INTO bnpl.cure_cases (application_id, status, priority, cure_narrative) "
               f"VALUES ({aid}, 'OPEN', 'HIGH', {narrative}) "
               f"RETURNING case_id, application_id, status, priority"))

    step(6, "Learn: Genie surfaced Travel -> tighten threshold -> re-apply policy")
    print("before: " + psql("-t", "-A", "-c",
                            "SELECT merchant_category||' '||threshold FROM bnpl.cohort_thresholds WHERE merchant_category='Travel'"))
    new_thr = TIGHTENED_TRAVEL_THRESHOLD
    print(psql("-c",
               "UPDATE bnpl.cohort_thresholds SET threshold=" + str(float(new_thr)) + ", "
               "updated_by=current_user, updated_at=now() "
               "WHERE merchant_category='Travel' RETURNING merchant_category, threshold"))
    print("after:  " + psql("-t", "-A", "-c",
                            "SELECT merchant_category||' '||threshold FROM bnpl.cohort_thresholds WHERE merchant_category='Travel'"))
    redecided = decide(score, new_thr)
    print(f"re-apply policy: score={score}  new_threshold[{cat}]={new_thr}  ->  DECISION={redecided}")
    print("historical Lakebase row is unchanged; the next checkout for this cohort uses the new cut.")

    print(f"\n{'=' * 74}")
    print("JOURNEY COMPLETE: serve -> slip -> cure -> queue -> learn -> re-threshold -> re-decide.")
    print("=" * 74)


if __name__ == "__main__":
    sys.exit(main())
