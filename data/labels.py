"""First-payment-default (FPD) label logic for the synthetic BNPL dataset.

Driver weighting: AFFORDABILITY-DOMINANT (chosen 2026-09-16).

The latent default score rises with financial strain and risk, and falls with
capacity to pay. Affordability signals (instalment-to-disposable-income strain
and disposable income itself) carry the most weight, so the model recovers an
affordability story and the adverse-action reason codes lean that way. This
matches the reframed problem (thin-file affordability at approval, Consumer
Duty aligned) rather than a fraud-first story.

Two deliberate properties, both from the design spec (Section 5):
  - thin-file customers get WIDER noise: they are genuinely harder to predict,
    which is the cold-start reality the demo is about.
  - bureau_score is ABSENT for thin-file customers, so it contributes to the
    latent score only when present. The model must lean on alternative data.

The label is derived by ranking latent scores and cutting at the quantile that
yields the target base rate, so the FPD rate is stable and evidence reproduces.
"""
from __future__ import annotations

import numpy as np

# Weights act on STANDARDISED (z-scored) signals.
# Sign convention: a positive weight raises default probability.
WEIGHTS: dict[str, float] = {
    "amount_to_disposable_ratio": 1.30,  # affordability strain (largest driver)
    "disposable_income_proxy": -1.15,    # capacity to pay (largest protective)
    "inflow_regularity_score": -0.80,    # stable salary cadence protects
    "applications_last_24h": 0.55,       # velocity (secondary)
    "device_risk_score": 0.50,           # device risk (secondary)
    "email_age_days": -0.35,             # established identity protects
    "bureau_score": -0.60,               # only contributes when present (thin-file: absent)
}

THIN_FILE_NOISE_STD = 1.30
STD_NOISE_STD = 0.70
TARGET_FPD_RATE = 0.055


def latent_scores(
    z: dict[str, np.ndarray], thin_file: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    """Weighted sum of standardised signals plus heteroscedastic noise.

    z maps a feature name to its standardised (z-scored) array. A NaN entry
    (for example bureau_score on a thin-file customer) contributes zero.
    thin_file is a boolean array selecting the wider noise band.
    """
    n = len(thin_file)
    score = np.zeros(n, dtype=float)
    for feat, w in WEIGHTS.items():
        if feat not in z:
            continue
        col = np.asarray(z[feat], dtype=float)
        col = np.where(np.isnan(col), 0.0, col)
        score += w * col
    noise_std = np.where(thin_file, THIN_FILE_NOISE_STD, STD_NOISE_STD)
    score = score + rng.standard_normal(n) * noise_std
    return score


def fpd_labels(
    latent: np.ndarray, target_rate: float = TARGET_FPD_RATE
) -> tuple[np.ndarray, float]:
    """Cut the latent distribution at the quantile giving the target base rate.

    Returns (labels, threshold). label == 1 means first-payment default.
    """
    threshold = float(np.quantile(latent, 1.0 - target_rate))
    labels = (latent >= threshold).astype(int)
    return labels, threshold
