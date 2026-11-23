# Evidence 07: Lakebase (Autoscaling Postgres) case store

- **Project** `febar-ops` (created with `databricks postgres create-project febar-ops`): branch `production`, database `databricks_postgres`, schema `ops`.
- **Endpoint:** endpoint projects/febar-ops/branches/production/endpoints/primary ENDPOINT_TYPE_READ_WRITE ACTIVE autoscaling 1 - 1 CU
- **Auth:** an OAuth database credential from the Databricks SDK (`w.postgres.generate_database_credential(endpoint=…)`), generated per connection and used as the password with `sslmode=require`. **No static password** exists anywhere (`src/serve/lakebase_common.py`). The command-line checks below use `databricks psql --project febar-ops`, which fetches the same kind of short-lived credential.
- **Code:** `src/serve/case_flags_view.sql` (episode grouping), `src/serve/sync_cases.py` (T3), `src/serve/sync_cases_back.py` (T4). Job `febar_main`: T2 `explain_anomalies` → T3 `sync_cases` → T4 `sync_cases_back`.

## Design (approved 2026-11-23)

- **One case per episode:** flags with the same likely root cause and issuer segment on consecutive days (gap ≤ 1 day) → `case_key = root_cause|issuer_segment|episode_start`. **254 flags became 7 cases.**
- **`ops.cases`** has two kinds of column:
  - **Machine-owned**, written by T3 only: root cause, segment, region scope, episode dates, flag count, max score, severity (HIGH if max score ≥ 70), exposure, excess declines, merchants, suggested owner team, top slices, LLM summary and next step (prompt v3), versions.
  - **Human-owned**, written by the App only: status, assignee, owner team, due date, resolution code, recovered spend, resolved/updated metadata, version.
- **`ops.case_anomalies`:** the flags behind each case (254 rows).
- **`ops.case_events`:** append-only history.
- **Pattern:**
  - `INSERT … ON CONFLICT (case_key) DO UPDATE SET <machine columns> WHERE (machine columns) IS DISTINCT FROM (new values)`. Human columns are written once at insert and never again.
  - History: a CREATED event per new case, a MACHINE_UPDATE event only when a machine value actually changed.

### Constraints (from `pg_constraint`)

```
conname             |                                                                              pg_get_constraintdef                                                                              
---------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 cases_case_key_key              | UNIQUE (case_key)
 cases_check                     | CHECK (((status = ANY (ARRAY['RESOLVED'::text, 'DISMISSED'::text])) = (resolution_code IS NOT NULL)))
 cases_issuer_segment_check      | CHECK ((issuer_segment = ANY (ARRAY['OWN'::text, 'THIRD_PARTY'::text])))
 cases_recovered_spend_usd_check | CHECK ((recovered_spend_usd >= (0)::numeric))
 cases_resolution_code_check     | CHECK ((resolution_code = ANY (ARRAY['ACQUIRER_FIX'::text, 'CONFIG_CHANGE'::text, 'CREDENTIAL_REFRESH'::text, 'PROCESSOR_FIX'::text, 'FALSE_POSITIVE'::text, 'OTHER'::text])))
 cases_severity_check            | CHECK ((severity = ANY (ARRAY['HIGH'::text, 'MEDIUM'::text])))
 cases_status_check              | CHECK ((status = ANY (ARRAY['OPEN'::text, 'CLAIMED'::text, 'IN_PROGRESS'::text, 'WAITING_PARTNER'::text, 'RESOLVED'::text, 'DISMISSED'::text])))
(7 rows)
```

## Counts by status and table sizes (`databricks psql --project febar-ops`)

```
status    | severity | cases 
-------------+----------+-------
 CLAIMED     | HIGH     |     1
 IN_PROGRESS | HIGH     |     1
 OPEN        | HIGH     |     4
 OPEN        | MEDIUM   |     1
(4 rows)

 cases | case_anomalies | case_events 
-------+----------------+-------------
     7 |            254 |          12
(1 row)

   event_type   | actor_type | count 
----------------+------------+-------
 ASSIGN         | USER       |     1
 CREATED        | SYSTEM     |     7
 DUE_DATE       | USER       |     1
 MACHINE_UPDATE | SYSTEM     |     1
 STATUS_CHANGE  | USER       |     2
(5 rows)

 case_id |             case_key             |    root_cause     | severity | n_flags | max_score | exposure_usd |                                                 top_slices                                                 |                                                                                     llm_summary                                                                                      |                                                                                    llm_next_step                                                                                     | prompt_version 
---------+----------------------------------+-------------------+----------+---------+-----------+--------------+------------------------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+----------------
       6 | ACCEPTANCE_CONFIG|OWN|2026-09-24 | ACCEPTANCE_CONFIG | HIGH     |      21 |     88.54 |     12515.42 | {"ACQUIRER_CHANNEL: ACQ-017 / ECOM","ACQUIRER_CHANNEL: ACQ-017 / ECOM","ACQUIRER_CHANNEL: ACQ-017 / ECOM"} | On 2026-09-28, the ACQ-017 / ECOM slice on the acquired network recorded 20 acceptance declines against an expected 1.6, producing 18.4 excess declines across 19 merchants and an e | Acquirer Relations should contact Ridgeline Merchant Services today to confirm its acceptance profile for the e-commerce channel on the acquired network, citing the 2026-09-22 conf | v3
(1 row)

            
```

The 7 cases map to the answer key:
- INC1 → #6, INC2 → #1.
- INC3 → #3 (own cards) + #2 (third-party).
- INC4 → #5 (own cards) + #7 (third-party).
- **#4 is not an incident.** It comes from 2026-01-12, the network's first day, when no prior 28-day history existed (cold start), outside the evaluation window. It is left OPEN for an analyst to dismiss as `FALSE_POSITIVE`. Its top flag predates the explanation window, so it has no LLM summary.

### Sample row (case #6 = INC1), as stored

See the `case_id = 6` row above. The v3 next step names the acquirer and its configuration-change date, both taken from the facts: *"Acquirer Relations should contact Ridgeline Merchant Services today to confirm its acceptance profile for the e-commerce channel on the acquired network, citing the 2026-09-22 conf…"*

## Edit-survives-refresh test (case #3 = INC3 own cards)

**1. Human edits by hand** (three changes, one event each) **plus a deliberate tamper** of a machine-owned field (`max_score = 0`):

```
BEGIN
UPDATE 1
INSERT 0 1
UPDATE 1
INSERT 0 1
UPDATE 1
INSERT 0 1
UPDATE 1
COMMIT
 case_id |   status    |       assignee        |   owner_team    |  due_date  | version | max_score |     machine_refreshed_at      
---------+-------------+-----------------------+-----------------+------------+---------+-----------+-------------------------------
       3 | IN_PROGRESS | analyst.card-inv.demo | Card Technology | 2026-11-27 |       4 |      0.00 | 2026-11-23 07:24:30.958089+00
(1 row)
```

**2. Rerun the sync** (`databricks bundle run febar_main --only sync_cases`): `{"cases_from_gold": 7, "inserted": 0, "machine_updated": 1, "unchanged": 6}`

```
case_id |   status    |       assignee        |   owner_team    |  due_date  | version | max_score |    machine_refreshed_at     
---------+-------------+-----------------------+-----------------+------------+---------+-----------+-----------------------------
       3 | IN_PROGRESS | analyst.card-inv.demo | Card Technology | 2026-11-27 |       4 |     92.83 | 2026-11-23 07:26:57.8627+00
(1 row)

 event_id |   event_type   | old_value |                               new_value                                |                   note                   |    actor    | actor_type |          created_at           
----------+----------------+-----------+------------------------------------------------------------------------+------------------------------------------+-------------+------------+-------------------------------
        3 | CREATED        |           | {"n_flags": "138", "max_score": "92.83", "severity": "HIGH", "episode_ | Case opened from flagged anomalies       | sync_cases  | SYSTEM     | 2026-11-23 07:24:30.958089+00
        8 | ASSIGN         |           | analyst.card-inv.demo                                                  | Claimed for investigation                | manual-test | USER       | 2026-11-23 07:25:59.660618+00
        9 | STATUS_CHANGE  | OPEN      | IN_PROGRESS                                                            | Merchant list requested                  | manual-test | USER       | 2026-11-23 07:25:59.660618+00
       10 | DUE_DATE       |           | 2026-11-27                                                             |                                          | manual-test | USER       | 2026-11-23 07:25:59.660618+00
       11 | MACHINE_UPDATE |           | {"n_flags": "138", "max_score": "92.83", "severity": "HIGH", "episode_ | Machine-owned fields refreshed from gold | sync_cases  | SYSTEM     | 2026-11-23 07:26:57.8627+00
(5 rows)
```

- Every human field survived: status `IN_PROGRESS`, assignee, due date, version 4.
- The tampered machine field was **restored** (0 → 92.83) with exactly **one** `MACHINE_UPDATE` event.
- The 6 untouched cases had **no** write and **no** event.

**3. A real machine change** (`top_slices` made distinct) touched 6 of 7 cases → **6 MACHINE_UPDATE events, 1 per changed case**. Human fields survived again:

```
case_id |                                                                   top_slices                                                                    
---------+-------------------------------------------------------------------------------------------------------------------------------------------------
       1 | {"MCC_GROUP_XB: TRAVEL_LODGING / CROSS_BORDER","REGION: INTL","CHANNEL: CP","CARD_SEGMENT: INTL_TRAVELER"}
       2 | {"CHANNEL: REC","MCC_GROUP_XB: BILLS / DOMESTIC","CARD_SEGMENT: DOMESTIC","ACQUIRER_CHANNEL: ACQ-001 / REC","REGION: SE"}
       3 | {"CHANNEL: REC","MCC_GROUP_XB: BILLS / DOMESTIC","ACQUIRER_CHANNEL: ACQ-001 / REC","CARD_SEGMENT: DOMESTIC","MCC_GROUP_XB: DIGITAL / DOMESTIC"}
       4 | {"CARD_SEGMENT: DOMESTIC","CHANNEL: CP"}
       5 | {"REGION: SE","CARD_SEGMENT: DOMESTIC","CHANNEL: CP","MCC_GROUP_XB: RETAIL / DOMESTIC","MCC_GROUP_XB: FOOD_GROCERY / DOMESTIC"}
       6 | {"ACQUIRER_CHANNEL: ACQ-017 / ECOM","CHANNEL: ECOM"}
       7 | {"REGION: SE","CHANNEL: CP","CARD_SEGMENT: DOMESTIC","MCC_GROUP_XB: RETAIL / DOMESTIC","MCC_GROUP_XB: FOOD_GROCERY / DOMESTIC"}
(7 rows)

   event_type   | actor_type | count 
----------------+------------+-------
 ASSIGN         | USER       |     1
 CREATED        | SYSTEM     |     7
 DUE_DATE       | USER       |     1
 MACHINE_UPDATE | SYSTEM     |     7
 STATUS_CHANGE  | USER       |     2
(5 rows)

 case_id |   status    |       assignee        |  due_date  | version 
---------+-------------+-----------------------+------------+---------
       3 | IN_PROGRESS | analyst.card-inv.demo | 2026-11-27 |       4
       1 | CLAIMED     | analyst.A             |            |       2
(2 rows)
```

## Concurrent claim (two sessions, same case, same moment)

Each session ran `UPDATE ops.cases SET status='CLAIMED', assignee=… WHERE case_key = … AND status = 'OPEN' RETURNING …` and inserted an event only if it won.

```
case_id | status  | assignee  | version 
---------+---------+-----------+---------
       1 | CLAIMED | analyst.A |       2
(1 row)

  event_type   |   actor   |         note          
---------------+-----------+-----------------------
 STATUS_CHANGE | analyst.A | concurrent-claim test
(1 row)
```

Session B **updated 0 rows**: it waited on the row lock and then re-checked `status = 'OPEN'`. Exactly one claim, one event.

## Back to the lakehouse (T4 → `gold_case_status`, Unity Catalog)

| case_id | root_cause | issuer_segment | region_scope | status | assignee | severity | n_flags | exposure_usd | n_events |
|---|---|---|---|---|---|---|---|---|---|
| 1 | CROSS_BORDER_BLOCK | OWN | INTL | CLAIMED | analyst.A | HIGH | 21 | 19315.0 | 2 |
| 2 | CARD_ON_FILE_STALE | THIRD_PARTY | SE | OPEN |  | HIGH | 23 | 4100.0 | 1 |
| 3 | CARD_ON_FILE_STALE | OWN | ALL | IN_PROGRESS | analyst.card-inv.demo | HIGH | 138 | 36968.0 | 5 |
| 4 | ACCEPTANCE_CONFIG | OWN | ALL | OPEN |  | MEDIUM | 2 | 288.0 | 1 |
| 5 | PROCESSOR_TIMEOUT | OWN | SE | OPEN |  | HIGH | 40 | 16056.0 | 1 |
| 6 | ACCEPTANCE_CONFIG | OWN | ALL | OPEN |  | HIGH | 21 | 12515.0 | 1 |
| 7 | PROCESSOR_TIMEOUT | THIRD_PARTY | SE | OPEN |  | HIGH | 9 | 1581.0 | 1 |

The persona row filter applies to the Delta copy (my entitlement row switched, then restored):

| persona | cases_visible | case_ids |
|---|---|---|
| P1_DIRECTOR | 5 | 1,3,4,5,6 |
| P2_REGIONAL | 1 | 5 |
| P4_PARTNER | 2 | 2,7 |
| ADMIN (restored) | 7 | 1,2,3,4,5,6,7 |

## Which access rules are enforced where (for the role-play)

| Layer | Enforced by | What |
|---|---|---|
| Delta tables (`gold_*`, `auth_detail`, `gold_anomalies`, `gold_case_status`) | **Unity Catalog, the platform** | Row filter (issuer segment × region) and the `card_ref` mask apply to every query (SQL, notebooks, Genie, the App via the warehouse), whatever tool is used. Bronze and silver are admin-only through grants. |
| Lakebase connection | **The platform** | Only Databricks identities with a short-lived OAuth credential can connect; each maps to a Postgres role. |
| Lakebase tables | **Postgres GRANTs, the platform** | What each role may do. The App's service principal gets USAGE on `ops` plus SELECT/INSERT/UPDATE on `cases`, and **INSERT only** on `case_events`, so history cannot be edited or deleted (granted in the App step). |
| Which cases a user sees in the App | **The App** | **Unity Catalog row filters do not apply to Lakebase rows.** The App connects as one service principal, so it reads the signed-in user from the Databricks Apps headers, looks up their persona in `entitlements`, filters cases by issuer segment and region, and records that user as `actor` on every event. |

**One-liner:** *Analytics data is governed by Unity Catalog for every tool. The case workbench applies the same entitlements in the App, and Postgres permissions stop anyone rewriting the history.*
