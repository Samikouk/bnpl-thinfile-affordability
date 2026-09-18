# Databricks notebook source
# MAGIC %md
# MAGIC # Workspace prep
# MAGIC Creates (or verifies) the isolated catalog/schema/volume and records the
# MAGIC warehouse id. Identifiers live in `config.py` and must match.

# COMMAND ----------
CATALOG, SCHEMA, VOLUME = "bnpl_fpd_samk", "demo", "raw"
WAREHOUSE_NAME = "bnpl-fpd-samk-wh"

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.{VOLUME}")
print(spark.sql("SELECT current_metastore(), current_catalog()").toPandas())
print(spark.sql(f"SHOW GRANT ON SCHEMA {CATALOG}.{SCHEMA}").toPandas())
print("volume", f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}")
print("warehouse_name", WAREHOUSE_NAME)
print("create a serverless SQL warehouse named", WAREHOUSE_NAME, "if missing, then copy its id into config.py WAREHOUSE_ID")
