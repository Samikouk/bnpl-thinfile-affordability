# Cold-Start Affordability for Pay-in-4 BNPL

An end-to-end Databricks data journey that solves a specific FinTech problem: a Buy-Now-Pay-Later lender deciding, at checkout, whether to approve a thin-file customer who has little or no credit-bureau history.

The build runs the full journey on one synthetic dataset:

1. **Lakeflow** (Declarative Pipelines + Auto Loader): ingest raw checkout, repayment, open-banking, and device events.
2. **Unity Catalog**: govern the data (PII masks, region row filter, tags on affordability-sensitive fields, lineage).
3. **ML + GenAI**: an FPD (first-payment-default) model with deterministic adverse-action reason codes, plus a GenAI affordability-narrative draft for human review.
4. **Lakebase**: operational serving for the mutable early-cure case queue and per-cohort approval thresholds.
5. **Genie**: natural-language investigation over the portfolio, embedded so its answer drives a threshold action.
6. **Databricks App**: an Approval and Early-Cure Console for the risk and collections team.

The intelligence sits at the **approval moment**, uses **alternative data** where a bureau score is absent (cold-start), and runs a **closed feedback loop**: score, slip, cure, learn, re-threshold.

## Status

Design complete. See [`docs/superpowers/specs/2026-09-16-bnpl-thinfile-affordability-design.md`](docs/superpowers/specs/2026-09-16-bnpl-thinfile-affordability-design.md).

Build in progress. Execution evidence (committed as text) will land under `evidence/` as each stage runs.

## Data

Fully synthetic and reproducible. No real customer data. See the design spec, Section 5.

## Repository layout (planned)

```
docs/        design spec and notes
data/        synthetic data generator
pipelines/   Lakeflow Declarative Pipeline
notebooks/   governance, ML, GenAI, Genie setup (committed with outputs)
lakebase/    schema and sync definitions
app/         Databricks App (Approval & Early-Cure Console)
journey/     end-to-end journey script (the evidence spine)
evidence/    committed run outputs, query results, transcripts, metrics
deck/        business presentation
```
