"""Deterministic adverse-action reason codes from model SHAP contributions.

The model produces per-feature SHAP contributions for a prediction; a positive
contribution pushes the prediction toward first-payment default. We map the
top risk-increasing contributors to fixed, human-readable adverse-action
reasons. These are deterministic and audit-safe: the LLM never authors them.
"""
from __future__ import annotations

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


def _label(feature: str) -> str | None:
    if feature.startswith("mcat_"):
        return f"High-risk merchant category: {feature[len('mcat_'):]}"
    return REASON_MAP.get(feature)


def reason_codes(shap_row: dict[str, float], top_n: int = 3) -> list[str]:
    """Return up to top_n adverse-action reason strings.

    Only risk-increasing (positive) contributions are considered. Ordering is
    by contribution descending, with feature name as a deterministic tiebreak.
    """
    risk = [(f, c) for f, c in shap_row.items() if c is not None and c > 0]
    risk.sort(key=lambda fc: (-fc[1], fc[0]))
    out: list[str] = []
    for feature, _ in risk[:top_n]:
        label = _label(feature)
        if label:
            out.append(label)
    return out
