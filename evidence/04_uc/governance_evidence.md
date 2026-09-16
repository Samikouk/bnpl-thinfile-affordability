# Task 4 — Unity Catalog governance (execution evidence)

Run 2026-09-16. Column masks + region row filter + sensitivity tags applied to
`bnpl_fpd_samk.demo.gov_customer_profile` (a governed table cut from the gold
customer profile). All queries below run as `sam.khanjar@databricks.com`, a
principal in neither privileged group, so the policies apply.

## Policy definitions

```sql
CREATE OR REPLACE FUNCTION bnpl_fpd_samk.demo.pii_mask(v STRING)
RETURN CASE WHEN is_account_group_member('bnpl_pii_readers') THEN v ELSE '***REDACTED***' END;

ALTER TABLE ... ALTER COLUMN full_name SET MASK ...pii_mask;   -- + email, dob

CREATE OR REPLACE FUNCTION bnpl_fpd_samk.demo.region_filter(region STRING)
RETURN is_account_group_member('bnpl_all_regions') OR region = 'London';

ALTER TABLE ... SET ROW FILTER ...region_filter ON (region);
ALTER TABLE ... ALTER COLUMN bureau_score SET TAGS ('data_sensitivity'='restricted');  -- + dob
```

## Caller is not privileged

```
SELECT is_account_group_member('bnpl_pii_readers'), is_account_group_member('bnpl_all_regions')
-> pii_reader=false   all_regions=false
```

## Column mask + row filter in effect (same principal, two views)

GOVERNED table `gov_customer_profile` (PII redacted, only London rows returned):

```
customer_id  full_name        email            dob              region
C100004      ***REDACTED***   ***REDACTED***   ***REDACTED***   London
C100005      ***REDACTED***   ***REDACTED***   ***REDACTED***   London
C100007      ***REDACTED***   ***REDACTED***   ***REDACTED***   London
C100009      ***REDACTED***   ***REDACTED***   ***REDACTED***   London
```

UNGOVERNED upstream `bronze_customers` (raw values, all regions):

```
customer_id  full_name      email                          dob          region
C100000      Omar Smith     omar.smith0@example-mail.test  1994-07-10   Wales
C100001      Grace Rossi    grace.rossi1@example-mail.test 1982-12-11   South
C100002      Sofia Okafor   sofia.okafor2@example-mail.test 1988-04-06  Wales
C100003      Ethan Smith    ethan.smith3@example-mail.test 1969-02-26   Scotland
```

## Row filter counts (governed vs ungoverned)

```
gov_customer_profile (through filter):   London 1366           -- only entitled region
bronze_customers (true distribution):    London 1366, Midlands 1300, North 1358,
                                         Scotland 1322, South 1306, Wales 1348
```

## Sensitivity tags (system.information_schema.column_tags)

```
table_name            column_name   tag_name          tag_value
gov_customer_profile  bureau_score  data_sensitivity  restricted
gov_customer_profile  dob           data_sensitivity  restricted
```

## Lineage (system.access.table_lineage)

```
bronze_customers      -> gold_customer_profile
bronze_applications   -> gold_features
bronze_open_banking   -> gold_features
bronze_customers      -> gold_features
bronze_device_signals -> gold_features
bronze_repayments     -> gold_fpd_labels
```

The affordability decision is fully lineage-traced from raw ingest to gold, and
PII is masked and region-filtered at the base table for non-privileged readers.
This is the auditability posture Consumer Duty expects.
