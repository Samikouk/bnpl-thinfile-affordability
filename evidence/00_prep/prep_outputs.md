# Task 0 — Workspace prep (execution evidence)

Run 2026-09-16 against profile `e2-demo-field-eng`.

## Identity + metastore

```
>>> SELECT current_user() AS me, current_metastore() AS metastore
[ { "me": "sam.khanjar@databricks.com",
    "metastore": "aws:us-west-2:b169b504-4c54-49f2-bc3a-adf4b128f36d" } ]
```

Workspace is AWS us-west-2. Lakebase Autoscaling is GA on AWS.

## Unity Catalog objects created (own, isolated)

```
>>> CREATE CATALOG IF NOT EXISTS bnpl_fpd_samk ...          -> Query executed successfully
>>> CREATE SCHEMA  IF NOT EXISTS bnpl_fpd_samk.demo ...     -> Query executed successfully
>>> CREATE VOLUME  IF NOT EXISTS bnpl_fpd_samk.demo.raw ... -> Query executed successfully
>>> SHOW VOLUMES IN bnpl_fpd_samk.demo
[ { "database": "demo", "volume_name": "raw" } ]
```

## Dedicated serverless warehouse

```
created warehouse id=fe2eca1293a1403a name=bnpl-fpd-samk-wh
  (2X-Small, PRO, serverless, auto_stop 10 min, max 1 cluster)
```

## Resource register (consumed by later tasks)

| Item | Value |
|---|---|
| Profile | `e2-demo-field-eng` |
| Catalog | `bnpl_fpd_samk` |
| Schema | `bnpl_fpd_samk.demo` |
| Raw volume | `/Volumes/bnpl_fpd_samk/demo/raw` |
| Warehouse | `bnpl-fpd-samk-wh` (`fe2eca1293a1403a`) |
| Fallback warehouse | `abacc2038735a065` (default) |
| GenAI endpoint | `databricks-claude-haiku-4-5` |

Note: the plan named schema `bnpl_fpd_samk`; the build uses an own catalog
`bnpl_fpd_samk` with schema `demo` (cleaner isolation on a shared workspace).
Fully-qualified names are `bnpl_fpd_samk.demo.<table>`.
