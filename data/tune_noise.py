"""Local noise tuner: vary label noise via data.labels.latent_scores."""
import numpy as np

from data.generate_synthetic import generate, _zscore
from data.labels import WEIGHTS, fpd_labels, latent_scores


def auc(score, y):
    order = np.argsort(score, kind="stable")
    ranks = np.empty(len(score)); ranks[order] = np.arange(1, len(score) + 1)
    npos = int(y.sum()); nneg = len(y) - npos
    return (ranks[y == 1].sum() - npos * (npos + 1) / 2) / (npos * nneg)


def main():
    d = generate(seed=7, n_customers=8000, n_apps=20000)
    g = (d["applications"].merge(d["customers"], on="customer_id")
         .merge(d["open_banking"], on="customer_id")
         .merge(d["device_signals"], on="device_id"))
    disp = g.disposable_income_proxy.values
    ratio = g.amount.values / np.clip(disp, 50, None)
    z = {
        "amount_to_disposable_ratio": _zscore(ratio),
        "disposable_income_proxy": _zscore(disp),
        "inflow_regularity_score": _zscore(g.inflow_regularity_score.values),
        "applications_last_24h": _zscore(g.applications_last_24h.values),
        "device_risk_score": _zscore(g.device_risk_score.values),
        "email_age_days": _zscore(g.email_age_days.values),
        "bureau_score": _zscore(g.bureau_score.values),
    }
    thin = g.thin_file_flag.values.astype(bool)
    bureau = g.bureau_score.values

    print(f"{'noise(std,thin)':18s} {'auc':>6s} {'base':>6s} {'model_fpd':>10s} {'base_fpd':>9s} {'reduction':>10s}")
    for s, t in [(0.7, 1.3), (1.6, 2.5), (2.2, 3.4), (2.8, 4.3), (3.4, 5.2)]:
        rng = np.random.default_rng(1)
        latent = latent_scores(z, thin, rng, thin_noise_std=t, std_noise_std=s)
        y, _ = fpd_labels(latent)
        signal = np.zeros(len(g))
        for f, w in WEIGHTS.items():
            signal += w * np.nan_to_num(z[f], nan=0.0)
        a = auc(signal, y)
        cut = np.quantile(signal, 0.85)
        m_appr = signal < cut
        n = int(m_appr.sum())
        brisk = np.where(np.isnan(bureau), np.inf, 850 - bureau)
        order = np.argsort(brisk, kind="stable")
        b_appr = np.zeros(len(g), bool); b_appr[order[:n]] = True
        mfpd = y[m_appr].mean(); bfpd = y[b_appr].mean()
        print(f"({s},{t})".ljust(18) + f" {a:6.3f} {y.mean():6.3f} {mfpd:10.4f} {bfpd:9.4f} {1 - mfpd / bfpd:10.3f}")


if __name__ == "__main__":
    main()
