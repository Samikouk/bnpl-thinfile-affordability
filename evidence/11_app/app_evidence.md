# Task 11 — Databricks App: Approval & Early-Cure Console (execution evidence)

AppKit (Node/TypeScript/React) app over Lakebase. Deployed and RUNNING. Run 2026-09-16.

## Deployment

```
app:    bnpl-cure-console
url:    https://bnpl-cure-console-1444828305810485.aws.databricksapps.com
status: RUNNING / active_deployment SUCCEEDED ("App started successfully")
sp:     48941986-a3e0-415d-8e2e-74d5d61b6523
```

The app's service principal was granted read on `public.decisions` (synced) and
read/write on `bnpl.*` (mutable) after deploy (it does not own those tables).

## Live API responses (authenticated OAuth call to the deployed app)

The console is text-native by design: its Express routes (`bnpl-cure-console/server/routes/console-routes.ts`)
issue the queries below against Lakebase and return real rows. On this branch the
KPI FPD is **approved-book** (`AVG(fpd_actual) FILTER (WHERE decision='APPROVE')`),
there is a `cures_in_progress` count, `PATCH /api/thresholds/:merchant` writes
cohort thresholds, and disposition requires a signed-in email
(`x-forwarded-email` or `DATABRICKS_USER` for local). Live JSON below is from
the previous deploy (portfolio FPD 5.50%); re-hit the APIs after deploy.

`GET /api/kpis`
```json
{"applications":20000,"approvals":17000,"approval_pct":"85.0","fpd_pct":"5.50"}
```

`GET /api/cohorts` (Travel on top, matches the Genie answer)
```json
[{"merchant_category":"Travel","applications":2500,"approvals":2049,"fpd_pct":"7.36"},
 {"merchant_category":"Electronics","applications":2595,"approvals":2052,"fpd_pct":"6.78"},
 {"merchant_category":"Jewellery","applications":2458,"approvals":1966,"fpd_pct":"6.67"}, ...]
```

`GET /api/decisions` (first record: score + deterministic reason codes)
```json
{"application_id":"A1017535","merchant_category":"Electronics","score":"0.994",
 "decision":"DECLINE",
 "reason_codes":"Requested amount is large relative to disposable income; Low disposable income; Elevated device-risk signal",
 "thin_file_flag":"1"}
```

`GET /api/cure-cases` (shows the case the journey inserted, with the GenAI narrative)
```json
[{"case_id":"2","application_id":"A1007312","status":"OPEN","priority":"HIGH",
  "cure_narrative":"# Early Cure Note – DRAFT FOR REVIEW\n\nWe've noticed a missed first instalment...","updated_at":"2026-09-16T11:00:00Z"}, ...]
```

`GET /api/thresholds`
```json
[{"merchant_category":"Beauty","threshold":0.3,"updated_by":"sam.khanjar@databricks.com", ...}, ...]
```

## What the app proves

The deployed app reads the synced decisions and the mutable case queue and
threshold tables from Lakebase, surfaces the score, reason codes, cohort FPD, and
the cure cases the journey created, and exposes a write-back route to disposition
cases and re-threshold cohorts. It is the business surface for the whole journey.
