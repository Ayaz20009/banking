# Evidence 09: Orchestration, one Lakeflow Job (`febar_main`)

- **Definition:** `resources/job.yml` (job id `1044833224187772`). `max_concurrent_runs: 1`, **queue enabled** (overlapping runs wait).
- **Trigger:** a file-arrival trigger is configured on `/Volumes/classic_stable_zjnu75_catalog/network_migration/landing/drops/`, where the generator writes `DROP_COMPLETE_<date>.json` **last**. It is **PAUSED**: the job runs **manually** (decision 2026-11-23, section 3 below).
- **Task chain:** every task has an explicit dependency, so nothing races.

```
setup_governance → refresh_pipeline → settle_pipeline → apply_tags → explain_anomalies → sync_cases → sync_cases_back → wave_readiness → evidence_snapshot
```

| Task | Type | Does |
|---|---|---|
| setup_governance | SQL file | Personas, entitlements, row-filter / mask functions, schema tags |
| refresh_pipeline | pipeline | Incremental Lakeflow update (ingest new files → silver → gold → scores) |
| settle_pipeline | pipeline | Second update that recomputes the views from committed inputs (section 4) |
| apply_tags | SQL file | Tags on pipeline-owned tables |
| explain_anomalies | notebook | Flags with the frozen threshold (45) → `gold_anomalies`; `ai_query` on each case's top flag (v3) |
| sync_cases | notebook | Cases into Lakebase (machine columns only, history events) |
| sync_cases_back | notebook | Lakebase → `gold_case_status` (row filter) |
| wave_readiness | SQL file | GO/HOLD gate + at-risk volume |
| evidence_snapshot | notebook | Cross-checks gold vs Lakebase vs readiness and freshness; the exit value is the snapshot |

## 1. Runs (from `databricks jobs get-run` / `get-run-output`)

| Run | Run ID | Trigger | Result | Duration |
|---|---|---|---|---|
| 1: first run (data to 11-17) | `135622324930856` | ONE_TIME (manual) | SUCCESS | 445 s |
| 2: rerun, no new data | `396921700125181` | ONE_TIME (manual) | SUCCESS | 417 s |
| 3: after the 11-18/19 drops landed | `321182104220187` | ONE_TIME (manual) | SUCCESS | 451 s |
| 4: rerun | `816748817140951` | ONE_TIME (manual) | SUCCESS | 455 s |
| 5: after adding settle_pipeline + freshness check | `143622898422721` | ONE_TIME (manual) | SUCCESS | 676 s |

The runs started from the existing state (no full refresh of the pipeline or Lakebase); the first full load is in evidence/01.

### Task states, durations and exit values

**Run 1: first run (data to 11-17)** (`135622324930856`)

| Task | State | Seconds | Exit value (key fields) |
|---|---|---|---|
| setup_governance | SUCCESS | 14 | `` |
| refresh_pipeline | SUCCESS | 233 | `` |
| apply_tags | SUCCESS | 10 | `` |
| explain_anomalies | SUCCESS | 58 | `{"explained_this_run": 0, "flagged_total": 254}` |
| sync_cases | SUCCESS | 37 | `{"cases_from_gold": 7, "inserted": 0, "machine_updated": 0, "unchanged": 7}` |
| sync_cases_back | SUCCESS | 25 | `{"rows": 7}` |
| wave_readiness | SUCCESS | 9 | `` |
| evidence_snapshot | SUCCESS | 39 | `{"latest_business_date": "2026-11-17", "gold_attempts": 10933861, "all_checks_pass": true}` |

**Run 2: rerun, no new data** (`396921700125181`)

| Task | State | Seconds | Exit value (key fields) |
|---|---|---|---|
| setup_governance | SUCCESS | 11 | `` |
| refresh_pipeline | SUCCESS | 213 | `` |
| apply_tags | SUCCESS | 9 | `` |
| explain_anomalies | SUCCESS | 61 | `{"explained_this_run": 0, "flagged_total": 254}` |
| sync_cases | SUCCESS | 38 | `{"cases_from_gold": 7, "inserted": 0, "machine_updated": 0, "unchanged": 7}` |
| sync_cases_back | SUCCESS | 25 | `{"rows": 7}` |
| wave_readiness | SUCCESS | 9 | `` |
| evidence_snapshot | SUCCESS | 29 | `{"latest_business_date": "2026-11-17", "gold_attempts": 10933861, "all_checks_pass": true}` |

**Run 3: after the 11-18/19 drops landed** (`321182104220187`)

| Task | State | Seconds | Exit value (key fields) |
|---|---|---|---|
| setup_governance | SUCCESS | 24 | `` |
| refresh_pipeline | SUCCESS | 244 | `` |
| apply_tags | SUCCESS | 11 | `` |
| explain_anomalies | SUCCESS | 59 | `{"explained_this_run": 0, "flagged_total": 254}` |
| sync_cases | SUCCESS | 28 | `{"cases_from_gold": 7, "inserted": 0, "machine_updated": 0, "unchanged": 7}` |
| sync_cases_back | SUCCESS | 22 | `{"rows": 7}` |
| wave_readiness | SUCCESS | 13 | `` |
| evidence_snapshot | SUCCESS | 30 | `{"latest_business_date": "2026-11-17", "gold_attempts": 10933861, "all_checks_pass": true}` |

**Run 4: rerun** (`816748817140951`)

| Task | State | Seconds | Exit value (key fields) |
|---|---|---|---|
| setup_governance | SUCCESS | 13 | `` |
| refresh_pipeline | SUCCESS | 253 | `` |
| apply_tags | SUCCESS | 10 | `` |
| explain_anomalies | SUCCESS | 71 | `{"explained_this_run": 0, "flagged_total": 254}` |
| sync_cases | SUCCESS | 32 | `{"cases_from_gold": 7, "inserted": 0, "machine_updated": 0, "unchanged": 7}` |
| sync_cases_back | SUCCESS | 22 | `{"rows": 7}` |
| wave_readiness | SUCCESS | 8 | `` |
| evidence_snapshot | SUCCESS | 26 | `{"latest_business_date": "2026-11-19", "gold_attempts": 10992550, "all_checks_pass": true}` |

**Run 5: after adding settle_pipeline + freshness check** (`143622898422721`)

| Task | State | Seconds | Exit value (key fields) |
|---|---|---|---|
| setup_governance | SUCCESS | 19 | `` |
| refresh_pipeline | SUCCESS | 223 | `` |
| settle_pipeline | SUCCESS | 253 | `` |
| apply_tags | SUCCESS | 9 | `` |
| explain_anomalies | SUCCESS | 62 | `{"explained_this_run": 0, "flagged_total": 254}` |
| sync_cases | SUCCESS | 29 | `{"cases_from_gold": 7, "inserted": 0, "machine_updated": 0, "unchanged": 7}` |
| sync_cases_back | SUCCESS | 23 | `{"rows": 7}` |
| wave_readiness | SUCCESS | 13 | `` |
| evidence_snapshot | SUCCESS | 23 | `{"latest_business_date": "2026-11-19", "latest_landed_business_date": "2026-11-19", "gold_attempts": 10992550, "all_checks_pass": true}` |

### Full `evidence_snapshot` exit value of the final run

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

## 2. Reruns are safe

- **Runs 1 → 2 (no new data):** `sync_cases` reported 7 unchanged, 0 inserted, 0 updated. The snapshot values were identical (10,933,861 attempts, gap 1.68 pp, 7 cases).
- **Runs 4 → 5 (no new data):** identical again (10,992,550 attempts, gap 1.64 pp, 7 cases, 254 flags). Lakebase events did not grow from machine refreshes. All 8 checks passed in run 5.

## 3. The file-arrival trigger did not fire in this workspace (recorded, not hidden)

The generator's replay job (`mode=replay`) landed each held-back day and wrote the drop marker **last**:

```
2026-11-23T08:32:12Z replay 2026-11-18: generator start
2026-11-23T15:35:19Z (first replay attempt at 08:32 never started: wrong run-now flag; relaunched)
2026-11-23T15:35:19Z replay 2026-11-18: generator start
generator_run_2026-11-18 365515320351450
2026-11-23T15:38:11Z replay 2026-11-18: drop marker present
2026-11-23T15:58:33Z replay 2026-11-18: febar_main run detected 396921700125181 (was 396921700125181)
2026-11-23T15:58:33Z replay 2026-11-19: generator start
generator_run_2026-11-19 238464759760791
2026-11-23T16:01:25Z replay 2026-11-19: drop marker present
2026-11-23T16:21:47Z replay 2026-11-19: febar_main run detected 396921700125181 (was 396921700125181)
2026-11-23T16:33:31Z test marker removed; trigger PAUSED (manual-only decision)
```

- **No run started:** across the two real markers (10:38 and 11:01 workspace time, `DROP_COMPLETE_20261118.json` and `DROP_COMPLETE_20261119.json`) and a later test marker, no `febar_main` run started within 20, 20 and 6 minutes. (My script's "febar_main run detected" lines above refer to the *previous* manual run; it gave up waiting.)
- **The trigger was never monitored:** the job's `trigger_state` stayed **null** after a pause/unpause reset.
- **Likely cause:** the external location under this catalog has **file events disabled**. It is shared, so it was not changed.
- **Decision (submitter, 2026-11-23):** **manual runs**. The trigger stays configured but PAUSED, and the test marker was deleted. The very first replay attempt (08:32) never started at all because of a wrong CLI flag in my script; it was relaunched.

## 4. Defect found and fixed: gold lagged one drop in run 3

- **Run 3** ingested the 11-18/19 files into bronze at 16:36 (`bronze_issuer_auth._ingested_at`). Its snapshot still showed gold at **2026-11-17**; **run 4** then showed 2026-11-19.
- **Cause, from the pipeline event log for update `b5496068…`:** `silver_auth` started (16:37:00) **before** its input `silver_issuer_auth` completed (16:37:02), so it read the previous version. The dependency **is** declared (the `flow_definition` inputs of `silver_auth` include `silver_issuer_auth`).
- **Fix:**
  - a `settle_pipeline` task (a second, ingest-free update that recomputes the views from committed inputs);
  - a **freshness check** in `evidence_snapshot` (latest gold date = latest landed bronze date), which would have caught run 3.
- **Run 5** passes with the fix.

## 5. Supplementary evaluation, window days 41–60 (EVAL_PROTOCOL Amendment 3; the primary days 41–58 result stays unchanged)

- **Run:** `febar_ai` `541626412450276`, label `eval_supp_41_60`, held out 2026-10-31 → 2026-11-19, protocol "v1 + A1 + A2 + A3 + Errata 1".
- **Method:** 210 flags, 210 hits (100%), incidents ['INC3', 'INC4'], decoy-driven flags 0.
- **Baseline:** 304 flags, 31 hits (10.2%), decoy-driven 125.
- **No-claim conditions:** `{"beats_baseline_by_20pts_at_equal_or_better_precision": false, "decoy_flagged_by_method": false, "method_precision_below_50pct": false, "look_ahead_detected": false}` (condition 1 still triggered: both caught 2/2). Holdout days without data: [].
- **Result:** the two demo days added **no** method flags and 8 baseline false alarms.

## 6. Numbers agree across gold, Lakebase, Genie and the App (after the final run)

| Number | Gold / Lakebase (evidence_snapshot) | Genie (Conversation API) | App overview (`/`) |
|---|---|---|---|
| Latest business date | 2026-11-19 | 2026-11-19 | 2026-11-19 |
| Approval gap, last 30 days (pp) | 1.64 | 1.6449 | 1.64 |
| Lost spend, last 30 days (USD) | 107948.23 | 107948.23 | 107,948 |
| Open cases | UC 7 = Lakebase 7 | 7 | 7 |
| Wave 7 at-risk spend per day (USD) | 1304.54 | 1304.54 | 1,305 |
| Wave 7 segments on HOLD | 8 of 8 | 8 | HOLD |

## 7. Which numbers to use

- **Final state:** all 12 months are now landed (to 2026-11-19), and this file holds the **final** headline numbers. **The deck must use these.**
- **Earlier evidence is dated snapshots** taken before the two demo days landed: 01 (pipeline), 05 (AI evaluation, primary held-out days 41–58), 06, 07, 08 (Genie benchmarks; ground truth then ended 2026-11-17) and 10 (App). They stay as they are, so their numbers end at 2026-11-17 (e.g. gap 1.68 pp, lost spend $112,911).
- **No new data will be landed** after this evidence.
