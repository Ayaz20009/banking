# Control-total manifests -> bronze_file_manifests (Python because SQL cannot read them).
# Each source folder ends with `_MANIFEST.json`. Spark and Auto Loader treat files whose
# names start with "_" as hidden, so read_files can never see them. This materialized view
# lists them directly from the volume (POSIX path) and flattens one row per data file.
import json
import os

from pyspark import pipelines as dp
from pyspark.sql import functions as F

SYSTEMS = ["iss_auth", "mrd_events", "atl_daily", "merchant_master", "card_portfolio", "acquirer_ref"]
SCHEMA = ("system STRING, business_date STRING, file_created_ts STRING, file_name STRING, "
          "record_count BIGINT, amount_total DOUBLE, _source_file STRING")


@dp.materialized_view(
    name="bronze_file_manifests",
    comment="Control totals from each source folder's _MANIFEST.json (record count, amount total, file creation time), one row per data file, as landed.")
def bronze_file_manifests():
    root = spark.conf.get("landing_path")
    rows = []
    for system in SYSTEMS:
        sys_dir = f"{root}/{system}"
        if not os.path.isdir(sys_dir):
            continue
        for folder in sorted(os.listdir(sys_dir)):
            path = f"{sys_dir}/{folder}/_MANIFEST.json"
            if not os.path.exists(path):
                continue  # folder still being written: the manifest is written last
            with open(path) as fh:
                man = json.load(fh)
            for f in man["files"]:
                amt = f.get("amount_total")
                rows.append((man["system"], man["business_date"], man["file_created_ts"], f["name"],
                             int(f["record_count"]), None if amt is None else float(amt), path))
    return spark.createDataFrame(rows, SCHEMA).withColumn("_ingested_at", F.current_timestamp())
