"""Shared definitions for the intelligent step (imported by the job notebooks in src/ai/).

EVAL_PROTOCOL v1 + Amendments 1-2. Nothing here reads the answer key except `incident_labels`,
which only the tuning and evaluation tasks call (never the scoring or the explanations).
"""
import json
import math

CAT = "classic_stable_zjnu75_catalog"
SCH = "network_migration"
NS = f"{CAT}.{SCH}"
TRUTH = f"/Volumes/{CAT}/{SCH}/landing/_generator_truth"

WINDOW = ("2026-09-21", "2026-11-19")
TUNING = ("2026-09-21", "2026-10-30")      # evaluation-window days 1-40
HOLDOUT = ("2026-10-31", "2026-11-17")     # window days 41-58 (Amendment 3; days 59-60 reserved for the live demo)

# Timing rule: day D is scored at D+1 07:00 with rows landed by then.
ON_TIME = "available_ts <= CAST(date_add(business_date, 1) AS TIMESTAMP) + INTERVAL 7 HOURS"

FAMILIES_SQL = """
  LATERAL VIEW explode(array(
    named_struct('family', 'ACQUIRER_CHANNEL', 'slice_value', concat(acquirer_id, ' / ', channel)),
    named_struct('family', 'MCC_GROUP_XB', 'slice_value', concat(mcc_group, ' / ', IF(cross_border, 'CROSS_BORDER', 'DOMESTIC'))),
    named_struct('family', 'REGION', 'slice_value', region),
    named_struct('family', 'CHANNEL', 'slice_value', channel),
    named_struct('family', 'CARD_SEGMENT', 'slice_value', card_segment)
  )) t AS f"""


def load_manifest():
    return json.load(open(f"{TRUTH}/incident_manifest.json"))


def incident_labels(spark):
    """Planted decline rows per slice-day (method) and per acquirer-day (baseline), by incident.
    Answer-key use only: tuning and evaluation."""
    spark.read.format("delta").load(f"{TRUTH}/auth_truth").select("AUTH_ID", "cause") \
        .where("cause IN ('INC1','INC2','INC3','INC4','DECOY_NSF')").createOrReplaceTempView("truth_causes")
    method = spark.sql(f"""
      SELECT s.business_date, s.issuer_segment, f.family, f.slice_value,
             CASE WHEN t.cause = 'DECOY_NSF' THEN 'DECOY' ELSE t.cause END AS incident, count(*) AS incident_rows
      FROM {NS}.silver_auth s JOIN truth_causes t ON t.AUTH_ID = s.auth_id
      {FAMILIES_SQL}
      WHERE s.network = 'MRD' AND NOT s.approved AND {ON_TIME}
      GROUP BY ALL""")
    baseline = spark.sql(f"""
      SELECT s.business_date, s.acquirer_id,
             CASE WHEN t.cause = 'DECOY_NSF' THEN 'DECOY' ELSE t.cause END AS incident, count(*) AS incident_rows
      FROM {NS}.silver_auth s JOIN truth_causes t ON t.AUTH_ID = s.auth_id
      WHERE NOT s.approved AND {ON_TIME}
      GROUP BY ALL""")
    return method, baseline


def baseline_flags(spark):
    """Dashboard rule (EVAL_PROTOCOL section 3 + A2): acquirer-day decline rate (all declines, both
    networks) > 1.5 x the acquirer's trailing 7-day average daily decline rate. Fixed, not tuned."""
    return spark.sql(f"""
      WITH d AS (
        SELECT business_date, acquirer_id, count(*) AS attempts, count_if(NOT approved) AS declines
        FROM {NS}.silver_auth WHERE {ON_TIME} AND acquirer_id IS NOT NULL GROUP BY ALL),
      r AS (
        SELECT *, declines / attempts AS rate,
          avg(declines / attempts) OVER (PARTITION BY acquirer_id ORDER BY unix_date(business_date)
                                         RANGE BETWEEN 7 PRECEDING AND 1 PRECEDING) AS trailing_rate,
          count(*) OVER (PARTITION BY acquirer_id ORDER BY unix_date(business_date)
                         RANGE BETWEEN 7 PRECEDING AND 1 PRECEDING) AS trailing_days
        FROM d)
      SELECT business_date, acquirer_id, attempts, declines, rate, trailing_rate,
             declines - attempts * trailing_rate AS excess_declines
      FROM r WHERE trailing_days = 7 AND trailing_rate > 0 AND rate > 1.5 * trailing_rate""")


def wilson(k, n, z=1.96):
    """Wilson score interval: never zero width, even for k = 0 or k = n."""
    if n == 0:
        return (None, None)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def metrics(flags, manifest, split, method_name):
    """flags: list of dicts with business_date (str), hit (incident id or None), root_cause (method only).
    Returns the protocol measures for one split."""
    lo, hi = split
    incs = [m for m in manifest if m["id"] != "DECOY" and lo <= m["window"][0] <= hi]
    fl = [f for f in flags if lo <= f["business_date"] <= hi]
    hits = [f for f in fl if f["hit"] and f["hit"] != "DECOY"]
    caught = sorted({f["hit"] for f in hits})
    out = {"method": method_name, "split": f"{lo}..{hi}", "flags": len(fl), "hits": len(hits),
           "precision": (len(hits) / len(fl)) if fl else None, "precision_wilson95": wilson(len(hits), len(fl)),
           "incidents": [m["id"] for m in incs], "incidents_caught": caught,
           "incident_recall": (len([i for i in caught if i in [m["id"] for m in incs]]) / len(incs)) if incs else None,
           "decoy_flags": len([f for f in fl if f["hit"] == "DECOY"])}
    per = {}
    for m in incs:
        days = sorted({f["business_date"] for f in hits if f["hit"] == m["id"]})
        import datetime as _d
        start, end = _d.date.fromisoformat(m["window"][0]), _d.date.fromisoformat(m["window"][1])
        n_days = (end - start).days + 1
        first = min((f for f in hits if f["hit"] == m["id"]), key=lambda f: f["business_date"], default=None)
        per[m["id"]] = {
            "caught": bool(days), "first_flag": days[0] if days else None,
            "delay_days": ((_d.date.fromisoformat(days[0]) - start).days if days else None),
            "incident_days_flagged": f"{len(days)}/{n_days}",
            "root_cause_first_flag": first.get("root_cause") if first else None,
            "root_cause_matches": (first.get("root_cause") == m["type"]) if first and "root_cause" in first else None}
    out["per_incident"] = per
    hits_days = sum(int(v["incident_days_flagged"].split("/")[0]) for v in per.values())
    tot_days = sum(int(v["incident_days_flagged"].split("/")[1]) for v in per.values())
    out["incident_day_recall"] = (hits_days / tot_days) if tot_days else None
    return out
