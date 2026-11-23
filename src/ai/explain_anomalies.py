# Databricks notebook source
# MAGIC %md
# MAGIC # T2: flag anomalies (frozen threshold) and explain the top N with `ai_query`
# MAGIC * Ranking stays in the explainable score. The LLM never outputs a rank or a severity.
# MAGIC * The LLM is called only for flagged anomalies not yet explained with this prompt version,
# MAGIC   newest first and highest score first, capped at `top_n`. Reruns are idempotent and cost-bounded.
# MAGIC * Facts given to the model are only the row's own facts, known at the decision time.
# MAGIC * Every row keeps the model name, the prompt version, the raw response and the error message.

# COMMAND ----------

import json
import sys

sys.path.append("/Workspace" + "/".join(dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get().split("/")[:-1]))
import common as C  # noqa: E402

dbutils.widgets.text("llm_endpoint", "databricks-claude-sonnet-4-6")
dbutils.widgets.text("prompt_version", "v1")
dbutils.widgets.text("top_n", "60")
dbutils.widgets.text("from_date", "2026-09-21")
EP, PV, TOP_N, FROM_D = (dbutils.widgets.get(k) for k in ["llm_endpoint", "prompt_version", "top_n", "from_date"])

cfg = spark.sql(f"SELECT threshold, volume_floor FROM {C.NS}.detector_config WHERE config_version = 'detector_v1'").first()
T, FLOOR = cfg["threshold"], cfg["volume_floor"]

# COMMAND ----------

# MAGIC %md ## Flagged anomalies -> gold_anomalies (machine fields only; MERGE on anomaly_key)

# COMMAND ----------

spark.sql(f"""CREATE TABLE IF NOT EXISTS {C.NS}.gold_anomalies (
  anomaly_key STRING NOT NULL, business_date DATE, issuer_segment STRING, family STRING, slice_value STRING, region STRING,
  attempts BIGINT, acc_declines BIGINT, expected_declines DOUBLE, excess_declines DOUBLE, z_score DOUBLE,
  exposure_usd DOUBLE, acc_merchants BIGINT, likely_root_cause STRING, dominant_share DOUBLE, owner_team STRING,
  excess_points DOUBLE, impact_points DOUBLE, clarity_points DOUBLE, breadth_points DOUBLE, persistence_points DOUBLE,
  score DOUBLE, drivers ARRAY<STRING>, score_version STRING, detector_version STRING, flagged_at TIMESTAMP,
  facts STRING, llm_summary STRING, llm_likely_cause STRING, llm_certainty STRING, llm_next_step STRING,
  llm_owner_team STRING, llm_facts_used ARRAY<STRING>, llm_raw STRING, llm_error STRING,
  llm_model STRING, prompt_version STRING, explained_at TIMESTAMP)
  CLUSTER BY (business_date)
  COMMENT 'Flagged anomalies (explainable score >= frozen threshold) with the LLM explanation and next step. One row per anomaly_key. Row filter by persona.'""")
spark.sql(f"ALTER TABLE {C.NS}.gold_anomalies SET ROW FILTER {C.NS}.f_row_filter ON (issuer_segment, region)")

spark.sql(f"""
MERGE INTO {C.NS}.gold_anomalies t
USING (
  SELECT s.*, 'detector_v1' AS detector_version,
    to_json(named_struct(
      'business_date', CAST(s.business_date AS STRING),
      'card_issuer_segment', CASE s.issuer_segment WHEN 'OWN' THEN 'the bank''s own cards' ELSE 'third-party issuers'' cards processed on the network' END,
      'slice_type', s.family, 'slice', s.slice_value, 'network', 'acquired network (cards already migrated)',
      'attempts', s.attempts, 'acceptance_declines', s.acc_declines,
      'expected_acceptance_declines', round(s.expected_declines, 1), 'excess_declines', round(s.excess_declines, 1),
      'z_score', round(s.z_score, 1), 'estimated_lost_spend_usd', round(s.exposure_usd, 0),
      'merchants_with_acceptance_declines', s.acc_merchants,
      'decline_categories', map_filter(map(
          'ACCEPTANCE_CONFIG (merchant/acquirer acceptance profile not configured or rejected)', s.c_acceptance_config,
          'TOKEN_PROVISIONING (wallet or card-on-file token not provisioned)', s.c_token_provisioning,
          'CROSS_BORDER_BLOCK (cross-border not enabled for merchant category or product)', s.c_cross_border_block,
          'CARD_ON_FILE_STALE (stored card credential not updated after reissue)', s.c_card_on_file_stale,
          'PROCESSOR_TIMEOUT (issuer or switch timed out)', s.c_processor_timeout,
          'SYSTEM_ERROR (network system error)', s.c_system_error), (k, v) -> v > 0),
      'dominant_category', s.likely_root_cause, 'dominant_category_share_pct', round(100 * s.dominant_share, 0),
      'elevated_on_prior_days_of_last_2', s.prior_elevated_days,
      'candidate_owner_team', s.owner_team,
      'acquirer', CASE WHEN s.family = 'ACQUIRER_CHANNEL' THEN named_struct(
          'name', a.acquirer_name,
          'last_configuration_change', CASE WHEN a.last_config_change <= s.business_date THEN CAST(a.last_config_change AS STRING) END,
          'configuration_note', CASE WHEN a.last_config_change <= s.business_date THEN a.config_note END) END
    )) AS facts
  FROM {C.NS}.gold_anomaly_scores s
  LEFT JOIN {C.NS}.silver_acquirers a ON s.family = 'ACQUIRER_CHANNEL' AND a.acquirer_id = split(s.slice_value, ' / ')[0]
  WHERE s.score >= {T} AND s.attempts >= {FLOOR}
) s
ON t.anomaly_key = s.anomaly_key
WHEN MATCHED THEN UPDATE SET
  t.attempts = s.attempts, t.acc_declines = s.acc_declines, t.expected_declines = s.expected_declines,
  t.excess_declines = s.excess_declines, t.z_score = s.z_score, t.exposure_usd = s.exposure_usd, t.score = s.score,
  t.drivers = s.drivers, t.facts = s.facts
WHEN NOT MATCHED THEN INSERT (anomaly_key, business_date, issuer_segment, family, slice_value, region, attempts, acc_declines,
  expected_declines, excess_declines, z_score, exposure_usd, acc_merchants, likely_root_cause, dominant_share, owner_team,
  excess_points, impact_points, clarity_points, breadth_points, persistence_points, score, drivers, score_version,
  detector_version, flagged_at, facts)
VALUES (s.anomaly_key, s.business_date, s.issuer_segment, s.family, s.slice_value, s.region, s.attempts, s.acc_declines,
  s.expected_declines, s.excess_declines, s.z_score, s.exposure_usd, s.acc_merchants, s.likely_root_cause, s.dominant_share,
  s.owner_team, s.excess_points, s.impact_points, s.clarity_points, s.breadth_points, s.persistence_points, s.score, s.drivers,
  s.score_version, s.detector_version, current_timestamp(), s.facts)
""")

# COMMAND ----------

# MAGIC %md ## Explain the top N with ai_query (structured output, temperature 0)

# COMMAND ----------

PROMPTS = {
 "v1": """You are assisting a payment network operations analyst at a card issuer that is migrating cards to an acquired payment network.
Below are the facts about ONE flagged authorization anomaly, as JSON. Write a short explanation and the next action.

Rules:
- Use ONLY the facts given. Do not invent people, merchants, amounts, dates, tickets, documents or systems that are not in the facts.
- Every number you write must appear in the facts.
- The cause is an inference from decline codes: present it as likely (or possible), never as a confirmed fact.
- Do not restate or change the score, rank or severity; do not rate priority.
- next_step: one concrete action an operations team can take today, naming what to check or whom to contact, based on the facts.
- owner_team: choose from the allowed list; prefer candidate_owner_team unless the facts clearly contradict it.
- facts_used: list the fact names you relied on.

FACTS:
""",
}
PROMPTS["v2"] = PROMPTS["v1"]  # placeholder; replaced during the single iteration if needed
PROMPT = PROMPTS[PV]

SCHEMA = {
  "type": "object",
  "properties": {
    "summary": {"type": "string"},
    "likely_cause": {"type": "string", "enum": ["ACCEPTANCE_CONFIG", "TOKEN_PROVISIONING", "CROSS_BORDER_BLOCK",
                                                 "CARD_ON_FILE_STALE", "PROCESSOR_TIMEOUT", "SYSTEM_ERROR", "UNCLEAR"]},
    "certainty": {"type": "string", "enum": ["likely", "possible", "unclear"]},
    "next_step": {"type": "string"},
    "owner_team": {"type": "string", "enum": ["Acquirer Relations", "Network Integration", "Card Technology",
                                               "Network Operations", "Issuer Processing", "Unclear"]},
    "facts_used": {"type": "array", "items": {"type": "string"}}},
  "required": ["summary", "likely_cause", "certainty", "next_step", "owner_team", "facts_used"],
  "additionalProperties": False}
RESPONSE_FORMAT = json.dumps({"type": "json_schema", "json_schema": {"name": "anomaly_explanation", "schema": SCHEMA, "strict": True}})
PARSE_SCHEMA = "summary STRING, likely_cause STRING, certainty STRING, next_step STRING, owner_team STRING, facts_used ARRAY<STRING>"

spark.sql(f"""CREATE TABLE IF NOT EXISTS {C.NS}.anomaly_explanations (
  anomaly_key STRING, business_date DATE, prompt_version STRING, llm_model STRING, facts STRING, prompt_text STRING,
  llm_raw STRING, llm_error STRING, summary STRING, likely_cause STRING, certainty STRING, next_step STRING,
  owner_team STRING, facts_used ARRAY<STRING>, explained_at TIMESTAMP)
  COMMENT 'Append-only history of LLM explanations per anomaly and prompt version (before/after comparisons).'""")

todo = spark.sql(f"""
  SELECT a.anomaly_key, a.business_date, a.facts FROM {C.NS}.gold_anomalies a
  WHERE a.business_date >= '{FROM_D}'
    AND NOT EXISTS (SELECT 1 FROM {C.NS}.anomaly_explanations e WHERE e.anomaly_key = a.anomaly_key AND e.prompt_version = '{PV}')
  ORDER BY a.business_date DESC, a.score DESC LIMIT {int(TOP_N)}""")
todo.createOrReplaceTempView("todo")
n_todo = todo.count()
res = spark.sql(f"""
  SELECT anomaly_key, business_date, '{PV}' AS prompt_version, '{EP}' AS llm_model, facts,
         concat(:prompt, facts) AS prompt_text,
         ai_query('{EP}', concat(:prompt, facts),
                  responseFormat => :rf,
                  modelParameters => named_struct('temperature', CAST(0.0 AS DOUBLE), 'max_tokens', 700),
                  failOnError => false) AS r
  FROM todo""", args={"prompt": PROMPT, "rf": RESPONSE_FORMAT})
res.createOrReplaceTempView("res")
spark.sql(f"""
  INSERT INTO {C.NS}.anomaly_explanations
  SELECT anomaly_key, business_date, prompt_version, llm_model, facts, prompt_text, r.result AS llm_raw, r.errorMessage AS llm_error,
         p.summary, p.likely_cause, p.certainty, p.next_step, p.owner_team, p.facts_used, current_timestamp()
  FROM (SELECT *, from_json(r.result, '{PARSE_SCHEMA}') AS p FROM res)""")

# latest explanation per anomaly for this prompt version -> gold_anomalies
spark.sql(f"""
MERGE INTO {C.NS}.gold_anomalies t
USING (SELECT * FROM {C.NS}.anomaly_explanations WHERE prompt_version = '{PV}'
       QUALIFY row_number() OVER (PARTITION BY anomaly_key ORDER BY explained_at DESC) = 1) e
ON t.anomaly_key = e.anomaly_key
WHEN MATCHED THEN UPDATE SET t.llm_summary = e.summary, t.llm_likely_cause = e.likely_cause, t.llm_certainty = e.certainty,
  t.llm_next_step = e.next_step, t.llm_owner_team = e.owner_team, t.llm_facts_used = e.facts_used, t.llm_raw = e.llm_raw,
  t.llm_error = e.llm_error, t.llm_model = e.llm_model, t.prompt_version = e.prompt_version, t.explained_at = e.explained_at""")

st = spark.sql(f"""SELECT count(*) n, count_if(llm_error IS NULL AND summary IS NOT NULL) ok, count_if(llm_error IS NOT NULL) errors
                   FROM {C.NS}.anomaly_explanations WHERE prompt_version = '{PV}'""").first()
flagged = spark.sql(f"SELECT count(*) c FROM {C.NS}.gold_anomalies").first()["c"]
summary = {"threshold": T, "volume_floor": FLOOR, "flagged_total": flagged, "explained_this_run": n_todo,
           "prompt_version": PV, "llm_model": EP, "explanations_total": st["n"], "ok": st["ok"], "errors": st["errors"]}
print(json.dumps(summary, indent=1))
dbutils.notebook.exit(json.dumps(summary))
