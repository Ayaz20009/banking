# Databricks notebook source
# MAGIC %md
# MAGIC # Evaluation (EVAL_PROTOCOL v1 + A1 + A2)
# MAGIC **Part A, detection:** method (frozen threshold) vs the dashboard baseline on tuning and held-out days, against the answer key.
# MAGIC **Part B, GenAI:** 30 held-out explanations, MLflow 3 `mlflow.genai.evaluate` with 4 Guidelines judges
# MAGIC (judge model from a different family than the generator) plus the rule-based number check (rule wins).
# MAGIC Results are written per row to `eval_detection_flags`, `eval_judge_results` and `eval_runs` (append-only).

# COMMAND ----------

# MAGIC %pip install -q "mlflow[databricks]>=3.4"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import datetime as dt
import json
import os
import re
import sys

sys.path.append("/Workspace" + "/".join(dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get().split("/")[:-1]))
import common as C  # noqa: E402
from pyspark.sql import functions as F

dbutils.widgets.text("judge_endpoint", "databricks-gpt-5-4")
dbutils.widgets.text("prompt_version", "v1")
dbutils.widgets.text("run_label", "eval_v1")
dbutils.widgets.text("parts", "detection,genai")
dbutils.widgets.text("same_keys_as_run", "")
JUDGE, PV, LABEL = dbutils.widgets.get("judge_endpoint"), dbutils.widgets.get("prompt_version"), dbutils.widgets.get("run_label")
PARTS = set(dbutils.widgets.get("parts").split(","))
SAME_KEYS = dbutils.widgets.get("same_keys_as_run").strip()
RUN_AT = dt.datetime.utcnow().isoformat() + "Z"
cfg_row = spark.sql(f"SELECT * FROM {C.NS}.detector_config WHERE config_version = 'detector_v1'").first()
CFG = json.loads(cfg_row["details"])
T, FLOOR = CFG["threshold"], CFG["volume_floor"]
assert CFG["frozen_at_utc"] < RUN_AT, "threshold must be frozen before evaluation"
manifest = C.load_manifest()
summary = {"run_label": LABEL, "run_at_utc": RUN_AT, "protocol": "v1 + A1 + A2", "detector": {k: CFG[k] for k in
           ["config_version", "threshold", "volume_floor", "frozen_at_utc"]}}

# COMMAND ----------

# MAGIC %md ## Part A: detection

# COMMAND ----------

if "detection" in PARTS:
    lab_m, lab_b = C.incident_labels(spark)
    top_m = lab_m.groupBy("business_date", "issuer_segment", "family", "slice_value").agg(
        F.max_by("incident", "incident_rows").alias("top_incident"), F.max("incident_rows").alias("top_rows"))
    top_b = lab_b.groupBy("business_date", "acquirer_id").agg(
        F.max_by("incident", "incident_rows").alias("top_incident"), F.max("incident_rows").alias("top_rows"))
    m_flags = (spark.table(f"{C.NS}.gold_anomaly_scores")
               .where((F.col("score") >= T) & (F.col("attempts") >= FLOOR) & F.col("business_date").between(*C.WINDOW))
               .join(top_m, ["business_date", "issuer_segment", "family", "slice_value"], "left")
               .withColumn("hit", F.when(F.col("top_rows") >= 0.5 * F.greatest(F.col("excess_declines"), F.lit(1.0)), F.col("top_incident")))
               .select(F.lit("method").alias("method"), "anomaly_key", F.date_format("business_date", "yyyy-MM-dd").alias("business_date"),
                       "score", "excess_declines", "likely_root_cause", "top_incident", "top_rows", "hit"))
    b_flags = (C.baseline_flags(spark).where(F.col("business_date").between(*C.WINDOW))
               .join(top_b, ["business_date", "acquirer_id"], "left")
               .withColumn("hit", F.when(F.col("top_rows") >= 0.5 * F.greatest(F.col("excess_declines"), F.lit(1.0)), F.col("top_incident")))
               .select(F.lit("baseline").alias("method"),
                       F.concat_ws("|", F.col("business_date").cast("string"), F.col("acquirer_id")).alias("anomaly_key"),
                       F.date_format("business_date", "yyyy-MM-dd").alias("business_date"), F.lit(None).cast("double").alias("score"),
                       "excess_declines", F.lit(None).cast("string").alias("likely_root_cause"), "top_incident", "top_rows", "hit"))
    flags = m_flags.unionByName(b_flags).withColumn("run_label", F.lit(LABEL)).withColumn("run_at_utc", F.lit(RUN_AT))
    flags.write.mode("append").option("mergeSchema", "true").saveAsTable(f"{C.NS}.eval_detection_flags")
    rows = [r.asDict() for r in flags.collect()]
    res = {}
    for meth in ["method", "baseline"]:
        fl = [{"business_date": r["business_date"], "hit": r["hit"], "root_cause": r["likely_root_cause"]} for r in rows if r["method"] == meth]
        if meth == "baseline":
            for f in fl:
                f.pop("root_cause")
        res[meth] = {"tuning": C.metrics(fl, manifest, C.TUNING, meth), "holdout": C.metrics(fl, manifest, C.HOLDOUT, meth)}
    mh, bh = res["method"]["holdout"], res["baseline"]["holdout"]
    landed = spark.sql(f"SELECT max(business_date) d FROM {C.NS}.silver_auth").first()["d"].isoformat()
    excluded = spark.sql(f"""SELECT count(*) c FROM {C.NS}.silver_auth WHERE network = 'MRD'
                             AND business_date BETWEEN '{C.WINDOW[0]}' AND '{C.WINDOW[1]}' AND NOT ({C.ON_TIME})""").first()["c"]
    no_claim = {
        "beats_baseline_by_20pts_at_equal_or_better_precision": (
            mh["incident_recall"] is not None and bh["incident_recall"] is not None
            and mh["incident_recall"] - bh["incident_recall"] >= 0.20
            and (mh["precision"] or 0) >= (bh["precision"] or 0)),
        "decoy_flagged_by_method": mh["decoy_flags"] > 0,
        "method_precision_below_50pct": (mh["precision"] is not None and mh["precision"] < 0.5),
        "look_ahead_detected": False}
    summary["detection"] = res
    summary["detection_checks"] = {"no_claim_conditions": no_claim, "last_landed_business_date": landed,
                                   "rows_excluded_by_timing_rule_in_window": excluded,
                                   "holdout_days_without_data": [d for d in ["2026-11-18", "2026-11-19"] if d > landed]}

# COMMAND ----------

# MAGIC %md ## Part B: GenAI explanations (30 held-out rows, fixed-seed sample)

# COMMAND ----------

NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers(text):
    """Numbers as values rounded to 2 decimals (Errata 1: compare values, not text)."""
    return {round(float(n.replace(",", "")), 2) for n in NUM.findall(text or "") if n.replace(",", "").replace(".", "").isdigit()}


def fact_numbers(facts):
    return numbers(facts)


if "genai" in PARTS:
    import mlflow
    from mlflow.genai.scorers import Guidelines
    os.environ["MLFLOW_GENAI_EVAL_MAX_WORKERS"] = "4"        # limit concurrent judge calls
    user = spark.sql("SELECT current_user()").first()[0]
    mlflow.set_experiment(f"/Users/{user}/febar_ai_evaluation")
    sample = spark.sql(f"""
      SELECT anomaly_key, business_date, facts, llm_raw, llm_error, summary, likely_cause, certainty, next_step, owner_team, facts_used
      FROM {C.NS}.anomaly_explanations
      WHERE prompt_version = '{PV}' AND business_date BETWEEN '{C.HOLDOUT[0]}' AND '{C.HOLDOUT[1]}'
        {"AND anomaly_key IN (SELECT DISTINCT anomaly_key FROM " + C.NS + ".eval_judge_results WHERE run_label = '" + SAME_KEYS + "')" if SAME_KEYS else ""}
      QUALIFY row_number() OVER (PARTITION BY anomaly_key ORDER BY explained_at DESC) = 1
      ORDER BY xxhash64(anomaly_key, 20261120) LIMIT 30""").collect()
    data, rule_rows = [], []
    for r in sample:
        facts = json.loads(r["facts"])
        out = {"summary": r["summary"], "likely_cause": r["likely_cause"], "certainty": r["certainty"],
               "next_step": r["next_step"], "owner_team": r["owner_team"]}
        data.append({"inputs": {"facts": facts}, "outputs": out})
        text_nums = numbers((r["summary"] or "") + " " + (r["next_step"] or ""))
        unsupported = sorted(n for n in text_nums - fact_numbers(r["facts"]))
        rule_rows.append({"anomaly_key": r["anomaly_key"], "rule_numbers_grounded": not unsupported, "unsupported_numbers": unsupported,
                          "rule_cause_matches": r["likely_cause"] == facts.get("dominant_category"),
                          "llm_error": r["llm_error"]})
    judge_model = f"databricks:/{JUDGE}"
    scorers = [
        Guidelines(name="grounded_in_facts", model=judge_model, guidelines=[
            "Every statement in the response's summary and next_step must be supported by the facts in the request.",
            "Every number in the response must appear in the request's facts (same value; rounding to the precision shown is acceptable)."]),
        Guidelines(name="cause_agreement", model=judge_model, guidelines=[
            "The response's likely_cause must equal the request's dominant_category, unless the response explicitly explains, using the facts, why the facts contradict it."]),
        Guidelines(name="actionable_next_step", model=judge_model, guidelines=[
            "The next_step must be one concrete action an operations team could start today: it says what to check or whom to contact, and it fits the likely cause and owner_team.",
            "Generic advice such as 'monitor the situation' or 'investigate further' without saying what to check fails."]),
        Guidelines(name="no_invented_data", model=judge_model, guidelines=[
            "The response must not mention any person, merchant, acquirer, amount, date, ticket, document, system or event that is not in the request's facts.",
            "The response must present the cause as likely or possible (an inference from decline codes), not as a confirmed fact."]),
    ]
    with mlflow.start_run(run_name=f"{LABEL}_{PV}") as run:
        mlflow.log_params({"generator_prompt_version": PV, "judge_endpoint": JUDGE, "n_rows": len(data), "protocol": "v1+A1+A2"})
        results = mlflow.genai.evaluate(data=data, scorers=scorers)
        traces = mlflow.search_traces(run_id=results.run_id)
    judge_rows = []
    for i, (_, tr) in enumerate(traces.iterrows()):
        req = tr["request"]
        req = json.loads(req) if isinstance(req, str) else req
        key_match = None
        for j, d in enumerate(data):
            if d["inputs"] == req or json.dumps(d["inputs"], sort_keys=True) == json.dumps(req, sort_keys=True):
                key_match = j
                break
        rr = rule_rows[key_match] if key_match is not None else {"anomaly_key": None}
        for a in tr["assessments"]:
            name = getattr(a, "name", None) or (a.get("assessment_name") if isinstance(a, dict) else None)
            fb = getattr(a, "feedback", None)
            val = getattr(fb, "value", None) if fb is not None else (a.get("feedback", {}).get("value") if isinstance(a, dict) else None)
            rat = getattr(a, "rationale", None) or (a.get("rationale") if isinstance(a, dict) else None)
            if name in [s.name for s in scorers]:
                judge_rows.append((LABEL, PV, rr["anomaly_key"], name, str(val), rat, JUDGE, RUN_AT))
    for rr in rule_rows:
        judge_rows.append((LABEL, PV, rr["anomaly_key"], "rule_numbers_grounded", "yes" if rr["rule_numbers_grounded"] else "no",
                           "unsupported numbers: " + ", ".join(str(x) for x in rr["unsupported_numbers"]) if rr["unsupported_numbers"] else "all numbers found in facts",
                           "rule", RUN_AT))
        judge_rows.append((LABEL, PV, rr["anomaly_key"], "rule_cause_matches", "yes" if rr["rule_cause_matches"] else "no",
                           "likely_cause vs dominant_category", "rule", RUN_AT))
    jdf = spark.createDataFrame(judge_rows, "run_label STRING, prompt_version STRING, anomaly_key STRING, judge STRING, value STRING, rationale STRING, judge_model STRING, run_at_utc STRING")
    jdf.write.mode("append").saveAsTable(f"{C.NS}.eval_judge_results")
    agg = {r["judge"]: {"pass": r["p"], "n": r["n"], "pass_rate": round(r["p"] / r["n"], 3)} for r in
           jdf.groupBy("judge").agg(F.count_if(F.col("value").isin("yes", "True", "true")).alias("p"), F.count("*").alias("n")).collect()}
    rule_g = agg.get("rule_numbers_grounded", {}).get("pass_rate", 0)
    summary["genai"] = {"n_rows": len(data), "generator_prompt_version": PV, "judge_endpoint": JUDGE, "mlflow_run_id": results.run_id,
                        "per_judge": agg, "llm_errors_in_sample": sum(1 for r in rule_rows if r["llm_error"]),
                        "no_claim_grounding_below_90pct": rule_g < 0.90}

spark.sql(f"CREATE TABLE IF NOT EXISTS {C.NS}.eval_runs (run_label STRING, run_at_utc STRING, summary STRING) COMMENT 'Append-only evaluation run summaries'")
spark.createDataFrame([(LABEL, RUN_AT, json.dumps(summary, default=str))], "run_label STRING, run_at_utc STRING, summary STRING") \
    .write.mode("append").saveAsTable(f"{C.NS}.eval_runs")
print(json.dumps(summary, indent=1, default=str))
dbutils.notebook.exit(json.dumps(summary, default=str))
