"""Run SQL on the bundle's SQL warehouse via the Databricks CLI and print a markdown table.
Usage: python3 -I tools/sql.py "<sql>" [--json]   (profile: febar; warehouse from databricks.yml default)
"""
import json, subprocess, sys, time

WAREHOUSE = "34e45919b39491cf"
PROFILE = "febar"


def run(sql, timeout_s=600):
    body = {"warehouse_id": WAREHOUSE, "statement": sql, "wait_timeout": "50s", "on_wait_timeout": "CONTINUE",
            "catalog": "classic_stable_zjnu75_catalog", "schema": "network_migration", "format": "JSON_ARRAY",
            "disposition": "INLINE"}
    out = json.loads(subprocess.check_output(["databricks", "api", "post", "/api/2.0/sql/statements",
                                              "--profile", PROFILE, "--json", json.dumps(body)]))
    t0 = time.time()
    while out["status"]["state"] in ("PENDING", "RUNNING"):
        if time.time() - t0 > timeout_s:
            raise SystemExit("timeout")
        time.sleep(3)
        out = json.loads(subprocess.check_output(["databricks", "api", "get", f"/api/2.0/sql/statements/{out['statement_id']}",
                                                  "--profile", PROFILE]))
    if out["status"]["state"] != "SUCCEEDED":
        raise SystemExit(json.dumps(out["status"], indent=1))
    cols = [c["name"] for c in out.get("manifest", {}).get("schema", {}).get("columns", [])] or ["status"]
    rows = out.get("result", {}).get("data_array", []) or []
    return cols, rows


def md(cols, rows):
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join("" if v is None else str(v) for v in r) + " |" for r in rows]
    return "\n".join(lines)


if __name__ == "__main__":
    cols, rows = run(sys.argv[1])
    if "--json" in sys.argv:
        print(json.dumps({"columns": cols, "rows": rows}))
    else:
        print(md(cols, rows))
