# Task 9 — Genie natural-language investigation (execution evidence)

Genie space `BNPL Cold-Start Affordability` (`01f1b1b88d51197c9e023880108f6c77`)
over `gold_decisions`, `gold_fpd_labels`, `gold_repayments`. Asked via the Genie
Conversation API. Run 2026-09-16.

## Conversation transcript

```
conversation=01f1b1b8a0601cd8bd060b97f6b348c8  message=01f1b1b8a06a1972b29c13ef924305f8

QUESTION:
  Which merchant category has the highest first-payment-default rate,
  and how many approvals did it drive?

status: FILTERING_CONTEXT -> PENDING_WAREHOUSE -> ASKING_AI -> COMPLETED
```

Genie-generated SQL:

```sql
WITH merchant_fpd AS (
  SELECT gold_decisions.merchant_category,
         ROUND(AVG(gold_decisions.fpd_actual) * 100, 2) AS fpd_pct,
         SUM(CASE WHEN gold_decisions.decision = 'APPROVE' THEN 1 ELSE 0 END) AS approvals
  FROM bnpl_fpd_samk.demo.gold_decisions
  WHERE gold_decisions.merchant_category IS NOT NULL
    AND gold_decisions.fpd_actual IS NOT NULL
  GROUP BY gold_decisions.merchant_category
), ranked AS (
  SELECT merchant_category, fpd_pct, approvals,
         RANK() OVER (ORDER BY fpd_pct DESC) AS rnk
  FROM merchant_fpd
)
SELECT merchant_category, fpd_pct, approvals FROM ranked WHERE rnk = 1
```

Genie natural-language answer:

```
Travel has the highest first-payment-default rate at 7.36% and drove 2,049 approvals.
In the returned result set of 1 top-ranked merchant category, Travel is the
highest-risk category by first-payment-default rate.
```

Result rows:

```
columns: [merchant_category, fpd_pct, approvals]
rows:    [["Travel", "7.36", "2049"]]
```

## Why this closes the loop

Genie is the analyst's investigation surface. Its answer ("Travel, 7.36%, 2049
approvals") is the exact signal that drives the operational action: tighten the
Travel cohort's approval threshold in `bnpl.cohort_thresholds` (Lakebase), which
the scoring path then reads. The journey script exercises this end to end.
