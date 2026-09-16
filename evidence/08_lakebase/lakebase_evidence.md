# Task 8 — Lakebase operational serving (execution evidence)

Lakebase Autoscaling project `bnpl-fpd-samk` (Postgres 17, branch `production`,
endpoint `primary`). Run 2026-09-16. Two roles: a **synced read** copy of the
scored decisions, and the **mutable OLTP** state the app writes.

## Synced table (managed Delta -> Postgres, SNAPSHOT)

Source `bnpl_fpd_samk.demo.gold_decisions` synced to Postgres `public.decisions`
via `databricks postgres create-synced-table` (Lakebase UC catalog `bnpl_lakebase`).

```
SELECT count(*) AS synced_rows FROM public.decisions;
 synced_rows
-------------
       20000

SELECT application_id, merchant_category, round(score::numeric,3), decision
FROM public.decisions WHERE decision='DECLINE' LIMIT 1;
 A1005207 | Gaming | 0.558 | DECLINE
```

## Mutable OLTP (the load-bearing Lakebase justification)

Online tables and feature serving are read-only one-way syncs. The early-cure
case queue needs transactional read/write, which is what Lakebase provides:

```
INSERT INTO bnpl.cure_cases (application_id, customer_id, status, priority)
VALUES ('A1099999','C199999','OPEN','HIGH') RETURNING case_id, status, updated_at;
 case_id | status |          updated_at
---------+--------+-------------------------------
       1 | OPEN   | 2026-09-16 10:28:25.89+00

UPDATE bnpl.cure_cases SET status='IN_PROGRESS', assignee='analyst.jo', updated_at=now()
WHERE application_id='A1099999' RETURNING case_id, status, assignee;
 case_id |   status    |  assignee
---------+-------------+------------
       1 | IN_PROGRESS | analyst.jo
```

State genuinely changed in place (`OPEN` -> `IN_PROGRESS`, assignee set).

## Cohort thresholds (write-back that closes the loop)

```
SELECT merchant_category, threshold FROM bnpl.cohort_thresholds ORDER BY merchant_category LIMIT 3;
 Beauty      | 0.3
 Electronics | 0.3
 Fashion     | 0.3
```

The analyst tightens a risky cohort's threshold here (Genie flagged Travel); the
scoring path reads it. Schema DDL: `lakebase/schema.sql`.
