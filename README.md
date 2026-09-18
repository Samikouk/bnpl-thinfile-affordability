# Cold-Start Affordability for Pay-in-4 BNPL

An end-to-end Databricks data journey that solves a specific FinTech problem: a
Buy-Now-Pay-Later lender deciding, **at checkout**, whether to approve a
**thin-file** customer who has little or no credit-bureau history.

The intelligence sits at the approval moment, uses **alternative data** where a
bureau score is absent (cold-start), and runs a **closed feedback loop**: score,
slip, cure, learn, re-threshold. This is deliberately not a dbdemos rehash of
credit scoring; the cold-start framing and the loop are the difference.

Everything below ran on `e2-demo-field-eng` against fully synthetic data, and the
execution evidence is committed as text under [`evidence/`](evidence/).

## The six-stage journey

| Stage | What it does here | Evidence |
|---|---|---|
| **Lakeflow** | Declarative Pipeline + Auto Loader ingests checkout, repayment, open-banking, device events (bronze → gold) with expectations | [`evidence/03_lakeflow/`](evidence/03_lakeflow/pipeline_run.md) |
| **Unity Catalog** | PII column masks, region row filter, sensitivity tags, end-to-end lineage | [`evidence/04_uc/`](evidence/04_uc/governance_evidence.md) |
| **Lakebase** | Synced `decisions` (20k rows) + mutable `cure_cases` / `cohort_thresholds` the app writes | [`evidence/08_lakebase/`](evidence/08_lakebase/lakebase_evidence.md) |
| **ML** | XGBoost FPD model, MLflow, UC-registered; deterministic SHAP reason codes; matched-rate 2x2 | [`evidence/05_ml/`](evidence/05_ml/model_metrics.md), [`evidence/06_serving/`](evidence/06_serving/serving_evidence.md) |
| **GenAI** | One `ai_query` drafts an affordability narrative + cure note for human review, guardrailed | [`evidence/07_genai/`](evidence/07_genai/genai_output.md) |
| **Genie** | NL question → generated SQL → "Travel has the highest FPD, 7.36%" → threshold action | [`evidence/09_genie/`](evidence/09_genie/genie_transcript.md) |
| **Databricks App** | Approval & Early-Cure Console over Lakebase (`bnpl-cure-console/`) | [`evidence/11_app/`](evidence/11_app/app_evidence.md) |
| **Integrated journey** | One script walks a single applicant through all stages | [`evidence/10_journey/journey_log.txt`](evidence/10_journey/journey_log.txt) |

## Headline result (synthetic, illustrative)

At a **matched 85% approval rate** on a held-out test set, the model cuts approved
first-payment default from **5.22% (bureau-only) to 3.39%**, a **35% relative
reduction**, by scoring thin-file applicants with alternative data where bureau-only
underwriting is blind. AUC 0.795. This demonstrates the mechanism; the deck carries
the ROI as a buyer-set sensitivity model, not a portfolio claim.

## Data

Fully synthetic and reproducible (`data/generate_synthetic.py`, seed 7). No real
customer data. ~8k customers, 20k applications, 80k repayments. FPD base rate 5.5%,
~50% thin-file with no bureau score. See [`evidence/01_data/`](evidence/01_data/data_stats.txt).

## Deck

[`deck/BNPL_Cold_Start_Affordability.pdf`](deck/BNPL_Cold_Start_Affordability.pdf)
(12 slides) and [`deck/DECK_LINK.md`](deck/DECK_LINK.md).

## Repository layout

```
data/         synthetic generator, feature transform, reason codes, guardrail (+ tests)
pipelines/    Lakeflow Declarative Pipeline (SQL)
notebooks/    landing, governance, training, GenAI, Lakebase setup
lakebase/     Postgres DDL for the mutable OLTP tables
genie/        Genie space definition
journey/      end-to-end journey script (the evidence spine)
bnpl-cure-console/  AppKit app (Approval & Early-Cure Console)
evidence/     committed run outputs, query results, transcripts, metrics
deck/         business presentation (PDF + link)
docs/         design spec + implementation plan
SUBMISSION.md requirement-to-artifact map
```

## Run it yourself

Tests: `python3 -m pytest -q` (generator, features, reason codes, guardrail, labels, policy, serving, notebook parity).
Journey (needs the workspace resources): `PYTHONPATH=. python3 journey/run_journey.py`.
Reproduce the pipeline/model/Genie/app: see `docs/superpowers/plans/2026-09-16-bnpl-thinfile-affordability.md`.

## How it was built

The problem was pressure-tested by a five-role adversarial panel (FinTech industry
expert, Databricks SSA, customer exec, customer technical rep, red-team critic)
before any code, which reframed it from post-loan triage to thin-file affordability
at approval with a closed loop. Design spec and plan are under `docs/`.
