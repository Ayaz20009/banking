# Decisions

> [YOUR WORDS] Drafted by AI from your choices. Rewrite each entry in your own words.

## 2026-11-20 — Unity Catalog naming
- **Decision:** use `febar.network_migration` instead of the originally proposed schema, which named the customer and the network.
- **Options considered:** (A) keep the customer-named schema; (B) neutral `febar.network_migration`; (C) existing sandbox catalog with a neutral schema.
- **Why:** [YOUR WORDS] The original names contain the customer's name and the acquired network's name, which breaks the FE Bar no-names rule.

## 2026-11-20 — Workspace and CLI profile
- **Decision:** workspace `fevm-classic-stable-zjnu75`, CLI profile `febar`.
- **Why:** [YOUR WORDS]

## 2026-11-20 — Catalog location (supersedes the `febar` catalog)
- **Decision:** use `classic_stable_zjnu75_catalog.network_migration`.
- **Options considered:** (A) the workspace default catalog; (B) request CREATE_CATALOG for `febar`; (C) default now, migrate later.
- **Why:** [YOUR WORDS] No CREATE_CATALOG on the metastore. You already have ALL_PRIVILEGES and MANAGE on the default catalog, so nothing blocks the build. The catalog stays a bundle variable.

## 2026-11-20 — Use case story and scope
- **Decision:** story B, Decline Triage + Next-Wave Gate, framed by your discovery answers. All five challenge fixes applied.
- **Options considered:** (A) Readiness Control Tower; (B) Decline Triage + Next-Wave Gate; (C) Card-on-File Continuity.
- **Scope:** five core sources (issuer auths, acquired-network feed, legacy feed, merchant/acquirer reference, cards and waves) plus two small static tables. Complaints and token events are stretch only.
- **Value:** three scenarios (1/3, 2/3, ~0.78 of the gap fixable) → $9.2M / $18.5M / $21.6M a year per wave cohort.
- **Why:** [YOUR WORDS] A narrow, fully evidenced build scores better than a broad one; a range is easier to defend than one assumed number; the unverified regulatory claims were removed.

---

# Build design decisions (2026-11-20)

> [REWRITE IN YOUR WORDS] All eleven build decisions plus the planted-data design. You chose the recommended option for each. The "Why" lines are AI drafts.

## D1 — Ingestion
- **Decision:** synthetic files in a UC volume, read with Auto Loader.
- **Alternatives:** Lakeflow Connect or Zerobus streaming ingest.
- **Why:** [REWRITE IN YOUR WORDS] Easy to replay, shows schema handling and late files, and file arrival can trigger the job. Streaming ingest adds setup and risk for little extra evidence.

## D2 — One source or two
- **Decision:** two network feeds (new + legacy) merged into one conformed schema.
- **Alternatives:** a single feed.
- **Why:** [REWRITE IN YOUR WORDS] Reconciling different codes and merchant IDs is the Director's main pain; one feed would lose the story. About 30 min extra.

## D3 — Data quality rules
- **Decision:** balanced.
  - **Fail the update:** null primary key in cards or merchants; empty decline-code map.
  - **Drop to quarantine:** null `auth_id`, an amount that won't parse or is ≤ 0, a future timestamp.
  - **Warn:** unmapped native code (`UNMAPPED`), legacy file > 24 h late, stale MCC.
- **Alternatives:** strict (also quarantine unmapped codes).
- **Why:** [REWRITE IN YOUR WORDS] Unmapped new-network codes may *be* the incident; hiding them in quarantine would remove the signal.

## D4 — Governance personas
- **Decision:** three personas.
  - `ops_analyst`: the bank's own portfolio, card fields masked.
  - `network_partner_ops`: third-party issuer rows only.
  - `exec_viewer`: gold tables only.
- **Alternatives:** two personas (analyst / exec).
- **Why:** [REWRITE IN YOUR WORDS] Separating third-party issuers' data is the strongest governance argument in the case.

## D5 — Access-test identity
- **Decision:** a dedicated workspace service principal in `ops_analyst`. Its OAuth secret never appears in output, logs or the repo.
- **Alternatives:** the App's own service principal.
- **Why:** [REWRITE IN YOUR WORDS] Same queries, different identity, different results: clean, text-only evidence.

## D6 — Lakebase pattern
- **Decision:** a job task upserts cases (`ON CONFLICT` updates only machine fields); human fields are never overwritten.
- **Alternatives:** a synced table from gold.
- **Why:** [REWRITE IN YOUR WORDS] Synced tables are read-only in Postgres; analysts must write claims and notes to the same rows.

## D7 — Intelligent step
- **Decision:** an explainable score (decline excess over the matched baseline + the decline category it concentrates in → root cause) plus `ai_query` explanations.
- **Alternatives:** a trained model; both.
- **Why:** [REWRITE IN YOUR WORDS] Defensible to a steering committee, predictable cost, and fits the time budget; a model trained on our own planted labels adds little.

## D8 — AI evaluation
- **Decision:** detection measured against the planted incidents, plus an MLflow LLM judge on 30 explanations (grounding, cause agreement, actionability).
- **Alternatives:** rule-based checks only.
- **Why:** [REWRITE IN YOUR WORDS]

## D9 — Evaluation protocol
- **Decision:** EVAL_PROTOCOL.md as committed on 2026-11-20: fixed-threshold baseline; time-based holdout (days 41–60, unseen incidents + a decoy); main measure = held-out incidents caught at ≥ 80% precision; as-of timing rule; explicit no-claim conditions.
- **Alternatives:** split by acquirer instead of by time.
- **Why:** [REWRITE IN YOUR WORDS] A time split mirrors real use and prevents look-ahead.

## D10 — App
- **Decision:** Streamlit. Screens: Anomaly feed, Case workbench, Wave readiness, Ask (Genie).
- **Alternatives:** AppKit (Node/React); FastAPI + HTMX.
- **Why:** [REWRITE IN YOUR WORDS] Fastest path; Python end to end.

## D11 — Trigger
- **Decision:** file arrival on the raw volume (60 s minimum interval), plus manual runs.
- **Alternatives:** every 15 min on a schedule; manual only.
- **Why:** [REWRITE IN YOUR WORDS] Shows minute-level detection and yields a measured latency.

## D-DATA — Planted data issues
- **Decision:**
  - **Data quality problems:** about 2% duplicate retries; 3 late legacy files; field names that differ between networks; about 15% of merchants with different IDs per network; about 0.5% bad amounts or timestamps; 12 unmapped new-network codes.
  - **Incidents:** #1 ACQ-017 e-commerce token misconfiguration after wave 6 (about 200 merchants); #2 international block for one MCC group; #3 (held out) recurring charges failing after reissue; #4 (held out) a regional processor timing out.
  - **Decoy:** a holiday spike in legitimate insufficient-funds declines.
- **Alternatives:** incident #1 + the decoy only.
- **Why:** [REWRITE IN YOUR WORDS] Enough distinct incidents for a held-out test; the decoy proves the method separates acceptance failures from legitimate issuer declines.

## 2026-11-20 — Synthetic source data design
- **Decision:** approved as proposed.
  - 7 source systems; 12 months; about 30K attempts a day (about 11M); invented "Meridian" (acquired) and "Atlas" (legacy) networks.
  - Messiness and planted findings: DQ1–DQ10, INC1–INC4 plus a decoy.
  - The landing volume is renamed `raw` → `landing`; the last 60 days form the evaluation window (EVAL_PROTOCOL Amendment 1).
- **Alternatives:** 15K/day (faster, sparser slices); 60 days only (conflicts with the 12-month requirement).
- **Why:** [REWRITE IN YOUR WORDS]

## 2026-11-21 — Gold grain
- **Decision:** option A. `gold_auth_daily` keeps all the dimensions at day grain (the table detection scores); `gold_auth_hourly` is redefined as a small hourly table by network × region × channel × issuer segment (intraday timing).
- **Alternatives:** (B) keep the hourly × 9-dimension table (7.9M rows) and have detection roll up itself.
- **Why:** [REWRITE IN YOUR WORDS] At 1:270 scale the hourly grain was almost row-level, too sparse to score and slow for Genie and the App.

## 2026-11-21 — Governance personas and policies (refines D4)
- **Decision:** four personas plus ADMIN.
  - P1 Director (OWN, all regions, card_ref masked); P2 Southeast analyst (OWN, SE, masked); P3 Card investigations (OWN, all regions, card_ref clear); P4 Partner ops (THIRD_PARTY only, masked).
  - Entitlements live in tables (`personas`, `entitlements`); one row filter on (issuer_segment, region) and one card_ref mask.
  - Policies apply only to the consumption tables (gold_*, new `auth_detail`); the service principal tested as P2.
- **Alternatives:** the three D4 personas without regional scope; group-based grants (not possible: no account-admin rights to create account groups).
- **Why:** [REWRITE IN YOUR WORDS]

## 2026-11-23 — Intelligent step and evaluation amendment
- **Decision:** option A (D7 confirmed).
  - An explainable 0–100 score per Meridian slice-day, from five named components: excess, impact, clarity, breadth, persistence.
  - Five slice families: acquirer × channel, MCC group × cross-border, region, channel, card segment.
  - `ai_query` explains the top flagged items only; judges come from a different model family. EVAL_PROTOCOL Amendment 2 (daily grain, own-history expected rate, 50% overlap rule).
- **Alternatives:** (B) a trained model; (C) A plus `ai_classify` on config notes.
- **Why:** [REWRITE IN YOUR WORDS]

## 2026-11-23 — Held-out days vs the live demo
- **Decision:** the primary held-out result uses window days 41–58; days 59–60 stay unlanded for the live demo, with a supplementary rerun on 41–60 afterwards (EVAL_PROTOCOL Amendment 3).
- **Alternatives:** land 11-18/19 now and evaluate 41–60 exactly as written (loses the live demo days).
- **Why:** [REWRITE IN YOUR WORDS]

## 2026-11-23 — Lakebase case store design
- **Decision:** one case per episode (same root cause + issuer segment, gap ≤ 1 day). Statuses OPEN, CLAIMED, IN_PROGRESS, WAITING_PARTNER, RESOLVED, DISMISSED; resolution codes ACQUIRER_FIX, CONFIG_CHANGE, CREDENTIAL_REFRESH, PROCESSOR_FIX, FALSE_POSITIVE, OTHER; severity HIGH if max score ≥ 70. Job-task upsert (machine columns only) plus history events; T4 copies cases back to UC. Cases carry the v3 explanation (second iteration approved).
- **Alternatives:** one case per flagged anomaly (254 cases, noisy); a synced table (read-only in Postgres).
- **Why:** [REWRITE IN YOUR WORDS]

## 2026-11-23 — Genie benchmarks and readiness rule
- **Decision:** benchmark questions 1, 3, 4, 7, 8, 13, 14, 15 (of 15 proposed). Readiness option A: a wave segment is GO only if its migrated approval gap over the last 14 days is ≤ 0.3 pp and no HIGH-severity case is open; at-risk volume = expected daily attempts × gap.
- **Alternatives:** a weighted 0–100 readiness score (GO ≥ 80).
- **Why:** [REWRITE IN YOUR WORDS]

## 2026-11-23 — App framework, look and screens (changes D10)
- **Decision:**
  - **Framework:** FastAPI + Jinja on uvicorn (replaces D10 Streamlit).
  - **Look:** clean neutral (white, one slate accent, status colours only for GO/HOLD and severity, no logos).
  - **Screens:** Overview (VP), Priority list (Director), Case view (analyst acts), Ask Genie.
  - **Access:** gold and Genie with the user's token; Lakebase cases shown only if Unity Catalog lets the user see the case_id.
- **Alternatives:** keep Streamlit; Flask + gunicorn; dark theme; framework default styling.
- **Why:** [REWRITE IN YOUR WORDS]

## 2026-11-23 — Job trigger: manual runs (supersedes D11 file arrival)
- **Decision:** `febar_main` runs manually. The file-arrival trigger stays configured on `landing/drops/` (the generator writes the drop-complete marker last) but is **PAUSED**.
- **Why it changed:** in this workspace the trigger never fired. Two real drop markers and one test marker produced no run in 20 / 20 / 6 minutes; `trigger_state` stayed null after a pause/unpause reset. The external location under the catalog has file events disabled; it is shared, so it was not changed.
- **Alternatives:** the generator's replay job starts `febar_main` (run_job_task); ask the platform team for file events; a 15-minute schedule.
- **Why:** [REWRITE IN YOUR WORDS]
