"""Shared namespace + resource identifiers for the demo.

Single source of truth so the journey script, the app, and helper scripts all
point at the same workspace objects. Notebooks that run on Databricks restate
these inline (they do not import local files), but they must match here.
"""

PROFILE = "e2-demo-field-eng"

# Unity Catalog namespace (own catalog, fully isolated on the shared workspace)
CATALOG = "bnpl_fpd_samk"
SCHEMA = "demo"
FQ = f"{CATALOG}.{SCHEMA}"  # fully-qualified schema prefix

# Volumes
VOLUME_RAW = f"/Volumes/{CATALOG}/{SCHEMA}/raw"

# Compute
WAREHOUSE_ID = "fe2eca1293a1403a"
WAREHOUSE_NAME = "bnpl-fpd-samk-wh"

# Lakebase (Autoscaling Postgres; `databricks postgres` surface, not the retired `database` tier)
LAKEBASE_PROJECT = "bnpl-fpd-samk"
LAKEBASE_BRANCH = "projects/bnpl-fpd-samk/branches/production"
LAKEBASE_ENDPOINT = "projects/bnpl-fpd-samk/branches/production/endpoints/primary"
LAKEBASE_DB = "databricks_postgres"
LAKEBASE_HOST = "ep-wispy-unit-d1og6839.database.us-west-2.cloud.databricks.com"
LAKEBASE_SCHEMA = "bnpl"

# Model Serving (real-time FPD scoring)
SERVING_ENDPOINT = "bnpl-fpd-samk-endpoint"
MODEL_UC = "bnpl_fpd_samk.demo.fpd_model"

# Genie space (NL investigation surface)
GENIE_SPACE_ID = "01f1b1b88d51197c9e023880108f6c77"

# GenAI (single ai_query call; swappable)
GENAI_ENDPOINT = "databricks-claude-haiku-4-5"

# Naming
RESOURCE_PREFIX = "bnpl-fpd-samk"
