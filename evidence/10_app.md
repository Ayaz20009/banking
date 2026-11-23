# Evidence 10: Databricks App `febar-ops-app`

- **URL:** https://febar-ops-app-7474654297305416.aws.databricksapps.com (FastAPI + Jinja on uvicorn, port from `DATABRICKS_APP_PORT`, host 0.0.0.0).
- **Deployment:** `databricks bundle deploy` then `databricks bundle run febar_app`. Code is in `src/app/` (`app.py`, `app.yaml`, `requirements.txt`, `templates/`); the resource is in `resources/app.yml`.
- **App resources, IDs via `valueFrom` (nothing hard-coded in the code):**
  - `sql-warehouse` (CAN_USE) → `DATABRICKS_WAREHOUSE_ID`
  - `genie-space` (CAN_RUN) → `GENIE_SPACE_ID`
  - `database`: `postgres` branch `projects/febar-ops/branches/production` (CAN_CONNECT_AND_CREATE) → `PGHOST` / `PGUSER` / `PGDATABASE`, injected by the platform
- **User authorization:** `user_api_scopes: [sql, genie]`. Gold-table reads and Genie calls use the signed-in user's `x-forwarded-access-token`, so the **Unity Catalog row filter applies per user**.
- **Lakebase** is always bound to the App's service principal. The App shows a case only if Unity Catalog lets the user see that `case_id` in `gold_case_status` (same row filter), and records the signed-in user as `actor` on every history row.

## Screens

| Route | Screen | Purpose | Data from |
|---|---|---|---|
| `/` | Overview (VP) | Where the migration stands: gap vs matched baseline, lost spend, open cases, wave 7 gate with reasons, and the raw-to-readiness journey with live counts | gold_baseline_gap, gold_wave_readiness, gold_case_status, gold_auth_daily, gold_anomalies (user token) |
| `/cases` | Priority list (Director) | Open cases ranked by severity and lost spend, with why each was flagged, owner and status | ops.cases (Lakebase, live) ∩ case_ids visible in gold_case_status |
| `/cases/{id}` | Case view (analyst) | AI explanation (labelled likely), flagged-slice evidence, daily numbers; claim / status / owner / due date / note / resolve, each written to Lakebase with a history row | ops.cases, ops.case_events (Lakebase); gold_anomalies (user token) |
| `/ask` | Ask Genie | Plain-English questions; shows Genie's answer, the result table and the SQL it ran | Genie Conversation API with the user token |

## Route checks (every route returns 200; called with an OAuth user token; status and size only)

```
GET /health -> 200 (11 bytes, 0.11s)
GET / -> 200 (8073 bytes, 4.91s)
GET /cases -> 200 (7406 bytes, 1.12s)
GET /cases/5 -> 200 (11807 bytes, 1.72s)
GET /ask -> 200 (5790 bytes, 0.56s)
```

App log: **0** errors, tracebacks or exceptions. Excerpt, user identities redacted:

```
2026-11-23T08:05:31Z [APP] INFO:     Waiting for application startup.
2026-11-23T08:05:31Z [APP] INFO:     Application startup complete.
2026-11-23T08:05:31Z [APP] INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
2026-11-23T08:06:31Z [APP] INFO:     10.92.54.17:0 - "GET / HTTP/1.1" 200 OK
2026-11-23T08:06:34Z [APP] INFO:     10.92.70.112:0 - "GET /cases HTTP/1.1" 200 OK
2026-11-23T08:06:37Z [APP] INFO:     10.92.62.137:0 - "GET /cases/6 HTTP/1.1" 200 OK
2026-11-23T08:06:38Z [APP] INFO:     10.92.54.17:0 - "GET /ask HTTP/1.1" 200 OK
2026-11-23T08:06:54Z [APP] INFO:     10.92.59.247:0 - "GET / HTTP/1.1" 200 OK
2026-11-23T08:06:56Z [APP] INFO:     10.92.68.183:0 - "GET /cases HTTP/1.1" 200 OK
2026-11-23T08:07:24Z [APP] INFO:     10.92.54.17:0 - "GET / HTTP/1.1" 200 OK
2026-11-23T08:07:26Z [APP] INFO:     10.92.60.23:0 - "GET /cases HTTP/1.1" 200 OK
2026-11-23T08:07:27Z [APP] INFO:     10.92.51.220:0 - "GET /cases/6 HTTP/1.1" 403 Forbidden
2026-11-23T08:07:36Z [APP] INFO:     10.92.62.137:0 - "GET / HTTP/1.1" 200 OK
2026-11-23T08:07:38Z [APP] INFO:     10.92.60.64:0 - "GET /cases HTTP/1.1" 200 OK
2026-11-23T08:07:38Z [APP] INFO:     10.92.70.43:0 - "GET /cases/6 HTTP/1.1" 403 Forbidden
2026-11-23T08:07:47Z [APP] INFO:     10.92.70.112:0 - "GET / HTTP/1.1" 200 OK
2026-11-23T08:07:49Z [APP] INFO:     10.92.68.183:0 - "GET /cases HTTP/1.1" 200 OK
2026-11-23T08:07:51Z [APP] INFO:     10.92.54.17:0 - "GET /cases/6 HTTP/1.1" 200 OK
2026-11-23T08:08:16Z [APP] INFO:     10.92.67.129:0 - "POST /cases/5/action HTTP/1.1" 303 See Other
2026-11-23T08:08:20Z [APP] INFO:     10.92.57.165:0 - "GET /cases/5?msg=Saved HTTP/1.1" 200 OK
2026-11-23T08:08:20Z [APP] INFO:     10.92.51.229:0 - "POST /cases/5/action HTTP/1.1" 303 See Other
2026-11-23T08:08:22Z [APP] INFO:     10.92.51.220:0 - "GET /cases/5?msg=Saved HTTP/1.1" 200 OK
2026-11-23T08:08:23Z [APP] INFO:     10.92.70.112:0 - "POST /cases/5/action HTTP/1.1" 303 See Other
2026-11-23T08:08:25Z [APP] INFO:     10.92.51.220:0 - "GET /cases/5?msg=Someone+else+updated+this+case+first.+Reloaded. HTTP/1.1" 200 OK
2026-11-23T08:08:46Z [APP] INFO:     10.92.56.57:0 - "POST /ask HTTP/1.1" 200 OK
```

## The same screens as different personas (my entitlement row switched in turn, then restored to ADMIN)

| Persona | "Your data access" line (derived from Unity Catalog) | Gap tile | Lost-spend tile | Open cases tile | Governed gold in the journey strip | Wave 7 rows | Priority list | `/cases/6` (INC1, own cards) |
|---|---|---|---|---|---|---|---|---|
| P2_REGIONAL | OWN cards · regions SE | 2.52 pp | $31,877 | 1 | 2,420,664 attempts in 528,431 daily rows you can see, to 2026-11-17 | 0 | #5 | 403 |
| P4_PARTNER | THIRD_PARTY cards · regions INTL, MW, NE, SE, SW, W | 1.75 pp | $12,983 | 2 | 1,088,686 attempts in 647,696 daily rows you can see, to 2026-11-17 | 4 | #2, #7 | 403 |
| ADMIN | OWN, THIRD_PARTY cards · regions INTL, MW, NE, SE, SW, W | 1.68 pp | $112,911 | 7 | 10,933,861 attempts in 3,124,425 daily rows you can see, to 2026-11-17 | 8 | #3, #1, #5, #6, #2, #7, #4 | 200 |

- **Southeast analyst (P2):** every number is recomputed on own-card Southeast data only. The priority list shows only case #5 (INC4, the Southeast processor timeouts). Case #6 returns **403** (outside Unity Catalog access). Wave 7 rows are hidden because wave gates are national (`region = ALL`).
- **Partner operations (P4):** sees only third-party issuer data and the two third-party cases, never the bank's own portfolio.

## An edit on the case screen appears in Lakebase and in the history (case #5)

```
POST /cases/5/action [claim] -> 200 after redirect (4.74s); message: Saved
POST /cases/5/action [note] -> 200 after redirect (2.51s); message: Saved
POST /cases/5/action [stale-version write (expect conflict)] -> 200 after redirect (3.25s); message: Someone else updated this case first. Reloaded.
POST /ask -> 200 (20.79s); Genie status COMPLETED; table rows: 8; SQL shown: True
```

Lakebase afterwards (`databricks psql --project febar-ops`; the user identity is redacted in this file):

```
case_id | status  | assignee_is_signed_in_user |     owner_team     | version 
---------+---------+----------------------------+--------------------+---------
       5 | CLAIMED | t                          | Network Operations |       2
(1 row)

 event_id |   event_type   | old_value |                     new_value                      |                           note                           |      actor       | actor_type 
----------+----------------+-----------+----------------------------------------------------+----------------------------------------------------------+------------------+------------
        5 | CREATED        |           | {"n_flags": "40", "max_score": "92.5", "severity": | Case opened from flagged anomalies                       | sync_cases       | SYSTEM
       16 | MACHINE_UPDATE |           | {"n_flags": "40", "max_score": "92.5", "severity": | Machine-owned fields refreshed from gold                 | sync_cases       | SYSTEM
       19 | STATUS_CHANGE  | OPEN      | CLAIMED                                            | Taking this one                                          | <signed-in user> | USER
       20 | ASSIGN         |           | <signed-in user>                                   |                                                          | <signed-in user> | USER
       21 | NOTE           |           |                                                    | Asked Network Operations for SE processor response times | <signed-in user> | USER
(5 rows)
```

- **Claim:** status OPEN → CLAIMED with the signed-in user as assignee, version 1 → 2, **two** history rows (STATUS_CHANGE, ASSIGN).
- **Note:** one NOTE row.
- **Stale write:** the attempt with the old version was **refused** ("Someone else updated this case first"), so the owner team stayed *Network Operations*. Every row has `actor_type = USER` and the signed-in user as `actor`.

## Lakebase permissions for the App's service principal (least privilege, enforced by Postgres)

```
rolname                
--------------------------------------
 3d3fa39d-6012-499e-b96d-af94efe19d0a
(1 row)

GRANT
GRANT
GRANT
GRANT
   table_name   | privilege_type | columns_or_1 
----------------+----------------+--------------
 case_anomalies | SELECT         |            0
 case_anomalies | SELECT         |            6
 case_events    | INSERT         |            0
 case_events    | INSERT         |            9
 case_events    | SELECT         |            0
 case_events    | SELECT         |            9
 cases          | SELECT         |            0
 cases          | SELECT         |           31
 cases          | UPDATE         |           10
(9 rows)
```

- `UPDATE` is granted on the **10 human-owned columns only**, so the App cannot change machine-owned fields.
- `case_events` is `INSERT` + `SELECT` only, so the App cannot edit or delete history.
