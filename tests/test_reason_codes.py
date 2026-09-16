"""Tests for deterministic adverse-action reason codes.

Reason codes come from the model (SHAP contributions), never the LLM, so they
survive an adverse-action / Consumer Duty audit. Given the same contributions,
the output must be identical every time.
"""
from data.reason_codes import reason_codes


def test_topn_and_ordering():
    shap = {
        "amount_to_disposable_ratio": 0.9,
        "disposable_income_proxy": 0.6,
        "device_risk_score": 0.1,
        "inflow_regularity_score": -0.2,  # protective, must not appear
    }
    codes = reason_codes(shap, top_n=2)
    assert codes == [
        "Requested amount is large relative to disposable income",
        "Low disposable income",
    ]


def test_only_risk_increasing_contributions():
    shap = {"disposable_income_proxy": -0.9, "amount_to_disposable_ratio": 0.3}
    codes = reason_codes(shap, top_n=3)
    assert codes == ["Requested amount is large relative to disposable income"]


def test_deterministic_on_ties():
    shap = {"applications_last_24h": 0.5, "applications_last_7d": 0.5}
    assert reason_codes(shap, top_n=2) == reason_codes(shap, top_n=2)


def test_merchant_category_reason():
    shap = {"mcat_Travel": 0.4}
    assert reason_codes(shap, top_n=1) == ["High-risk merchant category: Travel"]
