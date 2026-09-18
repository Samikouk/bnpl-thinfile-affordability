"""Tests for latent FPD labels: weights, noise bands, target rate."""
import numpy as np

from data.labels import (
    TARGET_FPD_RATE,
    THIN_FILE_NOISE_STD,
    STD_NOISE_STD,
    WEIGHTS,
    fpd_labels,
    latent_scores,
)


def test_target_rate_and_weight_signs():
    assert TARGET_FPD_RATE == 0.055
    assert WEIGHTS["amount_to_disposable_ratio"] > 0
    assert WEIGHTS["disposable_income_proxy"] < 0
    assert WEIGHTS["bureau_score"] < 0
    assert THIN_FILE_NOISE_STD > STD_NOISE_STD


def test_nan_bureau_contributes_zero():
    rng = np.random.default_rng(0)
    n = 200
    z = {
        "amount_to_disposable_ratio": np.zeros(n),
        "disposable_income_proxy": np.zeros(n),
        "inflow_regularity_score": np.zeros(n),
        "applications_last_24h": np.zeros(n),
        "device_risk_score": np.zeros(n),
        "email_age_days": np.zeros(n),
        "bureau_score": np.full(n, np.nan),
    }
    thin = np.zeros(n, dtype=bool)
    a = latent_scores(z, thin, rng, thin_noise_std=0.0, std_noise_std=0.0)
    assert np.allclose(a, 0.0)


def test_fpd_labels_hit_target_rate():
    rng = np.random.default_rng(7)
    latent = rng.normal(0, 1, 20_000)
    y, _thr = fpd_labels(latent, target_rate=0.055)
    assert abs(y.mean() - 0.055) < 0.002
