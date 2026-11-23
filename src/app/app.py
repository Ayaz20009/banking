"""Acceptance Risk Control: Databricks App (FastAPI + Jinja).

Identity model
* Gold tables and Genie: the SIGNED-IN USER's token (x-forwarded-access-token, scopes sql + genie),
  so Unity Catalog row filters and masks apply per user.
* Lakebase cases: the App's service principal (Lakebase is always bound to the SP). Which cases a
  user may see is decided by Unity Catalog: the App asks gold_case_status, with the user's token,
  for the case_ids that user can see, and shows only those. Every write records the user as actor.
* All IDs come from app resources (valueFrom) or app.yaml values; nothing is hard-coded here.
"""
import datetime as dt
import json
import os
import time
from contextlib import contextmanager

import psycopg
import requests
from databricks import sql as dbsql
from databricks.sdk import WorkspaceClient
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

HOST = os.environ.get("DATABRICKS_HOST", "").replace("https://", "")
WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "")
GENIE_SPACE_ID = os.environ.get("GENIE_SPACE_ID", "")
LAKEBASE_ENDPOINT = os.environ.get("LAKEBASE_ENDPOINT", "")
NS = f"{os.environ.get('UC_CATALOG', '')}.{os.environ.get('UC_SCHEMA', '')}"

app = FastAPI(title="Acceptance Risk Control")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

STATUSES = ["OPEN", "CLAIMED", "IN_PROGRESS", "WAITING_PARTNER", "RESOLVED", "DISMISSED"]
RESOLUTIONS = ["ACQUIRER_FIX", "CONFIG_CHANGE", "CREDENTIAL_REFRESH", "PROCESSOR_FIX", "FALSE_POSITIVE", "OTHER"]
TEAMS = ["Acquirer Relations", "Network Integration", "Card Technology", "Network Operations", "Issuer Processing"]
STARTERS = [
    "What is the approval gap for migrated cards vs the matched baseline over the last 30 days?",
    "Is wave 7 ready to launch?",
    "Which acquirers had the most acceptance declines on the acquired network in the last 14 days?",
    "How many HIGH-severity cases are open, and who owns them?",
    "How much spend did we lose to excess declines in the last 30 days?",
]


# ---------------------------------------------------------------- identity / data access
def user_token(request: Request) -> str:
    tok = request.headers.get("x-forwarded-access-token")
    if not tok:
        raise HTTPException(401, "No user token: open the app through Databricks so it can act on your behalf.")
    return tok


def user_email(request: Request) -> str:
    return request.headers.get("x-forwarded-email") or request.headers.get("x-forwarded-preferred-username") or "unknown"


def uc_query(token: str, statements):
    """Run one or more parameterised statements on ONE warehouse connection as the signed-in user."""
    out = []
    with dbsql.connect(server_hostname=HOST, http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}", access_token=token) as conn:
        with conn.cursor() as cur:
            for stmt, params in statements:
                cur.execute(stmt, params or {})
                cols = [d[0] for d in cur.description] if cur.description else []
                out.append([dict(zip(cols, r)) for r in cur.fetchall()])
    return out


_sp = None


@contextmanager
def lakebase():
    """Connection as the App's service principal; OAuth DB credential generated per connection."""
    global _sp
    _sp = _sp or WorkspaceClient()
    token = _sp.postgres.generate_database_credential(endpoint=LAKEBASE_ENDPOINT).token
    conn = psycopg.connect(host=os.environ["PGHOST"], port=int(os.environ.get("PGPORT", "5432")), dbname=os.environ["PGDATABASE"],
                           user=os.environ["PGUSER"], password=token, sslmode=os.environ.get("PGSSLMODE", "require"),
                           connect_timeout=20)
    try:
        yield conn
    finally:
        conn.close()


def allowed_case_ids(token: str):
    """Unity Catalog decides: the case_ids this user can see in gold_case_status (row filter)."""
    rows = uc_query(token, [(f"SELECT case_id FROM {NS}.gold_case_status", None)])[0]
    return [int(r["case_id"]) for r in rows]


def scope_label(token: str):
    rows = uc_query(token, [(f"""SELECT concat_ws(', ', sort_array(collect_set(issuer_segment))) AS segs,
                                       concat_ws(', ', sort_array(collect_set(region))) AS regions
                                FROM {NS}.gold_auth_daily
                                WHERE business_date = (SELECT max(business_date) FROM {NS}.gold_auth_daily)""", None)])[0]
    r = rows[0] if rows else {}
    return {"segments": r.get("segs") or "none", "regions": r.get("regions") or "none"}


def base_ctx(request: Request, token: str, page: str):
    return {"request": request, "page": page, "user": user_email(request), "scope": scope_label(token)}


# ---------------------------------------------------------------- formatting
def money(v):
    return "—" if v is None else f"${float(v):,.0f}"


def pct(v, d=2):
    return "—" if v is None else f"{float(v):.{d}f}%"


def num(v, d=0):
    return "—" if v is None else f"{float(v):,.{d}f}"


templates.env.filters.update(money=money, pct=pct, num=num)


# ---------------------------------------------------------------- routes
@app.get("/health")
def health():
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def overview(request: Request):
    tok = user_token(request)
    kpi, ready, journey, cases = uc_query(tok, [
        (f"""WITH g AS (SELECT * FROM {NS}.gold_baseline_gap
                        WHERE business_date > (SELECT date_sub(max(business_date), 30) FROM {NS}.gold_baseline_gap))
             SELECT max(business_date) AS latest_date,
                    100 * sum(migrated_approvals) / sum(migrated_attempts) AS migrated_rate,
                    100 * sum(expected_approvals) / sum(migrated_attempts) AS baseline_rate,
                    100 * (sum(expected_approvals) - sum(migrated_approvals)) / sum(migrated_attempts) AS gap_pp,
                    sum(lost_spend) AS lost_spend, sum(excess_declines) AS excess_declines, sum(migrated_attempts) AS migrated_attempts
             FROM g""", None),
        (f"""SELECT card_segment, issuer_segment, gate, gate_reason, expected_daily_attempts, at_risk_declines_per_day,
                    at_risk_spend_usd_per_day, planned_migration_date
             FROM {NS}.gold_wave_readiness WHERE wave_id = 7 ORDER BY issuer_segment, at_risk_spend_usd_per_day DESC""", None),
        (f"""SELECT
               (SELECT count(*) FROM {NS}.gold_auth_daily) AS daily_rows,
               (SELECT sum(attempts) FROM {NS}.gold_auth_daily) AS attempts,
               (SELECT max(business_date) FROM {NS}.gold_auth_daily) AS latest_date,
               (SELECT count(*) FROM {NS}.gold_anomalies) AS flags,
               (SELECT count(*) FROM {NS}.gold_case_status) AS cases,
               (SELECT count(*) FROM {NS}.gold_wave_readiness) AS readiness_rows""", None),
        (f"""SELECT count_if(status NOT IN ('RESOLVED','DISMISSED')) AS open_cases,
                    count_if(status NOT IN ('RESOLVED','DISMISSED') AND severity = 'HIGH') AS open_high,
                    sum(CASE WHEN status NOT IN ('RESOLVED','DISMISSED') THEN exposure_usd END) AS open_exposure
             FROM {NS}.gold_case_status""", None),
    ])
    ctx = base_ctx(request, tok, "overview")
    ctx.update(kpi=kpi[0] if kpi else {}, ready=ready, journey=journey[0] if journey else {}, cases=cases[0] if cases else {},
               gate=("HOLD" if any(r["gate"] == "HOLD" for r in ready) else ("GO" if ready else "—")),
               at_risk=sum(float(r["at_risk_spend_usd_per_day"] or 0) for r in ready))
    return templates.TemplateResponse("overview.html", ctx)


@app.get("/cases", response_class=HTMLResponse)
def cases(request: Request, show: str = "open"):
    tok = user_token(request)
    ids = allowed_case_ids(tok)
    rows = []
    if ids:
        with lakebase() as conn, conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute("""SELECT case_id, root_cause, issuer_segment, region_scope, episode_start, episode_end, n_flags, max_score,
                                  severity, exposure_usd, excess_declines, merchants, suggested_owner_team, owner_team, top_slices,
                                  status, assignee, due_date, updated_at
                           FROM ops.cases WHERE case_id = ANY(%s) AND (%s = 'all' OR status NOT IN ('RESOLVED','DISMISSED'))
                           ORDER BY (severity = 'HIGH') DESC, exposure_usd DESC NULLS LAST""", (ids, show))
            rows = cur.fetchall()
    ctx = base_ctx(request, tok, "cases")
    ctx.update(rows=rows, show=show, n_allowed=len(ids))
    return templates.TemplateResponse("cases.html", ctx)


def load_case(tok, case_id):
    if case_id not in allowed_case_ids(tok):
        raise HTTPException(403, "This case is outside your data access (Unity Catalog).")
    with lakebase() as conn, conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("SELECT * FROM ops.cases WHERE case_id = %s", (case_id,))
        case = cur.fetchone()
        cur.execute("""SELECT event_type, old_value, new_value, note, actor, actor_type, created_at
                       FROM ops.case_events WHERE case_key = %s ORDER BY created_at DESC, event_id DESC""", (case["case_key"],))
        events = cur.fetchall()
    return case, events


@app.get("/cases/{case_id}", response_class=HTMLResponse)
def case_view(request: Request, case_id: int, msg: str = ""):
    tok = user_token(request)
    case, events = load_case(tok, case_id)
    evidence, daily = uc_query(tok, [
        (f"""SELECT business_date, family, slice_value, attempts, acc_declines, expected_declines, z_score, exposure_usd, score, drivers
             FROM {NS}.gold_anomalies
             WHERE likely_root_cause = :rc AND issuer_segment = :seg AND business_date BETWEEN :d0 AND :d1
             ORDER BY score DESC LIMIT 12""",
         {"rc": case["root_cause"], "seg": case["issuer_segment"], "d0": case["episode_start"], "d1": case["episode_end"]}),
        (f"""SELECT business_date, max(acc_declines) AS acc_declines, max(round(expected_declines, 1)) AS expected_declines,
                    max(exposure_usd) AS exposure_usd
             FROM {NS}.gold_anomalies
             WHERE likely_root_cause = :rc AND issuer_segment = :seg AND business_date BETWEEN :d0 AND :d1
             GROUP BY business_date ORDER BY business_date""",
         {"rc": case["root_cause"], "seg": case["issuer_segment"], "d0": case["episode_start"], "d1": case["episode_end"]}),
    ])
    ctx = base_ctx(request, tok, "cases")
    ctx.update(case=case, events=events, evidence=evidence, daily=daily, statuses=STATUSES, resolutions=RESOLUTIONS, teams=TEAMS, msg=msg)
    return templates.TemplateResponse("case.html", ctx)


@app.post("/cases/{case_id}/action")
def case_action(request: Request, case_id: int, action: str = Form(...), version: int = Form(...), status: str = Form(""),
                owner_team: str = Form(""), due_date: str = Form(""), note: str = Form(""), resolution_code: str = Form(""),
                recovered_spend_usd: str = Form("")):
    tok = user_token(request)
    actor = user_email(request)
    case, _ = load_case(tok, case_id)
    ck = case["case_key"]
    sets, events = [], []
    if action == "claim":
        sets = [("status", "CLAIMED"), ("assignee", actor)]
        events = [("STATUS_CHANGE", case["status"], "CLAIMED", note or None), ("ASSIGN", case["assignee"], actor, None)]
    elif action == "status" and status in STATUSES and status not in ("RESOLVED", "DISMISSED"):
        sets = [("status", status)]
        events = [("STATUS_CHANGE", case["status"], status, note or None)]
    elif action == "owner" and owner_team in TEAMS:
        sets = [("owner_team", owner_team)]
        events = [("OWNER_CHANGE", case["owner_team"], owner_team, note or None)]
    elif action == "due" and due_date:
        sets = [("due_date", dt.date.fromisoformat(due_date))]
        events = [("DUE_DATE", str(case["due_date"]) if case["due_date"] else None, due_date, note or None)]
    elif action == "note" and note.strip():
        events = [("NOTE", None, None, note.strip()[:2000])]
    elif action in ("resolve", "dismiss") and resolution_code in RESOLUTIONS:
        final = "RESOLVED" if action == "resolve" else "DISMISSED"
        rec = float(recovered_spend_usd) if recovered_spend_usd.strip() else None
        sets = [("status", final), ("resolution_code", resolution_code), ("recovered_spend_usd", rec), ("resolved_at", dt.datetime.utcnow())]
        events = [("RESOLVE", case["status"], f"{final} / {resolution_code}" + (f" / recovered ${rec:,.0f}" if rec is not None else ""), note or None)]
    else:
        return RedirectResponse(f"/cases/{case_id}?msg=Nothing+to+save", status_code=303)
    with lakebase() as conn:
        with conn.cursor() as cur:
            if sets:
                cols = ", ".join(f"{c} = %s" for c, _ in sets) + ", updated_by = %s, updated_at = now(), version = version + 1"
                cur.execute(f"UPDATE ops.cases SET {cols} WHERE case_id = %s AND version = %s",
                            [v for _, v in sets] + [actor, case_id, version])
                if cur.rowcount == 0:            # someone else changed the case first
                    conn.rollback()
                    return RedirectResponse(f"/cases/{case_id}?msg=Someone+else+updated+this+case+first.+Reloaded.", status_code=303)
            for et, old, new, nt in events:
                cur.execute("""INSERT INTO ops.case_events (case_key, event_type, old_value, new_value, note, actor, actor_type)
                               VALUES (%s, %s, %s, %s, %s, %s, 'USER')""", (ck, et, old, new, nt, actor))
        conn.commit()
    return RedirectResponse(f"/cases/{case_id}?msg=Saved", status_code=303)


def genie_ask(token, question):
    h = {"Authorization": f"Bearer {token}"}
    base = f"https://{HOST}/api/2.0/genie/spaces/{GENIE_SPACE_ID}"
    r = requests.post(f"{base}/start-conversation", headers=h, json={"content": question}, timeout=30)
    r.raise_for_status()
    conv, msg = r.json()["conversation_id"], r.json()["message_id"]
    t0, m = time.time(), {}
    while time.time() - t0 < 120:
        m = requests.get(f"{base}/conversations/{conv}/messages/{msg}", headers=h, timeout=30).json()
        if m.get("status") in ("COMPLETED", "FAILED", "CANCELLED"):
            break
        time.sleep(2)
    out = {"status": m.get("status"), "text": None, "sql": None, "columns": [], "rows": [], "error": (m.get("error") or {}).get("error")}
    for a in m.get("attachments") or []:
        if a.get("text"):
            out["text"] = a["text"].get("content")
        if a.get("query"):
            out["sql"] = a["query"].get("query")
            qr = requests.get(f"{base}/conversations/{conv}/messages/{msg}/attachments/{a['attachment_id']}/query-result",
                              headers=h, timeout=30).json()
            sr = qr.get("statement_response", {})
            out["columns"] = [c["name"] for c in sr.get("manifest", {}).get("schema", {}).get("columns", [])]
            out["rows"] = (sr.get("result", {}).get("data_array") or [])[:200]
    return out


@app.get("/ask", response_class=HTMLResponse)
def ask_page(request: Request):
    tok = user_token(request)
    ctx = base_ctx(request, tok, "ask")
    ctx.update(starters=STARTERS, question=None, answer=None)
    return templates.TemplateResponse("ask.html", ctx)


@app.post("/ask", response_class=HTMLResponse)
def ask_post(request: Request, question: str = Form(...)):
    tok = user_token(request)
    ctx = base_ctx(request, tok, "ask")
    ctx.update(starters=STARTERS, question=question, answer=genie_ask(tok, question[:500]))
    return templates.TemplateResponse("ask.html", ctx)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("DATABRICKS_APP_PORT", "8000")))
