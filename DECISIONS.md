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
