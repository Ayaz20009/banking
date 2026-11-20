# FE Bar Context — read before every task and follow it

## 1. Purpose

I am building my own FE Bar submission: a working prototype that addresses **credit card payment declines and acceptance risks during migration to an acquired payment network** for *a large U.S. bank and credit card issuer* (FINS).

- **Executive sponsor:** VP of Payment Network Integration
- **Domain owner:** Director of Payment Network Operations
- **Success metrics:** authorization approval rate, payment decline rate, at-risk transaction volume, migration readiness, lost spend

## 2. Non-negotiable FE Bar rules

1. **One connected journey from RAW data.** Start from raw synthetic or public data, then: Lakeflow ingest → Unity Catalog governance → Lakebase operational serving → ML or GenAI → Genie agent → Databricks App. Each stage consumes the previous stage's output. No disconnected demos.
2. **Text evidence only.** The evaluator reads text only. Every stage needs committed text evidence that it ran: notebook outputs, run logs, query results, model output. Screenshots and recordings do not count. Source code alone fails the Build domain.
3. **Readable repo.** The GitHub repo must be readable by the evaluator: public, or a private EMU repo connected through the submission form.
4. **Synthetic or public data only.** Never use real customer data, customer names, people's names, or internal system names or logos. This applies to code, data, docs, commit messages and the deck.
5. **My own work.** Never use or imitate Solution Builder output. Never copy another person's build.
6. **Deck and role-play.** A business deck (PDF, .txt or .md) and an AI role-play are also required. We prepare both at the end.

## 3. How you work with me

- **Small, verifiable steps.** After each step, report what you changed, how you verified it, and what is next.
- **Stop and ask before deciding** any of these: use case and story, personas, architecture and trade-offs, which data issues to plant, quality rules, access rules, AI approach, numbers in the value case, slide content, narrative. Give 2–3 options with pros and cons and a recommendation. I decide.
- **BUILD_LOG.md:** for every entry, record the date, what you tried, what failed, and what you changed and why. I use it to write up how I used AI.
- **DECISIONS.md:** record every decision I make: the decision, the options considered, and why. I will rewrite it in my own words.
- **[YOUR WORDS] markers:** mark every narrative, opinion or decision section you draft (README, DECISIONS.md, deck notes) with `[YOUR WORDS]` so I rewrite it myself. The use case, the decisions, the numbers and the words must be mine.
- **Secrets:** never print, log or commit tokens, passwords or connection strings.
- **CLI profile:** never guess a Databricks CLI profile. Ask me.

## 4. Engineering conventions

- **Workspace:** `https://fevm-classic-stable-zjnu75.cloud.databricks.com` (workspace ID `7474654297305416`). CLI profile: `febar`. Pass `--profile febar` on every CLI command.
- **Unity Catalog:** everything lives under `classic_stable_zjnu75_catalog.network_migration` (catalog and schema are bundle variables). Raw files go in a UC volume under that schema.
- **Declarative Automation Bundle:** deploy everything from a bundle.
  - `databricks.yml` holds the variables (`catalog`, `schema`, `warehouse_id`, model endpoints) and one target.
  - `resources/*.yml` defines pipelines, jobs and apps.
  - Commands: `databricks bundle validate`, `databricks bundle deploy`, `databricks bundle run <resource>`.
- **Serverless first:** serverless Lakeflow pipelines, serverless jobs and a serverless SQL warehouse.
- **SQL pipelines:** write pipelines in SQL (Lakeflow Spark Declarative Pipelines) unless Python is clearly better.
- **Idempotent reruns:** a step that runs twice must not create duplicate rows.
- **Run summaries:** every notebook task ends with `dbutils.notebook.exit(json.dumps(summary))`, a short JSON of what it did (rows, IDs, pass counts). Python file tasks print the same summary. The evidence step reads these back, because `.py` notebooks carry no outputs in the repo.
- **Agent skills:** if Databricks agent skills are installed, load the matching skill before working on each product (pipelines, Unity Catalog, Lakebase, apps, Genie, MLflow, jobs, bundles) and follow it.

## 5. Repository layout

```
README.md  FEBAR_CONTEXT.md  USE_CASE.md  BUILD_PLAN.md  EVAL_PROTOCOL.md
DECISIONS.md  BUILD_LOG.md  databricks.yml
resources/  src/data/  src/pipeline/  src/governance/  src/ai/
src/serve/  src/genie/  src/app/  tools/  evidence/  deck/
```

`.gitignore` must cover `.databricks/`, `.env`, `*.pem`, local notes and any credentials.

## 6. Definition of done (every task)

A task is done only when all of these are true:

- The code is committed.
- It is deployed.
- It ran successfully in the workspace.
- It is verified by a query or API call whose output you showed me.
- A line has been added to BUILD_LOG.md.
