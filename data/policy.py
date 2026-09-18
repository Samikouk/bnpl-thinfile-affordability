"""Operational approve/decline policy.

Matched-rate evaluation (the exec 2x2) uses a global 85% approval quantile so
the model is compared with the bureau baseline at the same volume.

The *operational* decision the console, Lakebase, and the journey use is
different: approve when model score < the per-merchant cohort threshold.
Those thresholds start at DEFAULT_THRESHOLD and are written back when an
analyst tightens a risky cohort. This module is the single source of truth
for that rule so training, serving, and the journey cannot drift.
"""
from __future__ import annotations

from data.features import MERCHANT_CATEGORIES

# Approve when P(FPD) is strictly below this value. Seeded in lakebase/schema.sql.
DEFAULT_THRESHOLD = 0.30
# Journey / Genie demo action: tighten the worst cohort (Travel).
TIGHTENED_TRAVEL_THRESHOLD = 0.15

DEFAULT_THRESHOLDS: dict[str, float] = {c: DEFAULT_THRESHOLD for c in MERCHANT_CATEGORIES}

APPROVE = "APPROVE"
DECLINE = "DECLINE"


def threshold_for(merchant_category: str, thresholds: dict[str, float] | None = None) -> float:
    table = DEFAULT_THRESHOLDS if thresholds is None else thresholds
    return float(table.get(merchant_category, DEFAULT_THRESHOLD))


def decide(score: float, threshold: float) -> str:
    """Approve the lowest-risk side of the cut: score is P(FPD)."""
    return APPROVE if float(score) < float(threshold) else DECLINE


def decide_row(
    score: float,
    merchant_category: str,
    thresholds: dict[str, float] | None = None,
) -> tuple[str, float]:
    thr = threshold_for(merchant_category, thresholds)
    return decide(score, thr), thr
