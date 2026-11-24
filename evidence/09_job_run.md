# Evidence 09: Orchestrated job run

Generated 2026-11-24T20:16:05Z by tools/generate_evidence.py from the live workspace.

Proves that the whole flow runs as one Lakeflow job (`febar_main`): the task graph, the run used for every other evidence file (run `143622898422721`), each task's state and duration, and what each task returned (notebook exit values, the pipeline update it started, the SQL it ran). It also lists the job's recent runs.

## Job definition (Jobs API)

| item | value |
|---|---|
| job_id | 1044833224187772 |
| name | febar_main |
| max_concurrent_runs | 1 |
| queue | True |
| trigger | file_arrival /Volumes/classic_stable_zjnu75_catalog/network_migration/landing/drops/ (pause_status PAUSED) |
| tasks | 9 |
| deployed by | Declarative Automation Bundle (`resources/job.yml`) |


Task graph:

| task | type | depends on | what it runs |
|---|---|---|---|
| apply_tags | sql_task | settle_pipeline | src/governance/governance_tags.sql |
| evidence_snapshot | notebook_task | wave_readiness | src/serve/evidence_snapshot |
| explain_anomalies | notebook_task | apply_tags | src/ai/explain_anomalies |
| refresh_pipeline | pipeline_task | setup_governance | pipeline 9f46a185-fb6f-4e70-be6f-a4742066453b |
| settle_pipeline | pipeline_task | refresh_pipeline | pipeline 9f46a185-fb6f-4e70-be6f-a4742066453b |
| setup_governance | sql_task |  | src/governance/governance.sql |
| sync_cases | notebook_task | explain_anomalies | src/serve/sync_cases |
| sync_cases_back | notebook_task | sync_cases | src/serve/sync_cases_back |
| wave_readiness | sql_task | sync_cases_back | src/serve/wave_readiness.sql |


## Final run `143622898422721`

| item | value |
|---|---|
| run_id | 143622898422721 |
| trigger | ONE_TIME |
| result | SUCCESS |
| started | 2026-11-23T17:43:46Z |
| ended | 2026-11-23T17:55:02Z |
| duration s | 676 |
| run page | https://fevm-classic-stable-zjnu75.cloud.databricks.com/?o=7474654297305416#job/1044833224187772/run/143622898422721 |


| task | task run id | result | started | seconds |
|---|---|---|---|---|
| setup_governance | 1106682730922237 | SUCCESS | 2026-11-23T17:43:46Z | 20 |
| refresh_pipeline | 443219000220575 | SUCCESS | 2026-11-23T17:44:06Z | 224 |
| settle_pipeline | 58577146430534 | SUCCESS | 2026-11-23T17:47:50Z | 254 |
| apply_tags | 491131885864749 | SUCCESS | 2026-11-23T17:52:05Z | 10 |
| explain_anomalies | 972814512564110 | SUCCESS | 2026-11-23T17:52:15Z | 66 |
| sync_cases | 443993955983986 | SUCCESS | 2026-11-23T17:53:22Z | 33 |
| sync_cases_back | 315214082498731 | SUCCESS | 2026-11-23T17:53:55Z | 25 |
| wave_readiness | 43058479048867 | SUCCESS | 2026-11-23T17:54:21Z | 13 |
| evidence_snapshot | 291086743805622 | SUCCESS | 2026-11-23T17:54:35Z | 27 |


## What each task returned


### setup_governance

SQL file task; Jobs API returns the statement text it ran (90 lines). First lines:

```sql
-- =============================================================================
-- Unity Catalog governance for classic_stable_zjnu75_catalog.network_migration
-- Run by job task `setup_governance` (SQL file task on the serverless warehouse).
-- Idempotent: CREATE ... IF NOT EXISTS, MERGE, CREATE OR REPLACE FUNCTION, SET TAGS.
--
-- Model (approved 2026-11-21, DECISIONS.md):
--   personas      = what a persona may see (issuer scope, region scope, sensitive fields)
--   entitlements  = who holds which persona (user, service principal or account group)
--   Access changes are ROW CHANGES in `entitlements`; no identity is hard-coded in a function.
-- Policy functions run with the table owner's authority, so readers need no access to
-- these two tables. Policies are attached only to the tables people, Genie and the App
-- query (gold_*, auth_detail), never to tables the pipeline reads.
```


### refresh_pipeline

| item | value |
|---|---|
| pipeline update id | 76a63700-3ea5-449b-a2b4-f6581744e4f4 |
| update final state (event log) | COMPLETED |
| update started | 2026-11-23T17:44:10.832Z |
| update ended | 2026-11-23T17:47:45.453Z |

Error field: Please refer to the logs for this pipeline in the pipelines page.


### settle_pipeline

| item | value |
|---|---|
| pipeline update id | bdb37d30-faf7-44d4-a541-7b9e81022323 |
| update final state (event log) | COMPLETED |
| update started | 2026-11-23T17:47:54.631Z |
| update ended | 2026-11-23T17:52:00.025Z |

Error field: Please refer to the logs for this pipeline in the pipelines page.


### apply_tags

SQL file task; Jobs API returns the statement text it ran (25 lines). First lines:

```sql
-- =============================================================================
-- Post-pipeline governance: tags on pipeline-owned tables (run after the pipeline update,
-- because the tables must exist). Idempotent. Column comments for pipeline tables live in
-- the pipeline definitions (ALTER COLUMN COMMENT is not allowed on pipeline materialized views).
-- Tag keys are namespaced (nm_*) because generic keys are governed by other teams' tag policies.
-- =============================================================================
USE CATALOG classic_stable_zjnu75_catalog;
USE SCHEMA network_migration;

-- Consumption tables (people, Genie, App): row filter by persona.
ALTER TABLE gold_auth_daily   SET TAGS ('nm_layer' = 'gold',   'nm_data_class' = 'commercially_sensitive', 'nm_policy' = 'row_filter_persona');
ALTER TABLE gold_auth_hourly  SET TAGS ('nm_layer' = 'gold',   'nm_data_class' = 'commercially_sensitive', 'nm_policy' = 'row_filter_persona');
```


### explain_anomalies

Notebook exit value (`dbutils.notebook.exit`):

```json
{
 "threshold": 45.0,
 "volume_floor": 0,
 "flagged_total": 254,
 "explained_this_run": 0,
 "prompt_version": "v3",
 "llm_model": "databricks-claude-sonnet-4-6",
 "explanations_total": 36,
 "ok": 36,
 "errors": 0
}
```


### sync_cases

Notebook exit value (`dbutils.notebook.exit`):

```json
{
 "cases_from_gold": 7,
 "inserted": 0,
 "machine_updated": 0,
 "unchanged": 7,
 "links": 254,
 "by_status_severity": [
  [
   "CLAIMED",
   "HIGH",
   "2"
  ],
  [
   "IN_PROGRESS",
   "HIGH",
   "1"
  ],
  [
   "OPEN",
   "HIGH",
   "3"
  ],
  [
   "OPEN",
   "MEDIUM",
   "1"
  ]
 ],
 "events_total": 21,
 "prompt_version": "v3"
}
```


### sync_cases_back

Notebook exit value (`dbutils.notebook.exit`):

```json
{
 "rows": 7,
 "by_status_severity": [
  {
   "status": "CLAIMED",
   "severity": "HIGH",
   "n": 2
  },
  {
   "status": "IN_PROGRESS",
   "severity": "HIGH",
   "n": 1
  },
  {
   "status": "OPEN",
   "severity": "HIGH",
   "n": 3
  },
  {
   "status": "OPEN",
   "severity": "MEDIUM",
   "n": 1
  }
 ]
}
```


### wave_readiness

SQL file task; Jobs API returns the statement text it ran (86 lines). First lines:

```sql
-- =============================================================================
-- T5: wave readiness gate (decision 2026-11-23: option A, simple gate)
-- One row per upcoming wave (7-10) x card segment x issuer segment.
--   GO   = the segment's matched-baseline approval gap on migrated cards over the last 14 days is <= 0.3 pp
--          AND no HIGH-severity case is open for that issuer segment.
--   HOLD = otherwise, with the reason in words.
-- At-risk volume = the wave's expected daily attempts x the segment's gap (declines/day and $/day).
-- Runs as the job owner (ADMIN persona); readers see it through the persona row filter.
-- =============================================================================
USE CATALOG classic_stable_zjnu75_catalog;
USE SCHEMA network_migration;
```


### evidence_snapshot

Notebook exit value (`dbutils.notebook.exit`):

```json
{
 "latest_business_date": "2026-11-19",
 "latest_landed_business_date": "2026-11-19",
 "gold_attempts": 10992550,
 "silver_attempts": 10992550,
 "gap_pp_30d": 1.64,
 "lost_spend_30d": "107948.23",
 "flagged_anomalies": 254,
 "uc_cases": 7,
 "uc_open_cases": 7,
 "uc_open_high_own": 4,
 "wave7_hold_segments": 8,
 "wave7_segments": 8,
 "wave7_at_risk_usd_per_day": 1304.54,
 "readiness_open_high_own": 4,
 "files_reconciled_or_break": 1449,
 "file_breaks": 1,
 "lakebase_cases": 7,
 "lakebase_open_cases": 7,
 "lakebase_open_high_own": 4,
 "lakebase_case_anomalies": 254,
 "lakebase_events": 21,
 "checks": {
  "gold is as fresh as the landed data (latest gold date == latest bronze date)": true,
  "gold_attempts == silver_attempts": true,
  "uc_cases == lakebase_cases": true,
  "uc_open_cases == lakebase_open_cases": true,
  "status per case identical (UC copy vs Lakebase)": true,
  "flagged anomalies == lakebase case_anomalies": true,
  "readiness open HIGH (own) == lakebase open HIGH (own)": true,
  "only the planted file break": true
 },
 "all_checks_pass": true
}
```


## Recent runs of the job

| run_id | trigger | result | started | seconds |
|---|---|---|---|---|
| 143622898422721 | ONE_TIME | SUCCESS | 2026-11-23T17:43:46Z | 676 |
| 816748817140951 | ONE_TIME | SUCCESS | 2026-11-23T16:41:14Z | 455 |
| 321182104220187 | ONE_TIME | SUCCESS | 2026-11-23T16:33:31Z | 451 |
| 396921700125181 | ONE_TIME | SUCCESS | 2026-11-23T08:25:06Z | 417 |
| 135622324930856 | ONE_TIME | SUCCESS | 2026-11-23T08:17:38Z | 445 |
| 107587885085987 | ONE_TIME | SUCCESS | 2026-11-23T07:35:36Z | 15 |
| 117878283129238 | ONE_TIME | SUCCESS | 2026-11-23T07:29:54Z | 90 |
| 714386380834148 | ONE_TIME | SUCCESS | 2026-11-23T07:28:09Z | 46 |
| 293581557420966 | ONE_TIME | SUCCESS | 2026-11-23T07:26:11Z | 50 |
| 293336479551704 | ONE_TIME | SUCCESS | 2026-11-23T07:18:37Z | 384 |
| 630235442628047 | ONE_TIME | SUCCESS | 2026-11-21T04:31:12Z | 236 |
