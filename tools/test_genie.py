"""Ask every benchmark through the Genie Conversation API and compare with the ground truth.

Match rule: every expected row must be found in Genie's result, i.e. some Genie row contains all of
the expected row's values (numbers equal after rounding: |a-b| <= max(0.011, 0.5% of b); strings
case-insensitive). 'exact' additionally requires the same number of rows.
Usage: python3 -I tools/test_genie.py <run_label>  -> writes /tmp/febar_out/genie_<run_label>.json
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src", "genie"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from benchmarks import BENCHMARKS  # noqa: E402
import sql  # noqa: E402

P = ["--profile", "febar"]
SID = open(os.path.join(ROOT, "src", "genie", "space_id.txt")).read().strip()
LABEL = sys.argv[1] if len(sys.argv) > 1 else "run1"


def cli(*args):
    return json.loads(subprocess.check_output(["databricks", *args, *P, "-o", "json"]))


def num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def same(e, g):
    if e is None:
        return True
    ne, ng = num(e), num(g)
    if ne is not None and ng is not None:
        return abs(ne - ng) <= max(0.011, 0.005 * abs(ne))
    return str(e).strip().lower() == str(g).strip().lower()


def row_found(erow, grows):
    return any(all(any(same(ev, gv) for gv in grow) for ev in erow) for grow in grows)


results = []
for qid, question, gt_sql in BENCHMARKS:
    cols, exp_rows = sql.run(gt_sql)
    t0 = time.time()
    start = cli("genie", "start-conversation", "--no-wait", SID, question)
    conv, msg = start["conversation_id"], start["message_id"]
    status, m = None, {}
    while time.time() - t0 < 300:
        m = cli("genie", "get-message", SID, conv, msg)
        status = m.get("status")
        if status in ("COMPLETED", "FAILED", "CANCELLED"):
            break
        time.sleep(5)
    genie_sql, text, g_cols, g_rows = None, None, [], []
    for a in m.get("attachments", []) or []:
        if a.get("text"):
            text = a["text"].get("content")
        if a.get("query"):
            genie_sql = a["query"].get("query")
            qr = cli("genie", "get-message-attachment-query-result", SID, conv, msg, a["attachment_id"])
            sr = qr.get("statement_response", {})
            g_cols = [c["name"] for c in sr.get("manifest", {}).get("schema", {}).get("columns", [])]
            g_rows = sr.get("result", {}).get("data_array", []) or []
    found = [row_found(r, g_rows) for r in exp_rows]
    match = bool(exp_rows) and all(found)
    results.append({"qid": qid, "question": question, "status": status, "seconds": round(time.time() - t0),
                    "expected_columns": cols, "expected_rows": exp_rows, "genie_sql": genie_sql, "genie_text": text,
                    "genie_columns": g_cols, "genie_rows": g_rows[:20], "rows_found": f"{sum(found)}/{len(found)}",
                    "match": match, "exact": match and len(g_rows) == len(exp_rows)})
    print(f"{qid} {status} match={match} exact={results[-1]['exact']} rows_found={results[-1]['rows_found']} ({results[-1]['seconds']}s)", flush=True)

json.dump(results, open(f"/tmp/febar_out/genie_{LABEL}.json", "w"), indent=1, default=str)
print(json.dumps({"label": LABEL, "matched": sum(r["match"] for r in results), "exact": sum(r["exact"] for r in results), "total": len(results)}))
