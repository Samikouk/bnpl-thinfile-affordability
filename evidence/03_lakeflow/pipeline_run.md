# Task 3 — Lakeflow Declarative Pipeline (execution evidence)

Pipeline `bnpl-fpd-samk-pipeline` (`486f09e2-5e78-43fa-bc29-362957cb693b`),
serverless, published to `bnpl_fpd_samk.demo`. Run 2026-09-16.

## Update lifecycle (polled to terminal)

```
update_id=e0c53591-1115-4663-ae3d-87c5ddf89925
10:34:49 state=CREATED
10:35:20 state=INITIALIZING
10:35:51 state=RUNNING
10:36:22 state=COMPLETED
FINAL_STATE=COMPLETED
```

## Data-quality expectations (from the event_log TVF)

```
flow: bnpl_fpd_samk.demo.bronze_applications
  valid_customer   passed=20000  failed=0
  amount_in_range  passed=19582  failed=418     (warn: sub-£50 baskets flagged, kept)

flow: bnpl_fpd_samk.demo.gold_features
  has_disposable   passed=20000  failed=0       (drop-on-violation; none dropped)
  amount_in_range  passed=19582  failed=418     (warn)
```

The 418 flagged rows are genuine sub-£50 purchases the generator emits, so the
expectation is doing real work rather than passing vacuously.

## Row counts (bronze + gold)

| table | rows |
|---|---|
| bronze_applications | 20000 |
| bronze_customers | 8000 |
| bronze_repayments | 80000 |
| gold_features | 20000 |
| gold_fpd_labels | 20000 |
| gold_repayments | 80000 |
| gold_customer_profile | 8000 |

## Label sanity through the pipeline

```
SELECT round(avg(fpd)*100,3) fpd_pct, count(*) n FROM bnpl_fpd_samk.demo.gold_fpd_labels
-> fpd_pct = 5.5,  n = 20000
```

The 5.5% base rate set in the generator survives ingest -> bronze -> gold intact.

## Pipeline source

`pipelines/bnpl_fpd_pipeline.sql`: 5 bronze Auto Loader streaming tables, 4 gold
materialized views (features, labels, repayments, customer profile), expectations
on bronze_applications and gold_features.
