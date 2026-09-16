"""Tests for the synthetic BNPL data generator.

These lock in the properties that make the demo credible to a real BNPL risk
audience (per the design spec, Section 5):
  - deterministic given a seed (so committed evidence reproduces)
  - a realistic first-payment-default base rate (~5.5%)
  - a realistic thin-file share, with bureau_score genuinely absent for them
  - no post-decision / outcome columns leaking into the checkout feature frame
"""
import pandas as pd

from data.generate_synthetic import generate


def test_deterministic():
    a = generate(seed=7, n_customers=2000, n_apps=5000)
    b = generate(seed=7, n_customers=2000, n_apps=5000)
    pd.testing.assert_frame_equal(a["applications"], b["applications"])


def test_fpd_base_rate_near_5_5pct():
    d = generate(seed=7, n_customers=5000, n_apps=12000)
    rep = d["repayments"]
    first = rep[rep.installment_no == 1]
    fpd_rate = 1 - first.paid_flag.mean()
    assert 0.045 <= fpd_rate <= 0.070, f"FPD base rate off target: {fpd_rate:.4f}"


def test_thin_file_share_and_missing_bureau():
    d = generate(seed=7, n_customers=5000, n_apps=12000)
    cust = d["customers"]
    thin_share = cust.thin_file_flag.mean()
    assert 0.40 <= thin_share <= 0.60, f"thin-file share off: {thin_share:.3f}"
    # thin-file customers must have NULL bureau_score (that is the cold-start point)
    thin = cust[cust.thin_file_flag == 1]
    assert thin.bureau_score.isna().mean() > 0.95


def test_no_leakage_columns_in_features():
    # the applications (checkout feature) frame must not contain any
    # post-decision or outcome column
    d = generate(seed=7, n_customers=2000, n_apps=5000)
    feats = set(d["applications"].columns)
    banned = {"paid_flag", "paid_date", "fpd", "installment_no"}
    assert not (banned & feats), f"leakage columns present: {banned & feats}"
