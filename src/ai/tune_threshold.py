# Databricks notebook source
# MAGIC %md
# MAGIC # Tune and FREEZE the flag threshold (tuning days only)
# MAGIC EVAL_PROTOCOL §3: the threshold and minimum-volume floor are chosen on evaluation-window days 1–40
# MAGIC **only**, to maximise incident recall at ≥ 80% precision, then frozen and recorded before the
# MAGIC held-out days are scored. This notebook never reads scores or labels for held-out days.

# COMMAND ----------

import json
import sys
import datetime as dt

sys.path.append("/Workspace" + "/".join(dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get().split("/")[:-1]))
import common as C  # noqa: E402

from pyspark.sql import functions as F

# COMMAND ----------

lo, hi = C.TUNING
scores = (spark.table(f"{C.NS}.gold_anomaly_scores")
          .where(F.col("business_date").between(lo, hi)))               # tuning days only
lab_m, _ = C.incident_labels(spark)
lab_m = lab_m.where(F.col("business_date").between(lo, hi))
best = (lab_m.groupBy("business_date", "issuer_segment", "family", "slice_value")
        .agg(F.max_by("incident", "incident_rows").alias("top_incident"), F.max("incident_rows").alias("top_rows")))
cand = (scores.where("score >= 10")    # candidates: the grid starts at threshold 10
        .join(best, ["business_date", "issuer_segment", "family", "slice_value"], "left")
        .select(F.date_format("business_date", "yyyy-MM-dd").alias("business_date"), "score", "attempts",
                "excess_declines", "likely_root_cause", "top_incident", "top_rows"))
rows = [r.asDict() for r in cand.collect()]
manifest = C.load_manifest()


def flags_for(t, floor):
    out = []
    for r in rows:
        if r["score"] >= t and r["attempts"] >= floor:
            hit = r["top_incident"] if (r["top_incident"] and r["top_rows"] >= 0.5 * max(r["excess_declines"], 1.0)) else None
            out.append({"business_date": r["business_date"], "hit": hit, "root_cause": r["likely_root_cause"]})
    return out


grid = []
for floor in [0, 10, 20, 50, 100]:
    for t in range(10, 96):
        m = C.metrics(flags_for(t, floor), manifest, C.TUNING, "method")
        grid.append({"threshold": t, "volume_floor": floor, "precision": m["precision"], "incident_recall": m["incident_recall"],
                     "incident_day_recall": m["incident_day_recall"], "flags": m["flags"]})
ok = [g for g in grid if g["precision"] is not None and g["precision"] >= 0.8]
# Objective: max incident recall at >= 80% precision; tie-breaks (stated here, before any held-out result):
# higher precision, then higher incident-day recall, then LOWER threshold (more sensitive), then lower floor.
ok.sort(key=lambda g: (-g["incident_recall"], -g["precision"], -g["incident_day_recall"], g["threshold"], g["volume_floor"]))
chosen = ok[0] if ok else None
assert chosen, "no configuration reaches 80% precision on the tuning days"
tuning_metrics = C.metrics(flags_for(chosen["threshold"], chosen["volume_floor"]), manifest, C.TUNING, "method")

frozen_at = dt.datetime.utcnow().isoformat() + "Z"
cfg = {"config_version": "detector_v1", "score_version": "score_v1", "protocol": "v1 + A1 + A2",
       "threshold": chosen["threshold"], "volume_floor": chosen["volume_floor"], "frozen_at_utc": frozen_at,
       "tuning_split": C.TUNING, "grid_size": len(grid), "configs_meeting_80pct_precision": len(ok),
       "tuning_metrics": tuning_metrics}
spark.sql(f"""CREATE TABLE IF NOT EXISTS {C.NS}.detector_config (
  config_version STRING, threshold DOUBLE, volume_floor INT, frozen_at_utc STRING, protocol STRING, details STRING)
  COMMENT 'Frozen anomaly-flag threshold (tuned on evaluation-window days 1-40 only). Append-only: never updated.'""")
exists = spark.sql(f"SELECT count(*) c FROM {C.NS}.detector_config WHERE config_version = 'detector_v1'").first()["c"]
if exists == 0:   # freeze once; reruns never overwrite a frozen config
    spark.createDataFrame([(cfg["config_version"], float(cfg["threshold"]), int(cfg["volume_floor"]), frozen_at, cfg["protocol"],
                            json.dumps(cfg, default=str))],
                          "config_version STRING, threshold DOUBLE, volume_floor INT, frozen_at_utc STRING, protocol STRING, details STRING") \
        .write.mode("append").saveAsTable(f"{C.NS}.detector_config")
frozen = json.loads(spark.sql(f"SELECT details FROM {C.NS}.detector_config WHERE config_version = 'detector_v1'").first()["details"])
summary = {"frozen": {k: frozen[k] for k in ["config_version", "threshold", "volume_floor", "frozen_at_utc", "protocol",
                                              "grid_size", "configs_meeting_80pct_precision"]},
           "tuning_metrics": frozen["tuning_metrics"], "newly_frozen": exists == 0}
print(json.dumps(summary, indent=1, default=str))
dbutils.notebook.exit(json.dumps(summary, default=str))
