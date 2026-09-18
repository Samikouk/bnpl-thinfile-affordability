# Databricks notebook source
# MAGIC %md
# MAGIC # Genie space
# MAGIC Definition: `genie/genie_space.json`. Sample question that drives the loop:
# MAGIC "Which merchant category has the highest first-payment-default rate, and how
# MAGIC many approvals did it drive?" Evidence transcript: `evidence/09_genie`.

# COMMAND ----------
print("space tables: gold_decisions, gold_fpd_labels, gold_repayments")
print("action: worst cohort (Travel in the committed run) -> PATCH bnpl.cohort_thresholds")
print("embed: Databricks App user_api_scopes dashboards.genie when you want Genie inside the console")
