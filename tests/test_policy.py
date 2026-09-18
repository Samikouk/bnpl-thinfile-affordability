"""Operational policy: score vs per-cohort threshold."""
from data.policy import (
    DEFAULT_THRESHOLD,
    DEFAULT_THRESHOLDS,
    TIGHTENED_TRAVEL_THRESHOLD,
    decide,
    decide_row,
)


def test_decide_cut_is_strict_less_than():
    assert decide(0.29, 0.30) == "APPROVE"
    assert decide(0.30, 0.30) == "DECLINE"
    assert decide(0.547, 0.30) == "DECLINE"
    assert decide(0.547, 0.60) == "APPROVE"


def test_travel_tighten_flips_borderline_score():
    score = 0.22
    before, thr0 = decide_row(score, "Travel")
    assert thr0 == DEFAULT_THRESHOLD
    assert before == "APPROVE"
    after, thr1 = decide_row(score, "Travel", {**DEFAULT_THRESHOLDS, "Travel": TIGHTENED_TRAVEL_THRESHOLD})
    assert thr1 == TIGHTENED_TRAVEL_THRESHOLD
    assert after == "DECLINE"


def test_every_seeded_category_has_a_threshold():
    from data.features import MERCHANT_CATEGORIES
    assert set(DEFAULT_THRESHOLDS) == set(MERCHANT_CATEGORIES)
