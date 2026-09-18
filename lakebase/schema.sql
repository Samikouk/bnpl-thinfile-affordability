-- Lakebase (Postgres) operational schema for the Approval & Early-Cure Console.
-- These are the MUTABLE, transactional tables the app reads and writes. Online
-- tables / feature serving are read-only one-way syncs and cannot host this.

CREATE SCHEMA IF NOT EXISTS bnpl;

-- Per-merchant-cohort approval threshold (approve if model score < threshold).
-- The analyst tightens a risky cohort here; the scoring path reads it. This is
-- the write-back that closes the feedback loop.
CREATE TABLE IF NOT EXISTS bnpl.cohort_thresholds (
    merchant_category text PRIMARY KEY,
    threshold         double precision NOT NULL,
    updated_by        text NOT NULL DEFAULT current_user,
    updated_at        timestamptz NOT NULL DEFAULT now()
);

-- Early-cure case queue: one row per account routed for human-in-the-loop cure.
CREATE TABLE IF NOT EXISTS bnpl.cure_cases (
    case_id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    application_id text NOT NULL,
    customer_id    text,
    status         text NOT NULL DEFAULT 'OPEN',      -- OPEN | IN_PROGRESS | CURED | CLOSED
    assignee       text,
    priority       text NOT NULL DEFAULT 'MEDIUM',    -- LOW | MEDIUM | HIGH
    cure_narrative text,                              -- GenAI draft, for human review
    disposition    text,                              -- analyst outcome note
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

-- Seed a starting threshold per merchant category (must match data/policy.py
-- DEFAULT_THRESHOLD). Scoring approves when score < threshold; the loop tightens risky cohorts.
INSERT INTO bnpl.cohort_thresholds (merchant_category, threshold) VALUES
  ('Fashion', 0.30), ('Electronics', 0.30), ('Home', 0.30), ('Beauty', 0.30),
  ('Gaming', 0.30), ('Travel', 0.30), ('Fitness', 0.30), ('Jewellery', 0.30)
ON CONFLICT (merchant_category) DO NOTHING;
