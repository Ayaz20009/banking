# Databricks notebook source
# MAGIC %md
# MAGIC # Verify the answer key from the landed files
# MAGIC Recomputes every planted finding **from the raw files only**, using the recognition rule
# MAGIC written in `evidence/00_answer_key.md`, and compares the result with the generator's
# MAGIC answer key. Also writes the file inventory (folders, files, bytes per system).

# COMMAND ----------

import json
import os

from pyspark.sql import Window
from pyspark.sql import functions as F

dbutils.widgets.text("catalog", "classic_stable_zjnu75_catalog")
dbutils.widgets.text("schema", "network_migration")
CAT, SCH = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
LANDING = f"/Volumes/{CAT}/{SCH}/landing"
ak = json.load(open(f"{LANDING}/_generator_truth/answer_key.json"))
SYSTEMS = ["iss_auth", "mrd_events", "atl_daily", "merchant_master", "card_portfolio", "acquirer_ref", "ref"]

folder_dt = F.regexp_extract(F.col("_metadata.file_path"), r"/(\d{4}-\d{2}-\d{2})/", 1)


def csv(system, sep=","):
    return (spark.read.option("header", True).option("sep", sep).option("inferSchema", False)
            .option("ignoreLeadingWhiteSpace", False).option("ignoreTrailingWhiteSpace", False)
            .csv(f"{LANDING}/{system}/*/[!_]*").withColumn("folder_dt", folder_dt)
            .withColumn("file_name", F.col("_metadata.file_name")))


iss = csv("iss_auth")
atl = csv("atl_daily", "|")
mm = csv("merchant_master")
cp = csv("card_portfolio")
mrd = (spark.read.json(f"{LANDING}/mrd_events/*/[!_]*").withColumn("folder_dt", folder_dt)
       .withColumn("file_name", F.col("_metadata.file_name")))
code_map = spark.read.option("header", True).csv(f"{LANDING}/ref/*/RESPONSE_CODE_MAP_v1.csv")

# COMMAND ----------

# MAGIC %md ## Inventory and manifests

# COMMAND ----------

inventory, manifests = {}, []
for s in SYSTEMS:
    root = f"{LANDING}/{s}"
    folders = sorted(os.listdir(root)) if os.path.isdir(root) else []
    n_files, n_bytes = 0, 0
    for f_ in folders:
        for x in os.listdir(f"{root}/{f_}"):
            n_files += 1
            n_bytes += os.path.getsize(f"{root}/{f_}/{x}")
            if x == "_MANIFEST.json":
                manifests.append(json.load(open(f"{root}/{f_}/{x}")))
    inventory[s] = {"folders": len(folders), "files_incl_manifests": n_files, "mbytes": round(n_bytes / 1e6, 1),
                    "first": folders[0] if folders else None, "last": folders[-1] if folders else None}

actual_counts = {}
for s, df in [("iss_auth", iss), ("atl_daily", atl), ("merchant_master", mm), ("card_portfolio", cp), ("mrd_events", mrd)]:
    for r in df.groupBy("file_name").count().collect():
        actual_counts[r["file_name"]] = r["count"]
mismatch = [{"file": f["name"], "manifest": f["record_count"], "actual": actual_counts.get(f["name"])}
            for mf in manifests if mf["system"] not in ("ref", "acquirer_ref") for f in mf["files"]
            if actual_counts.get(f["name"]) != f["record_count"]]
import datetime as _dt
late = sorted(f"{mf['system']}/{mf['business_date']}" for mf in manifests if mf["system"] != "ref"
              and (_dt.datetime.fromisoformat(mf["file_created_ts"]).date() - _dt.date.fromisoformat(mf["business_date"])).days >= 2)

# COMMAND ----------

# MAGIC %md ## Recompute each planted finding from the files

# COMMAND ----------

got = {}
got["DQ1_duplicate_rows"] = (iss.filter("AUTH_ID IS NOT NULL").groupBy("AUTH_ID").count()
                             .agg(F.sum(F.col("count") - 1)).first()[0])
good_amt = F.col("TRAN_AMT").rlike(r"^[0-9]+\.[0-9]{2}$") & (F.expr("try_cast(TRAN_AMT AS DOUBLE)") > 0)
got["DQ2_bad_amount_rows"] = iss.filter(~good_amt).count()
got["DQ3_future_ts_rows"] = iss.filter(F.to_date(F.expr("try_to_timestamp(AUTH_TS_LOCAL)")) > F.date_add(F.to_date("folder_dt"), 1)).count()
got["DQ4_null_auth_id_rows"] = iss.filter(F.col("AUTH_ID").isNull() | (F.trim("AUTH_ID") == "")).count()
mrd_codes = code_map.filter("network_cd = 'MRD'").select(F.col("native_cd").alias("responseCode"))
unm = mrd.join(mrd_codes, "responseCode", "left_anti")
got["DQ5_unmapped_codes"] = sorted(r[0] for r in unm.select("responseCode").distinct().collect())
got["DQ5_unmapped_rows"] = unm.count()
master_mid = mm.filter(F.col("folder_dt") == ak["landed_dates"][0]).select("MRD_MID").distinct()
seen = mrd.select("merchantNetworkId").distinct()
exact = seen.join(master_mid, seen.merchantNetworkId == master_mid.MRD_MID, "left_semi")
norm = lambda c: F.expr(f"try_cast(regexp_replace({c}, '[^0-9]', '') AS BIGINT)")
variant = (seen.join(exact, "merchantNetworkId", "left_anti")
           .join(master_mid, norm("merchantNetworkId") == norm("MRD_MID"), "left_semi"))
got["DQ6_merchants_mid_variant_seen_on_mrd"] = variant.count()
wcard = Window.partitionBy("CARD_REF").orderBy("folder_dt", "UPDATE_TS").rowsBetween(Window.unboundedPreceding, -1)
got["DQ7_out_of_sequence_card_records"] = (cp.withColumn("prev_max", F.max("UPDATE_TS").over(wcard))
                                           .filter(F.col("UPDATE_TS") < F.col("prev_max")).count())
got["DQ8_control_total_mismatch"] = mismatch
got["DQ9_late_files"] = late
mm_full = mm.filter(F.col("folder_dt") == ak["landed_dates"][0]).select(F.col("MRCH_NUM"), F.col("MCC").alias("MASTER_MCC"))
got["DQ10_merchants_stale_mcc_seen"] = (iss.filter("MCC IS NOT NULL").join(mm_full, iss.CARD_ACCEPTOR_ID == mm_full.MRCH_NUM)
                                        .filter(F.col("MCC") != F.col("MASTER_MCC")).select("CARD_ACCEPTOR_ID").distinct().count())


def inc(code):
    x = mrd.filter(F.col("responseCode") == code)
    r = x.agg(F.count("*").alias("rows"), F.countDistinct(norm("merchantNetworkId")).alias("m"),
              F.min("folder_dt").alias("first"), F.max("folder_dt").alias("last")).first()
    return {"rows": r["rows"], "distinct_merchants": r["m"], "window_seen": [r["first"], r["last"]]}


got["INC1"], got["INC2"], got["INC3"], got["INC4"] = inc("M065"), inc("M057"), inc("M014"), inc("M091")
got["INC4_stip_approved"] = mrd.filter("processingPath = 'STIP'").count()

# Decoy: NSF excess in the window vs the prior 28 days, on BOTH networks
ws, we = ak["DECOY"]["window"]


def nsf_excess(df, code_col, nsf_code):
    base = df.filter((F.col("folder_dt") >= F.date_format(F.date_sub(F.to_date(F.lit(ws)), 28), "yyyy-MM-dd")) & (F.col("folder_dt") < ws))
    win = df.filter(F.col("folder_dt").between(ws, we))
    rb = base.agg(F.avg((F.col(code_col) == nsf_code).cast("double"))).first()[0]
    n_w = win.count()
    k_w = win.filter(F.col(code_col) == nsf_code).count()
    return {"baseline_rate": round(rb, 5), "window_rate": round(k_w / n_w, 5), "ratio": round(k_w / n_w / rb, 2),
            "excess_rows": round(k_w - rb * n_w)}


iss_d = iss.dropDuplicates(["AUTH_ID"])
got["DECOY"] = {"ATL": nsf_excess(atl, "resp_cd", "116"), "MRD": nsf_excess(mrd, "responseCode", "M151"),
                "ISSUER_all": nsf_excess(iss_d, "ISS_RESP_CD", "51")}

# Calibration from the files: wave-6 cohort vs Atlas, first 30 days after wave 6
waves = (cp.withColumn("rn", F.row_number().over(Window.partitionBy("CARD_REF").orderBy(F.desc("UPDATE_TS"))))
         .filter("rn = 1").select("CARD_REF", "WAVE_ID"))
p = iss_d.filter(F.col("folder_dt").between("2026-09-08", "2026-10-07")).join(waves, "CARD_REF", "left")
ap = lambda df: df.agg(F.avg((F.col("AUTH_DECISION") == "A").cast("double"))).first()[0]
w6, base = ap(p.filter("WAVE_ID = '6'")), ap(p.filter("NETWORK_ID = 'ATL'"))
got["calibration"] = {"wave6_first30d_approval": round(w6, 4), "atl_same_period_approval": round(base, 4),
                      "gap_pp": round((base - w6) * 100, 2),
                      "avg_ticket": round(iss_d.filter(good_amt).agg(F.avg(F.expr("try_cast(TRAN_AMT AS DOUBLE)"))).first()[0], 2)}

# COMMAND ----------

# MAGIC %md ## Compare

# COMMAND ----------

checks = []


def chk(name, expected, recomputed, ok=None):
    ok = (expected == recomputed) if ok is None else ok
    checks.append({"check": name, "answer_key": expected, "recomputed_from_files": recomputed, "match": bool(ok)})


for k in ["DQ1_duplicate_rows", "DQ2_bad_amount_rows", "DQ3_future_ts_rows", "DQ4_null_auth_id_rows",
          "DQ5_unmapped_codes", "DQ5_unmapped_rows", "DQ6_merchants_mid_variant_seen_on_mrd",
          "DQ7_out_of_sequence_card_records", "DQ10_merchants_stale_mcc_seen"]:
    chk(k, ak[k], got[k])
dq8 = ak["DQ8_control_total_mismatch"]
trunc_tag = dq8["folder"].split("/")[1].replace("-", "")
chk("DQ8_control_total_mismatch", dq8, mismatch,
    len(mismatch) == 1 and trunc_tag in mismatch[0]["file"] and
    (mismatch[0]["manifest"] - (mismatch[0]["actual"] or 0)) == dq8["rows_missing"])
chk("DQ9_late_files", sorted(ak["DQ9_late_files"]), late)
for i in ["INC1", "INC2", "INC3", "INC4"]:
    chk(f"{i}_rows", ak[i]["rows"], got[i]["rows"])
    chk(f"{i}_distinct_merchants", ak[i]["distinct_merchants"], got[i]["distinct_merchants"])
    chk(f"{i}_window", ak[i]["window"], got[i]["window_seen"],
        got[i]["window_seen"][0] >= ak[i]["window"][0] and got[i]["window_seen"][1] <= ak[i]["window"][1])
chk("INC4_stip_approved", ak["INC4_stip_approved"], got["INC4_stip_approved"])
dec = got["DECOY"]
chk("DECOY_rows_vs_excess_all_networks", ak["DECOY"]["rows"], dec["ISSUER_all"]["excess_rows"],
    abs(dec["ISSUER_all"]["excess_rows"] - ak["DECOY"]["rows"]) <= 0.15 * ak["DECOY"]["rows"])
chk("DECOY_both_networks_elevated", "ratio > 1.8 on ATL and MRD", [dec["ATL"]["ratio"], dec["MRD"]["ratio"]],
    dec["ATL"]["ratio"] > 1.8 and dec["MRD"]["ratio"] > 1.8)
chk("calibration_gap_pp", ak["calibration"]["gap_pp"], got["calibration"]["gap_pp"],
    abs(ak["calibration"]["gap_pp"] - got["calibration"]["gap_pp"]) <= 0.15)

summary = {"inventory": inventory, "n_checks": len(checks), "n_pass": sum(c["match"] for c in checks),
           "checks": checks, "recomputed": got}
os.makedirs(f"{LANDING}/_generator_truth", exist_ok=True)
with open(f"{LANDING}/_generator_truth/verify_result.json", "w") as fh:
    json.dump(summary, fh, indent=1, default=str)
print(json.dumps({k: summary[k] for k in ["inventory", "n_checks", "n_pass"]}, indent=1))
for c_ in checks:
    print(("PASS " if c_["match"] else "FAIL ") + c_["check"], "| key:", c_["answer_key"], "| files:", c_["recomputed_from_files"])
dbutils.notebook.exit(json.dumps(summary, default=str))
