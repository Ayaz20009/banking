"""Non-admin access test for the governance step.

Runs as the service principal profile `febar-sp` (persona P2_REGIONAL = OWN cards, SE region,
no sensitive fields) and as the admin profile `febar` for grants and clean-up.

* Protected reads are recorded as status + error class + response size only, never content.
* A harmless probe table with the SAME permissions is used to tell "not found because no
  permission" from "really does not exist".
* All temporary grants and the SP's entitlement row are removed at the end (in `finally`).

Usage: python3 -I tools/access_test.py <sp_application_id>   -> markdown on stdout
"""
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sql  # noqa: E402

NS = "classic_stable_zjnu75_catalog.network_migration"
SP = sys.argv[1]
ADMIN, TEST = "febar", "febar-sp"
log = []


def call(statement, profile, show_rows=True):
    """Execute; return a dict with state, error class, response bytes and (optionally) rows."""
    body = {"warehouse_id": sql.WAREHOUSE, "statement": statement, "wait_timeout": "50s",
            "on_wait_timeout": "CONTINUE", "format": "JSON_ARRAY", "disposition": "INLINE"}
    raw = subprocess.run(["databricks", "api", "post", "/api/2.0/sql/statements", "--profile", profile,
                          "--json", json.dumps(body)], capture_output=True, text=True)
    txt = raw.stdout or raw.stderr
    try:
        out = json.loads(raw.stdout)
        while out.get("status", {}).get("state") in ("PENDING", "RUNNING"):
            time.sleep(3)
            txt = subprocess.run(["databricks", "api", "get", f"/api/2.0/sql/statements/{out['statement_id']}",
                                  "--profile", profile], capture_output=True, text=True).stdout
            out = json.loads(txt)
        state = out["status"]["state"]
        msg = out["status"].get("error", {}).get("message", "")
    except (json.JSONDecodeError, KeyError):
        state, msg = "CLIENT_ERROR", txt
    m = re.search(r"ErrorClass=([A-Z_.]+)", msg) or re.search(r"\[([A-Z_]+(?:\.[A-Z_]+)?)\]", msg)
    res = {"state": state, "error_class": m.group(1) if m else (None if state == "SUCCEEDED" else "UNKNOWN"),
           "response_bytes": len(txt.encode())}
    if state == "SUCCEEDED" and show_rows:
        res["columns"] = [c["name"] for c in out["manifest"]["schema"].get("columns", [])]
        res["rows"] = out.get("result", {}).get("data_array", [])
    return res


def step(title, statement, profile, show_rows=True, expect=None):
    r = call(statement, profile, show_rows)
    ok = None if expect is None else (r["state"] == expect)
    log.append((title, statement, profile, r, ok))
    return r


def admin(statement):
    r = call(statement, ADMIN, show_rows=False)
    if r["state"] != "SUCCEEDED":
        raise SystemExit(f"admin step failed: {statement} -> {r['error_class']}")
    log.append(("(admin) " + statement.split(" TO ")[0].split(" FROM ")[0][:80], statement, ADMIN, r, True))


APPROVED = [f"{NS}.gold_auth_daily", f"{NS}.auth_detail", f"{NS}.zz_access_probe"]
GRANTS = [f"GRANT USE CATALOG ON CATALOG classic_stable_zjnu75_catalog TO `{SP}`",
          f"GRANT USE SCHEMA ON SCHEMA {NS} TO `{SP}`"] + [f"GRANT SELECT ON TABLE {t} TO `{SP}`" for t in APPROVED]
REVOKES = [g.replace("GRANT", "REVOKE").replace(" TO ", " FROM ") for g in reversed(GRANTS)]

try:
    # Setup (admin): harmless probe table, SP entitlement = P2_REGIONAL
    admin(f"CREATE TABLE IF NOT EXISTS {NS}.zz_access_probe AS SELECT 1 AS probe_value, 'harmless' AS note")
    admin(f"DELETE FROM {NS}.entitlements WHERE principal = '{SP}'")
    admin(f"INSERT INTO {NS}.entitlements VALUES ('{SP}', 'SERVICE_PRINCIPAL', 'P2_REGIONAL', current_timestamp(), 'access test')")

    # 0. Who am I, which account groups do I belong to (checked by the identity itself)
    step("0. identity seen by UC", "SELECT current_user() AS me, is_account_group_member('account users') AS in_account_users, is_account_group_member('admins') AS in_admins", TEST)

    # 1. Before any grant: approved table vs harmless probe (same permissions = none)
    step("1a. BEFORE grant: read approved table gold_auth_daily", f"SELECT count(*) FROM {NS}.gold_auth_daily", TEST, False, "FAILED")
    step("1b. BEFORE grant: read harmless probe zz_access_probe", f"SELECT * FROM {NS}.zz_access_probe", TEST, False, "FAILED")

    # 2. Temporary minimum grants
    for g in GRANTS:
        admin(g)

    # 3. Reads that should succeed, governed by the row filter and mask
    step("3a. AFTER grant: probe readable (so 1b failed only for lack of permission)", f"SELECT * FROM {NS}.zz_access_probe", TEST, True, "SUCCEEDED")
    step("3b. governed read: attempts by issuer segment x region (expect OWN + SE only)",
         f"SELECT issuer_segment, region, sum(attempts) AS attempts FROM {NS}.gold_auth_daily GROUP BY ALL ORDER BY 1, 2", TEST, True, "SUCCEEDED")
    step("3c. masked column: card_ref in auth_detail (expect RESTRICTED)",
         f"SELECT card_ref, count(*) AS rows FROM {NS}.auth_detail GROUP BY 1 ORDER BY 2 DESC LIMIT 3", TEST, True, "SUCCEEDED")
    step("3d. join on the masked column (all values collapse to RESTRICTED, so cards cannot be linked)",
         f"""SELECT count(*) AS joined_pairs, count(DISTINCT a.card_ref) AS distinct_card_ref_values
             FROM {NS}.auth_detail a JOIN {NS}.auth_detail b ON a.card_ref = b.card_ref
             WHERE a.business_date = '2026-11-14' AND b.business_date = '2026-11-14' AND a.acquirer_id = 'ACQ-001' AND b.acquirer_id = 'ACQ-001'""",
         TEST, True, "SUCCEEDED")
    step("3e. column statistics for the masked column (DESCRIBE ... card_ref): is min/max exposed?",
         f"DESCRIBE TABLE EXTENDED {NS}.auth_detail card_ref", TEST, True, "SUCCEEDED")

    # 4. Protected reads: no grant on these (record status + size only)
    for t in ["silver_auth", "bronze_issuer_auth", "quarantine_auth", "entitlements", "gold_baseline_gap"]:
        step(f"4. PROTECTED read {t} (not granted)", f"SELECT * FROM {NS}.{t} LIMIT 5", TEST, False, "FAILED")
    step("4f. metadata: table names visible via inherited READ_METADATA (account users)",
         f"SELECT count(*) AS tables_listed FROM classic_stable_zjnu75_catalog.information_schema.tables WHERE table_schema = 'network_migration'", TEST, True, None)

finally:
    # 5. Clean-up: revoke everything, remove the SP's entitlement
    for rv in REVOKES:
        try:
            admin(rv)
        except SystemExit as e:
            log.append(("(admin) revoke FAILED", rv, ADMIN, {"state": "FAILED", "error_class": str(e)[:120], "response_bytes": 0}, False))
    admin(f"DELETE FROM {NS}.entitlements WHERE principal = '{SP}'")

# 6. After clean-up: the read that worked must now fail
step("6a. AFTER revoke: read gold_auth_daily again", f"SELECT count(*) FROM {NS}.gold_auth_daily", TEST, False, "FAILED")
step("6b. AFTER revoke: read probe again", f"SELECT * FROM {NS}.zz_access_probe", TEST, False, "FAILED")

# Report
lines = ["| # | Step | Identity | Result | Error class | Response bytes | Matches expectation |", "|---|---|---|---|---|---|---|"]
details = []
for i, (title, stmt, prof, r, ok) in enumerate(log, 1):
    who = "service principal" if prof == TEST else "admin"
    lines.append(f"| {i} | {title} | {who} | {r['state']} | {r.get('error_class') or ''} | {r['response_bytes']} | {'' if ok is None else ('✓' if ok else '✗')} |")
    if r.get("rows") is not None:
        rows = r["rows"]
        if "DESCRIBE" in stmt:  # report only whether stats values exist, not the values
            stats = {row[0]: row[1] for row in rows if row and row[0] in ("min", "max", "num_nulls", "distinct_count")}
            details.append(f"**{title}**: statistics rows returned = {sorted(stats)}; min/max values present = "
                           f"{bool(stats.get('min') not in (None, 'NULL')) or bool(stats.get('max') not in (None, 'NULL'))}")
        else:
            details.append(f"**{title}**\n\n```sql\n{' '.join(stmt.split())}\n```\n\n" + sql.md(r["columns"], rows))
print("\n".join(lines))
print()
print("\n\n".join(details))
