# Databricks notebook source
# MAGIC %md
# MAGIC # BNPL first-payment-default model
# MAGIC Train (XGBoost) -> register to Unity Catalog -> batch-score with deterministic
# MAGIC SHAP reason codes into `gold_decisions` -> matched-approval-rate comparison vs a
# MAGIC bureau-only baseline. Feature transform mirrors `data/features.py` (validated by
# MAGIC local tests): region excluded, missing bureau flagged.

# COMMAND ----------
import json
import numpy as np
import pandas as pd
import xgboost as xgb
import mlflow
from mlflow.tracking import MlflowClient
from mlflow.models import infer_signature
from sklearn.metrics import roc_auc_score, average_precision_score

CATALOG, SCHEMA = "bnpl_fpd_samk", "demo"
FULL = f"{CATALOG}.{SCHEMA}.fpd_model"
EXPERIMENT = "/Users/sam.khanjar@databricks.com/bnpl_fpd_experiment"

mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(EXPERIMENT)

# COMMAND ----------
# feature transform (mirrors data/features.py)
NUMERIC = [
    "amount", "amount_to_disposable_ratio", "disposable_income_proxy",
    "inflow_regularity_score", "current_balance", "device_risk_score",
    "applications_last_24h", "applications_last_7d", "email_age_days",
    "customer_tenure_days",
]
CATS = ["Fashion", "Electronics", "Home", "Beauty", "Gaming", "Travel", "Fitness", "Jewellery"]
FEATURES = NUMERIC + ["thin_file_flag", "bureau_missing", "bureau_score"] + [f"mcat_{c}" for c in CATS]
BUREAU_IMPUTE = 600.0
REASON_MAP = {
    "amount_to_disposable_ratio": "Requested amount is large relative to disposable income",
    "disposable_income_proxy": "Low disposable income",
    "inflow_regularity_score": "Irregular or unstable income pattern",
    "applications_last_24h": "High number of recent credit applications (24h)",
    "applications_last_7d": "High number of recent credit applications (7d)",
    "device_risk_score": "Elevated device-risk signal",
    "email_age_days": "Recently created email address (thin digital footprint)",
    "current_balance": "Low current-account balance",
    "customer_tenure_days": "Short customer tenure",
    "bureau_missing": "No credit-bureau history (thin file)",
    "bureau_score": "Low credit-bureau score",
}


def build_features(df):
    out = pd.DataFrame(index=df.index)
    for c in NUMERIC:
        out[c] = pd.to_numeric(df[c], errors="coerce")
    out["thin_file_flag"] = pd.to_numeric(df["thin_file_flag"], errors="coerce").fillna(0).astype(int)
    b = pd.to_numeric(df["bureau_score"], errors="coerce")
    out["bureau_missing"] = b.isna().astype(int)
    out["bureau_score"] = b.fillna(BUREAU_IMPUTE)
    cats = df["merchant_category"].astype("string")
    for c in CATS:
        out[f"mcat_{c}"] = (cats == c).astype(int)
    return out.reindex(columns=FEATURES).fillna(0.0)


def reason_for(feat):
    if feat.startswith("mcat_"):
        return f"High-risk merchant category: {feat[5:]}"
    return REASON_MAP.get(feat)


def top_reasons(contrib, n=3):
    risk = [(f, c) for f, c in contrib.items() if c > 0]
    risk.sort(key=lambda x: (-x[1], x[0]))
    out = []
    for f, _ in risk[:n]:
        r = reason_for(f)
        if r:
            out.append(r)
    return out

# COMMAND ----------
# MAGIC %md ## Load gold, split by time, train

# COMMAND ----------
feat = spark.table(f"{CATALOG}.{SCHEMA}.gold_features").toPandas()
lab = spark.table(f"{CATALOG}.{SCHEMA}.gold_fpd_labels").toPandas()
df = feat.merge(lab, on="application_id", how="inner").sort_values("ts").reset_index(drop=True)

X = build_features(df)
y = df["fpd"].astype(int).values

k = int(len(df) * 0.7)
Xtr, Xte, ytr, yte = X.iloc[:k], X.iloc[k:], y[:k], y[k:]
pos = int(ytr.sum()); neg = len(ytr) - pos
spw = neg / max(pos, 1)

with mlflow.start_run(run_name="fpd_xgb") as run:
    model = xgb.XGBClassifier(
        n_estimators=250, max_depth=4, learning_rate=0.1,
        subsample=0.9, colsample_bytree=0.8, scale_pos_weight=spw,
        eval_metric="aucpr", n_jobs=4, random_state=7,
    )
    model.fit(Xtr, ytr)
    p_te = model.predict_proba(Xte)[:, 1]
    auc = float(roc_auc_score(yte, p_te))
    pr_auc = float(average_precision_score(yte, p_te))
    mlflow.log_params({"n_estimators": 250, "max_depth": 4, "learning_rate": 0.1,
                       "scale_pos_weight": round(spw, 3)})
    mlflow.log_metrics({"test_auc": auc, "test_pr_auc": pr_auc,
                        "train_rows": float(len(Xtr)), "test_rows": float(len(Xte))})
    # UC requires a model signature (input + output schema).
    signature = infer_signature(Xtr, model.predict_proba(Xtr)[:, 1])
    info = mlflow.xgboost.log_model(
        model, artifact_path="model", registered_model_name=FULL,
        signature=signature, input_example=Xtr.iloc[:3],
    )

client = MlflowClient(registry_uri="databricks-uc")
client.set_registered_model_alias(FULL, "prod", info.registered_model_version)
model_version = info.registered_model_version

# COMMAND ----------
# MAGIC %md ## Batch score all applications + deterministic SHAP reason codes -> gold_decisions

# COMMAND ----------
booster = model.get_booster()
dall = xgb.DMatrix(X.values, feature_names=list(X.columns))
proba = model.predict_proba(X)[:, 1]
contribs = booster.predict(dall, pred_contribs=True)  # (n, F+1); last col = bias
fnames = list(X.columns)

APPROVE_RATE = 0.85
cutoff = float(np.quantile(proba, APPROVE_RATE))  # approve the lowest-risk 85%

reasons_all = []
for i in range(len(df)):
    cd = {fnames[j]: float(contribs[i][j]) for j in range(len(fnames))}
    reasons_all.append("; ".join(top_reasons(cd, 3)))

dec = pd.DataFrame({
    "application_id": df["application_id"].values,
    "customer_id": df["customer_id"].values,
    "ts": df["ts"].astype(str).values,
    "merchant_category": df["merchant_category"].values,
    "amount": df["amount"].astype(float).values,
    "region": df["region"].values,
    "thin_file_flag": df["thin_file_flag"].astype(int).values,
    "score": proba.astype(float),
    "decision": np.where(proba < cutoff, "APPROVE", "DECLINE"),
    "reason_codes": reasons_all,
    "threshold_used": float(cutoff),
    "fpd_actual": y.astype(int),
})
(spark.createDataFrame(dec)
    .write.mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(f"{CATALOG}.{SCHEMA}.gold_decisions"))

# COMMAND ----------
# MAGIC %md ## Matched-approval-rate: model vs bureau-only baseline (same approval count)

# COMMAND ----------
m_appr = proba < cutoff
n_appr = int(m_appr.sum())

bureau = pd.to_numeric(df["bureau_score"], errors="coerce").values
# bureau-only baseline: risk = 850 - bureau; thin-file (no bureau) -> worst possible.
baseline_risk = np.where(np.isnan(bureau), np.inf, 850.0 - bureau)
order = np.argsort(baseline_risk, kind="stable")
b_appr = np.zeros(len(df), dtype=bool)
b_appr[order[:n_appr]] = True


def fpd_rate(mask):
    return float(y[mask].mean()) if mask.sum() > 0 else float("nan")


avg_amt_approved = float(df.loc[m_appr, "amount"].mean())
model_fpd = fpd_rate(m_appr)
base_fpd = fpd_rate(b_appr)
# simple loss proxy on the approved book (principal at risk, 25% recovery)
model_loss = n_appr * model_fpd * avg_amt_approved * 0.75
base_loss = n_appr * base_fpd * avg_amt_approved * 0.75

result = {
    "model_version": model_version,
    "test_auc": round(auc, 4),
    "test_pr_auc": round(pr_auc, 4),
    "rows_scored": int(len(df)),
    "approval_rate": round(n_appr / len(df), 4),
    "n_approved": n_appr,
    "model_approved_fpd": round(model_fpd, 4),
    "baseline_approved_fpd": round(base_fpd, 4),
    "relative_fpd_reduction": round(1 - model_fpd / base_fpd, 4) if base_fpd else None,
    "avg_amount_approved": round(avg_amt_approved, 2),
    "model_loss_proxy": round(model_loss, 0),
    "baseline_loss_proxy": round(base_loss, 0),
    "decisions_table": f"{CATALOG}.{SCHEMA}.gold_decisions",
}
print(json.dumps(result, indent=2))
dbutils.notebook.exit(json.dumps(result))
