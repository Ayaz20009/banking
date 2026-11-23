# Build Plan: Acceptance Risk Control for Network Migration

> **Status: APPROVED 2026-11-20.** All decisions D1–D11 and D-DATA were made on 2026-11-20 (see DECISIONS.md); each is marked (Dn ✓) where it applies. Built from FEBAR_CONTEXT.md and USE_CASE.md.
> **Namespace:** `classic_stable_zjnu75_catalog.network_migration`, referred to below as `<ns>`. This replaces the originally proposed customer-named schema, per DECISIONS.md. Both names are bundle variables.
> **Target effort:** 8.0 engineer-hours, the top of the 4–8 h budget (§6).

---

## 1. Data flow

```
 src/data/generate.py (synthetic generator, seeded; plants incidents per D-DATA)
        │  writes CSV/JSON files, one folder per source, one file per day
        ▼
 /Volumes/<cat>/<schema>/landing/  {issuer_auth, network_auth, legacy_auth, merchants, acquirers, cards, ref}
        │
        │  JOB febar_main  (trigger: file arrival on landing/)   (D11 ✓)
        │
 ┌──────┴───────────────────── T1  PIPELINE febar_pipeline (Lakeflow SDP, SQL, serverless) ──────────────────┐
 │ BRONZE (Auto Loader → streaming tables; + _source_file, _load_ts)                                         │
 │   bronze_issuer_auth  bronze_network_auth  bronze_legacy_auth  bronze_merchants  bronze_acquirers         │
 │   bronze_cards        ref_response_code_map  ref_recovery_assumptions                                     │
 │          │ expectations: drop → quarantine_auth / warn / fail   (D3 ✓)                              │
 │ SILVER                                                                                                    │
 │   silver_network_response  ← append flows: network_auth + legacy_auth, conformed fields + std category    │
 │   silver_merchants         ← merchant ID crosswalk (one merchant_key across both networks' IDs)           │
 │   silver_cards             ← AUTO CDC, SCD2 on wave / migration_date                                      │
 │   silver_auth              ← issuer_auth dedup + network response + merchant + card-as-of-event           │
 │   quarantine_auth          ← rows that failed DROP expectations, with the failed rule name                │
 │ GOLD (materialized views)                                                                                 │
 │   gold_auth_hourly         ← silver_auth                                                                  │
 │   gold_baseline_gap        ← gold_auth_hourly (migrated vs MATCHED baseline) + ref_recovery_assumptions   │
 └──────┬────────────────────────────────────────────────────────────────────────────────────────────────────┘
        ▼
 T2  detect_anomalies (Python task)  reads gold_auth_hourly + gold_baseline_gap
        │  explainable score + root-cause attribution + ai_query explanation   (D7 ✓)
        │  writes gold_anomalies (MERGE on anomaly_key → idempotent)
        ▼
 T3  upsert_cases  reads gold_anomalies ──► LAKEBASE  febar-ops / ops.cases, ops.case_events   (D6 ✓)
        │                                           ▲
        │                                           │ analysts claim / assign / resolve (App writes)
        ▼                                           │
 T4  sync_cases_back  reads Lakebase ops.cases ──► gold_case_status (MERGE on case_id)
        ▼
 T5  wave_readiness (SQL task)  reads gold_baseline_gap + gold_anomalies + gold_case_status
        │  writes gold_wave_readiness
        ▼
 T6  evidence_snapshot  reads all of the above ──► run summary JSON (exit value); tools/pull_evidence.py → evidence/*.md

 Consumers:
   GENIE AGENT  "Migration Readiness"  ← gold_baseline_gap, gold_anomalies, gold_case_status, gold_wave_readiness
   APP          febar-ops  ← reads gold_* via SQL warehouse; reads/writes Lakebase ops.cases (+ case_events);
                             Ask tab → Genie Conversation API
   GOVERNANCE   UC grants, row filter (own vs third-party issuer), column masks — applied by T0 setup_governance
```

**Why every stage is load-bearing (no stage can be deleted):**
- Without the pipeline, there is no conformed `silver_auth` and no matched baseline, so nothing to score.
- Without the AI step, there are no anomalies, so Lakebase gets no cases.
- Without Lakebase, there is no case status, so the readiness gate's "zero open high-severity cases" condition can't be computed.
- Without the back-sync, readiness and Genie can't see human work.
- Without UC governance, the App's service principal can't read anything (it is granted only through the personas), and third-party issuer rows would leak.
- Without Genie, the App's Ask tab has no backend and the VP has no plain-English path.

---

## 2. Stages

### 2.1 Lakeflow (ingest and conform)
- **For the Director:** one trusted, deduplicated view of every authorization across both networks, with every decline mapped to one standard category. No more reconciling five systems by hand.
- **Reads:** `/Volumes/<cat>/<schema>/landing/*`
- **Writes:** `bronze_*`, `ref_*`, `silver_*`, `quarantine_auth`, `gold_auth_hourly`, `gold_baseline_gap`
- **Features:**
  - Lakeflow Spark Declarative Pipelines (SQL, serverless)
  - Auto Loader (`read_files`) with schema hints and `rescuedDataColumn`
  - Append flows to fan in two networks
  - `AUTO CDC … STORED AS SCD TYPE 2` for cards
  - Expectations (drop / warn / fail)
  - Materialized views for gold
- **Idempotency:** Auto Loader checkpoints mean each file is read once. Dedup in silver on `(auth_id)` keeps the latest `_load_ts`, so a re-sent file creates no duplicates. Gold tables are materialized views, recomputed rather than appended.
- **Verify:**
  - Row counts per layer
  - Duplicate check: `SELECT auth_id, count(*) … HAVING count(*) > 1` returns 0
  - Expectation metrics from the pipeline event log
  - Rerun with no new files → zero new rows
- **Evidence:** `evidence/01_ingest.md`

### 2.2 Unity Catalog (govern)
- **For the Director:** analysts see the bank's own portfolio with card numbers masked. Third-party issuers' data on the network is separated, and the VP sees aggregates only. The data stays trustworthy enough to show a steering committee.
- **Reads / writes:** grants, row filters and masks on `silver_auth`, `silver_network_response` and `gold_*`. Writes `evidence/02_governance.md`.
- **Features:**
  - Account groups per persona (D4 ✓)
  - `GRANT USE CATALOG / USE SCHEMA / SELECT`
  - A row-filter function on `issuer_segment` (`OWN` vs `THIRD_PARTY`)
  - A column mask on `card_token` and `pan_last4`
  - Table and column comments, lineage, and tags (`pii`, `commercially_sensitive`)
- **Verify:** T0 is idempotent (`CREATE OR REPLACE FUNCTION`, re-runnable GRANTs). The access test runs as a non-admin identity (D5 ✓) and records:
  - row counts visible per persona
  - masked values visible per persona
  - a denied query per persona
  - a lineage query from `system.access.table_lineage`
- **Evidence:** `evidence/02_governance.md`

### 2.3 Lakebase (operational case store)
- **For the Director:** each anomaly becomes a case that the team claims, assigns and resolves, with an audit trail. This replaces spreadsheets and separate tickets.
- **Reads:** `gold_anomalies` (T3); App writes
- **Writes:** Postgres `ops.cases` and `ops.case_events`; `gold_case_status` (T4)
- **Features:**
  - Lakebase Autoscaling project `febar-ops` (scale-to-zero)
  - The App's Lakebase resource binding, with OAuth token refresh
  - A Postgres unique key on `anomaly_key`
  - `INSERT … ON CONFLICT (anomaly_key) DO UPDATE` that changes only *machine* fields (exposure, score), never human fields (status, owner, notes) (D6 ✓)
  - Transactional claim: `UPDATE cases SET assignee=$1, status='claimed' WHERE case_id=$2 AND status='open'`
- **Verify:**
  - Rerun T3 → case count unchanged
  - Human edits survive a rerun
  - Concurrent-claim test: two threads → one row updated, one rejected
  - App read and write latency (p50/p95 over 50 calls)
  - Resolving a case → T4 → `gold_wave_readiness` changes
- **Evidence:** `evidence/03_lakebase.md`

### 2.4 ML / GenAI (detect, attribute, explain)
- **For the Director:** detects unusual decline patterns against a matched baseline, names the likely cause and the dollar exposure, and gives a plain-English summary with the next step. Takes "4–6 hours to root cause" to "a proposed cause on the case".
- **Reads:** `gold_auth_hourly`, `gold_baseline_gap`
- **Writes:** `gold_anomalies`
- **Features** (D7 ✓): explainable score + `ai_query` explanations.
  - **Score:** for each (window, wave cohort, acquirer × channel × MCC group × region) slice, measure the decline-rate excess over the matched baseline. The z-score uses only prior windows. The concentration in a standard decline category drives root-cause attribution (e.g. `ACCEPTANCE_CONFIG`, `TOKEN_PROVISIONING`, `CROSS_BORDER_BLOCK`, `ISSUER_LEGIT`).
  - **Exposure:** excess declines × average ticket × unrecovered rate.
  - **Explanation:** `ai_query(<llm_endpoint>, prompt)` with structured output (summary, likely cause, next step, owner team), given *only* the slice's metrics.
  - Prompt and model versions are logged with MLflow.
- **Verify:** an evaluation exactly as specified in EVAL_PROTOCOL.md (D8, D9 ✓), including incident-level recall and precision against the planted ground truth, and LLM output graded by an MLflow judge.
- **Evidence:** `evidence/04_ai.md`, `evidence/eval_results.md`

### 2.5 Genie (ask)
- **For the Director and the VP:** plain-English questions such as "What spend is at risk in wave 7's e-commerce segment, and at which acquirers?" or "How many high-severity cases are still open?" No SQL ticket to the team.
- **Reads:** `gold_baseline_gap`, `gold_anomalies`, `gold_case_status`, `gold_wave_readiness`
- **Features:**
  - A Genie Agent with curated instructions, example SQL, and sample questions
  - Column descriptions taken from the UC comments
  - The definition is committed in `src/genie/space.json` and created by `tools/create_genie.py`
- **Verify:** 8 benchmark questions with expected answers, run through the Genie Conversation API. Record the generated SQL, the answer, and pass/fail against the expected value.
- **Evidence:** `evidence/05_genie.md`

### 2.6 App (act)
- **For the Director:** a command center to see anomalies, work cases and judge wave readiness.
- **Reads:** `gold_*` through the SQL warehouse; Lakebase `ops.cases` and `case_events`; Genie
- **Writes:** Lakebase (claim / assign / resolve / note)
- **Features:** Databricks Apps (framework (D10 ✓): Streamlit) with resource bindings for the SQL warehouse, Lakebase and Genie. Its service principal is granted only through UC.
- **Screens** (D10 ✓):
  1. **Anomaly feed:** a ranked list with exposure and cause.
  2. **Case workbench:** claim, assign, resolve, add notes; shows the history.
  3. **Wave readiness:** the gate for each wave and segment, with its components.
  4. **Ask:** Genie chat.
- **Verify:** `databricks apps get` shows the app RUNNING. An HTTP smoke test of each screen's API, a claim through the App reflected in `ops.case_events`, and the App logs.
- **Evidence:** `evidence/06_app.md`

---

## 3. Tables (all in `<ns>`)

**Bronze** (raw as landed, plus `_source_file` and `_load_ts`)

| Table | Grain (one row per…) | Note |
|---|---|---|
| `bronze_issuer_auth` | landed authorization record | Duplicates kept as landed |
| `bronze_network_auth` | acquired-network response event as landed | Native codes and merchant IDs |
| `bronze_legacy_auth` | legacy-network record as landed | Different field names; late files |
| `bronze_merchants` | merchant row per daily snapshot file | Network-specific merchant IDs |
| `bronze_acquirers` | acquirer row per snapshot | 80 synthetic acquirers |
| `bronze_cards` | card change record | wave / migration_date updates |
| `ref_response_code_map` | (network, native code) | → standard decline category, `is_acceptance_failure` |
| `ref_recovery_assumptions` | segment | Unrecovered-spend rate (Finance) |

**Silver** (cleaned and conformed)

| Table | Grain | Note |
|---|---|---|
| `silver_network_response` | network response for an `auth_id` | Both networks conformed to one schema + standard category |
| `silver_merchants` | `merchant_key` | Crosswalk of both networks' merchant IDs |
| `silver_cards` | card × validity period (SCD2) | Which wave a card was in *at event time* |
| `silver_auth` | authorization attempt (`auth_id`) | Deduped; issuer decision + network response + merchant + card-as-of; `issuer_segment` for the row filter |
| `quarantine_auth` | rejected record | Failed rule name + source file |

**Gold** (business-ready; five tables, as the pitfalls require)

| Table | Grain | Note |
|---|---|---|
| `gold_auth_hourly` | hour × wave cohort × network × acquirer × channel × MCC group × region | Attempts, approvals, declines by standard category, amount |
| `gold_baseline_gap` | day × wave cohort × match segment | Migrated vs matched-baseline approval rate, gap (pp), excess declines, lost spend ($); also shows the unmatched gap for comparison |
| `gold_anomalies` | anomaly (`anomaly_key` = window + slice) | Score, root cause, exposure, severity, LLM summary / next step / owner team, model + prompt version |
| `gold_case_status` | case (`case_id`) | Mirror of Lakebase `ops.cases`: status, owner, resolved_at, recovered spend |
| `gold_wave_readiness` | wave × segment | Gap vs the 0.3 pp gate, open high-severity cases, at-risk volume, segment risk, explicit weights, GO/HOLD |

**Lakebase** (Postgres, project `febar-ops`, database `ops`)

| Table | Grain | Note |
|---|---|---|
| `cases` | case (unique `anomaly_key`) | Machine fields (from T3) + human fields (from the App) |
| `case_events` | event | Append-only audit trail (who, what, when) |

---


**As built (step 2, 2026-11-21):**
- `bronze_manifests` became `bronze_file_manifests`, a Python materialized view: files starting with `_` are hidden from `read_files`.
- Added `silver_issuer_auth` (dedup on `auth_id`), `silver_acquirers`, `recon_file_control` (per-file control totals), and the private staging tables `stg_issuer_auth` and `stg_cards`, which carry the expectations.
- **App (step 7):** FastAPI + Jinja (`src/app`, `resources/app.yml`), screens Overview / Priority list / Case view / Ask Genie; OBO user token for UC and Genie; Lakebase as the App SP with column-level grants.
- **Readiness + Genie (step 6):** `febar_main` T5 `wave_readiness` → `gold_wave_readiness`. Genie space over 5 gold tables (`src/genie/space.json`, id in `src/genie/space_id.txt`).
- **Lakebase (step 5):** project `febar-ops`, schema `ops` (`cases` per episode, `case_anomalies`, `case_events`); `febar_main` T2 explain (case representatives) → T3 `sync_cases` → T4 `sync_cases_back` → `gold_case_status`. The `gold_case_flags` view groups flags into episodes.
- **Governance (step 3):** `personas` + `entitlements` tables; row filter + `card_ref` mask on gold_* and a new consumption table `auth_detail` (60-day transaction detail for the App). `febar_main` now runs T0 `setup_governance` → T1 `refresh_pipeline` → T1b `apply_tags`.
- **Gold grain (decision 2026-11-21):** `gold_auth_daily` (day × all dimensions, scored by detection) + `gold_auth_hourly` (hour × network × region × channel × issuer segment).
- `silver_merchants` is the latest record per merchant, a materialized view, instead of a crosswalk table: normalised IDs for both networks sit on the same row.

## 4. Bundle layout

```
databricks.yml
  bundle: febar
  variables:
    catalog          default: classic_stable_zjnu75_catalog
    schema           default: network_migration
    warehouse_id     default: 34e45919b39491cf      # Serverless Starter Warehouse
    llm_endpoint     default: <chosen at build time: a pay-per-token foundation model endpoint>
    lakebase_project default: febar-ops
    app_name         default: febar-ops-${workspace.current_user.domain_friendly_name}  (≤ 30 chars, checked)
  targets:
    dev: { mode: development, default: true, workspace: { host: https://fevm-classic-stable-zjnu75.cloud.databricks.com } }

resources/
  febar.schema.yml       schema network_migration + volume landing (managed)
  febar.pipeline.yml     febar_pipeline: serverless SDP, SQL in src/pipeline/, catalog/schema from vars
  febar_main.job.yml     febar_main: T0–T6, file-arrival trigger on the landing volume
  febar_replay.job.yml   febar_replay: generate / drop the next day of synthetic files (manual; used to demo detection)
  febar.app.yml          febar_app: source src/app/, bindings for the SQL warehouse, Lakebase and Genie
  (Lakebase project: a bundle resource if the CLI version supports postgres projects; otherwise tools/create_lakebase.py, idempotent; checked at build time)
```

Commands: `databricks bundle validate --strict --profile febar` → `databricks bundle deploy --profile febar` → `databricks bundle run febar_main --profile febar`.

---

## 5. Orchestration: one job, `febar_main`

| Task | Type | Depends on | Does | Exit summary |
|---|---|---|---|---|
| T0 `setup_governance` | SQL file | — | Groups' grants, row filter, masks, comments, tags (idempotent) | grants applied, functions created |
| T1 `refresh_pipeline` | pipeline task | T0 | Incremental update of `febar_pipeline` | rows per table, expectation pass/fail |
| T2 `detect_anomalies` | notebook | T1 | Score + attribute + `ai_query` → MERGE `gold_anomalies` | windows scored, anomalies new/updated, LLM calls |
| T3 `upsert_cases` | notebook | T2 | `gold_anomalies` → Lakebase `cases` (ON CONFLICT, human fields kept) | cases inserted/updated/unchanged |
| T4 `sync_cases_back` | notebook | T3 | Lakebase `cases` → MERGE `gold_case_status` | rows merged |
| T5 `wave_readiness` | SQL file | T4 | Rebuild `gold_wave_readiness` | waves GO/HOLD |
| T6 `evidence_snapshot` | notebook | T5 | Collect counts, checks and latency into one JSON | all checks pass/fail |

- **Trigger:** file arrival on `/Volumes/<cat>/<schema>/landing/` (D11 ✓), with a 60 s minimum interval between triggers. Manual run is always available.
- **Demo loop:** run `febar_replay` → a file lands → `febar_main` fires → a new anomaly appears in the App. The time from landing to anomaly is recorded as the measured detection latency.
- **Separately:** the evaluation (`src/ai/evaluate.py`) runs once, as a task in `febar_replay` with `mode=eval`, after all 60 days have landed.

---

## 6. Time plan (8.0 h)

| # | Stage | Hours | Done when |
|---|---|---|---|
| 0 | Bundle skeleton, schema/volume, EVAL_PROTOCOL.md committed | 0.5 | `bundle validate` passes; protocol committed *before* any results |
| 1 | Synthetic generator + planted incidents | 1.0 | Files in the volume; generator prints row counts and an incident manifest |
| 2 | Lakeflow pipeline (bronze → silver → gold) | 1.5 | Pipeline run green; duplicate check = 0; expectation metrics captured |
| 3 | UC governance + access test | 0.75 | Persona visibility matrix in evidence |
| 4 | AI: score + attribution + `ai_query` + evaluation | 1.25 | `eval_results.md` against the protocol |
| 5 | Lakebase: project, tables, T3/T4, concurrency test | 1.0 | Idempotent rerun, human edits survive, concurrent-claim result |
| 6 | Genie Agent + benchmark | 0.5 | 8 questions with pass/fail |
| 7 | App (3 core screens + Ask) + deploy | 1.0 | RUNNING; a claim through the App appears in `case_events` |
| 8 | Wire the job, end-to-end run, evidence pull | 0.5 | `febar_main` green from a file arrival; `evidence/*.md` committed |
| | **Total** | **8.0** | No buffer. If late, cut in this order: (a) App Ask screen (Genie is still proven by `evidence/05`), (b) the stretch sources (already out), (c) LLM-judge grading down to a rule-based grounding check |

---

## Decisions (all made 2026-11-20, see DECISIONS.md)

D1 Ingestion · D2 One or two sources · D3 Data quality · D4 Personas · D5 Access-test identity · D6 Lakebase pattern · D7 Intelligent step · D8 AI evaluation · D9 EVAL_PROTOCOL · D10 App framework + screens · D11 Trigger · D-DATA Planted data issues
