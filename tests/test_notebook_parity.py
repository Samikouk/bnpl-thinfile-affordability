"""Notebook copies of features/reason_codes/policy must match the tested modules."""
from pathlib import Path

from data.features import FEATURE_COLUMNS, BUREAU_IMPUTE, MERCHANT_CATEGORIES
from data.policy import DEFAULT_THRESHOLD
from data.reason_codes import REASON_MAP

ROOT = Path(__file__).resolve().parents[1]
TRAIN = (ROOT / "notebooks" / "03_train_model.py").read_text()
GENAI = (ROOT / "notebooks" / "05_genai_narrative.py").read_text()


def test_train_notebook_lists_the_same_features():
    for col in FEATURE_COLUMNS:
        if col.startswith("mcat_"):
            continue
        assert col in TRAIN, col
    assert 'f"mcat_{c}"' in TRAIN
    assert f"BUREAU_IMPUTE = {BUREAU_IMPUTE}" in TRAIN
    assert f"DEFAULT_THRESHOLD = {DEFAULT_THRESHOLD}" in TRAIN
    for cat in MERCHANT_CATEGORIES:
        assert cat in TRAIN


def test_train_notebook_reason_map_covers_modules():
    for key, label in REASON_MAP.items():
        assert key in TRAIN
        assert label in TRAIN


def test_train_notebook_has_thin_file_matched_rate_and_ops_policy():
    assert "matched_thin_file" in TRAIN
    assert "operational_decision" in TRAIN
    assert "test_brier" in TRAIN
    assert "region_slices_monitor_only" in TRAIN
    assert "serving_env_pin" in TRAIN


def test_genai_notebook_mirrors_guardrail_patterns():
    from data.guardrail import BANNED_PATTERNS
    for pat in BANNED_PATTERNS:
        assert pat in GENAI, pat
