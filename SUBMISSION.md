# Submission map

FinTech end-to-end Databricks build: **cold-start affordability for Pay-in-4 BNPL**.
Built on `e2-demo-field-eng`, catalog `bnpl_fpd_samk`, fully synthetic data.

## Requirement to artifact

| Requirement | Where it is | Evidence (text) |
|---|---|---|
| **Lakeflow** ingest (synthetic) | `pipelines/bnpl_fpd_pipeline.sql` | `evidence/03_lakeflow/pipeline_run.md` (COMPLETED, expectations 19582/418, gold counts) |
| **Unity Catalog** govern | `notebooks/02_governance.sql` | `evidence/04_uc/governance_evidence.md` (masked vs raw, region filter, tags, lineage) |
| **Lakebase** operational serving | `lakebase/schema.sql`, `notebooks/06_lakebase_setup.py` | `evidence/08_lakebase/lakebase_evidence.md` (20k synced + INSERT/UPDATE OLTP) |
| **ML** intelligence | `notebooks/03_train_model.py`, `data/features.py`, `data/reason_codes.py` | `evidence/05_ml/model_metrics.md` (AUC 0.795, matched-rate 2x2 35% reduction), `evidence/06_serving/serving_evidence.md` |
| **GenAI** intelligence | `notebooks/05_genai_narrative.py`, `data/guardrail.py` | `evidence/07_genai/genai_output.md` (ai_query narrative + guardrail pass/fail) |
| **Genie** natural language | `genie/genie_space.json` | `evidence/09_genie/genie_transcript.md` (Q -> generated SQL -> "Travel 7.36%, 2049 approvals") |
| **Databricks App** | `bnpl-cure-console/` (AppKit) | `evidence/11_app/` (data-access queries + returned rows + URL) |
| **Integrated journey** (not siloed) | `journey/run_journey.py` | `evidence/10_journey/journey_log.txt` (serve -> decide -> cure -> queue -> learn) |
| Synthetic data only | `data/generate_synthetic.py`, `data/labels.py` | `evidence/01_data/data_stats.txt`, `evidence/02_land/landing_manifest.md` |
| Specific industry problem | Pay-in-4 BNPL thin-file FPD at checkout | `docs/superpowers/specs/2026-09-16-bnpl-thinfile-affordability-design.md` |
| Not a dbdemos / internal rehash | cold-start + closed loop (spec Section 2) | design spec Section 2 |
| **Business deck** | `deck/` | `deck/BNPL_Cold_Start_Affordability.pdf` (12 slides) + `deck/DECK_LINK.md` |
| Public repo the validator can read | this repo | make public before submission (synthetic data only, scrubbed) |
| Conversation ID (optional) | the Claude Code session that built this | add on the form if requested |

## The novelty in one line

Score first-payment-default at the BNPL checkout for **thin-file** customers
(no bureau score for ~half) using alternative data, with deterministic
adverse-action reason codes, a GenAI affordability narrative for human review,
and a **closed feedback loop** (Genie surfaces the worst cohort, the analyst
re-thresholds it, the next decision reads the new threshold). Not in dbdemos.

## Design + plan

- Spec: `docs/superpowers/specs/2026-09-16-bnpl-thinfile-affordability-design.md`
- Plan: `docs/superpowers/plans/2026-09-16-bnpl-thinfile-affordability.md`
- The problem was pressure-tested by a 5-role adversarial panel (FinTech expert,
  Databricks SSA, customer exec, customer technical rep, red-team critic) before build.
