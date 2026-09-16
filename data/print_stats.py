"""Print summary stats for the synthetic dataset (committed as text evidence)."""
from __future__ import annotations

import numpy as np

from data.generate_synthetic import generate
from data.labels import WEIGHTS


def main() -> None:
    seed, n_cust, n_apps = 7, 8000, 20000
    d = generate(seed=seed, n_customers=n_cust, n_apps=n_apps)
    cust, apps, ob, dev, rep = (
        d["customers"], d["applications"], d["open_banking"], d["device_signals"], d["repayments"],
    )

    first = rep[rep.installment_no == 1]
    fpd_rate = 1 - first.paid_flag.mean()

    print("=" * 68)
    print("SYNTHETIC BNPL DATASET — SUMMARY (seed=%d, customers=%d, apps=%d)" % (seed, n_cust, n_apps))
    print("=" * 68)
    print(f"rows: customers={len(cust)}, applications={len(apps)}, "
          f"open_banking={len(ob)}, device_signals={len(dev)}, repayments={len(rep)}")
    print()
    print("first-payment-default (FPD) base rate : %.3f%%" % (fpd_rate * 100))
    print("thin-file share                        : %.1f%%" % (cust.thin_file_flag.mean() * 100))
    print("thin-file customers w/ NULL bureau     : %.1f%%" %
          (cust[cust.thin_file_flag == 1].bureau_score.isna().mean() * 100))
    print("non-thin customers w/ bureau score     : %.1f%%" %
          (cust[cust.thin_file_flag == 0].bureau_score.notna().mean() * 100))
    print()

    print("AFFORDABILITY-DOMINANT latent weights (on standardised signals):")
    for k, v in WEIGHTS.items():
        print(f"   {k:32s} {v:+.2f}")
    print()

    print("applications columns (checkout features, no outcome column):")
    print("   " + ", ".join(apps.columns))
    print()

    print("FPD rate by merchant category (drives the Genie cohort story):")
    m = apps.merge(first[["application_id", "paid_flag"]], on="application_id", how="inner")
    m["fpd"] = 1 - m["paid_flag"]
    by_cat = m.groupby("merchant_category")["fpd"].mean().sort_values(ascending=False)
    for cat, r in by_cat.items():
        print(f"   {cat:14s} {r * 100:5.2f}%")
    print()

    print("FPD rate: thin-file vs bureau-scored (cold-start is harder):")
    j = apps.merge(cust[["customer_id", "thin_file_flag"]], on="customer_id", how="left")
    j = j.merge(first[["application_id", "paid_flag"]], on="application_id", how="inner")
    j["fpd"] = 1 - j["paid_flag"]
    for flag, label in [(1, "thin-file "), (0, "bureau    ")]:
        sub = j[j.thin_file_flag == flag]
        print(f"   {label} n={len(sub):6d}  FPD={sub['fpd'].mean() * 100:5.2f}%")


if __name__ == "__main__":
    main()
