"""Deterministic synthetic data generator for the BNPL cold-start demo.

Emits five raw frames that mimic separate source systems, so the Lakeflow
pipeline has a realistic join to do:

  customers      identity + bureau (bureau_score NULL for thin-file)
  open_banking   consented balance / inflow / disposable-income signals
  device_signals per-checkout device fingerprint + application velocity
  applications   the checkout events (checkout-available fields only)
  repayments     pay-in-4 instalments; instalment 1 carries the FPD label

Design choices (see design spec Section 5):
  - Fully synthetic and reproducible from a single seed.
  - ~50% of customers are thin-file with no bureau score (the cold-start point).
  - Features in `applications` are point-in-time correct: no outcome column
    leaks in. The FPD outcome lives only in `repayments`.
  - Outcomes are generated for every application (no reject inference); this is
    a deliberate demo simplification.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from data.labels import latent_scores, fpd_labels

_FIRST_NAMES = [
    "Alex", "Sam", "Priya", "Chen", "Omar", "Grace", "Liam", "Aisha",
    "Noah", "Sofia", "Mia", "Ethan", "Zara", "Leo", "Nina", "Kai",
]
_LAST_NAMES = [
    "Taylor", "Patel", "Wong", "Khan", "Smith", "Nowak", "Silva", "Ahmed",
    "Brown", "Ivanova", "Okafor", "Dubois", "Rossi", "Haidar", "Lund", "Reyes",
]
_REGIONS = ["London", "South", "Midlands", "North", "Scotland", "Wales"]
# Merchant categories with a typical basket size (GBP) for pay-in-4.
_CATEGORIES = {
    "Fashion": 120,
    "Electronics": 380,
    "Home": 260,
    "Beauty": 70,
    "Gaming": 210,
    "Travel": 450,
    "Fitness": 150,
    "Jewellery": 340,
}


def _zscore(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    mu = np.nanmean(x)
    sd = np.nanstd(x)
    if sd == 0 or np.isnan(sd):
        return np.zeros_like(x)
    return (x - mu) / sd


def generate(seed: int = 7, n_customers: int = 5000, n_apps: int = 12000) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)

    # ---- customers -------------------------------------------------------
    cust_ids = np.array([f"C{100000 + i}" for i in range(n_customers)])
    thin_file = (rng.random(n_customers) < 0.50).astype(int)
    email_age_days = np.clip(rng.exponential(500, n_customers), 1, 3650).round().astype(int)
    tenure_days = np.clip(rng.exponential(300, n_customers), 0, 2000).round().astype(int)
    # bureau_score present only for non-thin-file customers
    bureau_raw = np.clip(rng.normal(660, 80, n_customers), 300, 850).round()
    bureau_score = np.where(thin_file == 1, np.nan, bureau_raw)
    first = rng.choice(_FIRST_NAMES, n_customers)
    last = rng.choice(_LAST_NAMES, n_customers)
    full_name = np.array([f"{f} {l}" for f, l in zip(first, last)])
    email = np.array([f"{f}.{l}{i}@example-mail.test".lower() for f, l, i in zip(first, last, range(n_customers))])
    birth_year = rng.integers(1960, 2005, n_customers)
    birth_month = rng.integers(1, 13, n_customers)
    birth_day = rng.integers(1, 28, n_customers)
    dob = np.array([f"{y:04d}-{m:02d}-{d:02d}" for y, m, d in zip(birth_year, birth_month, birth_day)])
    region = rng.choice(_REGIONS, n_customers)

    customers = pd.DataFrame({
        "customer_id": cust_ids,
        "full_name": full_name,
        "email": email,
        "dob": dob,
        "region": region,
        "email_age_days": email_age_days,
        "customer_tenure_days": tenure_days,
        "thin_file_flag": thin_file,
        "bureau_score": bureau_score,
    })

    # ---- open_banking ----------------------------------------------------
    avg_monthly_inflow = np.clip(rng.lognormal(7.7, 0.45, n_customers), 400, 12000).round(2)
    committed_ratio = np.clip(rng.normal(0.62, 0.15, n_customers), 0.2, 0.95)
    committed_outflows = (avg_monthly_inflow * committed_ratio).round(2)
    disposable_income_proxy = np.clip(avg_monthly_inflow - committed_outflows, 20, None).round(2)
    inflow_regularity_score = np.clip(rng.beta(5, 2, n_customers), 0, 1).round(3)
    current_balance = np.clip(rng.lognormal(6.2, 1.0, n_customers), 0, 40000).round(2)

    open_banking = pd.DataFrame({
        "customer_id": cust_ids,
        "current_balance": current_balance,
        "avg_monthly_inflow": avg_monthly_inflow,
        "inflow_regularity_score": inflow_regularity_score,
        "committed_outflows": committed_outflows,
        "disposable_income_proxy": disposable_income_proxy,
    })

    # ---- applications + device_signals ----------------------------------
    app_ids = np.array([f"A{1000000 + i}" for i in range(n_apps)])
    app_cust_idx = rng.integers(0, n_customers, n_apps)
    app_customer = cust_ids[app_cust_idx]
    categories = np.array(list(_CATEGORIES.keys()))
    cat_base = np.array(list(_CATEGORIES.values()), dtype=float)
    cat_idx = rng.integers(0, len(categories), n_apps)
    merchant_category = categories[cat_idx]
    amount = np.clip(cat_base[cat_idx] * rng.lognormal(0.0, 0.35, n_apps), 40, 2000).round(2)
    merchant_id = np.array([f"M{200 + (i % 60)}" for i in cat_idx])
    channel = rng.choice(["web", "ios", "android"], n_apps, p=[0.4, 0.35, 0.25])
    device_id = np.array([f"D{i}" for i in range(n_apps)])
    ip_hash = np.array([f"ip_{h:08x}" for h in rng.integers(0, 16**8, n_apps)])
    start = np.datetime64("2026-06-01T00:00:00")
    ts = start + rng.integers(0, 90 * 24 * 3600, n_apps).astype("timedelta64[s]")

    device_risk_score = np.clip(rng.beta(2, 6, n_apps), 0, 1).round(3)
    applications_last_24h = rng.poisson(0.6, n_apps)
    applications_last_7d = applications_last_24h + rng.poisson(1.2, n_apps)

    applications = pd.DataFrame({
        "application_id": app_ids,
        "customer_id": app_customer,
        "ts": ts,
        "merchant_id": merchant_id,
        "merchant_category": merchant_category,
        "amount": amount,
        "channel": channel,
        "device_id": device_id,
        "ip_hash": ip_hash,
    })

    device_signals = pd.DataFrame({
        "device_id": device_id,
        "device_risk_score": device_risk_score,
        "applications_last_24h": applications_last_24h,
        "applications_last_7d": applications_last_7d,
    })

    # ---- latent FPD + labels --------------------------------------------
    disp = disposable_income_proxy[app_cust_idx]
    ratio = amount / np.clip(disp, 50, None)
    z = {
        "amount_to_disposable_ratio": _zscore(ratio),
        "disposable_income_proxy": _zscore(disp),
        "inflow_regularity_score": _zscore(inflow_regularity_score[app_cust_idx]),
        "applications_last_24h": _zscore(applications_last_24h),
        "device_risk_score": _zscore(device_risk_score),
        "email_age_days": _zscore(email_age_days[app_cust_idx]),
        "bureau_score": _zscore(bureau_score[app_cust_idx]),  # NaN entries -> 0 contribution
    }
    app_thin = thin_file[app_cust_idx].astype(bool)
    latent = latent_scores(z, app_thin, rng)
    fpd, _threshold = fpd_labels(latent)

    # ---- repayments (pay-in-4) ------------------------------------------
    rows = []
    due0 = ts
    for app_id, first_ts, is_fpd in zip(app_ids, due0, fpd):
        for k in range(1, 5):
            due = first_ts + np.timedelta64(14 * (k - 1), "D")
            if k == 1:
                paid = 0 if is_fpd == 1 else 1
            else:
                # if the first instalment missed, later ones very likely missed too
                if is_fpd == 1:
                    paid = int(rng.random() < 0.15)
                else:
                    paid = int(rng.random() < 0.97)
            paid_date = (due + np.timedelta64(int(rng.integers(0, 3)), "D")) if paid == 1 else np.datetime64("NaT")
            rows.append((app_id, k, due, paid, paid_date))
    repayments = pd.DataFrame(rows, columns=["application_id", "installment_no", "due_date", "paid_flag", "paid_date"])

    return {
        "customers": customers,
        "open_banking": open_banking,
        "device_signals": device_signals,
        "applications": applications,
        "repayments": repayments,
    }
