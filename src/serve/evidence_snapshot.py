# Databricks notebook source
# MAGIC %md
# MAGIC # T6: evidence snapshot, a cross-check of the same numbers across layers
# MAGIC Reads the headline numbers from the gold tables (Unity Catalog), from Lakebase (ops.*) and from
# MAGIC the readiness gate, checks that they agree, and returns everything as the task's exit value.
# MAGIC Runs as the job owner (ADMIN persona), so it sees every row.

# COMMAND ----------

# MAGIC %pip install -q "psycopg[binary]>=3.1" "databricks-sdk>=0.68"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import json
import sys

sys.path.append("/Workspace" + "/".join(dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get().split("/")[:-1]))
import lakebase_common as LB  # noqa: E402

NS = "classic_stable_zjnu75_catalog.network_migration"
g = spark.sql(f"""
WITH gap AS (SELECT * FROM {NS}.gold_baseline_gap WHERE business_date > (SELECT date_sub(max(business_date), 30) FROM {NS}.gold_baseline_gap))
SELECT
  (SELECT max(business_date) FROM {NS}.gold_auth_daily) AS latest_business_date,
  (SELECT max(to_date(_business_date)) FROM {NS}.bronze_issuer_auth) AS latest_landed_business_date,
  (SELECT sum(attempts) FROM {NS}.gold_auth_daily) AS gold_attempts,
  (SELECT count(*) FROM {NS}.silver_auth) AS silver_attempts,
  (SELECT round(100 * (sum(expected_approvals) - sum(migrated_approvals)) / sum(migrated_attempts), 2) FROM gap) AS gap_pp_30d,
  (SELECT round(sum(lost_spend), 2) FROM gap) AS lost_spend_30d,
  (SELECT count(*) FROM {NS}.gold_anomalies) AS flagged_anomalies,
  (SELECT count(*) FROM {NS}.gold_case_status) AS uc_cases,
  (SELECT count_if(status NOT IN ('RESOLVED','DISMISSED')) FROM {NS}.gold_case_status) AS uc_open_cases,
  (SELECT count_if(status NOT IN ('RESOLVED','DISMISSED') AND severity = 'HIGH' AND issuer_segment = 'OWN') FROM {NS}.gold_case_status) AS uc_open_high_own,
  (SELECT to_json(map_from_entries(collect_list(struct(CAST(case_id AS STRING), status)))) FROM {NS}.gold_case_status) AS uc_status_by_case,
  (SELECT count_if(gate = 'HOLD') FROM {NS}.gold_wave_readiness WHERE wave_id = 7) AS wave7_hold_segments,
  (SELECT count(*) FROM {NS}.gold_wave_readiness WHERE wave_id = 7) AS wave7_segments,
  (SELECT round(sum(at_risk_spend_usd_per_day), 2) FROM {NS}.gold_wave_readiness WHERE wave_id = 7) AS wave7_at_risk_usd_per_day,
  (SELECT max(open_high_cases) FROM {NS}.gold_wave_readiness WHERE issuer_segment = 'OWN') AS readiness_open_high_own,
  (SELECT count(*) FROM {NS}.recon_file_control) AS files_reconciled_or_break,
  (SELECT count_if(status = 'BREAK') FROM {NS}.recon_file_control) AS file_breaks
""").first().asDict()

with LB.connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT (SELECT count(*) FROM ops.cases),
                          (SELECT count(*) FROM ops.cases WHERE status NOT IN ('RESOLVED','DISMISSED')),
                          (SELECT count(*) FROM ops.cases WHERE status NOT IN ('RESOLVED','DISMISSED') AND severity = 'HIGH' AND issuer_segment = 'OWN'),
                          (SELECT count(*) FROM ops.case_anomalies), (SELECT count(*) FROM ops.case_events)""")
    lb_cases, lb_open, lb_open_high_own, lb_links, lb_events = cur.fetchone()
    cur.execute("SELECT case_id::text, status FROM ops.cases")
    lb_status = dict(cur.fetchall())

checks = {
    "gold is as fresh as the landed data (latest gold date == latest bronze date)": g["latest_business_date"] == g["latest_landed_business_date"],
    "gold_attempts == silver_attempts": g["gold_attempts"] == g["silver_attempts"],
    "uc_cases == lakebase_cases": g["uc_cases"] == lb_cases,
    "uc_open_cases == lakebase_open_cases": g["uc_open_cases"] == lb_open,
    "status per case identical (UC copy vs Lakebase)": json.loads(g["uc_status_by_case"]) == lb_status,
    "flagged anomalies == lakebase case_anomalies": g["flagged_anomalies"] == lb_links,
    "readiness open HIGH (own) == lakebase open HIGH (own)": g["readiness_open_high_own"] == lb_open_high_own,
    "only the planted file break": g["file_breaks"] == 1,
}
summary = {k: (str(v) if not isinstance(v, (int, float, type(None))) else v) for k, v in g.items() if k != "uc_status_by_case"}
summary.update(lakebase_cases=lb_cases, lakebase_open_cases=lb_open, lakebase_open_high_own=lb_open_high_own,
               lakebase_case_anomalies=lb_links, lakebase_events=lb_events, checks=checks, all_checks_pass=all(checks.values()))
print(json.dumps(summary, indent=1, default=str))
dbutils.notebook.exit(json.dumps(summary, default=str))
