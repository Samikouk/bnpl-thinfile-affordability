-- Task 4: Unity Catalog governance on a dedicated governed cut of the
-- PII-bearing customer profile. Bronze stays unmasked so the same principal
-- can contrast raw vs governed (the evidence spine). Masks/filters attach to
-- the base table gov_customer_profile.

CREATE OR REPLACE TABLE bnpl_fpd_samk.demo.gov_customer_profile AS
SELECT * FROM bnpl_fpd_samk.demo.gold_customer_profile;

-- Column mask: only members of bnpl_pii_readers see raw PII; everyone else redacted.
CREATE OR REPLACE FUNCTION bnpl_fpd_samk.demo.pii_mask(v STRING)
RETURN CASE WHEN is_account_group_member('bnpl_pii_readers') THEN v ELSE '***REDACTED***' END;

ALTER TABLE bnpl_fpd_samk.demo.gov_customer_profile ALTER COLUMN full_name SET MASK bnpl_fpd_samk.demo.pii_mask;
ALTER TABLE bnpl_fpd_samk.demo.gov_customer_profile ALTER COLUMN email     SET MASK bnpl_fpd_samk.demo.pii_mask;
ALTER TABLE bnpl_fpd_samk.demo.gov_customer_profile ALTER COLUMN dob       SET MASK bnpl_fpd_samk.demo.pii_mask;

-- Row filter: members of bnpl_all_regions see all rows; everyone else only London.
CREATE OR REPLACE FUNCTION bnpl_fpd_samk.demo.region_filter(region STRING)
RETURN is_account_group_member('bnpl_all_regions') OR region = 'London';

ALTER TABLE bnpl_fpd_samk.demo.gov_customer_profile SET ROW FILTER bnpl_fpd_samk.demo.region_filter ON (region);

-- Sensitivity tags (governed metadata). Vocabulary matches evidence/04_uc.
ALTER TABLE bnpl_fpd_samk.demo.gov_customer_profile ALTER COLUMN bureau_score SET TAGS ('data_sensitivity' = 'restricted');
ALTER TABLE bnpl_fpd_samk.demo.gov_customer_profile ALTER COLUMN dob SET TAGS ('data_sensitivity' = 'restricted');
ALTER TABLE bnpl_fpd_samk.demo.gold_features ALTER COLUMN disposable_income_proxy SET TAGS ('data_sensitivity' = 'affordability');
