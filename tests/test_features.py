"""Tests for build_features: the single feature transform shared by training,
serving, and the journey script (one source of truth => no train/serve skew).
"""
import pandas as pd

from data.generate_synthetic import generate
from data.features import build_features, FEATURE_COLUMNS


def _assemble_gold_like(data):
    """Reproduce the pipeline's gold_features join locally for testing."""
    g = (
        data["applications"]
        .merge(data["customers"], on="customer_id", how="left")
        .merge(data["open_banking"], on="customer_id", how="left")
        .merge(data["device_signals"], on="device_id", how="left")
    )
    g["amount_to_disposable_ratio"] = (
        g["amount"] / g["disposable_income_proxy"].clip(lower=50)
    ).round(4)
    return g


def test_columns_match_and_ordered():
    g = _assemble_gold_like(generate(seed=7, n_customers=1000, n_apps=2500))
    X = build_features(g)
    assert list(X.columns) == FEATURE_COLUMNS


def test_no_id_or_leakage_columns():
    g = _assemble_gold_like(generate(seed=7, n_customers=1000, n_apps=2500))
    X = build_features(g)
    banned = {
        "application_id", "customer_id", "ts", "region", "merchant_id",
        "device_id", "ip_hash", "full_name", "email", "dob",
        "fpd", "paid_flag", "paid_date", "installment_no",
    }
    assert not (banned & set(X.columns)), banned & set(X.columns)


def test_no_nans_and_bureau_missing_flag():
    g = _assemble_gold_like(generate(seed=7, n_customers=2000, n_apps=5000))
    X = build_features(g)
    # model input must be fully populated
    assert X.isna().sum().sum() == 0
    # thin-file rows (no bureau) must be flagged
    thin_rows = g["thin_file_flag"] == 1
    assert (X.loc[thin_rows, "bureau_missing"] == 1).all()
    assert (X.loc[~thin_rows, "bureau_missing"] == 0).all()


def test_region_excluded_for_fairness():
    # region is a row-filter dimension and a potential proxy; it must not be a model feature
    g = _assemble_gold_like(generate(seed=7, n_customers=1000, n_apps=2000))
    X = build_features(g)
    assert not any(c.lower().startswith("region") for c in X.columns)


def test_prior_bnpl_missing_flag():
    g = _assemble_gold_like(generate(seed=7, n_customers=400, n_apps=1200))
    X = build_features(g)
    missing = g["prior_bnpl_ontime_rate"].isna()
    assert missing.any()
    assert (X.loc[missing, "prior_bnpl_missing"] == 1).all()
    assert (X.loc[~missing, "prior_bnpl_missing"] == 0).all()
