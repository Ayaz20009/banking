# Databricks notebook source
# MAGIC %md
# MAGIC # T3: upsert cases from gold into Lakebase (`ops.cases`), keeping human edits
# MAGIC * One case per episode (`gold_case_flags`).
# MAGIC * `INSERT ... ON CONFLICT (case_key) DO UPDATE SET <machine-owned columns only>`, and only when a
# MAGIC   machine value actually changed. Human-owned columns (status, assignee, owner_team, due_date,
# MAGIC   resolution, recovered spend) are written once at insert and never again by this task.
# MAGIC * History: one CREATED event per new case, one MACHINE_UPDATE event per changed case.

# COMMAND ----------

# MAGIC %pip install -q "psycopg[binary]>=3.1" "databricks-sdk>=0.68"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import json
import os
import sys

sys.path.append("/Workspace" + "/".join(dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get().split("/")[:-1]))
import lakebase_common as LB  # noqa: E402

dbutils.widgets.text("prompt_version", "v3")
PV = dbutils.widgets.get("prompt_version")
NS = "classic_stable_zjnu75_catalog.network_migration"

view_sql = open(os.path.join(os.path.dirname("/Workspace" + dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()), "case_flags_view.sql")).read()
spark.sql("\n".join(l for l in view_sql.splitlines() if not l.strip().startswith("--")))

# COMMAND ----------

cases = spark.sql(f"""
WITH f AS (SELECT * FROM {NS}.gold_case_flags),
per_day AS (   -- slice families overlap: take the largest flag per day, then add days
  SELECT case_key, business_date, max(exposure_usd) AS exp_d, max(excess_declines) AS exc_d, max(acc_merchants) AS m_d
  FROM f GROUP BY ALL),
agg_day AS (SELECT case_key, sum(exp_d) AS exposure_usd, sum(exc_d) AS excess_declines, max(m_d) AS merchants FROM per_day GROUP BY 1),
reg AS (
  SELECT case_key, CASE WHEN count(DISTINCT slice_value) = 1 THEN first(slice_value) ELSE 'ALL' END AS region_scope
  FROM f WHERE family = 'REGION' GROUP BY ALL),
rep AS (SELECT case_key, anomaly_key FROM f WHERE is_representative),
expl AS (
  SELECT anomaly_key, summary, next_step, certainty, prompt_version FROM {NS}.anomaly_explanations
  WHERE prompt_version = '{PV}' AND llm_error IS NULL
  QUALIFY row_number() OVER (PARTITION BY anomaly_key ORDER BY explained_at DESC) = 1)
SELECT f.case_key, first(f.likely_root_cause) AS root_cause, first(f.issuer_segment) AS issuer_segment,
       coalesce(first(reg.region_scope), 'ALL') AS region_scope,
       min(f.episode_start) AS episode_start, max(f.episode_end) AS episode_end, count(*) AS n_flags,
       round(max(f.score), 2) AS max_score, CASE WHEN max(f.score) >= 70 THEN 'HIGH' ELSE 'MEDIUM' END AS severity,
       round(first(ad.exposure_usd), 2) AS exposure_usd, round(first(ad.excess_declines), 1) AS excess_declines,
       CAST(first(ad.merchants) AS INT) AS merchants,
       first(f.owner_team) AS suggested_owner_team,
       slice(array_distinct(transform(array_sort(collect_list(named_struct('s', -f.score, 'v', concat(f.family, ': ', f.slice_value)))), x -> x.v)), 1, 5) AS top_slices,
       first(e.summary) AS llm_summary, first(e.next_step) AS llm_next_step, first(e.certainty) AS llm_certainty,
       first(e.prompt_version) AS prompt_version, first(f.detector_version) AS detector_version
FROM f
LEFT JOIN reg USING (case_key)
LEFT JOIN agg_day ad ON ad.case_key = f.case_key
LEFT JOIN rep ON rep.case_key = f.case_key
LEFT JOIN expl e ON e.anomaly_key = rep.anomaly_key
GROUP BY f.case_key
""")
links = spark.sql(f"SELECT case_key, anomaly_key, business_date, family, slice_value, round(score, 2) AS score FROM {NS}.gold_case_flags")
case_rows = [r.asDict() for r in cases.collect()]
link_rows = [r.asDict() for r in links.collect()]

# COMMAND ----------

MACHINE = ["root_cause", "issuer_segment", "region_scope", "episode_start", "episode_end", "n_flags", "max_score", "severity",
           "exposure_usd", "excess_declines", "merchants", "suggested_owner_team", "top_slices", "llm_summary", "llm_next_step",
           "llm_certainty", "prompt_version", "detector_version"]
cols = ["case_key"] + MACHINE
set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in MACHINE) + ", machine_refreshed_at = now()"
changed = "(" + ", ".join(f"ops.cases.{c}" for c in MACHINE) + ") IS DISTINCT FROM (" + ", ".join(f"EXCLUDED.{c}" for c in MACHINE) + ")"
upsert = f"""
INSERT INTO ops.cases ({", ".join(cols)}, owner_team)
VALUES ({", ".join(["%s"] * len(cols))}, %s)
ON CONFLICT (case_key) DO UPDATE SET {set_clause}
WHERE {changed}
RETURNING case_key, (xmax = 0) AS inserted"""

ins, upd = [], []
with LB.connect() as conn:
    with conn.cursor() as cur:
        cur.execute(LB.DDL)
        for r in case_rows:
            cur.execute(upsert, [r[c] for c in cols] + [r["suggested_owner_team"]])
            got = cur.fetchone()
            if got is None:
                continue                                   # nothing changed: no write, no event
            snap = json.dumps({c: (str(r[c]) if r[c] is not None else None) for c in ["n_flags", "max_score", "severity", "episode_end", "exposure_usd", "prompt_version"]})
            if got[1]:
                ins.append(r["case_key"])
                cur.execute("INSERT INTO ops.case_events (case_key, event_type, new_value, note, actor, actor_type) VALUES (%s,'CREATED',%s,%s,'sync_cases','SYSTEM')",
                            (r["case_key"], snap, "Case opened from flagged anomalies"))
            else:
                upd.append(r["case_key"])
                cur.execute("INSERT INTO ops.case_events (case_key, event_type, new_value, note, actor, actor_type) VALUES (%s,'MACHINE_UPDATE',%s,%s,'sync_cases','SYSTEM')",
                            (r["case_key"], snap, "Machine-owned fields refreshed from gold"))
        cur.executemany("""INSERT INTO ops.case_anomalies (case_key, anomaly_key, business_date, family, slice_value, score)
                           VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (case_key, anomaly_key) DO UPDATE SET score = EXCLUDED.score
                           WHERE ops.case_anomalies.score IS DISTINCT FROM EXCLUDED.score""",
                        [(l["case_key"], l["anomaly_key"], l["business_date"], l["family"], l["slice_value"], l["score"]) for l in link_rows])
        cur.execute("SELECT status, severity, count(*) FROM ops.cases GROUP BY 1, 2 ORDER BY 1, 2")
        by_status = [list(map(str, x)) for x in cur.fetchall()]
        cur.execute("SELECT count(*) FROM ops.case_events")
        n_events = cur.fetchone()[0]
    conn.commit()

summary = {"cases_from_gold": len(case_rows), "inserted": len(ins), "machine_updated": len(upd),
           "unchanged": len(case_rows) - len(ins) - len(upd), "links": len(link_rows),
           "by_status_severity": by_status, "events_total": n_events, "prompt_version": PV}
print(json.dumps(summary, indent=1))
dbutils.notebook.exit(json.dumps(summary))
