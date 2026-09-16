# Cold-Start Affordability for Pay-in-4 BNPL

**End-to-end Databricks demo. Design spec.**
Date: 2026-09-16
Author: Sam Khanjar (built with an adversarial 4-role design panel: FinTech industry expert, Databricks SSA, customer exec, customer technical rep, plus a red-team critic)
Build target: `e2-demo-field-eng` (Step-0 entitlement gate passed 2026-09-16)

---

## 1. The problem (specific, one industry)

A Pay-in-4 Buy-Now-Pay-Later lender has to approve or decline a £150 to £500 installment plan **at checkout, in real time**, for a customer base that is **mostly thin-file**: little or no credit-bureau history, so a traditional FICO/bureau score either doesn't exist or is uninformative.

The lender is caught in a pincer:

- **Approve too loosely** and it eats first-payment defaults (FPD, the customer misses the very first installment, the strongest early signal of loss and never-pay), and it draws FCA Consumer Duty affordability scrutiny for lending without evidencing affordability.
- **Decline too hard** and it loses good thin-file customers, GMV, merchant relationships, and conversion.

Today the decision runs on static rules and stale bureau pulls. Neither reflects the thin-file customer's actual, current ability to pay.

**This is a cold-start affordability problem, not a generic credit-scoring problem.** That distinction is the whole point (see Section 2).

## 2. Why this is not a dbdemos clone (novelty)

The red-team critic's warning: a plain "predict default on a loan" build maps onto dbdemos `lakehouse-fsi-credit-decisioning` in about 30 seconds, and fails the novelty gate. Two elements make this unmistakably different:

1. **Cold-start with alternative data.** The model deliberately operates where a bureau score is absent. Roughly half of synthetic applicants have no bureau score at all. The signal comes from point-in-time alternative data (open-banking-style balance and salary-inflow cadence, disposable-income proxy, application velocity, device and email age), which is exactly what a real Pay-in-4 lender leans on and what generic credit scoring ignores.
2. **A closed feedback loop.** Score a no-bureau applicant, some approved accounts slip into FPD, GenAI drafts an affordability narrative and cure note for human review, an analyst dispositions the case in an operational queue, outcomes aggregate back to per-merchant-cohort FPD, Genie surfaces the worst cohort, and the analyst adjusts that cohort's approval threshold, which the scoring path then reads. The demo shows the loop closing, not just a one-shot prediction.

## 3. Submission alignment (how each requirement is met)

| Requirement | How this build meets it |
|---|---|
| Integrated journey, not siloed, across six stages | One dataset flows Lakeflow -> UC -> ML/GenAI -> Lakebase -> Genie -> App, tied together by a single end-to-end journey script (Section 8). |
| Lakeflow ingest (synthetic ok) | Declarative Pipelines + Auto Loader over a synthetic event volume. Not Lakeflow Connect (that is for real SaaS sources). |
| Unity Catalog govern | Column masks on PII, region row filter, tags on affordability-sensitive fields, lineage. |
| Lakebase operational serving | Mutable OLTP case queue and cohort-threshold table the App reads and writes, plus a synced read table. |
| ML or GenAI | Both. FPD model (MLflow, UC registry, Model Serving, deterministic reason codes) and a single `ai_query` GenAI affordability-narrative call. |
| Genie agent, natural language | Genie Space over the gold layer, with a Conversation-API transcript committed as text, embedded as the analyst investigation surface. |
| A Databricks App | "Approval and Early-Cure Console" over Lakebase. |
| Committed execution evidence readable as text | Per-stage text artifacts plus the journey-script log (Section 8). No screenshot is load-bearing. |
| Specific industry problem | Pay-in-4 BNPL thin-file affordability at checkout. |
| Not a dbdemos / internal rehash | Cold-start + closed loop (Section 2). |
| Synthetic data only, no customer data | Fully synthetic generator (Section 5). |
| Business deck for exec sponsor and domain owner | Section 10. |

## 4. Personas and KPIs

**Executive sponsor: VP Credit Risk / acting CFO.** Cares about money and regulatory exposure. Tracks:
- FPD rate (baseline illustrative 5.5%), and net credit loss (£/year).
- Approval rate (baseline illustrative 67%, must not fall below a floor).
- Customer LTV, and regulatory complaint/escalation count.
- The one closing artifact: a 2x2 proving lower loss at the **same** approval rate, so the story is a better trade-off, not a smaller book.

**Domain owner: Head of Collections / Credit Risk lead.** Cares about operating the thing. Tracks:
- Analyst hours saved per cured account.
- Reason-code explainability for adverse-action notices.
- Decision latency and cure success rate.

**Honesty rule for both:** synthetic labels prove the mechanism, not the buyer's portfolio number. ROI in the deck is a **sensitivity model** the buyer parameterises (Section 9), never a claimed result.

## 5. Synthetic data design

Fully synthetic, generated with reproducible seeds. Emphasis on realistic thin-file structure (the industry expert's key credibility test).

**Entities and raw event streams (land as JSON/CSV in a volume, ingested by Auto Loader):**
- `applications`: application_id, customer_id, ts, merchant_id, merchant_category, amount, channel, device_id, ip_hash.
- `customers`: customer_id, region, email_age_days, customer_tenure_days, thin_file_flag, bureau_score (NULL for ~50%), dob (PII), full_name (PII), email (PII).
- `open_banking`: customer_id, current_balance, avg_monthly_inflow, inflow_regularity_score, committed_outflows, disposable_income_proxy (inflow minus committed).
- `device_signals`: device_id, device_risk_score, applications_last_24h, applications_last_7d (network velocity).
- `repayments`: application_id, installment_no, due_date, paid_flag, paid_date. First installment drives the FPD label.

**Feature set (point-in-time correct, available at checkout only).** The technical rep's leakage traps are avoided by construction: no post-decision velocity, no future utilization, no bureau refresh after decision.

| Feature | Source | Checkout-available | Leakage-safe |
|---|---|---|---|
| amount | application | yes | yes |
| merchant_category | application | yes | yes |
| device_risk_score | device_signals | yes | yes |
| applications_last_24h / _7d | device_signals (pre-decision window) | yes | yes (window ends at decision ts) |
| email_age_days | customers | yes | yes |
| customer_tenure_days | customers | yes | yes |
| disposable_income_proxy | open_banking (consented) | yes | yes |
| inflow_regularity_score | open_banking | yes | yes |
| current_balance | open_banking | yes | yes |
| bureau_score | customers (NULL for ~50%) | yes when present | yes |
| prior_bnpl_ontime_rate | derived, returning customers only, NULL for new | yes | yes (uses only pre-decision history) |

**Label logic (FPD).** A latent affordability score is a weighted function of disposable_income_proxy (strong negative on FPD), inflow_regularity_score (negative), device_risk_score (positive), applications_last_24h (positive), email_age_days (negative), amount relative to disposable income (positive), plus Gaussian noise. Thin-file customers get wider noise variance (harder to predict, the cold-start reality). FPD = 1 when latent score crosses a threshold calibrated to a ~5.5% base rate. Deterministic given seed, so evidence reproduces.

**Volumes (demo scale):** ~50k customers, ~120k applications, repayments for approved accounts. Enough for a credible AUC and cohort slices, small enough to run in the time budget.

## 6. Architecture and the closed loop

```
 synthetic events (volume)
        |  Auto Loader
        v
 [Lakeflow Declarative Pipeline]  bronze -> silver -> gold  (expectations enforced)
        |                                   |
        |                                   +--> [Unity Catalog] masks, row filter, tags, lineage
        v
 [ML]  train FPD model -> MLflow -> UC registry -> Model Serving (warm) -> score + SHAP reason codes
        |
        v
 gold.scored_decisions ---- synced ----> [Lakebase Postgres]
                                            - decisions (read)
                                            - cure_cases (mutable OLTP)   <----> [Databricks App: Approval & Early-Cure Console]
                                            - cohort_thresholds (mutable) <----> analyst action
        ^                                                                          |
        |                                                                          v
        |                                            [GenAI ai_query] drafts affordability narrative / cure note (human review)
        |                                                                          |
        +---- threshold update feeds next scoring run <---- [Genie] "which merchant cohort drives FPD?" -> recommended threshold
```

The loop: score -> approve -> slip -> cure draft -> analyst disposition (Lakebase) -> cohort FPD aggregates -> Genie surfaces cohort -> threshold adjusted -> next score uses new threshold.

## 7. Stage specifications

### 7.1 Lakeflow (ingest)
- Declarative Pipeline reads the synthetic event volume with Auto Loader into bronze, cleans and joins to silver, builds gold feature and decision tables.
- Data-quality expectations (for example non-null customer_id, amount in valid range, disposable_income_proxy present when thin_file_flag).
- **Evidence:** pipeline event-log query result (states, rows written), expectation pass/fail counts, gold row counts. All as committed query-result text.

### 7.2 Unity Catalog (govern)
- Column mask on PII (full_name, email, dob) so a non-privileged principal sees masked values.
- Row filter by region.
- Tags on affordability-sensitive columns (disposable_income_proxy, bureau_score).
- Lineage captured from pipeline and model reads.
- **Evidence:** `DESCRIBE` showing mask/filter definitions, the **same SELECT run twice** (masked vs unmasked principal) with both outputs committed, one `system.access` lineage row.

### 7.3 ML (intelligence, part 1)
- Features from gold, point-in-time correct (Section 5). Train a gradient-boosted classifier (for example LightGBM or sklearn HistGBT) with a train/holdout split.
- Log to MLflow: AUC, PR-AUC, calibration, confusion at the operating threshold. Register the model in UC.
- Deploy to Model Serving. **Warm the endpoint** (min provisioned concurrency 1) before capturing latency, so cold start does not corrupt the number.
- **Deterministic reason codes**: SHAP top contributors mapped to fixed human-readable adverse-action reasons (for example "low disposable income relative to instalment", "high recent application velocity", "short email tenure"). Reason codes come from the model, never the LLM.
- **Matched-approval-rate evaluation**: compare the model policy against a baseline rules/bureau policy at the **same approval rate**, report loss delta. This is the exec's 2x2.
- **Evidence:** MLflow run metrics table, registered model version, a serving invocation returning score + reason-code JSON, the matched-approval-rate comparison table, a measured p50/p99 latency line.

### 7.4 GenAI (intelligence, part 2)
- A single `ai_query` call against a Claude endpoint (`databricks-claude-haiku-4-5` for speed, or `databricks-claude-sonnet-5` for quality). Input: tokenised case context (no raw PII) plus the model's deterministic reason codes. Output: an affordability narrative for the audit file and a cure-note draft **for human review**, against an approved-template instruction.
- **Guardrails:** PII tokenised before the call, output constrained to approved payment-plan options, a post-generation check that flags any term outside policy. Reframed from "compliant outreach" to "draft for human review".
- **Evidence:** the `ai_query` output text row and the guardrail-check output, committed.

### 7.5 Lakebase (operational serving)
- Lakebase Postgres instance (Public Preview `databricks database` surface).
- Tables:
  - `decisions` (read): synced from `gold.scored_decisions`. Fields: decision_id, customer_id, ts, amount, merchant_category, score, decision, reason_codes, threshold_used.
  - `cure_cases` (mutable OLTP): case_id, decision_id, status, assignee, priority, cure_narrative, disposition, created_at, updated_at. The App inserts and updates these.
  - `cohort_thresholds` (mutable): merchant_category, threshold, updated_by, updated_at. Analyst action writes here; the scoring path reads it.
- The mutable tables are the load-bearing justification: read-only online tables and feature serving physically cannot host this state. This is the SSA's verdict and it settles the "is Lakebase bolted on" question.
- **Evidence:** a SELECT of a synced `decisions` row, an UPDATE to a `cure_cases` row with the before/after state, a measured query latency line.

### 7.6 Genie (natural language)
- Genie Space over gold (decisions, cohorts, repayments), with curated table metadata and sample questions.
- Embedded as the analyst investigation surface: the demo question "which merchant category has the highest FPD rate this month, and how many approvals did it drive?" returns a cohort, which maps to a recommended `cohort_thresholds` change. Genie drives an action, it is not a side read path.
- **Evidence:** a Genie Conversation-API transcript committed as text (question, generated SQL, result table).

### 7.7 Databricks App (surface to the business)
- "Approval and Early-Cure Console" reading and writing Lakebase.
- Screens: decision queue with score and reason codes; case detail with the GenAI narrative draft and disposition controls; a cohort view that shows Genie's answer and the threshold-adjust action; a KPI header (FPD rate, approval rate, cures in progress).
- Built for text-native evidence: the App's data-access functions and the exact queries it issues are committed, and the journey script exercises the same code path and logs the outputs. A screenshot is a nice-to-have, never the evidence.
- Framework decision open (Section 12): FastAPI + minimal UI, or AppKit.

## 8. Evidence spine (the critic's kill-shot, pre-empted)

The App and Genie are visual, and the grader rejects screenshots. The centrepiece artifact is **one committed end-to-end journey script** whose logged output walks a single applicant through the whole loop:

`ingest sample -> build features -> score + reason codes -> approve/decline vs cohort threshold -> account slips to FPD -> GenAI cure draft -> case inserted in Lakebase -> Genie surfaces the cohort -> threshold updated -> re-score reflects new threshold`

That single log proves the six stages are integrated and that the loop closes, in text. Around it, each stage commits its own artifact.

**Evidence inventory (all committed as text in the repo):**

| Stage | Artifact | Format |
|---|---|---|
| Lakeflow | event-log + expectations + row counts | query result (md/csv) |
| UC | mask/filter DESCRIBE + two-principal SELECT + lineage row | committed outputs |
| ML | MLflow metrics, model version, serving JSON, matched-rate 2x2, latency | notebook outputs + json + md |
| GenAI | `ai_query` output + guardrail check | committed text rows |
| Lakebase | synced SELECT + case UPDATE before/after + latency | committed outputs |
| Genie | Conversation-API transcript | committed text |
| App | data-access queries + returned rows | committed code + logged output |
| Integration | end-to-end journey-script log | committed log |

## 9. ROI sensitivity model (deck, honest)

A parameterised calculator, not a claimed result. Buyer inputs: annual GMV, baseline FPD rate, matched approval rate, recovery rate on defaults. Output: net loss avoided and GMV upside range.

Illustrative anchor (labelled illustrative on the slide): £4B GMV, 5.5% baseline FPD, ~25% recovery gives roughly £165M net loss. A defensible 23 to 27% relative FPD reduction at matched approval rate maps to roughly £35 to £45M net loss avoided per year, plus GMV upside from cutting thin-file over-declines 8 to 12%. Every figure carries the illustrative label and the mechanism-not-portfolio caveat.

## 10. Deck outline (Google Slides, shareable link)

1. Title and the one-line business outcome.
2. The problem: thin-file cold-start, the £ pincer and the regulatory pincer.
3. Who feels it: exec sponsor and domain owner, in their own words.
4. The outcome: headline KPI moves (illustrative), matched-approval-rate framing.
5. How it works: the closed loop, one diagram.
6. The six-stage journey on Databricks.
7. Proof: the 2x2 and the evidence spine.
8. ROI sensitivity model (buyer sets the inputs).
9. Governance and compliance posture: UC, deterministic reason codes, human-in-loop, GenAI guardrails.
10. What is demo vs production (the honesty slide the panel demanded).
11. Pilot design and next steps (the exec's 10k-customer, 12-week holdout).

## 11. Namespacing and shared-workspace hygiene

`e2-demo-field-eng` is shared and busy. Rules:
- All Unity Catalog objects under a dedicated schema, for example `<catalog>.bnpl_fpd_samk`.
- All resources (pipeline, model, endpoint, Lakebase instance, Genie space, app) carry a `bnpl-fpd-samk` prefix.
- Do not modify or delete any existing shared resource. Create a small dedicated serverless warehouse rather than reusing a "DO-NOT-DELETE" one.
- Verify `CREATE SCHEMA` rights as the first build action.

## 12. Scope, sequence, time budget, cut-lines

Target 4 to 8 hours of build. Order chosen so the highest-evidence-risk stages are proven early.

1. Verify create rights and namespace, create serverless warehouse (~10 min).
2. Synthetic data generator + land in volume (~45 min).
3. Lakeflow Declarative Pipeline bronze-silver-gold + expectations (~60 min).
4. UC governance (masks, filter, tags, lineage) + two-principal evidence (~30 min).
5. ML train, register, serve, reason codes, matched-rate 2x2 (~90 min).
6. GenAI `ai_query` narrative + guardrails (~30 min).
7. Lakebase instance, synced table, mutable case/threshold tables (~60 min).
8. Genie Space + Conversation-API transcript (~30 min).
9. Journey script (the evidence spine) (~45 min).
10. App (~60 to 90 min).
11. Deck (~60 min).

**Cut-lines if time is short (protect the mandatory journey):** keep all six stages present and evidenced; shrink the App to a minimal read/write UI over Lakebase; keep GenAI to the single call; trim data volume before trimming any stage. The integration journey script is never cut.

## 13. Risks and mitigations (from the panel)

| Risk | Mitigation |
|---|---|
| Reads like dbdemos credit scoring | Cold-start + closed loop; bureau absent for half the population. |
| App/Genie evidence is visual, grader rejects screenshots | Journey script + committed queries/transcripts as text. |
| "<2s at checkout" overclaim | Measure p50/p99 on a warm endpoint, present honestly, mark demo vs prod. |
| "Compliant outreach" overclaim | Reframe to human-review drafts; deterministic reason codes; guardrail check. |
| Synthetic ROI overclaim | Sensitivity model, not a result; illustrative labels throughout. |
| Feature leakage | Point-in-time-correct features by construction. |
| Lakebase seen as bolted on | Mutable OLTP case queue and threshold table the App writes. |
| Genie seen as bolted on | Embedded as investigation surface that drives a threshold action. |
| Shared-workspace collisions | Namespacing and no-touch rules (Section 11). |
| Genie Conversation API is Public Preview | Verified reachable in Step 0; capture transcript early. |

## 14. Open decisions for the user

1. App framework: FastAPI + minimal UI, or AppKit (Node/React).
2. Foundation-model endpoint for the GenAI call: `databricks-claude-haiku-4-5` (fast/cheap) or `databricks-claude-sonnet-5` (higher quality narrative).
3. Product/demo name for the deck and app (working title: "Cold-Start Affordability Console").
4. Deck format: Google Slides shareable link, or an HTML deck committed to the repo.
5. Repo home and public-repo timing (build local now, decide before submission).
