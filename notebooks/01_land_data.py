"""Task 2: land synthetic events as JSONL shards for Auto Loader.

Generates the dataset locally and writes each source as several JSONL shards
under build/landing/<source>/. A separate upload step copies them to the UC
volume /Volumes/bnpl_fpd_samk/demo/raw/<source>/. Multiple shards per source
make the downstream Auto Loader ingest meaningful (incremental file discovery).
"""
from __future__ import annotations

import pathlib

from data.generate_synthetic import generate

SEED, N_CUST, N_APPS = 7, 8000, 20000
LOCAL = pathlib.Path("build/landing")
SHARDS = {
    "customers": 2,
    "open_banking": 2,
    "device_signals": 4,
    "applications": 4,
    "repayments": 4,
}


def write_shards(df, name: str, n: int) -> int:
    d = LOCAL / name
    d.mkdir(parents=True, exist_ok=True)
    for f in d.glob("*.json"):
        f.unlink()
    for k in range(n):
        part = df.iloc[k::n]  # interleaved, deterministic
        part.to_json(d / f"part-{k:03d}.json", orient="records", lines=True, date_format="iso")
    return len(df)


def main() -> None:
    data = generate(seed=SEED, n_customers=N_CUST, n_apps=N_APPS)
    for name, n in SHARDS.items():
        rows = write_shards(data[name], name, n)
        print(f"{name:15s} {rows:6d} rows -> {n} shards  ({LOCAL / name})")


if __name__ == "__main__":
    main()
