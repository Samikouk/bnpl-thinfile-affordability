# Databricks notebook source
# MAGIC %md
# MAGIC # Model Serving pin (follow-up to the failed managed image)
# MAGIC Operational serving in this demo is a Lakebase primary-key lookup of
# MAGIC `gold_decisions` (see `evidence/06_serving`). Checkout scoring in production
# MAGIC should be a Model Serving endpoint whose **environment pins the same xgboost
# MAGIC version the training run logged** (`serving_env_pin` in the training result
# MAGIC JSON). This notebook documents that wrapper; it does not recreate the deleted
# MAGIC endpoint.

# COMMAND ----------
import xgboost as xgb

print("train-time xgboost", xgb.__version__)
print("pin serving pip: xgboost==%s pandas numpy scikit-learn" % xgb.__version__)
print("wrapper: data/serving.py::FpdScorer (build_features + cohort threshold policy)")
print("policy: approve iff score < bnpl.cohort_thresholds[merchant] (default 0.30)")
print("Do not claim p50/p99 until a warm endpoint with this pin is invoked.")
