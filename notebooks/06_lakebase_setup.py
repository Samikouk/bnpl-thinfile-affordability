# Databricks notebook source
# MAGIC %md
# MAGIC # Lakebase setup
# MAGIC Synced `public.decisions` from `gold_decisions`, plus mutable
# MAGIC `bnpl.cure_cases` / `bnpl.cohort_thresholds` from `lakebase/schema.sql`.
# MAGIC Apply the DDL with `databricks psql` (see evidence/08_lakebase). This notebook
# MAGIC is the checklist, not a second source of DDL.

# COMMAND ----------
print("1. databricks postgres create-synced-table from bnpl_fpd_samk.demo.gold_decisions -> public.decisions")
print("2. databricks psql --project bnpl-fpd-samk -- -f lakebase/schema.sql")
print("3. GRANT SELECT on public.decisions and SELECT,INSERT,UPDATE on bnpl.* to the app service principal")
print("Operational policy: APPROVE when score < bnpl.cohort_thresholds.threshold (seeded 0.30).")
print("Analyst write-back updates bnpl.cohort_thresholds; the next score uses FpdScorer / operational_decision.")
