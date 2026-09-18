# Databricks notebook source
# MAGIC %md
# MAGIC # BNPL first-payment-default model
# MAGIC Train (XGBoost) -> register to Unity Catalog -> batch-score with deterministic
# MAGIC SHAP reason codes into `gold_decisions` using the **operational cohort
# MAGIC threshold** (approve if score < threshold). Matched-approval-rate comparison
# MAGIC vs a bureau-only baseline stays on a **global 85% quantile** so the exec 2x2
# MAGIC is volume-matched, including a thin-file slice.
# MAGIC
# MAGIC Feature transform **must stay identical** to `data/features.py` (enforced by
# MAGIC `tests/test_notebook_parity.py`). Databricks notebooks cannot import the
# MAGIC repo package, so the functions are inlined here.

# COMMAND ----------
import json
import numpy as np
import pandas as pd
import xgboost as xgb
import mlflow
from mlflow.tracking import MlflowClient
from mlflow.models import infer_signature
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
)
from sklearn.calibration import calibration_curve

CATALOG, SCHEMA = "bnpl_fpd_samk", "demo"
FULL = f"{CATALOG}.{SCHEMA}.fpd_model"
EXPERIMENT = "/Users/sam.khanjar@databricks.com/bnpl_fpd_experiment"

mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(EXPERIMENT)

# COMMAND ----------
# Keep in lockstep with data/features.py, data/reason_codes.py, data/policy.py
NUMERIC = [
    "amount", "amount_to_disposable_ratio", "disposable_income_proxy",
    "inflow_regularity_score", "current_balance", "device_risk_score",
    "applications_last_24h", "applications_last_7d", "email_age_days",
    "customer_tenure_days", "prior_bnpl_ontime_rate",
]
CATS = ["Fashion", "Electronics", "Home", "Beauty", "Gaming", "Travel", "Fitness", "Jewellery"]
FEATURES = (
    NUMERIC
    + ["thin_file_flag", "bureau_missing", "bureau_score", "prior_bnpl_missing"]
    + [f"mcat_{c}" for c in CATS]
)
BUREAU_IMPUTE = 600.0
DEFAULT_THRESHOLD = 0.30
DEFAULT_THRESHOLDS = {c: DEFAULT_THRESHOLD for c in CATS}
MATCHED_APPROVE_RATE = 0.85
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
    "prior_bnpl_ontime_rate": "Low on-time rate on prior BNPL plans",
    "prior_bnpl_missing": "No prior BNPL repayment history",
}


def build_features(df):
    out = pd.DataFrame(index=df.index)
    for c in NUMERIC:
        if c == "prior_bnpl_ontime_rate":
            continue
        out[c] = pd.to_numeric(df[c], errors="coerce")
    out["thin_file_flag"] = pd.to_numeric(df["thin_file_flag"], errors="coerce").fillna(0).astype(int)
    b = pd.to_numeric(df["bureau_score"], errors="coerce")
    out["bureau_missing"] = b.isna().astype(int)
    out["bureau_score"] = b.fillna(BUREAU_IMPUTE)
    if "prior_bnpl_ontime_rate" in df.columns:
        prior = pd.to_numeric(df["prior_bnpl_ontime_rate"], errors="coerce")
    else:
        prior = pd.Series(pd.NA, index=df.index, dtype="Float64")
    out["prior_bnpl_ontime_rate"] = prior
    out["prior_bnpl_missing"] = prior.isna().astype(int)
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


def operational_decision(scores, merchant_category, thresholds=None):
    thr_map = DEFAULT_THRESHOLDS if thresholds is None else thresholds
    thr = pd.Series(merchant_category, dtype="string").map(thr_map).fillna(DEFAULT_THRESHOLD).astype(float)
    scores = np.asarray(scores, dtype=float)
    decision = np.where(scores < thr.to_numpy(), "APPROVE", "DECLINE")
    return decision, thr.to_numpy()


def matched_rate_block(proba, y, bureau, amounts, approve_rate=MATCHED_APPROVE_RATE):
    """Volume-matched model vs bureau-only policy. Bureau-missing => worst risk."""
    cutoff = float(np.quantile(proba, approve_rate))
    m_appr = proba < cutoff
    n_appr = int(m_appr.sum())
    baseline_risk = np.where(np.isnan(bureau), np.inf, 850.0 - bureau)
    order = np.argsort(baseline_risk, kind="stable")
    b_appr = np.zeros(len(proba), dtype=bool)
    b_appr[order[:n_appr]] = True

    def fpd_rate(mask):
        return float(y[mask].mean()) if mask.sum() > 0 else float("nan")

    avg_amt = float(amounts[m_appr].mean()) if n_appr else float("nan")
    model_fpd = fpd_rate(m_appr)
    base_fpd = fpd_rate(b_appr)
    return {
        "approval_rate": round(n_appr / len(proba), 4) if len(proba) else None,
        "n_approved": n_appr,
        "n_rows": int(len(proba)),
        "model_approved_fpd": round(model_fpd, 4) if model_fpd == model_fpd else None,
        "baseline_approved_fpd": round(base_fpd, 4) if base_fpd == base_fpd else None,
        "relative_fpd_reduction": round(1 - model_fpd / base_fpd, 4) if base_fpd else None,
        "avg_amount_approved": round(avg_amt, 2) if avg_amt == avg_amt else None,
        "model_loss_proxy": round(n_appr * model_fpd * avg_amt * 0.75, 0) if n_appr else None,
        "baseline_loss_proxy": round(n_appr * base_fpd * avg_amt * 0.75, 0) if n_appr else None,
        "cutoff": cutoff,
    }

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
    brier = float(brier_score_loss(yte, p_te))
    cutoff_te = float(np.quantile(p_te, MATCHED_APPROVE_RATE))
    yhat = (p_te >= cutoff_te).astype(int)
    tn, fp, fn, tp = [int(x) for x in confusion_matrix(yte, yhat).ravel()]
    frac_pos, mean_pred = calibration_curve(yte, p_te, n_bins=8, strategy="quantile")
    calibration = [
        {"mean_predicted": round(float(mp), 4), "frac_positive": round(float(fp_), 4)}
        for mp, fp_ in zip(mean_pred, frac_pos)
    ]
    mlflow.log_params({
        "n_estimators": 250, "max_depth": 4, "learning_rate": 0.1,
        "scale_pos_weight": round(spw, 3),
        "operational_threshold": DEFAULT_THRESHOLD,
        "matched_approve_rate": MATCHED_APPROVE_RATE,
        "xgboost_version": xgb.__version__,
    })
    mlflow.log_metrics({
        "test_auc": auc, "test_pr_auc": pr_auc, "test_brier": brier,
        "train_rows": float(len(Xtr)), "test_rows": float(len(Xte)),
        "confusion_tn": tn, "confusion_fp": fp, "confusion_fn": fn, "confusion_tp": tp,
    })
    signature = infer_signature(Xtr, model.predict_proba(Xtr)[:, 1])
    info = mlflow.xgboost.log_model(
        model, artifact_path="model", registered_model_name=FULL,
        signature=signature, input_example=Xtr.iloc[:3],
    )

client = MlflowClient(registry_uri="databricks-uc")
client.set_registered_model_alias(FULL, "prod", info.registered_model_version)
model_version = info.registered_model_version

# COMMAND ----------
# MAGIC %md ## Batch score + SHAP reason codes. Decision = score < cohort threshold.

# COMMAND ----------
booster = model.get_booster()
dall = xgb.DMatrix(X.values, feature_names=list(X.columns))
proba = model.predict_proba(X)[:, 1]
contribs = booster.predict(dall, pred_contribs=True)
fnames = list(X.columns)

op_decision, op_thr = operational_decision(proba, df["merchant_category"])

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
    "decision": op_decision,
    "reason_codes": reasons_all,
    "threshold_used": op_thr.astype(float),
    "fpd_actual": y.astype(int),
})
(spark.createDataFrame(dec)
    .write.mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(f"{CATALOG}.{SCHEMA}.gold_decisions"))

# COMMAND ----------
# MAGIC %md ## Matched-approval-rate 2x2 (all / thin-file / bureau) + fairness monitors

# COMMAND ----------
df_te = df.iloc[k:].reset_index(drop=True)
proba_te = p_te
bureau_te = pd.to_numeric(df_te["bureau_score"], errors="coerce").values
thin_te = df_te["thin_file_flag"].astype(int).values == 1
amt_te = df_te["amount"].astype(float).values

matched_all = matched_rate_block(proba_te, yte, bureau_te, amt_te)
matched_thin = matched_rate_block(proba_te[thin_te], yte[thin_te], bureau_te[thin_te], amt_te[thin_te])
matched_bureau = matched_rate_block(proba_te[~thin_te], yte[~thin_te], bureau_te[~thin_te], amt_te[~thin_te])

# Monitor only: region is not a model feature.
region_slices = []
for region, idx in df_te.groupby(df_te["region"]).groups.items():
    ix = list(idx)
    sub_p, sub_y = proba_te[ix], yte[ix]
    cut = matched_all["cutoff"]
    appr = sub_p < cut
    region_slices.append({
        "region": str(region),
        "n": int(len(ix)),
        "approval_rate": round(float(appr.mean()), 4),
        "approved_fpd": round(float(sub_y[appr].mean()), 4) if appr.any() else None,
    })

thin_auc = float(roc_auc_score(yte[thin_te], proba_te[thin_te])) if thin_te.sum() and yte[thin_te].sum() else None
bureau_auc = float(roc_auc_score(yte[~thin_te], proba_te[~thin_te])) if (~thin_te).sum() and yte[~thin_te].sum() else None

result = {
    "model_version": model_version,
    "xgboost_version": xgb.__version__,
    "test_auc": round(auc, 4),
    "test_pr_auc": round(pr_auc, 4),
    "test_brier": round(brier, 4),
    "confusion_at_matched_cutoff": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
    "calibration_quantile_bins": calibration,
    "rows_scored": int(len(df)),
    "matched_rate_basis": "held-out test set",
    "test_rows": int(len(df_te)),
    "operational_policy": "score < cohort_threshold (default 0.30)",
    "matched_all": matched_all,
    "matched_thin_file": matched_thin,
    "matched_bureau_scored": matched_bureau,
    "test_auc_thin_file": round(thin_auc, 4) if thin_auc else None,
    "test_auc_bureau_scored": round(bureau_auc, 4) if bureau_auc else None,
    "region_slices_monitor_only": region_slices,
    "decisions_table": f"{CATALOG}.{SCHEMA}.gold_decisions",
    "serving_env_pin": f"xgboost=={xgb.__version__}",
}
print(json.dumps(result, indent=2))
dbutils.notebook.exit(json.dumps(result))
