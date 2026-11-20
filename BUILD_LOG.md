# Build Log

| Date | Tried | Failed | Changed and why |
|---|---|---|---|
| 2026-11-20 | Installed the Databricks CLI (v1.27.0) and `databricks aitools install` | Homebrew refused the untrusted tap | Trusted only the `databricks/tap/databricks` formula, then installed |
| 2026-11-20 | Wrote FEBAR_CONTEXT.md and the CLAUDE.md pointer | — | Neutral UC names to follow the no-names rule |
| 2026-11-20 | `databricks auth login` / `auth describe --profile febar` | — | Authenticated as a workspace admin |
| 2026-11-20 | Read-only access checks: metastore grants, warehouses, Lakebase | No CREATE_CATALOG on the metastore, so the `febar` catalog can't be created | Chose `classic_stable_zjnu75_catalog.network_migration` |
