# Cold-Start Affordability for Pay-in-4 BNPL — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an integrated, end-to-end Databricks data journey that scores first-payment-default (FPD) risk for thin-file Pay-in-4 BNPL customers at checkout, closes a cure-feedback loop, and commits execution evidence as text at every stage.

**Architecture:** One synthetic dataset flows Lakeflow (Declarative Pipelines + Auto Loader) -> Unity Catalog governance -> ML (MLflow + Model Serving, deterministic reason codes) + GenAI (`ai_query` affordability narrative) -> Lakebase (mutable early-cure case queue + cohort thresholds) -> Genie (NL investigation that drives a threshold action) -> AppKit App (Approval & Early-Cure Console). A single end-to-end journey script ties the stages together and is the primary evidence artifact.

**Tech Stack:** Databricks (`e2-demo-field-eng`), Python 3.10+, PySpark, MLflow, LightGBM/sklearn HistGBT, SHAP, Databricks Model Serving, `ai_query` (`databricks-claude-haiku-4-5`), Lakebase (Public Preview `databricks database` CLI surface), Genie Conversation API, Databricks Apps (AppKit, Node/TypeScript/React), Google Slides for the deck.

**Spec:** `docs/superpowers/specs/2026-09-16-bnpl-thinfile-affordability-design.md` (read it alongside this plan; the spec carries the problem, personas, KPIs, data design, and evidence inventory).

## Global Constraints

- **Workspace/profile:** `e2-demo-field-eng`. Never modify or delete any pre-existing shared resource.
- **Namespace:** all Unity Catalog objects under schema `bnpl_fpd_samk` in a catalog the user owns (confirm in Task 0). All created resources carry the prefix `bnpl-fpd-samk` (warehouse, pipeline, model, endpoint, Lakebase instance, Genie space, app).
- **Data:** fully synthetic, deterministic seeds, no real customer data. PII columns (`full_name`, `email`, `dob`) exist only to demonstrate UC masking.
- **Features:** point-in-time correct only (available at checkout). No post-decision features. See spec Section 5.
- **GenAI:** single `ai_query` call, endpoint `databricks-claude-haiku-4-5` (swappable), PII tokenised before the call, output constrained to approved payment-plan options, guardrail check after. Reason codes come from the model (SHAP), never the LLM.
- **Evidence:** every task commits its output as text under `evidence/<stage>/`. No screenshot is load-bearing.
- **Latency claims:** measured p50/p99 on a warmed endpoint only, marked demo-vs-production.
- **Volatile Databricks syntax:** each platform task names the skill to consult for current CLI/SQL. Do not hardcode commands that may have drifted; pull them at execution.

---

## File Structure

```
data/generate_synthetic.py       Deterministic synthetic data generator (pure Python/pandas)
data/labels.py                    Latent-affordability -> FPD label function (pure, unit-tested)
tests/test_generate_synthetic.py  Determinism, base FPD rate, thin-file share, leakage-safety
pipelines/bnpl_fpd_pipeline.py    Lakeflow Declarative Pipeline (bronze/silver/gold + expectations)
notebooks/00_workspace_prep.py    Catalog/schema/volume/warehouse verification (outputs committed)
notebooks/01_land_data.py         Write synthetic events to the ingest volume
notebooks/02_governance.sql       UC masks, row filter, tags, lineage + two-principal evidence
notebooks/03_train_model.py       Feature build, train, MLflow log, UC register
notebooks/04_serve_reason.py      Serving deploy, SHAP reason codes, matched-rate 2x2, latency
notebooks/05_genai_narrative.py   ai_query narrative + guardrail check
notebooks/06_lakebase_setup.py    Lakebase instance, synced decisions, cure_cases, cohort_thresholds
lakebase/schema.sql               Postgres DDL for mutable tables
notebooks/07_genie_setup.py       Genie space config + Conversation API transcript capture
journey/run_journey.py            End-to-end journey script (the evidence spine)
app/                              AppKit app (Approval & Early-Cure Console)
evidence/                         Committed run outputs, query results, transcripts, metrics
deck/DECK_LINK.md                 Google Slides shareable link + speaker notes source
```

---

### Task 0: Workspace prep and namespace

**Files:**
- Create: `notebooks/00_workspace_prep.py`
- Create: `evidence/00_prep/` (committed outputs)

**Interfaces:**
- Produces: catalog name `CATALOG`, schema `bnpl_fpd_samk`, volume path `/Volumes/<CATALOG>/bnpl_fpd_samk/raw`, warehouse id `WH_ID`. All later tasks consume these.

- [ ] **Step 1:** Consult `databricks-core` and `databricks-unity-catalog` skills for current CLI/SQL. Identify a catalog the user can create schemas in (try `main`; else a users/sandbox catalog). Run `SELECT current_metastore(), current_catalog();` and `SHOW GRANTS`.
- [ ] **Step 2:** `CREATE SCHEMA IF NOT EXISTS <CATALOG>.bnpl_fpd_samk;` and `CREATE VOLUME IF NOT EXISTS <CATALOG>.bnpl_fpd_samk.raw;`
- [ ] **Step 3:** Create a small serverless SQL warehouse named `bnpl-fpd-samk-wh` (consult `databricks-execution-compute`). Capture its id.
- [ ] **Step 4 (evidence):** Commit the SQL outputs (schema created, volume created, warehouse id, grants) to `evidence/00_prep/prep_outputs.md`.
- [ ] **Step 5:** Commit.

---

### Task 1: Synthetic data generator (TDD)

**Files:**
- Create: `data/labels.py`, `data/generate_synthetic.py`
- Test: `tests/test_generate_synthetic.py`

**Interfaces:**
- Produces: `generate(seed:int, n_customers:int, n_apps:int) -> dict[str, pandas.DataFrame]` with keys `customers, applications, open_banking, device_signals, repayments`. `fpd_label(features:dict, rng) -> int`.

- [ ] **Step 1: Write failing tests** in `tests/test_generate_synthetic.py`:

```python
import pandas as pd
from data.generate_synthetic import generate

def test_deterministic():
    a = generate(seed=7, n_customers=2000, n_apps=5000)
    b = generate(seed=7, n_customers=2000, n_apps=5000)
    pd.testing.assert_frame_equal(a["applications"], b["applications"])

def test_fpd_base_rate_near_5_5pct():
    d = generate(seed=7, n_customers=5000, n_apps=12000)
    rep = d["repayments"]
    first = rep[rep.installment_no == 1]
    fpd_rate = 1 - first.paid_flag.mean()
    assert 0.045 <= fpd_rate <= 0.070, fpd_rate

def test_thin_file_share_and_missing_bureau():
    d = generate(seed=7, n_customers=5000, n_apps=12000)
    cust = d["customers"]
    thin_share = cust.thin_file_flag.mean()
    assert 0.40 <= thin_share <= 0.60
    # thin-file customers must have NULL bureau_score
    assert cust[cust.thin_file_flag == 1].bureau_score.isna().mean() > 0.95

def test_no_leakage_columns_in_features():
    # feature frame must not contain any post-decision or outcome column
    d = generate(seed=7, n_customers=2000, n_apps=5000)
    feats = d["applications"].columns
    banned = {"paid_flag", "paid_date", "fpd", "installment_no"}
    assert not (banned & set(feats))
```

- [ ] **Step 2: Run to verify fail** — `pytest tests/test_generate_synthetic.py -v` -> FAIL (module missing).
- [ ] **Step 3: Implement `data/labels.py`** — latent affordability score as a weighted sum (disposable_income_proxy negative, inflow_regularity negative, device_risk positive, applications_last_24h positive, email_age negative, amount/disposable ratio positive) plus Gaussian noise with **wider variance for thin-file**; FPD = 1 above a seed-calibrated threshold targeting ~5.5%.
- [ ] **Step 4: Implement `data/generate_synthetic.py`** — build the five frames with the spec Section 5 fields; `applications` holds only checkout-available features; `repayments` derives the first-installment paid_flag from `fpd_label`. Calibrate threshold to hit the base rate.
- [ ] **Step 5: Run to verify pass** — `pytest tests/test_generate_synthetic.py -v` -> PASS.
- [ ] **Step 6 (evidence):** Write `data/print_stats.py` that prints FPD rate, thin-file share, missing-bureau share, feature list; commit its stdout to `evidence/01_data/data_stats.txt`.
- [ ] **Step 7: Commit.**

---

### Task 2: Land synthetic events to the volume

**Files:** Create `notebooks/01_land_data.py`. Evidence: `evidence/02_land/`

**Interfaces:** Produces JSON/CSV files at `/Volumes/<CATALOG>/bnpl_fpd_samk/raw/{applications,customers,open_banking,device_signals,repayments}/`.

- [ ] **Step 1:** Run the generator (`seed=7`), write each frame to the volume as multiple JSON files (to make Auto Loader meaningful).
- [ ] **Step 2 (evidence):** `dbutils.fs.ls` the volume paths; commit the listing + per-source row counts to `evidence/02_land/landing_manifest.md`.
- [ ] **Step 3: Commit.**

---

### Task 3: Lakeflow Declarative Pipeline (bronze/silver/gold)

**Files:** Create `pipelines/bnpl_fpd_pipeline.py`. Evidence: `evidence/03_lakeflow/`

**Interfaces:** Produces gold tables `<CATALOG>.bnpl_fpd_samk.{gold_features, gold_decisions_base, gold_repayments}`.

- [ ] **Step 1:** Consult `databricks-pipelines` (Lakeflow Declarative Pipelines) skill for current decorator/syntax.
- [ ] **Step 2:** Bronze: Auto Loader streams from each raw volume path. Silver: typed, cleaned, joined. Gold: `gold_features` (one point-in-time row per application, checkout-available features only), `gold_repayments`, and a `gold_decisions_base` scaffold.
- [ ] **Step 3:** Add expectations: non-null `customer_id`, `amount` in [50, 2000], `disposable_income_proxy` non-null. Use expect-or-drop where appropriate.
- [ ] **Step 4:** Create and run the pipeline (prefix `bnpl-fpd-samk`).
- [ ] **Step 5 (evidence):** Query the pipeline event log for run state and expectation metrics; commit the result table + gold row counts to `evidence/03_lakeflow/pipeline_run.md`.
- [ ] **Step 6: Commit.**

---

### Task 4: Unity Catalog governance

**Files:** Create `notebooks/02_governance.sql`. Evidence: `evidence/04_uc/`

**Interfaces:** Applies mask/filter to gold; produces committed two-principal evidence.

- [ ] **Step 1:** Consult `databricks-unity-catalog` skill for current mask/row-filter/tag/lineage syntax.
- [ ] **Step 2:** Create a column mask on `full_name`, `email`, `dob`; a row filter by `region`; set tags on `disposable_income_proxy` and `bureau_score` (affordability-sensitive).
- [ ] **Step 3 (evidence):** `DESCRIBE` the mask/filter functions; run the **same SELECT twice** (once as owner/unmasked, once simulating a non-privileged principal or via a masked view) and commit both outputs; capture one `system.access.table_lineage` row. Write all to `evidence/04_uc/governance_evidence.md`.
- [ ] **Step 4: Commit.**

---

### Task 5: ML — train, log, register (TDD on feature logic)

**Files:** Create `notebooks/03_train_model.py`, `data/features.py`. Test: `tests/test_features.py`. Evidence: `evidence/05_ml/`

**Interfaces:** Produces UC-registered model `<CATALOG>.bnpl_fpd_samk.fpd_model`, and `build_features(df) -> X` used by both training and the journey script (single source of truth to prevent train/serve skew).

- [ ] **Step 1: Write failing test** for `build_features` — asserts output columns exactly match the checkout-available feature list and contains no banned/outcome column; asserts NULL bureau handling (imputed flag column added, no leakage).
- [ ] **Step 2: Run -> FAIL.**
- [ ] **Step 3:** Implement `data/features.py::build_features` (shared by train and serve).
- [ ] **Step 4: Run -> PASS.**
- [ ] **Step 5:** In `notebooks/03_train_model.py`: read `gold_features` + first-installment labels, train/holdout split by time, train HistGBT/LightGBM, log AUC, PR-AUC, calibration, confusion at operating threshold to MLflow; register to UC.
- [ ] **Step 6 (evidence):** Commit the MLflow metrics table + registered model version + feature-importance summary to `evidence/05_ml/model_metrics.md`.
- [ ] **Step 7: Commit.**

---

### Task 6: Serving, reason codes, matched-rate 2x2, latency

**Files:** Create `notebooks/04_serve_reason.py`, `data/reason_codes.py`. Test: `tests/test_reason_codes.py`. Evidence: `evidence/06_serving/`

**Interfaces:** Produces a warm Model Serving endpoint `bnpl-fpd-samk-endpoint`; `reason_codes(shap_row) -> list[str]` (deterministic).

- [ ] **Step 1: Write failing test** for `reason_codes` — given a SHAP contribution vector, returns the fixed human-readable adverse-action strings for the top contributors, deterministically.
- [ ] **Step 2: Run -> FAIL.** **Step 3:** Implement `data/reason_codes.py`. **Step 4: Run -> PASS.**
- [ ] **Step 5:** Consult `databricks-model-serving` skill. Deploy the registered model to a serving endpoint, set min provisioned concurrency 1 (warm). Invoke with a sample applicant; return score + reason codes JSON.
- [ ] **Step 6:** Compute the **matched-approval-rate 2x2**: baseline rules/bureau policy vs model policy at the same approval rate; report FPD/loss delta.
- [ ] **Step 7 (evidence):** Commit serving invocation JSON, the 2x2 table, and measured p50/p99 latency (warm) to `evidence/06_serving/serving_evidence.md`. Mark demo-vs-prod on latency.
- [ ] **Step 8: Commit.**

---

### Task 7: GenAI affordability narrative + guardrail

**Files:** Create `notebooks/05_genai_narrative.py`, `data/guardrail.py`. Test: `tests/test_guardrail.py`. Evidence: `evidence/07_genai/`

**Interfaces:** `guardrail_check(text, allowed_plans) -> {ok:bool, violations:list}`.

- [ ] **Step 1: Write failing test** for `guardrail_check` — flags any payment term not in the approved set; passes clean text.
- [ ] **Step 2: Run -> FAIL.** **Step 3:** Implement `data/guardrail.py`. **Step 4: Run -> PASS.**
- [ ] **Step 5:** Consult `databricks-ai-functions` skill. Build one `ai_query` call to `databricks-claude-haiku-4-5` with tokenised case context (no raw PII) + deterministic reason codes; produce an affordability narrative + cure-note draft for human review against an approved-template prompt.
- [ ] **Step 6 (evidence):** Commit the `ai_query` output text + the guardrail-check result to `evidence/07_genai/genai_output.md`.
- [ ] **Step 7: Commit.**

---

### Task 8: Lakebase operational serving

**Files:** Create `notebooks/06_lakebase_setup.py`, `lakebase/schema.sql`. Evidence: `evidence/08_lakebase/`

**Interfaces:** Produces Lakebase instance `bnpl-fpd-samk-pg` with tables `decisions` (synced), `cure_cases` (mutable), `cohort_thresholds` (mutable). Later tasks (App, journey) read/write these.

- [ ] **Step 1:** Consult `databricks-lakebase` skill for the current Public Preview `databricks database` CLI/SQL surface.
- [ ] **Step 2:** Create the Lakebase database instance (prefix `bnpl-fpd-samk`). Register the UC catalog for it.
- [ ] **Step 3:** Create a **synced table** `decisions` from `gold_decisions` (scored). Create mutable `cure_cases` and `cohort_thresholds` via `lakebase/schema.sql`.
- [ ] **Step 4 (evidence):** SELECT a synced `decisions` row; INSERT a `cure_case`, UPDATE its status, SELECT before/after; SELECT a `cohort_thresholds` row. Commit outputs + a measured query latency line to `evidence/08_lakebase/lakebase_evidence.md`.
- [ ] **Step 5: Commit.**

---

### Task 9: Genie space + Conversation API transcript

**Files:** Create `notebooks/07_genie_setup.py`. Evidence: `evidence/09_genie/`

**Interfaces:** Produces Genie space id `GENIE_SPACE`; a committed transcript.

- [ ] **Step 1:** Consult `databricks-genie` skill. Create a Genie space over gold (`gold_decisions`, cohorts, `gold_repayments`) with curated metadata + sample questions.
- [ ] **Step 2:** Via the Conversation API, ask: "Which merchant category has the highest first-payment-default rate this month, and how many approvals did it drive?" Capture question -> generated SQL -> result table.
- [ ] **Step 3 (evidence):** Commit the transcript as text to `evidence/09_genie/genie_transcript.md`. Note the recommended `cohort_thresholds` action the answer implies.
- [ ] **Step 4: Commit.**

---

### Task 10: End-to-end journey script (the evidence spine)

**Files:** Create `journey/run_journey.py`. Evidence: `evidence/10_journey/`

**Interfaces:** Consumes serving endpoint, Lakebase tables, `ai_query`, Genie; reuses `build_features`, `reason_codes`, `guardrail_check` (no duplicate logic).

- [ ] **Step 1:** Orchestrate one applicant through: build features -> serving score + reason codes -> approve/decline vs current `cohort_thresholds` -> simulate first-installment slip -> `ai_query` cure draft -> guardrail check -> INSERT `cure_case` in Lakebase -> Genie surfaces the cohort -> UPDATE `cohort_thresholds` -> re-score reflects the new threshold. Log every step with clear labels.
- [ ] **Step 2 (evidence):** Run it; commit the full stdout log to `evidence/10_journey/journey_log.txt`. This is the primary integration proof.
- [ ] **Step 3: Commit.**

---

### Task 11: AppKit App — Approval & Early-Cure Console

**Files:** Create `app/` (AppKit scaffold). Evidence: `evidence/11_app/`

**Interfaces:** Reads/writes Lakebase `decisions`, `cure_cases`, `cohort_thresholds`.

- [ ] **Step 1:** Consult `databricks-apps` (AppKit) and `databricks-app-design` skills. Scaffold the app.
- [ ] **Step 2:** Screens: decision queue (score + reason codes), case detail (GenAI narrative + disposition controls, writes `cure_cases`), cohort view (Genie answer + threshold-adjust action, writes `cohort_thresholds`), KPI header. Include loading/empty/error states; show the generated SQL/source for the Genie surface (AI-result trust).
- [ ] **Step 3 (evidence):** Commit the exact Lakebase queries the app issues + their returned rows (from a logged local run) to `evidence/11_app/app_data_access.md`. Deploy the app; record its URL. A screenshot is optional and never the evidence.
- [ ] **Step 4: Commit.**

---

### Task 12: Business deck (Google Slides)

**Files:** Create `deck/DECK_LINK.md` (link + speaker-notes source). Evidence: the link itself.

- [ ] **Step 1:** Consult `google-slides` skill. Build the deck per spec Section 10 (outcome-led, KPIs for exec + domain owner, closed-loop diagram, six-stage journey, the 2x2, ROI sensitivity model, governance posture, demo-vs-prod honesty slide, pilot design).
- [ ] **Step 2:** Set sharing to "Anyone with the link" as Viewer. Record the link in `deck/DECK_LINK.md`. Follow the user's writing rules (no em dashes, no negation-then-assert pattern, no banned phrases).
- [ ] **Step 3: Commit.**

---

### Task 13: README finalisation + submission checklist

**Files:** Modify `README.md`. Create `SUBMISSION.md`.

- [ ] **Step 1:** Update README status to complete; add an evidence index linking every `evidence/` artifact to its stage.
- [ ] **Step 2:** Write `SUBMISSION.md` mapping each submission requirement to its artifact (the six stages, the deck link, the repo, the conversation-ID note as optional).
- [ ] **Step 3:** Confirm the repo can be made public with synthetic data only (final scrub check).
- [ ] **Step 4: Commit.**

---

## Self-Review

**Spec coverage:** Lakeflow (T3), UC (T4), Lakebase (T8), ML (T5,T6), GenAI (T7), Genie (T9), App (T11), evidence spine (T10), deck (T12), synthetic data (T1,T2), novelty/closed-loop (T10 journey + T9 Genie action + T8 thresholds), KPIs/2x2 (T6), submission alignment (T13). All spec sections map to a task.

**Placeholder scan:** Platform tasks intentionally defer volatile CLI/SQL to the named skill at execution (an honesty choice against API drift), not a placeholder. Code tasks (T1, T5, T6, T7) carry real test code. No "TODO/handle edge cases" left.

**Type consistency:** `build_features` (T5) is reused by T6 and T10; `reason_codes` (T6) reused by T10; `guardrail_check` (T7) reused by T10. Names are consistent across tasks.
