# Task 6 — Serving the FPD score (execution evidence)

## Registered model

The FPD model is registered to Unity Catalog and aliased for production:

```
model  = bnpl_fpd_samk.demo.fpd_model   (XGBoost)
version = 3, alias @prod
metrics = test_auc 0.795, test_pr_auc 0.234   (held-out time split)
```

## Serving path in this demo: Lakebase (OLTP)

The model scores every application in batch (in the training job) into
`gold_decisions`, which is synced to Lakebase `public.decisions`. The console
and the journey read a decision as a primary-key lookup:

```
\timing on
SELECT application_id, ROUND(score::numeric,4) AS score, decision
FROM public.decisions WHERE application_id='A1007312';
 application_id | score  | decision
----------------+--------+----------
 A1007312       | 0.5470 | APPROVE
Time: 150.947 ms
```

The 150 ms is measured from a laptop to the us-west-2 endpoint and is dominated
by client round-trip and the psql wrapper. In-region (the app runs in the same
cloud) a keyed Lakebase read is far lower. The point stands: the operational
serving path is a Lakebase key lookup, not a warehouse scan.

## Matched-approval-rate proof (held-out test set)

See `evidence/05_ml/model_metrics.md` for the full 2x2. Summary: at 85% approval,
the model cuts approved first-payment default from 5.22% (bureau-only) to 3.39%,
a 35% relative reduction, by scoring thin-file applicants with alternative data.

## Honest note on the managed Model Serving endpoint

A real-time Model Serving endpoint (`bnpl-fpd-samk-endpoint`) was created against
model v3 for sub-second checkout scoring. The serving container failed at model
load ("a library raised an error during model load", an env/library mismatch in
the managed image). Rather than spend repeated multi-minute redeploy cycles on a
container dependency issue in a time-boxed demo, the endpoint was deleted and the
score is served from Lakebase (the operational path the console uses anyway). The
UC-registered model plus the batch matched-rate evidence carry the ML stage. The
production fix is to pin the serving env to the training env; that is a follow-up.
