# Build Log

| Date | Tried | Failed | Changed and why |
|---|---|---|---|
| 2026-11-20 | Installed the Databricks CLI (v1.27.0) and `databricks aitools install` | Homebrew refused the untrusted tap | Trusted only the `databricks/tap/databricks` formula, then installed |
| 2026-11-20 | Wrote FEBAR_CONTEXT.md and the CLAUDE.md pointer | — | Neutral UC names to follow the no-names rule |
| 2026-11-20 | `databricks auth login` / `auth describe --profile febar` | — | Authenticated as a workspace admin |
| 2026-11-20 | Read-only access checks: metastore grants, warehouses, Lakebase | No CREATE_CATALOG on the metastore, so the `febar` catalog can't be created | Chose `classic_stable_zjnu75_catalog.network_migration` |
| 2026-11-20 | Ran discovery (8 questions) and drafted USE_CASE.md from your answers; checked the value math | Push failed: no GitHub credentials on this machine | Value table built on your figures; added assumptions are marked [ASSUMPTION]; awaiting approval |
| 2026-11-20 | Applied 5 challenge fixes to USE_CASE.md | — | Scope to 5 core sources, 3 value scenarios, ML scored on planted incidents, [CHECK] claims removed, 5-min framed as a target |
| 2026-11-20 | Applied the "Lakebase looks bolted on" fix to USE_CASE.md §8.3 | — | Lakebase as the system of record for analyst work: transactional claims, case_events audit trail, two-way flow into the readiness gate and Genie, committed evidence tests |
| 2026-11-20 | Drafted BUILD_PLAN.md; you chose all recommended options (D1–D11, D-DATA); wrote DECISIONS.md and EVAL_PROTOCOL.md | First time plan added up to 8.25 h, over budget | Trimmed the App to 1.0 h and listed the cut order; protocol committed before any data exists |
| 2026-11-20 | Step 0: bundle skeleton (databricks.yml + schema and volume resources), deployed | `validate --strict` recommended one schema per `.schema.yml` file; `mode: development` would have prefixed the schema name | Split into `network_migration.schema.yml` + `raw.volume.yml`; used a plain target with an explicit root_path; redeploy idempotent (2 unchanged); email redacted from evidence |
