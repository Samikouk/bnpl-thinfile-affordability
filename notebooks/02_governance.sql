-- Task 4: Unity Catalog governance on the PII-bearing gold table.
-- Column masks on PII, a region row filter, and sensitivity tags on
-- affordability-relevant columns. Masks/filters attach to the base table, so
-- every reader is governed regardless of how they query.

-- Column mask: only members of bnpl_pii_readers see raw PII; everyone else redacted.
CREATE OR REPLACE FUNCTION bnpl_fpd_samk.demo.pii_mask(v STRING)
RETURN CASE WHEN is_account_group_member('bnpl_pii_readers') THEN v ELSE '***REDACTED***' END;

ALTER TABLE bnpl_fpd_samk.demo.gold_customer_profile ALTER COLUMN full_name SET MASK bnpl_fpd_samk.demo.pii_mask;
ALTER TABLE bnpl_fpd_samk.demo.gold_customer_profile ALTER COLUMN email     SET MASK bnpl_fpd_samk.demo.pii_mask;
ALTER TABLE bnpl_fpd_samk.demo.gold_customer_profile ALTER COLUMN dob       SET MASK bnpl_fpd_samk.demo.pii_mask;

-- Row filter: members of bnpl_all_regions see all rows; everyone else only their region.
-- (demo: non-members see only region = 'London')
CREATE OR REPLACE FUNCTION bnpl_fpd_samk.demo.region_filter(region STRING)
RETURN is_account_group_member('bnpl_all_regions') OR region = 'London';

ALTER TABLE bnpl_fpd_samk.demo.gold_customer_profile SET ROW FILTER bnpl_fpd_samk.demo.region_filter ON (region);

-- Sensitivity tags on affordability-relevant columns (governed metadata).
ALTER TABLE bnpl_fpd_samk.demo.gold_customer_profile ALTER COLUMN bureau_score SET TAGS ('data_sensitivity' = 'affordability');
ALTER TABLE bnpl_fpd_samk.demo.gold_features ALTER COLUMN disposable_income_proxy SET TAGS ('data_sensitivity' = 'affordability');
