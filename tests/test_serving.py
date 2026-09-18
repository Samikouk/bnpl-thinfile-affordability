"""FpdScorer applies build_features + cohort thresholds."""
import numpy as np

from data.features import build_features
from data.generate_synthetic import generate
from data.serving import FpdScorer


def _gold(n_customers=40, n_apps=80):
    data = generate(seed=7, n_customers=n_customers, n_apps=n_apps)
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


class _ConstModel:
    def __init__(self, p: float):
        self.p = p

    def predict_proba(self, X):
        n = len(X)
        p = np.full(n, self.p)
        return np.column_stack([1 - p, p])


def test_scorer_respects_threshold():
    g = _gold()
    scorer = FpdScorer(_ConstModel(0.22))
    out = scorer.score_frame(g)
    assert (out["decision"] == "APPROVE").all()
    assert (out["threshold_used"] == 0.30).all()
    tight = FpdScorer(_ConstModel(0.22), thresholds={c: 0.15 for c in scorer.thresholds})
    assert (tight.score_frame(g)["decision"] == "DECLINE").all()


def test_scorer_uses_same_feature_matrix():
    g = _gold()
    X = build_features(g)
    scorer = FpdScorer(_ConstModel(0.1))
    assert len(scorer.predict_proba(g)) == len(X)
