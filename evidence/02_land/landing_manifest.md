# Task 2 — Land synthetic events to the volume (execution evidence)

Run 2026-09-16. Source generated at seed=7 (customers=8000, apps=20000), sharded
to JSONL, uploaded to `/Volumes/bnpl_fpd_samk/demo/raw/<source>/`.

## Local shard write

```
customers         8000 rows -> 2 shards
open_banking      8000 rows -> 2 shards
device_signals   20000 rows -> 4 shards
applications     20000 rows -> 4 shards
repayments       80000 rows -> 4 shards
```

## Volume listing

```
$ databricks fs ls dbfs:/Volumes/bnpl_fpd_samk/demo/raw
applications
customers
device_signals
open_banking
repayments

$ databricks fs ls .../raw/applications
part-000.json  part-001.json  part-002.json  part-003.json
```

## Row counts read back from the volume (read_files, JSON)

| source | rows |
|---|---|
| applications | 20000 |
| customers | 8000 |
| device_signals | 20000 |
| open_banking | 8000 |
| repayments | 80000 |

Counts match the generator output exactly. Sample landed record (applications):

```json
{"application_id":"A1000000","customer_id":"C102412","ts":"2026-06-11T06:26:07.000",
 "merchant_id":"M200","merchant_category":"Fashion","amount":100.1,"channel":"web",
 "device_id":"D0","ip_hash":"ip_8f533ecc"}
```

No outcome column (`paid_flag`/`fpd`) present in the checkout event, by design.
