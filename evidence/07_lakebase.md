# Evidence 07: Lakebase case store (counts, history, edit test)

Generated 2026-11-24T20:09:43Z by tools/generate_evidence.py from the live workspace.

Proves that the operational case store runs on Lakebase (Autoscaling Postgres): the endpoint, the tables and their constraints, how many cases, links and history rows exist, that analysts' edits made through the App are recorded and survive the machine re-sync, that the copy in Unity Catalog matches Lakebase, and an edit test (optimistic locking and constraints) run inside a transaction that is rolled back, so it changes nothing. Identities are redacted; the connection uses a short-lived OAuth credential that is never written down.

Connection: psql, OAuth database credential from `POST /api/2.0/postgres/credentials`, sslmode=require.

## Endpoint (Postgres API)

| item | value |
|---|---|
| name | projects/febar-ops/branches/production/endpoints/primary |
| type | ENDPOINT_TYPE_READ_WRITE |
| state | ACTIVE |
| autoscaling CU | 1.0 – 1.0 |
| suspend timeout | 86400s |
| database | databricks_postgres |


## Tables and row counts

| table_name | rows |
|---|---|
| ops.cases | 7 |
| ops.case_anomalies | 254 |
| ops.case_events | 21 |


## Constraints (pg_constraint)

| table_name | conname | definition |
|---|---|---|
| ops.case_anomalies | case_anomalies_case_key_fkey | FOREIGN KEY (case_key) REFERENCES ops.cases(case_key) |
| ops.case_anomalies | case_anomalies_pkey | PRIMARY KEY (case_key, anomaly_key) |
| ops.case_events | case_events_actor_type_check | CHECK ((actor_type = ANY (ARRAY['SYSTEM'::text, 'USER'::text]))) |
| ops.case_events | case_events_case_key_fkey | FOREIGN KEY (case_key) REFERENCES ops.cases(case_key) |
| ops.case_events | case_events_event_type_check | CHECK ((event_type = ANY (ARRAY['CREATED'::text, 'MACHINE_UPDATE'::text, 'STATUS_CHANGE'::text, 'ASSIGN'::text, 'OWNER_CHANGE'::text, 'NOTE'::text, 'RESOLVE'::text, 'DUE_DATE'::text]))) |
| ops.case_events | case_events_pkey | PRIMARY KEY (event_id) |
| ops.cases | cases_case_key_key | UNIQUE (case_key) |
| ops.cases | cases_check | CHECK (((status = ANY (ARRAY['RESOLVED'::text, 'DISMISSED'::text])) = (resolution_code IS NOT NULL))) |
| ops.cases | cases_issuer_segment_check | CHECK ((issuer_segment = ANY (ARRAY['OWN'::text, 'THIRD_PARTY'::text]))) |
| ops.cases | cases_pkey | PRIMARY KEY (case_id) |
| ops.cases | cases_recovered_spend_usd_check | CHECK ((recovered_spend_usd >= (0)::numeric)) |
| ops.cases | cases_resolution_code_check | CHECK ((resolution_code = ANY (ARRAY['ACQUIRER_FIX'::text, 'CONFIG_CHANGE'::text, 'CREDENTIAL_REFRESH'::text, 'PROCESSOR_FIX'::text, 'FALSE_POSITIVE'::text, 'OTHER'::text]))) |
| ops.cases | cases_severity_check | CHECK ((severity = ANY (ARRAY['HIGH'::text, 'MEDIUM'::text]))) |
| ops.cases | cases_status_check | CHECK ((status = ANY (ARRAY['OPEN'::text, 'CLAIMED'::text, 'IN_PROGRESS'::text, 'WAITING_PARTNER'::text, 'RESOLVED'::text, 'DISMISSED'::text]))) |


## Cases (machine-owned and human-owned columns)

| case_id | root_cause | issuer_segment | region_scope | episode_start | episode_end | n_flags | max_score | severity | exposure_usd | status | assignee | owner_team | due_date | resolution_code | recovered_spend_usd | version | machine_refreshed_at | updated_at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | CROSS_BORDER_BLOCK | OWN | INTL | 2026-10-12 | 2026-10-20 | 21 | 90.10 | HIGH | 19314.88 | CLAIMED | <user> | Network Integration |  |  |  | 2 | 2026-11-23 07:30:49.543696+00 | 2026-11-23 07:27:36.478393+00 |
| 2 | CARD_ON_FILE_STALE | THIRD_PARTY | SE | 2026-11-02 | 2026-11-09 | 23 | 87.73 | HIGH | 4100.30 | OPEN |  | Card Technology |  |  |  | 1 | 2026-11-23 07:30:49.543696+00 |  |
| 3 | CARD_ON_FILE_STALE | OWN | ALL | 2026-11-02 | 2026-11-12 | 138 | 92.83 | HIGH | 36968.09 | IN_PROGRESS | <user> | Card Technology | 2026-11-27 |  |  | 4 | 2026-11-23 07:30:49.543696+00 | 2026-11-23 07:25:59.660618+00 |
| 4 | ACCEPTANCE_CONFIG | OWN | ALL | 2026-01-12 | 2026-01-12 | 2 | 62.29 | MEDIUM | 288.46 | OPEN |  | Acquirer Relations |  |  |  | 1 | 2026-11-23 07:24:30.958089+00 |  |
| 5 | PROCESSOR_TIMEOUT | OWN | SE | 2026-11-14 | 2026-11-16 | 40 | 92.50 | HIGH | 16056.23 | CLAIMED | <user> | Network Operations |  |  |  | 2 | 2026-11-23 07:30:49.543696+00 | 2026-11-23 08:08:16.604538+00 |
| 6 | ACCEPTANCE_CONFIG | OWN | ALL | 2026-09-24 | 2026-10-08 | 21 | 88.54 | HIGH | 12515.42 | OPEN |  | Acquirer Relations |  |  |  | 1 | 2026-11-23 07:30:49.543696+00 |  |
| 7 | PROCESSOR_TIMEOUT | THIRD_PARTY | SE | 2026-11-14 | 2026-11-16 | 9 | 84.92 | HIGH | 1580.69 | OPEN |  | Network Operations |  |  |  | 1 | 2026-11-23 07:30:49.543696+00 |  |


## History (ops.case_events) by type and actor type

| event_type | actor_type | events | first_at | last_at |
|---|---|---|---|---|
| CREATED | SYSTEM | 7 | 2026-11-23 07:24:30.958089+00 | 2026-11-23 07:24:30.958089+00 |
| MACHINE_UPDATE | SYSTEM | 7 | 2026-11-23 07:26:57.8627+00 | 2026-11-23 07:30:49.543696+00 |
| ASSIGN | USER | 2 | 2026-11-23 07:25:59.660618+00 | 2026-11-23 08:08:16.604538+00 |
| DUE_DATE | USER | 1 | 2026-11-23 07:25:59.660618+00 | 2026-11-23 07:25:59.660618+00 |
| NOTE | USER | 1 | 2026-11-23 08:08:20.939812+00 | 2026-11-23 08:08:20.939812+00 |
| STATUS_CHANGE | USER | 3 | 2026-11-23 07:25:59.660618+00 | 2026-11-23 08:08:16.604538+00 |


## Edits made by people through the App (actor redacted)

| case_id | event_type | old_value | new_value | note | actor_type | created_at |
|---|---|---|---|---|---|---|
| 3 | DUE_DATE | None | 2026-11-27 | None | USER | 2026-11-23 07:25:59.660618+00 |
| 3 | ASSIGN | None | analyst.card-inv.demo | Claimed for investigation | USER | 2026-11-23 07:25:59.660618+00 |
| 3 | STATUS_CHANGE | OPEN | IN_PROGRESS | Merchant list requested | USER | 2026-11-23 07:25:59.660618+00 |
| 1 | STATUS_CHANGE | OPEN | CLAIMED | concurrent-claim test | USER | 2026-11-23 07:27:36.478393+00 |
| 5 | STATUS_CHANGE | OPEN | CLAIMED | Taking this one | USER | 2026-11-23 08:08:16.604538+00 |
| 5 | ASSIGN | None | <user> | None | USER | 2026-11-23 08:08:16.604538+00 |
| 5 | NOTE | None | None | Asked Network Operations for SE processor response times | USER | 2026-11-23 08:08:20.939812+00 |


## Human edits survive the machine re-sync

`sync_cases` (the machine upsert) last ran in job run `143622898422721` at 2026-11-23T17:53:22Z.


| case_id | status_set_by_user | edited_at_utc | status_now | human_value_kept | sync_cases_ran_at | sync_ran_after_edit |
|---|---|---|---|---|---|---|
| 1 | CLAIMED | 2026-11-23T07:27:36Z | CLAIMED | t | 2026-11-23T17:53:22Z | True |
| 3 | IN_PROGRESS | 2026-11-23T07:25:59Z | IN_PROGRESS | t | 2026-11-23T17:53:22Z | True |
| 5 | CLAIMED | 2026-11-23T08:08:16Z | CLAIMED | t | 2026-11-23T17:53:22Z | True |


## Unity Catalog copy (gold_case_status, written by sync_cases_back) vs Lakebase

| case_id | uc_status | uc_owner_team | uc_version | lb_status | lb_owner_team | lb_version | identical |
|---|---|---|---|---|---|---|---|
| 1 | CLAIMED | Network Integration | 2 | CLAIMED | Network Integration | 2 | True |
| 2 | OPEN | Card Technology | 1 | OPEN | Card Technology | 1 | True |
| 3 | IN_PROGRESS | Card Technology | 4 | IN_PROGRESS | Card Technology | 4 | True |
| 4 | OPEN | Acquirer Relations | 1 | OPEN | Acquirer Relations | 1 | True |
| 5 | CLAIMED | Network Operations | 2 | CLAIMED | Network Operations | 2 | True |
| 6 | OPEN | Acquirer Relations | 1 | OPEN | Acquirer Relations | 1 | True |
| 7 | OPEN | Network Operations | 1 | OPEN | Network Operations | 1 | True |


## Edit test (inside a transaction that is rolled back)

```sql
BEGIN;
DO $$
DECLARE c record; n int;
BEGIN
  SELECT case_id, version, status INTO c FROM ops.cases WHERE status NOT IN ('RESOLVED','DISMISSED') ORDER BY case_id LIMIT 1;
  RAISE NOTICE 'T0 test case % status % version %', c.case_id, c.status, c.version;
  UPDATE ops.cases SET status = 'IN_PROGRESS', updated_at = now(), version = version + 1 WHERE case_id = c.case_id AND version = c.version;
  GET DIAGNOSTICS n = ROW_COUNT;
  RAISE NOTICE 'T1 analyst A saves with the version they loaded (%): rows updated = % (expected 1)', c.version, n;
  UPDATE ops.cases SET status = 'WAITING_PARTNER', updated_at = now(), version = version + 1 WHERE case_id = c.case_id AND version = c.version;
  GET DIAGNOSTICS n = ROW_COUNT;
  RAISE NOTICE 'T2 analyst B saves with the same, now stale, version (%): rows updated = % (expected 0, B is told to reload)', c.version, n;
  BEGIN
    UPDATE ops.cases SET status = 'RESOLVED' WHERE case_id = c.case_id;
    RAISE NOTICE 'T3 RESOLVED without a resolution code: ACCEPTED (unexpected)';
  EXCEPTION WHEN check_violation THEN
    RAISE NOTICE 'T3 RESOLVED without a resolution code: refused by CHECK constraint (%)', SQLERRM;
  END;
  BEGIN
    UPDATE ops.cases SET recovered_spend_usd = -1 WHERE case_id = c.case_id;
    RAISE NOTICE 'T4 negative recovered spend: ACCEPTED (unexpected)';
  EXCEPTION WHEN check_violation THEN
    RAISE NOTICE 'T4 negative recovered spend: refused by CHECK constraint (%)', SQLERRM;
  END;
  BEGIN
    INSERT INTO ops.cases (case_key, root_cause, issuer_segment, region_scope, episode_start, episode_end, n_flags, max_score, severity)
    SELECT case_key, root_cause, issuer_segment, region_scope, episode_start, episode_end, n_flags, max_score, severity FROM ops.cases WHERE case_id = c.case_id;
    RAISE NOTICE 'T5 second case with the same case_key: ACCEPTED (unexpected)';
  EXCEPTION WHEN unique_violation THEN
    RAISE NOTICE 'T5 second case with the same case_key: refused by UNIQUE constraint (%)', SQLERRM;
  END;
END $$;
ROLLBACK;
```

Output (NOTICE lines, verbatim):

```
T0 test case 1 status CLAIMED version 2
T1 analyst A saves with the version they loaded (2): rows updated = 1 (expected 1)
T2 analyst B saves with the same, now stale, version (2): rows updated = 0 (expected 0, B is told to reload)
T3 RESOLVED without a resolution code: refused by CHECK constraint (new row for relation "cases" violates check constraint "cases_check")
T4 negative recovered spend: refused by CHECK constraint (new row for relation "cases" violates check constraint "cases_recovered_spend_usd_check")
T5 second case with the same case_key: refused by UNIQUE constraint (duplicate key value violates unique constraint "cases_case_key_key")
```

Test case before and after (unchanged, because of the ROLLBACK):

| case_id | status | version |
|---|---|---|
| 1 | CLAIMED | 2 |
| 1 | CLAIMED | 2 |


## Read latency of the App's case-list query

| item | value |
|---|---|
| executions | 30 |
| method | psql \timing, one connection, server round trip per query |
| p50 ms | 16 |
| p95 ms | 20.3 |
| max ms | 26.1 |
