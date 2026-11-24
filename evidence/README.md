# Evidence index

Generated 2026-11-24T20:16:08Z by tools/generate_evidence.py from the live workspace.

Each file below was generated from the live workspace by `tools/generate_evidence.py` and is plain text, so it can be read without opening the workspace. All files describe the same final state: the orchestrated job run below, after which no data was landed and the pipeline was not refreshed.

## Final state these files describe

| item | value |
|---|---|
| final job run | 143622898422721 (SUCCESS, ended 2026-11-23T17:55:02Z) |
| pipeline updates started after that run | 0 |
| auth rows ingested after that run | 0 |
| latest business date in gold | 2026-11-19 |
| API access used | Databricks CLI |


## Files

| file | what it proves | generated (UTC) |
|---|---|---|
| [00_answer_key.md](00_answer_key.md) | Answer key of every planted data issue and incident (written by the generator; the pipeline never reads it). | kept (written earlier, not regenerated) |
| [01_pipeline_run.md](01_pipeline_run.md) | Lakeflow pipeline updates in the final run, rows per flow, expectation metrics, rows per table, duplicate check. | 2026-11-24T20:08:10Z |
| [02_data_quality.md](02_data_quality.md) | Planted vs observed data-quality issues, quarantine reasons, file reconciliation, completeness. | 2026-11-24T20:08:20Z |
| [03_business_results.md](03_business_results.md) | Gold answers: approval gap vs matched baseline, lost spend, cases, wave readiness gate. | 2026-11-24T20:08:28Z |
| [04_ai_output.md](04_ai_output.md) | Frozen detector config; AI explanations verbatim with the facts given; the full prompt. | 2026-11-24T20:08:41Z |
| [05_ai_evaluation.md](05_ai_evaluation.md) | Detection precision/recall vs baseline on held-out days; judge pass rates per prompt version. | 2026-11-24T20:08:54Z |
| [06_governance.md](06_governance.md) | Row filters, masks, tags, grants; the same query per persona; non-admin service principal; lineage. | 2026-11-24T20:08:56Z |
| [07_lakebase.md](07_lakebase.md) | Lakebase endpoint, constraints, counts, history, human edits surviving re-sync, rolled-back edit test, latency. | 2026-11-24T20:09:43Z |
| [08_genie.md](08_genie.md) | Genie benchmark questions asked live and compared with ground-truth SQL. | 2026-11-24T20:09:47Z |
| [09_job_run.md](09_job_run.md) | Job definition, final run, each task's state and exit value, recent runs. | 2026-11-24T20:16:05Z |
| [10_app.md](10_app.md) | App state, every route called live, page text, checks that the App equals gold and Lakebase. | 2026-11-24T20:15:06Z |


## Build history

`build_history/` keeps the dated evidence captured while each step was built (with the failures and fixes described in BUILD_LOG.md). Those files describe earlier states; the files above describe the final state.
