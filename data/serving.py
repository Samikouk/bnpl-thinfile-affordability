"""Checkout scoring wrapper: features + model + cohort-threshold policy.

Pin this module (and xgboost) in the Model Serving environment so the managed
image cannot drift from training. Lakebase remains the operational queue;
this wrapper is the live checkout path.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from data.features import build_features
from data.policy import DEFAULT_THRESHOLDS, decide_row
from data.reason_codes import reason_codes


class FpdScorer:
    """Score a gold_features-shaped frame and apply the operational policy."""

    def __init__(
        self,
        model: Any,
        thresholds: dict[str, float] | None = None,
        reason_top_n: int = 3,
    ) -> None:
        self.model = model
        self.thresholds = dict(DEFAULT_THRESHOLDS if thresholds is None else thresholds)
        self.reason_top_n = reason_top_n

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        X = build_features(df)
        return np.asarray(self.model.predict_proba(X)[:, 1], dtype=float)

    def score_frame(self, df: pd.DataFrame, shap_rows: list[dict[str, float]] | None = None) -> pd.DataFrame:
        proba = self.predict_proba(df)
        cats = df["merchant_category"].astype("string")
        decisions = []
        used = []
        reasons = []
        for i, (score, cat) in enumerate(zip(proba, cats)):
            decision, thr = decide_row(float(score), str(cat), self.thresholds)
            decisions.append(decision)
            used.append(thr)
            if shap_rows is not None:
                reasons.append("; ".join(reason_codes(shap_rows[i], top_n=self.reason_top_n)))
            else:
                reasons.append("")
        out = pd.DataFrame({
            "score": proba,
            "decision": decisions,
            "threshold_used": used,
            "reason_codes": reasons,
        }, index=df.index)
        return out
