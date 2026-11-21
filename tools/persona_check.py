"""Run the same governed query once per persona by switching the caller's own entitlement row,
then restore ADMIN. Prints one markdown table. Usage: python3 -I tools/persona_check.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sql  # noqa: E402

Q = """SELECT
  (SELECT persona FROM entitlements WHERE principal = current_user()) AS persona,
  sum(attempts) AS attempts_visible,
  sum(CASE WHEN issuer_segment = 'OWN' THEN attempts END) AS own_attempts,
  sum(CASE WHEN issuer_segment = 'THIRD_PARTY' THEN attempts END) AS third_party_attempts,
  concat_ws(',', sort_array(collect_set(region))) AS regions_visible,
  (SELECT count(*) FROM auth_detail) AS detail_rows,
  (SELECT max_by(card_ref, auth_id) FROM auth_detail WHERE business_date = '2026-11-14') AS card_ref_sample
FROM gold_auth_daily"""
out = []
try:
    for p in ["P1_DIRECTOR", "P2_REGIONAL", "P3_CARD_INV", "P4_PARTNER", "NONE", "ADMIN"]:
        if p == "NONE":
            sql.run("DELETE FROM entitlements WHERE principal = current_user()")
        else:
            sql.run(f"""MERGE INTO entitlements t USING (SELECT current_user() principal) s ON t.principal = s.principal
                        WHEN MATCHED THEN UPDATE SET persona = '{p}', granted_at = current_timestamp(), note = 'persona test'
                        WHEN NOT MATCHED THEN INSERT (principal, principal_type, persona, granted_at, note)
                        VALUES (s.principal, 'USER', '{p}', current_timestamp(), 'persona test')""")
        cols, rows = sql.run(Q)
        r = list(rows[0]); r[0] = r[0] or "(no entitlement)"
        out.append(r)
finally:
    sql.run("""MERGE INTO entitlements t USING (SELECT current_user() principal) s ON t.principal = s.principal
               WHEN MATCHED THEN UPDATE SET persona = 'ADMIN', granted_at = current_timestamp(), note = 'Pipeline and job owner'
               WHEN NOT MATCHED THEN INSERT (principal, principal_type, persona, granted_at, note)
               VALUES (s.principal, 'USER', 'ADMIN', current_timestamp(), 'Pipeline and job owner')""")
print(sql.md(cols, out))
