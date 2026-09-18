-- Lakeflow Declarative Pipeline: BNPL cold-start affordability
-- Bronze (Auto Loader streaming ingest) -> Gold (point-in-time features, labels, profile)
-- No silver layer: sources are already conformed JSON. README and this header
-- say bronze -> gold on purpose.
-- Published to the pipeline default catalog/schema: bnpl_fpd_samk.demo

-- ---------------------------------------------------------------------------
-- BRONZE: incremental ingest of each raw source with Auto Loader
-- ---------------------------------------------------------------------------
CREATE OR REFRESH STREAMING TABLE bronze_customers AS
SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('/Volumes/bnpl_fpd_samk/demo/raw/customers', format => 'json');

CREATE OR REFRESH STREAMING TABLE bronze_open_banking AS
SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('/Volumes/bnpl_fpd_samk/demo/raw/open_banking', format => 'json');

CREATE OR REFRESH STREAMING TABLE bronze_device_signals AS
SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('/Volumes/bnpl_fpd_samk/demo/raw/device_signals', format => 'json');

CREATE OR REFRESH STREAMING TABLE bronze_applications (
  CONSTRAINT valid_customer EXPECT (customer_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT amount_in_range EXPECT (amount BETWEEN 50 AND 2000)
) AS
SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('/Volumes/bnpl_fpd_samk/demo/raw/applications', format => 'json');

CREATE OR REFRESH STREAMING TABLE bronze_repayments AS
SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _ingested_at
FROM STREAM read_files('/Volumes/bnpl_fpd_samk/demo/raw/repayments', format => 'json');

-- ---------------------------------------------------------------------------
-- GOLD: one point-in-time, checkout-available feature row per application
-- (batch join across bronze sources; NO outcome column joined in)
-- ---------------------------------------------------------------------------
CREATE OR REFRESH MATERIALIZED VIEW gold_features (
  CONSTRAINT has_disposable EXPECT (disposable_income_proxy IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT amount_in_range EXPECT (amount BETWEEN 50 AND 2000)
) AS
SELECT
  a.application_id,
  a.customer_id,
  CAST(a.ts AS TIMESTAMP)                                   AS ts,
  a.merchant_id,
  a.merchant_category,
  a.amount,
  a.channel,
  d.device_risk_score,
  d.applications_last_24h,
  d.applications_last_7d,
  c.email_age_days,
  c.customer_tenure_days,
  c.thin_file_flag,
  c.bureau_score,
  c.region,
  o.disposable_income_proxy,
  o.inflow_regularity_score,
  o.current_balance,
  a.prior_bnpl_ontime_rate,
  ROUND(a.amount / GREATEST(o.disposable_income_proxy, 50), 4) AS amount_to_disposable_ratio
FROM bronze_applications a
LEFT JOIN bronze_customers      c ON a.customer_id = c.customer_id
LEFT JOIN bronze_open_banking   o ON a.customer_id = o.customer_id
LEFT JOIN bronze_device_signals d ON a.device_id   = d.device_id;

-- GOLD: first-payment-default label per application (installment #1)
CREATE OR REFRESH MATERIALIZED VIEW gold_fpd_labels AS
SELECT
  application_id,
  CAST(1 - MAX(CASE WHEN installment_no = 1 THEN paid_flag END) AS INT) AS fpd
FROM bronze_repayments
GROUP BY application_id;

-- GOLD: cleaned repayments (portfolio + Genie)
CREATE OR REFRESH MATERIALIZED VIEW gold_repayments AS
SELECT
  application_id,
  installment_no,
  CAST(due_date  AS TIMESTAMP) AS due_date,
  paid_flag,
  CAST(paid_date AS TIMESTAMP) AS paid_date
FROM bronze_repayments;

-- GOLD: customer profile carrying PII (target for UC masking + row filter in Task 4)
CREATE OR REFRESH MATERIALIZED VIEW gold_customer_profile AS
SELECT
  customer_id, full_name, email, dob, region,
  email_age_days, customer_tenure_days, thin_file_flag, bureau_score
FROM bronze_customers;
