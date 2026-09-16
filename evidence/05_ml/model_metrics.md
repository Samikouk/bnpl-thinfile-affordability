# Task 5 — ML training, registration, matched-rate comparison (execution evidence)

Serverless training job on the refreshed gold tables. Model registered to Unity
Catalog as `bnpl_fpd_samk.demo.fpd_model` (XGBoost). Run 2026-09-16.

## Structured job output (dbutils.notebook.exit)

```json
{
  "model_version": "3",
  "test_auc": 0.7946,
  "test_pr_auc": 0.2336,
  "rows_scored": 20000,
  "matched_rate_basis": "held-out test set",
  "test_rows": 6000,
  "approval_rate": 0.85,
  "n_approved": 5100,
  "model_approved_fpd": 0.0339,
  "baseline_approved_fpd": 0.0522,
  "relative_fpd_reduction": 0.3496,
  "avg_amount_approved": 248.88,
  "model_loss_proxy": 32292.0,
  "baseline_loss_proxy": 49651.0,
  "decisions_table": "bnpl_fpd_samk.demo.gold_decisions"
}
```

## What the numbers say (honest framing)

- **AUC 0.795, PR-AUC 0.234** on a held-out, time-based split with a 5.5% base rate.
  Realistic for thin-file FPD (not a suspiciously perfect model; label noise was
  calibrated deliberately, see `data/tune_noise.py`).
- **Matched-approval-rate 2x2 (the exec's proof), held-out test set only:**

  | policy | approval rate | approved FPD | loss proxy (£) |
  |---|---|---|---|
  | Bureau-only baseline | 85% | 5.22% | 49,651 |
  | FPD model | 85% | 3.39% | 32,292 |

  **35% relative reduction in approved first-payment default at the same approval
  rate.** The edge comes from scoring thin-file applicants with alternative data
  where bureau-only underwriting is blind. This is a mechanism demonstration on
  synthetic data, not a portfolio claim (the deck carries the ROI sensitivity model).

## Deterministic reason codes (top DECLINEs, from gold_decisions)

```
A1017535 | Electronics | score=0.994 | Requested amount is large relative to disposable income; Low disposable income; Elevated device-risk signal
A1012567 | Travel      | score=0.993 | Requested amount is large relative to disposable income; Low disposable income; Recently created email address (thin digital footprint)
A1008834 | Home        | score=0.992 | Requested amount is large relative to disposable income; Low disposable income; Elevated device-risk signal
```

Reason codes come from XGBoost SHAP `pred_contribs`, mapped deterministically
(`data/reason_codes.py`) — audit-safe adverse-action reasons, not LLM output.

## FPD and approval rate by merchant cohort (drives the Genie loop)

```
Travel       n=2500  FPD=7.36%  approve=82.0%
Electronics  n=2595  FPD=6.78%  approve=79.1%
Jewellery    n=2458  FPD=6.67%  approve=80.0%
Home         n=2517  FPD=6.28%  approve=80.9%
Gaming       n=2463  FPD=4.75%  approve=85.6%
Fitness      n=2513  FPD=4.42%  approve=87.7%
Fashion      n=2458  FPD=4.39%  approve=90.6%
Beauty       n=2496  FPD=3.29%  approve=94.5%
```

Travel is the highest-FPD cohort and the model already approves fewer there.
This is the signal Genie surfaces and the analyst acts on (threshold write-back).
