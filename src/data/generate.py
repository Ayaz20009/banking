# Databricks notebook source
# MAGIC %md
# MAGIC # Synthetic source-system generator: card migration to an acquired network
# MAGIC
# MAGIC Writes raw files **as the source systems would export them** into
# MAGIC `/Volumes/<catalog>/<schema>/landing/<system>/<YYYY-MM-DD>/` plus a `_MANIFEST.json`
# MAGIC (control totals) written **last** in each folder.
# MAGIC
# MAGIC * All names, codes and IDs are invented. Synthetic data only.
# MAGIC * Every random choice is `xxhash64(seed:salt, key)`, never `rand()`, so counts are
# MAGIC   identical on every run regardless of Spark partitioning.
# MAGIC * Reruns are safe: a folder that already has `_MANIFEST.json` is skipped.
# MAGIC * `mode=backfill` writes everything except the held-back dates; `mode=replay` writes one held-back date.
# MAGIC * The answer key (planted findings) is written to `landing/_generator_truth/`, which the
# MAGIC   pipeline and the detection method never read.

# COMMAND ----------

import datetime as dt
import json
import math
import os
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor

from pyspark.sql import Window
from pyspark.sql import functions as F

dbutils.widgets.text("catalog", "classic_stable_zjnu75_catalog")
dbutils.widgets.text("schema", "network_migration")
dbutils.widgets.text("mode", "backfill")  # backfill | replay
dbutils.widgets.text("replay_date", "")
dbutils.widgets.text("seed", "20261120")

CAT = dbutils.widgets.get("catalog")
SCH = dbutils.widgets.get("schema")
MODE = dbutils.widgets.get("mode").strip().lower()
REPLAY_DATE = dbutils.widgets.get("replay_date").strip()
SEED = dbutils.widgets.get("seed").strip()

LANDING = f"/Volumes/{CAT}/{SCH}/landing"
TRUTH = f"{LANDING}/_generator_truth"
START, END = dt.date(2025, 11, 20), dt.date(2026, 11, 19)
HELD_BACK = ["2026-11-18", "2026-11-19"]
assert MODE in ("backfill", "replay"), MODE
if MODE == "replay":
    assert REPLAY_DATE in HELD_BACK, f"replay_date must be one of {HELD_BACK}"

# Scale (approved 2026-11-20): 45K cards, 40K merchants, 80 acquirers, ~30K attempts/day.
N_CARDS, N_MERCH, N_ACQ, DAILY = 45_000, 40_000, 80, 30_000
REUSE = MODE == "replay" and os.path.exists(f"{LANDING}/_generator_truth/auth_truth/_delta_log")
BG_MULT = 1.1  # calibrates the migrated-cohort approval gap (see the summary)

# COMMAND ----------

# MAGIC %md ## Deterministic helpers

# COMMAND ----------

P = 2147483647


def U(salt, *cols):
    """Uniform [0,1) from a hash of the seed, a salt and key columns. Deterministic."""
    return F.pmod(F.xxhash64(F.lit(f"{SEED}:{salt}"), *cols), F.lit(P)).cast("double") / P


def pick(u, values, weights):
    """Weighted categorical choice driven by uniform column u."""
    tot, acc, expr = float(sum(weights)), 0.0, None
    for v, w in zip(values[:-1], weights[:-1]):
        acc += w / tot
        expr = F.when(u < acc, F.lit(v)) if expr is None else expr.when(u < acc, F.lit(v))
    return expr.otherwise(F.lit(values[-1]))


def cmap(col, mapping, default=None):
    """CASE col WHEN k THEN v ... (literal map)."""
    expr = None
    for k, v in mapping.items():
        expr = F.when(col == F.lit(k), F.lit(v)) if expr is None else expr.when(col == F.lit(k), F.lit(v))
    return expr.otherwise(F.lit(default))


def normal(salt, *cols):
    u1 = U(salt + "_a", *cols) * 0.999998 + 1e-6
    u2 = U(salt + "_b", *cols)
    return F.sqrt(-2.0 * F.log(u1)) * F.cos(2 * math.pi * u2)


def d(s):
    return F.to_date(F.lit(s))


# COMMAND ----------

# MAGIC %md ## Reference lists (invented)

# COMMAND ----------

STATES = [("NY", "NE", 9), ("NJ", "NE", 4), ("PA", "NE", 5), ("MA", "NE", 3), ("CT", "NE", 2),
          ("FL", "SE", 9), ("GA", "SE", 5), ("NC", "SE", 5), ("VA", "SE", 4), ("TN", "SE", 3), ("SC", "SE", 2),
          ("IL", "MW", 5), ("OH", "MW", 5), ("MI", "MW", 4), ("MN", "MW", 2), ("WI", "MW", 2), ("MO", "MW", 2),
          ("TX", "SW", 12), ("AZ", "SW", 3), ("OK", "SW", 1), ("NM", "SW", 1),
          ("CA", "W", 15), ("WA", "W", 3), ("OR", "W", 2), ("CO", "W", 2), ("NV", "W", 1), ("UT", "W", 1)]
STATE_REGION = {s: r for s, r, _ in STATES}
STATE_TZ = {s: ("America/New_York" if r in ("NE", "SE") else "America/Chicago" if r == "MW" else None) for s, r, _ in STATES}
STATE_TZ.update({"TX": "America/Chicago", "OK": "America/Chicago", "AZ": "America/Phoenix", "NM": "America/Denver",
                 "CO": "America/Denver", "UT": "America/Denver", "CA": "America/Los_Angeles",
                 "WA": "America/Los_Angeles", "OR": "America/Los_Angeles", "NV": "America/Los_Angeles"})

CITIES = ["Ashford Glen", "Brookhaven Point", "Cedarview", "Dunmore Heights", "Elm Crossing", "Fairhollow",
          "Granite Bay", "Harrow Field", "Ivywood", "Juniper Flats", "Kestrel Park", "Larkspur Hill", "Millbrook",
          "Northvale", "Orchard Bend", "Pebble Ford", "Quarry Lake", "Rosemont Ridge", "Silverleaf", "Thornbury",
          "Upton Vale", "Violet Springs", "Westhollow", "Yarrow Point", "Zephyr Cove"]
PFX = ["Copperleaf", "Bluestone", "Harbor Lane", "Silver Fern", "Red Maple", "Juniper", "Oakhollow",
       "Clearwater Row", "Summit Peak", "Prairie Gate", "Lantern Hill", "Ironwood", "Meadowlark", "Brightwater",
       "Stonebridge", "Willow Bend", "Golden Mile", "Riverbend", "Pinecrest", "Sandpiper", "Highline", "Foxglove",
       "Cobalt Bay", "Saltmarsh", "Amberly", "Kingfisher", "Driftwood", "Marigold", "Birchstone", "Tidewater",
       "Quillfeather", "Larchmont Way", "Emberline", "Glasswing", "Hollowtree", "Moonpetal", "Starling Row",
       "Thistledown", "Wrenfield", "Zinnia Park"]
MCC_SUFFIX = {5411: "Market", 5812: "Kitchen", 5814: "Quick Eats", 5541: "Fuel Stop", 5311: "Department Store",
              5651: "Outfitters", 5912: "Pharmacy", 5200: "Hardware", 5999: "Goods Co", 7011: "Inn & Suites",
              4111: "Transit", 5815: "Media", 5818: "Digital", 4511: "Airways", 4722: "Travel", 5732: "Electronics",
              4900: "Utilities", 4814: "Telecom", 4899: "Streaming", 6300: "Insurance", 5968: "Subscriptions",
              7512: "Car Rental"}
MCC_MEAN = {5411: 62, 5812: 48, 5814: 13, 5541: 45, 5311: 95, 5651: 78, 5912: 32, 5200: 92, 5999: 55, 7011: 290,
            4111: 6, 5815: 12, 5818: 25, 4511: 380, 4722: 450, 5732: 240, 4900: 135, 4814: 88, 4899: 16,
            6300: 165, 5968: 22, 7512: 210}
POOL_MCC = {
    "CP_DOM": ([5411, 5812, 5814, 5541, 5311, 5651, 5912, 5200, 5999, 7011, 4111], [18, 20, 14, 12, 6, 7, 7, 5, 6, 2, 3]),
    "ECOM_DOM": ([5999, 5651, 5815, 5818, 5311, 4511, 7011, 4722, 5732], [25, 15, 15, 10, 12, 8, 7, 4, 4]),
    "REC_DOM": ([4900, 4814, 4899, 6300, 5968], [25, 25, 20, 15, 15]),
    "CP_FOR": ([5812, 7011, 5411, 4111, 5999, 7512], [25, 25, 10, 10, 15, 15]),
    "ECOM_FOR": ([4511, 7011, 4722, 5818, 5999], [30, 25, 15, 15, 15]),
}
TRAVEL_MCC = [4511, 4722, 7011, 7512]
ACQ_PFX = ["Northgate", "Clearpath", "Bayside", "Keystone", "Lakemont", "Ridgeview", "Summitline", "Crestwave",
           "Harborpoint", "Ironbridge", "Westmark", "Eastfield", "Pinnacle Row", "Stonegate", "Redwater",
           "Bluefield", "Ridgeline", "Cascadia", "Fairwind", "Granitepoint"]
ACQ_SFX = ["Merchant Services", "Payments", "Acquiring", "Payment Solutions"]
WAVES = {1: "2026-01-12", 2: "2026-02-23", 3: "2026-04-13", 4: "2026-06-01", 5: "2026-07-20", 6: "2026-09-08",
         7: "2027-02-18", 8: "2027-04-15", 9: "2027-06-10", 10: "2027-08-05"}
INC = {  # approved planted incidents (evaluation window 2026-09-21 -> 2026-11-19)
    "INC1": ("2026-09-24", "2026-10-08"), "INC2": ("2026-10-12", "2026-10-20"),
    "INC3": ("2026-11-02", "2026-11-12"), "INC4": ("2026-11-14", "2026-11-16"), "DECOY": ("2026-11-06", "2026-11-08"),
}
LATE_ATL = ["2026-03-10", "2026-06-17", "2026-10-14"]   # DQ9
TRUNC_ATL = "2026-08-05"                                 # DQ8
UNMAPPED = [f"M2{i:02d}" for i in range(1, 13)]          # DQ5

# COMMAND ----------

# MAGIC %md ## Acquirers, merchants, cards (master data)

# COMMAND ----------

w = [1 / (i + 1) ** 0.9 for i in range(N_ACQ)]
w[16] = 0.0
s = sum(w)
ACQ_W = [x / s * 0.975 for x in w]
ACQ_W[16] = 0.025  # ACQ-017 = 2.5% of merchants (~200 e-commerce merchants)
REGIONS = ["NE", "SE", "MW", "SW", "W"]
acq_rows = []
for i in range(N_ACQ):
    acq_rows.append(dict(
        idx=i, acquirerId=f"ACQ-{i + 1:03d}", acquirerName=f"{ACQ_PFX[i % 20]} {ACQ_SFX[i // 20]}",
        bin=str(900000 + (i + 1) * 137), region=REGIONS[(i * 7) % 5], mrdCertified=True,
        certifiedDate=(dt.date(2025, 6, 2) + dt.timedelta(days=(i * 37) % 160)).isoformat(),
        lastConfigChange=(dt.date(2025, 5, 1) + dt.timedelta(days=(i * 53) % 300)).isoformat()))
acq = spark.createDataFrame(acq_rows)

m = spark.range(N_MERCH).withColumnRenamed("id", "mseq")
m = m.withColumn("pool", pick(U("m_pool", "mseq"), list(POOL_MCC), [60, 20, 8, 7, 5]))
mcc_expr = None
for p, (codes, wts) in POOL_MCC.items():
    c = pick(U("m_mcc", "mseq"), codes, wts)
    mcc_expr = F.when(F.col("pool") == p, c) if mcc_expr is None else mcc_expr.when(F.col("pool") == p, c)
m = m.withColumn("mcc", mcc_expr.cast("int"))
m = (m.withColumn("foreign", F.col("pool").endswith("_FOR"))
     .withColumn("cntry", F.when(F.col("foreign"), pick(U("m_cntry", "mseq"), ["CAN", "MEX", "GBR", "FRA", "JPN", "DEU"],
                                                       [25, 20, 20, 10, 10, 15])).otherwise(F.lit("USA")))
     .withColumn("state", F.when(F.col("foreign"), F.lit(None).cast("string"))
                 .otherwise(pick(U("m_state", "mseq"), [s_[0] for s_ in STATES], [s_[2] for s_ in STATES])))
     .withColumn("region", F.when(F.col("foreign"), F.lit("INTL")).otherwise(cmap(F.col("state"), STATE_REGION)))
     .withColumn("tz", F.when(F.col("foreign"), F.lit("UTC")).otherwise(cmap(F.col("state"), STATE_TZ)))
     .withColumn("city", pick(U("m_city", "mseq"), CITIES, [1] * len(CITIES)))
     .withColumn("acq_idx", pick(U("m_acq", "mseq"), list(range(N_ACQ)), ACQ_W).cast("int"))
     .withColumn("acquirerId", F.format_string("ACQ-%03d", F.col("acq_idx") + 1))
     .withColumn("acq_bin", (F.lit(900000) + (F.col("acq_idx") + 1) * 137).cast("string"))
     .withColumn("MRCH_NUM", F.concat(F.lit("MR"), F.lpad(((F.col("mseq") * 7919 + 101) % 1000000000).cast("string"), 9, "0")))
     .withColumn("MRD_MID", F.concat(F.lit("MRD"), F.lpad(((F.col("mseq") * 104723 + 7) % 100000000).cast("string"), 8, "0")))
     .withColumn("ATL_MID9", F.lpad(((F.col("mseq") * 15485863 + 3) % 1000000000).cast("string"), 9, "0"))
     .withColumn("dq6_mid_variant", U("dq6", "mseq") < 0.15)        # DQ6
     .withColumn("atl_padded", U("atl_pad", "mseq") < 0.08)          # messiness: zero padding
     .withColumn("dba_trailing", U("dba_sp", "mseq") < 0.08)         # messiness: trailing spaces
     .withColumn("dq10_stale_mcc", U("dq10", "mseq") < 0.02)         # DQ10
     .withColumn("mrd_feed_mid", F.when(F.col("dq6_mid_variant"),
                                        F.concat(F.lit("M-"), F.substring("MRD_MID", 4, 8).cast("int").cast("string")))
                 .otherwise(F.col("MRD_MID")))
     .withColumn("ATL_MID", F.when(F.col("atl_padded"), F.lpad("ATL_MID9", 15, "0")).otherwise(F.col("ATL_MID9")))
     .withColumn("suffix", cmap(F.col("mcc"), MCC_SUFFIX))
     .withColumn("DBA_NAME_CLEAN", F.concat_ws(" ", pick(U("m_pfx", "mseq"), PFX, [1] * len(PFX)), F.col("suffix"),
                                               F.concat(F.lit("#"), F.lpad(((F.col("mseq") * 31) % 9973).cast("string"), 4, "0"))))
     .withColumn("DBA_NAME", F.when(F.col("dba_trailing"), F.concat("DBA_NAME_CLEAN", F.lit("   "))).otherwise(F.col("DBA_NAME_CLEAN")))
     .withColumn("mcc_reported", F.when(F.col("dq10_stale_mcc"),
                                        F.when(F.col("mcc") == 5999, F.lit(5311)).otherwise(F.lit(5999))).otherwise(F.col("mcc")))
     .withColumn("pool_idx", F.row_number().over(Window.partitionBy("pool").orderBy("mseq")) - 1)
     .withColumn("EFF_DT", F.date_add(F.lit("2019-01-01"), (U("m_eff", "mseq") * 2000).cast("int"))))
if not REUSE:
    m.write.mode("overwrite").format("delta").save(f"{TRUTH}/merchants")
m = spark.read.format("delta").load(f"{TRUTH}/merchants")
POOL_SIZE = {r["pool"]: r["n"] for r in m.groupBy("pool").agg(F.count("*").alias("n")).collect()}

c = spark.range(N_CARDS).withColumnRenamed("id", "cseq")
c = (c.withColumn("CARD_REF", F.concat(F.lit("CR"), F.lpad(((F.col("cseq") * 104729 + 12345) % 100000000).cast("string"), 8, "0")))
     .withColumn("SEGMENT", pick(U("c_seg", "cseq"), ["DOMESTIC", "ECOM_HEAVY", "RECURRING_HEAVY", "WALLET_HEAVY", "INTL_TRAVELER"],
                                 [55, 15, 12, 10, 8]))
     .withColumn("PRODUCT_CD", pick(U("c_prod", "cseq"), ["RWD", "CSH", "TRV", "BUS", "SEC"], [40, 30, 10, 12, 8]))
     .withColumn("HOME_ST", pick(U("c_st", "cseq"), [s_[0] for s_ in STATES], [s_[2] for s_ in STATES]))
     .withColumn("ISSUER_SEG", F.when(U("c_iss", "cseq") < 0.10, F.lit("THIRD_PARTY")).otherwise(F.lit("OWN")))
     .withColumn("complex", F.col("SEGMENT") != "DOMESTIC")
     .withColumn("s1", U("c_w1", "cseq") + F.when(F.col("complex"), 0.25).otherwise(0.0))
     .withColumn("r1", F.row_number().over(Window.orderBy("s1", "cseq")))
     .withColumn("wave_a", F.when(F.col("r1") <= 9000, ((F.col("r1") - 1) / 1500).cast("int") + 1))
     .withColumn("s2", U("c_w2", "cseq") - F.when(F.col("complex"), 0.5).otherwise(0.0))
     .withColumn("r2", F.row_number().over(Window.partitionBy(F.col("wave_a").isNull()).orderBy("s2", "cseq")))
     .withColumn("WAVE_ID", F.coalesce(F.col("wave_a"),
                                       F.when(F.col("r2") <= 6000, ((F.col("r2") - 1) / 1500).cast("int") + 7)))
     .withColumn("planned0", F.to_date(cmap(F.col("WAVE_ID"), WAVES)))
     .withColumn("slipped", (F.col("WAVE_ID") <= 6) & (U("c_slip", "cseq") < 0.03))
     .withColumn("planned_final", F.when(F.col("slipped"), F.date_add("planned0", 7)).otherwise(F.col("planned0")))
     .withColumn("mig_date", F.when(F.col("WAVE_ID") <= 6, F.col("planned_final")))
     .withColumn("dq7_stale", (F.col("WAVE_ID") <= 6) & (U("dq7", "cseq") < 200 / 9000))
     .drop("s1", "r1", "s2", "r2", "wave_a", "complex"))
if not REUSE:
    c.write.mode("overwrite").format("delta").save(f"{TRUTH}/cards")
c = spark.read.format("delta").load(f"{TRUTH}/cards")

# COMMAND ----------

# MAGIC %md ## Authorization attempts (truth table)

# COMMAND ----------

days = (spark.sql(f"SELECT explode(sequence(DATE'{START}', DATE'{END}', INTERVAL 1 DAY)) AS bdate")
        .withColumn("dow_m", cmap(F.dayofweek("bdate"), {1: 0.86, 2: 0.95, 3: 0.97, 4: 1.0, 5: 1.02, 6: 1.12, 7: 1.08}))
        .withColumn("season", 1 + 0.04 * F.sin(2 * math.pi * F.dayofyear("bdate") / 365.0))
        .withColumn("holiday", F.when((F.month("bdate") == 12) & (F.dayofmonth("bdate") <= 24), 1.12)
                    .when((F.month("bdate") == 11) & (F.dayofmonth("bdate").between(27, 30)) & (F.year("bdate") == 2025), 1.10)
                    .otherwise(1.0))
        .withColumn("n", F.round(F.lit(DAILY) * F.col("dow_m") * F.col("season") * F.col("holiday")).cast("int"))
        .repartition(96))

a = days.select("bdate", F.explode(F.sequence(F.lit(0), F.col("n") - 1)).alias("j"))
a = a.withColumn("key", F.concat(F.date_format("bdate", "yyyyMMdd"), F.lpad(F.col("j").cast("string"), 6, "0")))
a = a.withColumn("cseq", F.least(F.floor(F.lit(N_CARDS) * F.pow(U("a_card", "key"), 1.3)), F.lit(N_CARDS - 1)).cast("long"))
a = a.join(F.broadcast(c.select("cseq", "CARD_REF", "SEGMENT", "ISSUER_SEG", "WAVE_ID", "mig_date")), "cseq")

CH = ["CP", "ECOM", "REC", "MANUAL"]
CH_W = {"DOMESTIC": [75, 18, 6, 1], "ECOM_HEAVY": [35, 55, 9, 1], "RECURRING_HEAVY": [50, 20, 29, 1],
        "WALLET_HEAVY": [60, 30, 9, 1], "INTL_TRAVELER": [60, 30, 9, 1]}
ch_expr = None
for seg, wts in CH_W.items():
    e = pick(U("a_ch", "key"), CH, wts)
    ch_expr = F.when(F.col("SEGMENT") == seg, e) if ch_expr is None else ch_expr.when(F.col("SEGMENT") == seg, e)
a = a.withColumn("channel", ch_expr)
a = a.withColumn("xb", F.col("channel").isin("CP", "ECOM") &
                 (U("a_xb", "key") < F.when(F.col("SEGMENT") == "INTL_TRAVELER", 0.25).otherwise(0.02)))
a = a.withColumn("pool", F.when(F.col("xb") & (F.col("channel") == "CP"), "CP_FOR")
                 .when(F.col("xb"), "ECOM_FOR").when(F.col("channel") == "ECOM", "ECOM_DOM")
                 .when(F.col("channel") == "REC", "REC_DOM").otherwise("CP_DOM"))
a = a.withColumn("pool_n", cmap(F.col("pool"), POOL_SIZE))
a = a.withColumn("pool_idx", F.least(F.floor(F.col("pool_n") * F.pow(U("a_merch", "key"), 1.6)), F.col("pool_n") - 1).cast("int"))
a = a.join(F.broadcast(m.select("pool", "pool_idx", "mseq", "MRCH_NUM", "mrd_feed_mid", "ATL_MID", "mcc", "mcc_reported",
                                "cntry", "region", "tz", "acquirerId", "acq_bin")), ["pool", "pool_idx"])

tok_p = (F.when(F.col("SEGMENT") == "WALLET_HEAVY", 0.70)
         .when(F.col("channel") == "ECOM", 0.35).when(F.col("channel") == "CP", 0.08)
         .when(F.col("channel") == "REC", 0.50).otherwise(0.0))
a = (a.withColumn("tokenized", U("a_tok", "key") < tok_p)
     .withColumn("WALLET_IND", F.when(~F.col("tokenized"), "N").when(F.col("channel") == "CP", "W")
                 .when(F.col("channel") == "REC", "C").otherwise(pick(U("a_tokt", "key"), ["W", "C"], [40, 60])))
     .withColumn("POS_ENTRY_MODE", F.when(F.col("channel") == "CP", pick(U("a_pos", "key"), ["05", "07"], [55, 45]))
                 .when(F.col("channel") == "ECOM", "81").when(F.col("channel") == "REC", "10").otherwise("01"))
     .withColumn("RECUR_IND", F.when(F.col("channel") == "REC", "Y").otherwise("N")))

HOUR_W = {"CP": [0.3, .2, .1, .1, .2, .5, 1.2, 2.5, 3.5, 4, 4.5, 5.5, 7, 6.5, 5.5, 5, 5.5, 6.5, 7, 6, 5, 3.5, 2, 1],
          "ECOM": [1.5, 1, .7, .5, .5, .7, 1.2, 2, 3, 3.5, 4, 4.5, 5, 5, 4.5, 4.5, 4.5, 5, 5.5, 6.5, 7, 7, 5.5, 3],
          "REC": [3, 6, 10, 12, 10, 6, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2]}
hour = (F.when(F.col("channel") == "ECOM", pick(U("a_hr", "key"), list(range(24)), HOUR_W["ECOM"]))
        .when(F.col("channel") == "REC", pick(U("a_hr", "key"), list(range(24)), HOUR_W["REC"]))
        .otherwise(pick(U("a_hr", "key"), list(range(24)), HOUR_W["CP"])))
a = (a.withColumn("hh", hour.cast("int"))
     .withColumn("mi", (U("a_mi", "key") * 60).cast("int")).withColumn("ss", (U("a_ss", "key") * 60).cast("int"))
     .withColumn("ts_local", F.expr("make_timestamp(year(bdate), month(bdate), day(bdate), hh, mi, ss)"))
     .withColumn("ts_utc", F.to_utc_timestamp("ts_local", F.col("tz")))
     .withColumn("amount", F.greatest(F.lit(1.0), F.round(cmap(F.col("mcc"), MCC_MEAN).cast("double") *
                                                         F.exp(0.65 * normal("a_amt", "key") - 0.21125), 2))))

# --- routing and decisions -------------------------------------------------
a = a.withColumn("migrated", F.col("mig_date").isNotNull() & (F.col("bdate") >= F.col("mig_date")))
a = a.withColumn("network", F.when(F.col("migrated"), "MRD").otherwise("ATL"))
mrd = F.col("network") == "MRD"


def win(name):
    s_, e_ = INC[name]
    return F.col("bdate").between(d(s_), d(e_))


inc1 = mrd & win("INC1") & (F.col("acquirerId") == "ACQ-017") & (F.col("POS_ENTRY_MODE") == "81") & (U("inc1", "key") < 0.55)
inc2 = mrd & win("INC2") & F.col("xb") & F.col("mcc").isin(TRAVEL_MCC) & (U("inc2", "key") < 0.35)
inc3 = mrd & win("INC3") & (F.col("RECUR_IND") == "Y") & (U("inc3", "key") < 0.30)
inc4 = mrd & win("INC4") & (F.col("region") == "SE") & (U("inc4", "key") < 0.25)
stip = U("stip", "key") < 0.40
decoy = win("DECOY") & (U("decoy", "key") < 0.025)
legit_p = F.when(F.col("SEGMENT") == "INTL_TRAVELER", 0.028).otherwise(0.021)
legit = U("legit", "key") < legit_p
reason = pick(U("legit_r", "key"), ["NSF", "DNH", "EXP", "INV", "NP", "FRAUD", "LIMIT"], [42, 23, 7, 5, 7, 12, 4])
base_bg = cmap(F.col("channel"), {"CP": 0.0040, "ECOM": 0.0080, "REC": 0.0100, "MANUAL": 0.0050}).cast("double")
bg_rate = F.lit(BG_MULT) * (base_bg + F.when(F.col("tokenized"), 0.005).otherwise(0.0) + F.when(F.col("xb"), 0.025).otherwise(0.0))
bg = mrd & (U("bg", "key") < bg_rate)
bg_cat = (F.when(F.col("xb"), "BG_XB").when(F.col("tokenized"), "BG_TOKEN").when(F.col("channel") == "REC", "BG_COF")
          .when(F.col("channel") == "ECOM", "BG_CFG").otherwise(pick(U("bg_c", "key"), ["BG_CFG", "BG_SYS"], [50, 50])))
atl_bg = (~mrd) & (U("atl_bg", "key") < 0.0005)
unm = mrd & (U("unm", "key") < 0.0002)

a = a.withColumn("cause", F.when(inc1, "INC1").when(inc2, "INC2").when(inc3, "INC3")
                 .when(inc4 & stip, "INC4_STIP").when(inc4, "INC4").when(decoy, "DECOY_NSF")
                 .when(legit, F.concat(F.lit("LEGIT_"), reason)).when(bg, bg_cat).when(atl_bg, "ATL_SYS")
                 .when(unm, "UNMAPPED").otherwise("APPROVE"))
a = a.withColumn("approved", F.col("cause").isin("APPROVE", "INC4_STIP"))

ISS_CD = {"APPROVE": "00", "INC4_STIP": "00", "INC1": "05", "INC2": "57", "INC3": "14", "INC4": "91",
          "DECOY_NSF": "51", "LEGIT_NSF": "51", "LEGIT_DNH": "05", "LEGIT_EXP": "54", "LEGIT_INV": "14",
          "LEGIT_NP": "57", "LEGIT_FRAUD": "59", "LEGIT_LIMIT": "61", "BG_XB": "57", "BG_TOKEN": "05",
          "BG_COF": "14", "BG_CFG": "58", "BG_SYS": "96", "ATL_SYS": "96", "UNMAPPED": "05"}
MRD_CD = {"APPROVE": "M000", "INC4_STIP": "M000", "INC1": "M065", "INC2": "M057", "INC3": "M014", "INC4": "M091",
          "DECOY_NSF": "M151", "LEGIT_NSF": "M151", "LEGIT_DNH": "M105", "LEGIT_EXP": "M154", "LEGIT_INV": "M114",
          "LEGIT_NP": "M157", "LEGIT_FRAUD": "M159", "LEGIT_LIMIT": "M161", "BG_XB": "M059", "BG_TOKEN": "M062",
          "BG_COF": "M015", "BG_CFG": "M058", "BG_SYS": "M096"}
ATL_CD = {"APPROVE": "000", "DECOY_NSF": "116", "LEGIT_NSF": "116", "LEGIT_DNH": "100", "LEGIT_EXP": "101",
          "LEGIT_INV": "111", "LEGIT_NP": "119", "LEGIT_FRAUD": "102", "LEGIT_LIMIT": "121", "ATL_SYS": "909"}
a = (a.withColumn("iss_resp", cmap(F.col("cause"), ISS_CD))
     .withColumn("mrd_resp", F.when(F.col("cause") == "UNMAPPED", pick(U("unm_c", "key"), UNMAPPED, [1] * 12))
                 .otherwise(cmap(F.col("cause"), MRD_CD)))
     .withColumn("atl_resp", cmap(F.col("cause"), ATL_CD)))

# --- data-quality flags on the issuer export ------------------------------
dq_u = U("dq", "key")
a = (a.withColumn("AUTH_ID", F.concat(F.lit("A"), F.col("key")))
     .withColumn("dq2_bad_amt", dq_u < 0.003)
     .withColumn("dq3_future_ts", (dq_u >= 0.003) & (dq_u < 0.004))
     .withColumn("dq4_null_id", (dq_u >= 0.004) & (dq_u < 0.005))
     .withColumn("dq1_dup", (U("dup", "key") < 0.02) & ~F.col("dq4_null_id"))
     .withColumn("dup_next_day", U("dup_nd", "key") < 0.40)
     .withColumn("mcc_blank", U("mccb", "key") < 0.01)
     .withColumn("cntry_blank", U("cb", "key") < 0.005)
     .withColumn("curr_usd", U("cur", "key") < 0.002)
     .withColumn("atl_trunc", (F.col("bdate") == d(TRUNC_ATL)) & (U("trunc", "key") < 0.018)))

if not REUSE:
    a.drop("pool_n").write.mode("overwrite").format("delta").save(f"{TRUTH}/auth_truth")
t = spark.read.format("delta").load(f"{TRUTH}/auth_truth")

# COMMAND ----------

# MAGIC %md ## Source-system exports (one DataFrame per system, column `dt` = business-date folder)

# COMMAND ----------

bad_amt = pick(U("bad_amt_v", "key"), ["0.00", "NEG", "N/A", "COMMA"], [35, 25, 25, 15])
amt_str = F.format_string("%.2f", F.col("amount"))
iss = t.select(
    F.date_format("bdate", "yyyy-MM-dd").alias("dt"),
    F.when(F.col("dq4_null_id"), F.lit(None).cast("string")).otherwise(F.col("AUTH_ID")).alias("AUTH_ID"),
    F.date_format(F.when(F.col("dq3_future_ts"), F.col("ts_local") + F.expr("INTERVAL 1 YEAR")).otherwise(F.col("ts_local")),
                  "yyyy-MM-dd HH:mm:ss").alias("AUTH_TS_LOCAL"),
    F.col("tz").alias("AUTH_TZ"), "CARD_REF", F.col("MRCH_NUM").alias("CARD_ACCEPTOR_ID"),
    F.col("acq_bin").alias("ACQ_INST_ID"),
    F.when(F.col("mcc_blank"), F.lit(None).cast("string")).otherwise(F.col("mcc_reported").cast("string")).alias("MCC"),
    "POS_ENTRY_MODE",
    F.when(F.col("dq2_bad_amt"), F.when(bad_amt == "NEG", F.concat(F.lit("-"), amt_str))
           .when(bad_amt == "COMMA", F.regexp_replace(amt_str, r"\.", ",")).otherwise(bad_amt)).otherwise(amt_str).alias("TRAN_AMT"),
    F.when(F.col("curr_usd"), F.lit("USD")).otherwise(F.lit("840")).alias("CURR_CD"),
    F.when(F.col("cntry_blank"), F.lit(None).cast("string")).otherwise(F.col("cntry")).alias("TERM_CNTRY"),
    F.col("network").alias("NETWORK_ID"), "WALLET_IND", "RECUR_IND",
    F.when(F.col("approved"), "A").otherwise("D").alias("AUTH_DECISION"), F.col("iss_resp").alias("ISS_RESP_CD"),
    "dq1_dup", "dup_next_day", F.col("amount").alias("_amt_true"), "dq2_bad_amt")
dups = (iss.filter("dq1_dup")
        .withColumn("dt", F.when(F.col("dup_next_day") & (F.col("dt") < F.lit(END.isoformat())),
                                 F.date_format(F.date_add(F.to_date("dt"), 1), "yyyy-MM-dd")).otherwise(F.col("dt"))))
iss_all = iss.unionByName(dups).drop("dq1_dup", "dup_next_day")
ISS_COLS = ["AUTH_ID", "AUTH_TS_LOCAL", "AUTH_TZ", "CARD_REF", "CARD_ACCEPTOR_ID", "ACQ_INST_ID", "MCC", "POS_ENTRY_MODE",
            "TRAN_AMT", "CURR_CD", "TERM_CNTRY", "NETWORK_ID", "WALLET_IND", "RECUR_IND", "AUTH_DECISION", "ISS_RESP_CD"]

mrd_df = (t.filter("network = 'MRD'").select(
    F.date_format("bdate", "yyyy-MM-dd").alias("dt"),
    F.concat(F.lit("MRD"), F.lower(F.hex(F.xxhash64(F.lit(SEED), "key")))).alias("netTxnId"),
    F.col("AUTH_ID").alias("issuerAuthRef"),
    F.date_format(F.col("ts_utc") + F.make_interval(secs=(U("lat", "key") * 1.8 + 0.2)),
                  "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'").alias("eventTimeUtc"),
    F.col("mrd_feed_mid").alias("merchantNetworkId"), F.col("acquirerId").alias("acquirerCode"),
    F.round(F.col("amount") * 100).cast("long").alias("amountMinor"), F.lit("USD").alias("currency"),
    F.col("mrd_resp").alias("responseCode"),
    F.when(F.col("cause") == "INC4_STIP", "STIP").otherwise(pick(U("path", "key"), ["DIRECT", "GATEWAY"], [85, 15])).alias("processingPath"),
    F.when(F.col("WALLET_IND") == "W", pick(U("trq", "key"), ["TR-40010", "TR-40022", "TR-40037"], [55, 35, 10]))
    .when(F.col("WALLET_IND") == "C", F.concat(F.lit("TR-6"), F.lpad((F.col("mseq") % 9000).cast("string"), 4, "0"))).alias("tokenRequestorId"),
    F.col("xb").alias("crossBorder"), (F.col("cause") == "INC4_STIP").alias("stipFlag"),
    F.col("amount").alias("_amt_true")))

atl_df = (t.filter("network = 'ATL' AND NOT atl_trunc").select(
    F.date_format("bdate", "yyyy-MM-dd").alias("dt"),
    F.concat(F.lit("ATL"), F.lpad(F.pmod(F.xxhash64(F.lit("atl"), "key"), F.lit(10 ** 12)).cast("string"), 12, "0")).alias("txn_ref"),
    F.col("AUTH_ID").alias("auth_reference"), F.date_format("ts_local", "MM/dd/yyyy").alias("txn_date"),
    F.date_format("ts_local", "HHmmss").alias("txn_time"), F.col("ATL_MID").alias("mer_id"), "acq_bin",
    F.format_string("%.2f", F.col("amount")).alias("amt"), F.col("atl_resp").alias("resp_cd"),
    F.when(F.col("approved"), F.lit("  ")).otherwise(F.concat(F.lit("R"), (F.pmod(F.xxhash64("key"), F.lit(9)) + 1).cast("string"))).alias("rsn_cd"),
    F.when(F.col("xb"), "Y").otherwise("N").alias("xb_flag"), F.col("POS_ENTRY_MODE").alias("pos_cd"),
    F.col("amount").alias("_amt_true")))
# intended ATL counts (pre-truncation) for the control totals -> DQ8 mismatch
atl_intended = {r["dt"]: (r["n"], r["s"]) for r in t.filter("network = 'ATL'").groupBy(
    F.date_format("bdate", "yyyy-MM-dd").alias("dt")).agg(F.count("*").alias("n"), F.round(F.sum("amount"), 2).alias("s")).collect()}

# Merchant master: full load on day 1 + ~50 change records/day
MM_COLS = ["MRCH_NUM", "DBA_NAME", "MCC", "CITY", "STATE", "CNTRY", "ACQ_INST_ID", "MRD_MID", "ATL_MID", "STATUS", "EFF_DT"]
mm_full = m.select(F.lit(START.isoformat()).alias("dt"), "MRCH_NUM", "DBA_NAME", F.col("mcc").cast("string").alias("MCC"),
                   F.col("city").alias("CITY"), F.col("state").alias("STATE"), F.col("cntry").alias("CNTRY"),
                   F.col("acq_bin").alias("ACQ_INST_ID"), "MRD_MID", "ATL_MID", F.lit("A").alias("STATUS"),
                   F.date_format("EFF_DT", "yyyy-MM-dd").alias("EFF_DT"))
chg = (spark.sql(f"SELECT explode(sequence(DATE'{START + dt.timedelta(days=1)}', DATE'{END}', INTERVAL 1 DAY)) AS bdate")
       .select("bdate", F.explode(F.sequence(F.lit(0), F.lit(49))).alias("k"))
       .withColumn("ck", F.concat(F.date_format("bdate", "yyyyMMdd"), F.col("k").cast("string")))
       .withColumn("mseq", F.floor(U("mchg", "ck") * N_MERCH).cast("long")))
mm_delta = (chg.join(m, "mseq").select(
    F.date_format("bdate", "yyyy-MM-dd").alias("dt"), "MRCH_NUM", "DBA_NAME", F.col("mcc").cast("string").alias("MCC"),
    pick(U("mchg_city", "ck"), CITIES, [1] * len(CITIES)).alias("CITY"), F.col("state").alias("STATE"),
    F.col("cntry").alias("CNTRY"), F.col("acq_bin").alias("ACQ_INST_ID"), "MRD_MID", "ATL_MID",
    pick(U("mchg_st", "ck"), ["A", "A", "A", "S"], [1, 1, 1, 0.15]).alias("STATUS"),
    F.date_format("bdate", "yyyy-MM-dd").alias("EFF_DT")))
mm_df = mm_full.unionByName(mm_delta)

# Card portfolio: full load + slip updates + migration updates + DQ7 stale re-sends
CP_COLS = ["CARD_REF", "PRODUCT_CD", "SEGMENT", "HOME_ST", "WAVE_ID", "PLANNED_MIG_DT", "ACTUAL_MIG_DT", "ISSUER_SEG", "STATUS", "UPDATE_TS"]


def card_rows(df, dt_col, planned, actual, upd):
    return df.select(F.date_format(dt_col, "yyyy-MM-dd").alias("dt"), "CARD_REF", "PRODUCT_CD", "SEGMENT", "HOME_ST",
                     F.col("WAVE_ID").cast("string").alias("WAVE_ID"), F.date_format(planned, "yyyy-MM-dd").alias("PLANNED_MIG_DT"),
                     F.date_format(actual, "yyyy-MM-dd").alias("ACTUAL_MIG_DT"), "ISSUER_SEG", F.lit("ACTIVE").alias("STATUS"),
                     F.date_format(upd, "yyyy-MM-dd HH:mm:ss").alias("UPDATE_TS"))


full_ts = F.to_timestamp(F.lit(f"{START} 01:00:00"))
cp_full = card_rows(c, F.lit(START), F.col("planned0"), F.lit(None).cast("date"), full_ts)
slip_dt = F.date_sub("planned0", 14)
cp_slip = card_rows(c.filter("slipped"), slip_dt, F.col("planned_final"), F.lit(None).cast("date"),
                    F.to_timestamp(F.concat(F.date_format(slip_dt, "yyyy-MM-dd"), F.lit(" 02:00:00"))))
cp_mig = card_rows(c.filter("mig_date IS NOT NULL"), F.col("mig_date"), F.col("planned_final"), F.col("mig_date"),
                   F.to_timestamp(F.concat(F.date_format("mig_date", "yyyy-MM-dd"), F.lit(" 03:00:00"))) +
                   F.make_interval(secs=(F.col("cseq") % 3600).cast("double")))
cp_stale = card_rows(c.filter("dq7_stale"), F.date_add("mig_date", 10), F.col("planned0"), F.lit(None).cast("date"), full_ts)
cp_df = cp_full.unionByName(cp_slip).unionByName(cp_mig).unionByName(cp_stale)

# COMMAND ----------

# MAGIC %md ## Writer: one file per folder, control-total manifest written last, skip complete folders

# COMMAND ----------

RUN_ID = uuid.uuid4().hex[:8]
DATES_ALL = [(START + dt.timedelta(days=i)).isoformat() for i in range((END - START).days + 1)]


def target_dates():
    if MODE == "replay":
        return {REPLAY_DATE}
    return set(DATES_ALL) - set(HELD_BACK)


def complete(system):
    root = f"{LANDING}/{system}"
    if not os.path.isdir(root):
        return set()
    return {x for x in os.listdir(root) if os.path.exists(f"{root}/{x}/_MANIFEST.json")}


def created_ts(system, dts):
    day = dt.date.fromisoformat(dts)
    if system == "atl_daily":
        lag = 2 if dts in LATE_ATL else 1
        return dt.datetime.combine(day + dt.timedelta(days=lag), dt.time(6, 0))
    if system in ("iss_auth", "mrd_events"):
        return dt.datetime.combine(day + dt.timedelta(days=1), dt.time(0, 30))
    return dt.datetime.combine(day + dt.timedelta(days=1), dt.time(4, 0))


FILE_NAME = {
    "iss_auth": lambda d_, c_: f"ISSAUTH_{d_.replace('-', '')}_{c_:%Y%m%d%H%M}.csv",
    "mrd_events": lambda d_, c_: f"MRD_AUTH_EVENTS_{d_.replace('-', '')}_{c_:%Y%m%d%H%M}.jsonl",
    "atl_daily": lambda d_, c_: f"ATL_DAILY_{d_.replace('-', '')}_{c_:%Y%m%d%H%M}.txt",
    "merchant_master": lambda d_, c_: f"MERCHANT_MASTER_{'FULL' if d_ == START.isoformat() else 'DELTA'}_{d_.replace('-', '')}.csv",
    "card_portfolio": lambda d_, c_: f"CARD_PORTFOLIO_{'FULL' if d_ == START.isoformat() else 'DELTA'}_{d_.replace('-', '')}.csv",
    "acquirer_ref": lambda d_, c_: f"ACQUIRER_REF_{d_.replace('-', '')}.jsonl",
}


def write_system(system, df, cols, fmt, opts=None, amount_col=None, intended=None):
    todo = sorted(target_dates() - complete(system))
    if not todo:
        return {"system": system, "written": 0, "skipped": "all complete"}
    sub = df.filter(F.col("dt").isin(todo))
    stats = {r["dt"]: (r["n"], r["s"]) for r in sub.groupBy("dt").agg(
        F.count("*").alias("n"),
        (F.round(F.sum(amount_col), 2) if amount_col else F.lit(None)).alias("s")).collect()}
    stage = f"{LANDING}/_staging/{RUN_ID}/{system}"
    w_ = sub.select("dt", *cols).repartition("dt").write.mode("overwrite").partitionBy("dt")
    if fmt == "csv":
        w_ = w_.option("header", True).option("ignoreLeadingWhiteSpace", False).option("ignoreTrailingWhiteSpace", False)
    for k, v in (opts or {}).items():
        w_ = w_.option(k, v)
    w_.format(fmt).save(stage)

    def finalize(dts):
        part_dir = f"{stage}/dt={dts}"
        parts = [p for p in os.listdir(part_dir) if p.startswith("part-")]
        assert len(parts) == 1, (system, dts, parts)
        cts = created_ts(system, dts)
        name = FILE_NAME[system](dts, cts)
        out = f"{LANDING}/{system}/{dts}"
        os.makedirs(out, exist_ok=True)
        for old in os.listdir(out):  # a half-written folder (no manifest) is redone fully
            os.remove(f"{out}/{old}")
        shutil.move(f"{part_dir}/{parts[0]}", f"{out}/{name}")
        n, s_ = (intended or stats)[dts] if (intended and dts in intended) else stats[dts]
        man = {"system": system, "business_date": dts, "file_created_ts": cts.isoformat(),
               "files": [{"name": name, "record_count": int(n), "amount_total": s_}]}
        with open(f"{out}/_MANIFEST.json", "w") as fh:  # written LAST
            json.dump(man, fh)
        return dts

    with ThreadPoolExecutor(32) as ex:
        done = list(ex.map(finalize, sorted(stats)))
    shutil.rmtree(stage, ignore_errors=True)
    return {"system": system, "written": len(done), "rows": int(sum(v[0] for v in stats.values()))}


results = []
results.append(write_system("iss_auth", iss_all, ISS_COLS, "csv", amount_col="_amt_true"))
results.append(write_system("mrd_events", mrd_df, [c_ for c_ in mrd_df.columns if c_ not in ("dt", "_amt_true")], "json",
                            amount_col="_amt_true"))
results.append(write_system("atl_daily", atl_df, [c_ for c_ in atl_df.columns if c_ not in ("dt", "_amt_true")], "csv",
                            {"sep": "|"}, amount_col="_amt_true", intended=atl_intended))
results.append(write_system("merchant_master", mm_df, MM_COLS, "csv"))
results.append(write_system("card_portfolio", cp_df, CP_COLS, "csv"))

# Acquirer reference: monthly snapshots + a 2026-09-23 snapshot after ACQ-017's configuration change
snap = [START.isoformat()] + [f"{y}-{mo:02d}-01" for y, mo in [(2025, 12)] + [(2026, k) for k in range(1, 12)]] + ["2026-09-23"]
acq_snap = (spark.createDataFrame([(s_,) for s_ in snap], "dt string").crossJoin(acq)
            .withColumn("after", F.col("dt") >= F.lit("2026-09-23"))
            .withColumn("lastConfigChange", F.when(F.col("after") & (F.col("acquirerId") == "ACQ-017"), F.lit("2026-09-22"))
                        .otherwise(F.col("lastConfigChange")))
            .withColumn("configNote", F.when(F.col("after") & (F.col("acquirerId") == "ACQ-017"),
                                             F.lit("Meridian profile update: e-commerce token cryptogram settings")))
            .filter(F.col("dt") <= F.lit(END.isoformat())))
results.append(write_system("acquirer_ref", acq_snap, ["acquirerId", "acquirerName", "bin", "region", "mrdCertified",
                                                       "certifiedDate", "lastConfigChange", "configNote"], "json"))

# COMMAND ----------

# MAGIC %md ## Reference files (static, governed by us)

# COMMAND ----------

ref_dir = f"{LANDING}/ref/{START.isoformat()}"
if MODE == "backfill" and not os.path.exists(f"{ref_dir}/_MANIFEST.json"):
    Y, N_ = "Y", "N"
    rows = [("ISS", "00", "Approved", "APPROVED", N_), ("ISS", "05", "Do not honor", "ISSUER_LEGIT_DNH", N_),
            ("ISS", "51", "Insufficient funds", "ISSUER_LEGIT_NSF", N_), ("ISS", "54", "Expired card", "ISSUER_LEGIT_EXPIRED", N_),
            ("ISS", "14", "Invalid card number", "ISSUER_LEGIT_INVALID", N_), ("ISS", "57", "Transaction not permitted", "ISSUER_LEGIT_NOT_PERMITTED", N_),
            ("ISS", "59", "Suspected fraud", "ISSUER_LEGIT_FRAUD", N_), ("ISS", "61", "Exceeds amount limit", "ISSUER_LEGIT_LIMIT", N_),
            ("ISS", "58", "Not permitted to terminal", "ACCEPTANCE_CONFIG", Y), ("ISS", "91", "Issuer or switch inoperative", "PROCESSOR_TIMEOUT", Y),
            ("ISS", "96", "System malfunction", "SYSTEM_ERROR", Y)]
    for cd_, desc, cat in [("01", "Refer to issuer", "ISSUER_LEGIT_DNH"), ("03", "Invalid merchant", "ACCEPTANCE_CONFIG"),
                           ("04", "Pick up card", "ISSUER_LEGIT_FRAUD"), ("12", "Invalid transaction", "ACCEPTANCE_CONFIG"),
                           ("13", "Invalid amount", "ISSUER_LEGIT_DNH"), ("15", "No such issuer", "ACCEPTANCE_CONFIG"),
                           ("19", "Re-enter transaction", "SYSTEM_ERROR"), ("41", "Lost card", "ISSUER_LEGIT_FRAUD"),
                           ("43", "Stolen card", "ISSUER_LEGIT_FRAUD"), ("55", "Incorrect PIN", "ISSUER_LEGIT_DNH"),
                           ("62", "Restricted card", "ISSUER_LEGIT_NOT_PERMITTED"), ("63", "Security violation", "ISSUER_LEGIT_FRAUD"),
                           ("65", "Exceeds frequency limit", "ISSUER_LEGIT_LIMIT"), ("75", "PIN tries exceeded", "ISSUER_LEGIT_DNH"),
                           ("78", "Blocked, first use", "ISSUER_LEGIT_NOT_PERMITTED"), ("N7", "CVV2 mismatch", "ISSUER_LEGIT_FRAUD"),
                           ("R0", "Stop recurring payment", "ISSUER_LEGIT_NOT_PERMITTED"), ("R1", "Revoke authorization", "ISSUER_LEGIT_NOT_PERMITTED")]:
        rows.append(("ISS", cd_, desc, cat, Y if cat in ("ACCEPTANCE_CONFIG", "SYSTEM_ERROR") else N_))
    atl = [("000", "Approved", "APPROVED"), ("100", "Do not honor", "ISSUER_LEGIT_DNH"), ("101", "Expired card", "ISSUER_LEGIT_EXPIRED"),
           ("102", "Suspected fraud", "ISSUER_LEGIT_FRAUD"), ("111", "Invalid card number", "ISSUER_LEGIT_INVALID"),
           ("116", "Insufficient funds", "ISSUER_LEGIT_NSF"), ("119", "Not permitted to cardholder", "ISSUER_LEGIT_NOT_PERMITTED"),
           ("121", "Exceeds withdrawal limit", "ISSUER_LEGIT_LIMIT"), ("909", "System malfunction", "SYSTEM_ERROR"),
           ("911", "Issuer timeout", "PROCESSOR_TIMEOUT"), ("120", "Not permitted to terminal", "ACCEPTANCE_CONFIG")]
    atl += [(f"{k}", f"Legacy decline {k}", "ISSUER_LEGIT_DNH") for k in
            [103, 104, 106, 107, 108, 109, 110, 112, 113, 114, 115, 117, 118, 122, 123, 125]]
    atl += [(f"{k}", f"Legacy pick-up {k}", "ISSUER_LEGIT_FRAUD") for k in range(200, 211)]
    atl += [(f"{k}", f"Legacy system {k}", "SYSTEM_ERROR") for k in [902, 903, 904, 905, 906, 907, 908, 910, 912, 913]]
    rows += [("ATL", cd_, desc, cat, Y if cat in ("ACCEPTANCE_CONFIG", "SYSTEM_ERROR", "PROCESSOR_TIMEOUT") else N_) for cd_, desc, cat in atl]
    mrd_codes = [("M000", "Approved", "APPROVED"), ("M105", "Issuer: do not honor", "ISSUER_LEGIT_DNH"),
                 ("M151", "Issuer: insufficient funds", "ISSUER_LEGIT_NSF"), ("M154", "Issuer: expired card", "ISSUER_LEGIT_EXPIRED"),
                 ("M114", "Issuer: invalid card", "ISSUER_LEGIT_INVALID"), ("M157", "Issuer: not permitted", "ISSUER_LEGIT_NOT_PERMITTED"),
                 ("M159", "Issuer: suspected fraud", "ISSUER_LEGIT_FRAUD"), ("M161", "Issuer: exceeds limit", "ISSUER_LEGIT_LIMIT"),
                 ("M014", "Card-on-file credential not updated", "CARD_ON_FILE_STALE"), ("M015", "Stored credential mismatch", "CARD_ON_FILE_STALE"),
                 ("M057", "Cross-border not enabled for merchant category", "CROSS_BORDER_BLOCK"),
                 ("M059", "Cross-border not supported for product", "CROSS_BORDER_BLOCK"),
                 ("M058", "Acceptance profile not configured", "ACCEPTANCE_CONFIG"),
                 ("M065", "Acquirer token cryptogram validation failed", "ACCEPTANCE_CONFIG"),
                 ("M062", "Token not provisioned on network", "TOKEN_PROVISIONING"), ("M063", "Token suspended", "TOKEN_PROVISIONING"),
                 ("M091", "Issuer processor timeout", "PROCESSOR_TIMEOUT"), ("M092", "Network switch timeout", "PROCESSOR_TIMEOUT"),
                 ("M096", "Network system error", "SYSTEM_ERROR")]
    mrd_codes += [(f"M1{k:02d}", f"Issuer passthrough {k}", "ISSUER_LEGIT_DNH") for k in range(62, 80)]
    mrd_codes += [(f"M0{k:02d}", f"Network acceptance {k}", "ACCEPTANCE_CONFIG") for k in range(70, 90)]
    rows += [("MRD", cd_, desc, cat, Y if not (cat.startswith("ISSUER_") or cat == "APPROVED") else N_) for cd_, desc, cat in mrd_codes]
    os.makedirs(ref_dir, exist_ok=True)
    import csv
    with open(f"{ref_dir}/RESPONSE_CODE_MAP_v1.csv", "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["network_cd", "native_cd", "description", "std_category", "is_acceptance_failure"])
        wr.writerows(rows)
    rec = [("DOMESTIC", 0.40), ("ECOM_HEAVY", 0.55), ("RECURRING_HEAVY", 0.35), ("WALLET_HEAVY", 0.45),
           ("INTL_TRAVELER", 0.60), ("DEFAULT", 0.45)]
    with open(f"{ref_dir}/RECOVERY_ASSUMPTIONS_v1.csv", "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["segment", "unrecovered_rate", "version", "effective_dt", "source"])
        wr.writerows([(s_, r_, "v1", "2026-01-01", "Finance estimate (synthetic)") for s_, r_ in rec])
    with open(f"{ref_dir}/_MANIFEST.json", "w") as fh:
        json.dump({"system": "ref", "business_date": START.isoformat(), "file_created_ts": f"{START}T00:00:00",
                   "files": [{"name": "RESPONSE_CODE_MAP_v1.csv", "record_count": len(rows)},
                             {"name": "RECOVERY_ASSUMPTIONS_v1.csv", "record_count": len(rec)}]}, fh)
    results.append({"system": "ref", "written": 1, "rows": len(rows) + len(rec)})

# COMMAND ----------

# MAGIC %md ## Answer key (intended counts over the dates currently landed)

# COMMAND ----------

landed = sorted(complete("iss_auth"))
lt = t.filter(F.date_format("bdate", "yyyy-MM-dd").isin(landed))
iss_landed = iss_all.filter(F.col("dt").isin(landed))
dup_landed = dups.filter(F.col("dt").isin(landed))
dup_cnt = dup_landed.join(iss.filter(F.col("dt").isin(landed)).select("AUTH_ID").distinct(), "AUTH_ID").count()


def inc_stats(cause_list, name):
    s_, e_ = INC[name]
    x = lt.filter(F.col("cause").isin(cause_list))
    r = x.agg(F.count("*").alias("rows"), F.countDistinct("MRCH_NUM").alias("merchants"),
              F.countDistinct("CARD_REF").alias("cards"), F.round(F.sum("amount"), 2).alias("amount")).first()
    return {"window": [s_, e_], "rows": r["rows"], "distinct_merchants": r["merchants"], "distinct_cards": r["cards"],
            "amount": r["amount"]}


ak = {
    "generated_with_seed": SEED, "landed_dates": [landed[0], landed[-1]] if landed else [], "n_landed_dates": len(landed),
    "DQ1_duplicate_rows": dup_cnt,
    "DQ2_bad_amount_rows": iss_landed.filter("dq2_bad_amt").count(),
    "DQ3_future_ts_rows": lt.filter("dq3_future_ts").count() + dup_landed.join(
        lt.filter("dq3_future_ts").select("AUTH_ID"), "AUTH_ID").count(),
    "DQ4_null_auth_id_rows": lt.filter("dq4_null_id").count(),
    "DQ5_unmapped_codes": sorted(r[0] for r in lt.filter("cause = 'UNMAPPED'").select("mrd_resp").distinct().collect()),
    "DQ5_unmapped_rows": lt.filter("cause = 'UNMAPPED'").count(),
    "DQ6_merchants_mid_variant": m.filter("dq6_mid_variant").count(),
    "DQ6_merchants_mid_variant_seen_on_mrd": lt.filter("network = 'MRD'").select("mseq").distinct().join(m.filter("dq6_mid_variant").select("mseq"), "mseq").count(),
    "DQ7_out_of_sequence_card_records": c.filter("dq7_stale").count(),
    "DQ8_control_total_mismatch": {"folder": f"atl_daily/{TRUNC_ATL}", "rows_missing": lt.filter("atl_trunc AND network = 'ATL'").count()},
    "DQ9_late_files": [f"atl_daily/{x}" for x in LATE_ATL],
    "DQ10_merchants_stale_mcc": m.filter("dq10_stale_mcc").count(),
    "DQ10_merchants_stale_mcc_seen": lt.filter("NOT mcc_blank").select("mseq").distinct().join(m.filter("dq10_stale_mcc").select("mseq"), "mseq").count(),
    "messiness": {"mcc_blank_rows": lt.filter("mcc_blank").count(), "term_cntry_blank_rows": lt.filter("cntry_blank").count(),
                  "curr_cd_USD_rows": lt.filter("curr_usd").count(), "dba_trailing_space_merchants": m.filter("dba_trailing").count(),
                  "atl_mid_zero_padded_merchants": m.filter("atl_padded").count()},
    "INC1": inc_stats(["INC1"], "INC1"), "INC2": inc_stats(["INC2"], "INC2"), "INC3": inc_stats(["INC3"], "INC3"),
    "INC4": inc_stats(["INC4"], "INC4"), "INC4_stip_approved": lt.filter("cause = 'INC4_STIP'").count(),
    "DECOY": inc_stats(["DECOY_NSF"], "DECOY"),
}

# calibration: business metrics the story relies on
w6 = lt.filter((F.col("WAVE_ID") == 6) & F.col("bdate").between(d("2026-09-08"), d("2026-10-07")))
atl_base = lt.filter((F.col("network") == "ATL") & F.col("bdate").between(d("2026-09-08"), d("2026-10-07")))
r6 = w6.agg(F.avg(F.col("approved").cast("double")).alias("ar"), F.count("*").alias("n")).first()
rb = atl_base.agg(F.avg(F.col("approved").cast("double")).alias("ar")).first()
tot = lt.agg(F.avg("amount").alias("avg_ticket"), F.count("*").alias("n"),
             F.avg((F.col("network") == "MRD").cast("double")).alias("mrd_share")).first()
last30 = lt.filter(F.col("bdate") >= d("2026-10-18")).agg(F.avg((F.col("network") == "MRD").cast("double"))).first()[0]
ak["calibration"] = {
    "wave6_first30d_approval": round(r6["ar"], 4), "wave6_first30d_attempts": r6["n"],
    "atl_same_period_approval": round(rb["ar"], 4), "gap_pp": round((rb["ar"] - r6["ar"]) * 100, 2),
    "avg_ticket": round(tot["avg_ticket"], 2), "attempts_landed": tot["n"],
    "mrd_share_overall": round(tot["mrd_share"], 4), "mrd_share_last30d": round(last30, 4), "bg_mult": BG_MULT}

incident_manifest = [
    {"id": "INC1", "split": "tuning", "type": "ACCEPTANCE_CONFIG", "network": "MRD", "window": INC["INC1"],
     "slice": {"acquirer": "ACQ-017", "channel": "ECOM", "pos_entry_mode": "81"}},
    {"id": "INC2", "split": "tuning", "type": "CROSS_BORDER_BLOCK", "network": "MRD", "window": INC["INC2"],
     "slice": {"cross_border": True, "mcc_group": "TRAVEL_LODGING", "mcc": TRAVEL_MCC}},
    {"id": "INC3", "split": "holdout", "type": "CARD_ON_FILE_STALE", "network": "MRD", "window": INC["INC3"],
     "slice": {"channel": "REC", "recurring": True}},
    {"id": "INC4", "split": "holdout", "type": "PROCESSOR_TIMEOUT", "network": "MRD", "window": INC["INC4"],
     "slice": {"region": "SE"}},
    {"id": "DECOY", "split": "holdout", "type": "ISSUER_LEGIT_NSF", "network": "BOTH", "window": INC["DECOY"],
     "slice": {"all": True}, "must_not_flag_as_acceptance": True},
]
os.makedirs(TRUTH, exist_ok=True)
with open(f"{TRUTH}/answer_key.json", "w") as fh:
    json.dump(ak, fh, indent=1, default=str)
with open(f"{TRUTH}/incident_manifest.json", "w") as fh:
    json.dump(incident_manifest, fh, indent=1)
shutil.rmtree(f"{LANDING}/_staging/{RUN_ID}", ignore_errors=True)

summary = {"mode": MODE, "replay_date": REPLAY_DATE or None, "seed": SEED, "systems": results, "answer_key": ak}
print(json.dumps(summary, indent=1, default=str))
dbutils.notebook.exit(json.dumps(summary, default=str))
