"""Feature transform for the FPD model.

`build_features` is the single source of truth used by training, by the serving
wrapper, and by the journey script, so the features a model sees at train time
and at score time are identical (no online/offline skew).

Design choices tied to the spec and the panel review:
  - Only checkout-available, point-in-time-correct fields become features.
  - `region` is deliberately excluded: it is a row-filter dimension and a
    potential proxy for protected characteristics, so it stays out of the model.
  - Missing bureau score (thin-file, the cold-start case) is imputed to a
    neutral value AND flagged with a `bureau_missing` indicator, so the model
    can learn "no bureau" as its own signal rather than treating it as average.
"""
from __future__ import annotations

import pandas as pd

NUMERIC_FEATURES = [
    "amount",
    "amount_to_disposable_ratio",
    "disposable_income_proxy",
    "inflow_regularity_score",
    "current_balance",
    "device_risk_score",
    "applications_last_24h",
    "applications_last_7d",
    "email_age_days",
    "customer_tenure_days",
]

MERCHANT_CATEGORIES = [
    "Fashion", "Electronics", "Home", "Beauty",
    "Gaming", "Travel", "Fitness", "Jewellery",
]

BUREAU_IMPUTE = 600.0  # neutral fill for a missing bureau score

FEATURE_COLUMNS = (
    NUMERIC_FEATURES
    + ["thin_file_flag", "bureau_missing", "bureau_score"]
    + [f"mcat_{c}" for c in MERCHANT_CATEGORIES]
)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Transform a gold_features-shaped frame into the model feature matrix.

    Extra columns (ids, PII, region, outcomes) are ignored, so leakage cannot
    slip in even if the caller passes a wider frame.
    """
    out = pd.DataFrame(index=df.index)

    for col in NUMERIC_FEATURES:
        out[col] = pd.to_numeric(df[col], errors="coerce")

    out["thin_file_flag"] = pd.to_numeric(df["thin_file_flag"], errors="coerce").fillna(0).astype(int)

    bureau = pd.to_numeric(df["bureau_score"], errors="coerce")
    out["bureau_missing"] = bureau.isna().astype(int)
    out["bureau_score"] = bureau.fillna(BUREAU_IMPUTE)

    cats = df["merchant_category"].astype("string")
    for cat in MERCHANT_CATEGORIES:
        out[f"mcat_{cat}"] = (cats == cat).astype(int)

    out = out.reindex(columns=FEATURE_COLUMNS)
    out = out.fillna(0.0)
    return out
