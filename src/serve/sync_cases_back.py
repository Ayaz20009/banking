# Databricks notebook source
# MAGIC %md
# MAGIC # T4: Lakebase `ops.cases` -> Delta `gold_case_status` (Unity Catalog, row filter by persona)
# MAGIC Brings human work (status, owner, resolution, recovered spend) back into the lakehouse, so the
# MAGIC wave-readiness gate and Genie can see it. Full refresh of a small table (one row per case): idempotent.

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
COLS = ["case_id", "case_key", "root_cause", "issuer_segment", "region_scope", "episode_start", "episode_end", "n_flags",
        "max_score", "severity", "exposure_usd", "excess_declines", "merchants", "suggested_owner_team", "status", "assignee",
        "owner_team", "due_date", "resolution_code", "recovered_spend_usd", "resolved_at", "updated_at", "machine_refreshed_at", "version"]
with LB.connect() as conn, conn.cursor() as cur:
    cur.execute(f"SELECT {', '.join(COLS)} FROM ops.cases")
    rows = cur.fetchall()
    cur.execute("SELECT case_key, count(*) FROM ops.case_events GROUP BY 1")
    ev = dict(cur.fetchall())

schema = """case_id BIGINT, case_key STRING, root_cause STRING, issuer_segment STRING, region_scope STRING, episode_start DATE,
  episode_end DATE, n_flags INT, max_score DOUBLE, severity STRING, exposure_usd DOUBLE, excess_declines DOUBLE, merchants INT,
  suggested_owner_team STRING, status STRING, assignee STRING, owner_team STRING, due_date DATE, resolution_code STRING,
  recovered_spend_usd DOUBLE, resolved_at TIMESTAMP, updated_at TIMESTAMP, machine_refreshed_at TIMESTAMP, version INT, n_events INT"""
data = [tuple(float(v) if c in ("max_score", "exposure_usd", "excess_declines", "recovered_spend_usd") and v is not None else v
              for c, v in zip(COLS, r)) + (int(ev.get(r[1], 0)),) for r in rows]
df = spark.createDataFrame(data, schema)
spark.sql(f"""CREATE TABLE IF NOT EXISTS {NS}.gold_case_status ({schema})
  COMMENT 'Cases from the Lakebase case store (ops.cases), copied back to the lakehouse by job task T4: status, owner, resolution and recovered spend set by analysts in the App. One row per case. Row filter by persona.'""")
spark.sql(f"ALTER TABLE {NS}.gold_case_status SET ROW FILTER {NS}.f_row_filter ON (issuer_segment, region_scope)")
df.createOrReplaceTempView("cases_src")
spark.sql(f"INSERT OVERWRITE {NS}.gold_case_status SELECT * FROM cases_src")
st = [r.asDict() for r in spark.sql(f"SELECT status, severity, count(*) n FROM {NS}.gold_case_status GROUP BY 1, 2 ORDER BY 1, 2").collect()]
summary = {"rows": len(data), "by_status_severity": st}
print(json.dumps(summary, indent=1, default=str))
dbutils.notebook.exit(json.dumps(summary, default=str))
