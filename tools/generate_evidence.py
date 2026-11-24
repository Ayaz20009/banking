"""Generate the evidence/ files from the LIVE workspace, as plain-text Markdown.

Every number in evidence/*.md written by this script comes from a query or API call made when the
script runs. Nothing is typed by hand. Each file starts with a "Generated ... from the live
workspace" line and a paragraph that says what the file proves.

Backends (same REST APIs either way):
* Databricks SDK `WorkspaceClient(profile=...)` when it is installed; otherwise the Databricks CLI
  (`databricks api ...`), which calls the same endpoints with the same profile.
* Lakebase: psycopg with an OAuth database credential when installed; otherwise `psql` with the same
  short-lived credential passed through the environment. The credential is never printed or written.

Usage:
  python3 -I tools/generate_evidence.py                       # all files
  python3 -I tools/generate_evidence.py --only=03_business_results.md   (or --only=03)
  options: --profile febar  --sp-profile febar-sp  --job-run-id <id>  --full-cell-outputs  --skip-genie
"""
import argparse
import base64
import csv
import datetime as dt
import html as htmllib
import io
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVID = os.path.join(ROOT, "evidence")
sys.path.insert(0, os.path.join(ROOT, "src", "genie"))

CATALOG, SCHEMA = "classic_stable_zjnu75_catalog", "network_migration"
NS = f"{CATALOG}.{SCHEMA}"
LANDING = f"/Volumes/{CATALOG}/{SCHEMA}/landing"
LB_ENDPOINT = "projects/febar-ops/branches/production/endpoints/primary"
LB_DATABASE = "databricks_postgres"
SCRIPT = "tools/generate_evidence.py"


# =============================================================================================== safety
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SECRETS = [
    (re.compile(r"dapi[0-9a-f]{20,}"), "<token>"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "<token>"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{20,}"), "Bearer <token>"),
    (re.compile(r"(?i)password\s*=\s*\S+"), "password=<redacted>"),
    (re.compile(r"ep-[a-z0-9-]+(-pooler)?\.database\.[a-z0-9.-]+"), "<lakebase-host>"),
    (re.compile(r"postgres(ql)?://\S+"), "<connection-string>"),
]


def clean(text):
    """Remove emails (identities), tokens, passwords, hosts and connection strings."""
    text = EMAIL.sub("<user>", str(text))
    for rx, rep in SECRETS:
        text = rx.sub(rep, text)
    return text


# =============================================================================================== markdown
def now_utc():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def header(title, proves):
    return f"# {title}\n\nGenerated {now_utc()} by {SCRIPT} from the live workspace.\n\n{proves}\n"


def cell(v):
    if v is None:
        return ""
    if isinstance(v, float):
        v = f"{v:,.4f}".rstrip("0").rstrip(".")
    return str(v).replace("|", "\\|").replace("\n", " ")


def table(cols, rows, limit=None):
    if not rows:
        return "_(no rows)_\n"
    shown = rows[:limit] if limit else rows
    out = ["| " + " | ".join(cell(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(cell(v) for v in r) + " |" for r in shown]
    if limit and len(rows) > limit:
        out.append(f"\n_{len(rows) - limit} more rows not shown ({len(rows)} total)._")
    return "\n".join(out) + "\n"


def code(text, lang=""):
    return f"```{lang}\n{text.rstrip()}\n```\n"


def kv(d):
    return table(["item", "value"], [[k, v] for k, v in d.items()])


def ms_to_utc(ms):
    return dt.datetime.fromtimestamp(int(ms) / 1000, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if ms else None


# =============================================================================================== workspace
class ApiError(Exception):
    pass


class Workspace:
    """REST calls through the SDK if installed, else through the Databricks CLI (same endpoints)."""

    def __init__(self, profile):
        self.profile = profile
        try:
            from databricks.sdk import WorkspaceClient
            self.w = WorkspaceClient(profile=profile)
            self.mode = "Databricks SDK"
        except ImportError:
            self.w = None
            self.mode = "Databricks CLI"
        self._token = None

    def api(self, method, path, body=None, query=None):
        if self.w is not None:
            try:
                return self.w.api_client.do(method, path, query=query, body=body) or {}
            except Exception as e:  # noqa: BLE001
                raise ApiError(clean(e)) from None
        if query:
            path += ("&" if "?" in path else "?") + urllib.parse.urlencode(query)
        cmd = ["databricks", "api", method.lower(), path, "--profile", self.profile]
        if body is not None:
            cmd += ["--json", json.dumps(body)]
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise ApiError(clean((p.stderr or p.stdout).strip()[:500]))
        return json.loads(p.stdout or "{}")

    def token(self):
        """OAuth token of the profile, used only as an HTTP header for the App routes; never printed."""
        if self._token is None:
            if self.w is not None:
                self._token = self.w.config.authenticate()["Authorization"].split(" ", 1)[1]
            else:
                out = subprocess.check_output(["databricks", "auth", "token", "--profile", self.profile])
                self._token = json.loads(out)["access_token"]
        return self._token

    def sql(self, statement, warehouse, limit=5000):
        body = {"warehouse_id": warehouse, "statement": statement, "wait_timeout": "50s", "on_wait_timeout": "CONTINUE",
                "catalog": CATALOG, "schema": SCHEMA, "format": "JSON_ARRAY", "disposition": "INLINE", "row_limit": limit}
        r = self.api("POST", "/api/2.0/sql/statements", body)
        t0 = time.time()
        while r["status"]["state"] in ("PENDING", "RUNNING"):
            if time.time() - t0 > 900:
                raise ApiError("statement timeout")
            time.sleep(2)
            r = self.api("GET", f"/api/2.0/sql/statements/{r['statement_id']}")
        if r["status"]["state"] != "SUCCEEDED":
            err = r["status"].get("error", {})
            raise ApiError(f"{err.get('error_code', r['status']['state'])}: {clean(err.get('message', ''))[:300]}")
        cols = [c["name"] for c in r.get("manifest", {}).get("schema", {}).get("columns", [])]
        return cols, r.get("result", {}).get("data_array") or []


# =============================================================================================== lakebase
class Lakebase:
    """Lakebase Postgres with a short-lived OAuth credential (psycopg if installed, else psql)."""

    def __init__(self, ws):
        self.ws = ws
        ep = ws.api("GET", f"/api/2.0/postgres/{LB_ENDPOINT}")
        self.endpoint = ep
        self.host = ep["status"]["hosts"]["host"]
        self.user = ws.api("GET", "/api/2.0/preview/scim/v2/Me")["userName"]
        self.password = ws.api("POST", "/api/2.0/postgres/credentials", {"endpoint": LB_ENDPOINT})["token"]
        try:
            import psycopg  # noqa: F401
            self.mode = "psycopg"
        except ImportError:
            self.psql = shutil.which("psql") or "/opt/homebrew/opt/libpq/bin/psql"
            if not os.path.exists(self.psql):
                raise SystemExit("Neither psycopg nor psql is available for the Lakebase evidence.")
            self.mode = "psql"

    def _env(self):
        return dict(os.environ, PGHOST=self.host, PGUSER=self.user, PGPASSWORD=self.password, PGDATABASE=LB_DATABASE,
                    PGSSLMODE="require", PGCONNECT_TIMEOUT="30")

    def query(self, sql):
        if self.mode == "psycopg":
            import psycopg
            with psycopg.connect(host=self.host, dbname=LB_DATABASE, user=self.user, password=self.password,
                                 sslmode="require", connect_timeout=30) as c, c.cursor() as cur:
                cur.execute(sql)
                return [d.name for d in cur.description], [list(r) for r in cur.fetchall()]
        p = subprocess.run([self.psql, "-X", "-q", "--csv", "-v", "ON_ERROR_STOP=1", "-c", sql],
                           capture_output=True, text=True, env=self._env())
        if p.returncode != 0:
            raise ApiError(clean(p.stderr.strip()[:500]))
        rows = list(csv.reader(io.StringIO(p.stdout)))
        return (rows[0], [[None if v == "" else v for v in r] for r in rows[1:]]) if rows else ([], [])

    def script(self, sql):
        """Run a multi-statement script; return the NOTICE lines it raised (in order)."""
        if self.mode == "psycopg":
            import psycopg
            notes = []
            with psycopg.connect(host=self.host, dbname=LB_DATABASE, user=self.user, password=self.password,
                                 sslmode="require", connect_timeout=30, autocommit=True) as c:
                c.add_notice_handler(lambda d: notes.append(d.message_primary))
                c.execute(sql)
            return notes
        p = subprocess.run([self.psql, "-X", "-q", "-v", "ON_ERROR_STOP=1", "-f", "-"], input=sql,
                           capture_output=True, text=True, env=self._env())
        if p.returncode != 0:
            raise ApiError(clean(p.stderr.strip()[:500]))
        return [ln.split("NOTICE:", 1)[1].strip() for ln in p.stderr.splitlines() if "NOTICE:" in ln]

    def timings(self, sql, n):
        """Client-side latency (ms) of n executions of one query."""
        if self.mode == "psycopg":
            import psycopg
            out = []
            with psycopg.connect(host=self.host, dbname=LB_DATABASE, user=self.user, password=self.password,
                                 sslmode="require", connect_timeout=30) as c, c.cursor() as cur:
                for _ in range(n):
                    t0 = time.perf_counter()
                    cur.execute(sql)
                    cur.fetchall()
                    out.append((time.perf_counter() - t0) * 1000)
            return out, "psycopg, one connection, time from execute to last row fetched"
        script = "\\timing on\n" + "\n".join([sql.rstrip(";") + ";"] * n) + "\n"
        p = subprocess.run([self.psql, "-X", "-q", "-o", "/dev/null", "-f", "-"], input=script,
                           capture_output=True, text=True, env=self._env())
        ms = [float(x) for x in re.findall(r"Time: ([0-9.]+) ms", p.stdout + p.stderr)]
        return ms, "psql \\timing, one connection, server round trip per query"


# =============================================================================================== context
class Ctx:
    def __init__(self, args):
        self.args = args
        self.ws = Workspace(args.profile)
        summary = json.loads(subprocess.check_output(["databricks", "bundle", "summary", "--profile", args.profile, "-o", "json"],
                                                     cwd=ROOT))
        res = summary["resources"]
        self.warehouse = summary.get("variables", {}).get("warehouse_id", {}).get("value") or "34e45919b39491cf"
        self.pipeline_id = res["pipelines"]["febar_pipeline"]["id"]
        self.job_main = res["jobs"]["febar_main"]["id"]
        self.job_ai = res["jobs"]["febar_ai"]["id"]
        self.app_name = res["apps"]["febar_app"]["id"] if "id" in res["apps"]["febar_app"] else "febar-ops-app"
        self.genie_space = open(os.path.join(ROOT, "src", "genie", "space_id.txt")).read().strip()
        self._run = None
        self._lb = None

    def sql(self, statement, limit=5000):
        return self.ws.sql(statement, self.warehouse, limit)

    def one(self, statement):
        cols, rows = self.sql(statement)
        return dict(zip(cols, rows[0])) if rows else {}

    def lb(self):
        if self._lb is None:
            self._lb = Lakebase(self.ws)
        return self._lb

    def run(self):
        """The final orchestrated run: --job-run-id, else the latest successful febar_main run."""
        if self._run is None:
            rid = self.args.job_run_id
            if not rid:
                runs = self.ws.api("GET", "/api/2.2/jobs/runs/list", query={"job_id": self.job_main, "limit": 25, "completed_only": "true"})
                ok = [r for r in runs.get("runs", []) if r["state"].get("result_state") == "SUCCESS"]
                if not ok:
                    raise SystemExit("No successful febar_main run found.")
                rid = ok[0]["run_id"]
            run = self.ws.api("GET", "/api/2.2/jobs/runs/get", query={"run_id": rid})
            run["tasks"] = sorted(run["tasks"], key=lambda t: t.get("start_time") or 0)
            for t in run["tasks"]:
                try:
                    t["_output"] = self.ws.api("GET", "/api/2.2/jobs/runs/get-output", query={"run_id": t["run_id"]})
                except ApiError as e:
                    t["_output"] = {"error": str(e)}
            self._run = run
        return self._run

    def task(self, key):
        return next(t for t in self.run()["tasks"] if t["task_key"] == key)

    def task_result(self, key):
        out = self.task(key)["_output"]
        res = (out.get("notebook_output") or {}).get("result")
        try:
            return json.loads(res) if res else None
        except ValueError:
            return res

    def pipeline_updates(self):
        """{task_key: update_id} for the pipeline tasks of the final run."""
        ups = {}
        for t in self.run()["tasks"]:
            po = t["_output"].get("pipeline_output")
            if po:
                po = po if isinstance(po, dict) else json.loads(po.replace("'", '"'))
                ups[t["task_key"]] = po.get("pipeline_update_id")
        return ups


# =============================================================================================== 00
def gen_00(ctx):
    """Answer key: only written if evidence/00_answer_key.md does not exist yet."""
    path = os.path.join(EVID, "00_answer_key.md")
    if os.path.exists(path) and ctx.args.only is None:
        return None
    ak = ctx.ws.api("GET", f"/api/2.0/fs/files{LANDING}/_generator_truth/answer_key.json")
    md = [header("Evidence 00: Answer key for the planted findings",
                 "The synthetic data generator (`src/data/generate.py`, hash-seeded) wrote this answer key next to the "
                 "landed files. It records every planted data-quality issue (DQ1–DQ10), every business incident "
                 "(INC1–INC4) and the decoy. The pipeline and the detection method never read it; only the evaluation does.")]
    md.append(f"Source: `{LANDING}/_generator_truth/answer_key.json`.\n")
    md.append(table(["key", "value"], [[k, json.dumps(v) if not isinstance(v, (str, int, float)) else v] for k, v in ak.items()]))
    return "\n".join(md)


# =============================================================================================== 01
def gen_01(ctx):
    pid = ctx.pipeline_id
    p = ctx.ws.api("GET", f"/api/2.0/pipelines/{pid}")
    spec = p.get("spec", {})
    libs = [lib.get("file", {}).get("path") or lib.get("notebook", {}).get("path") or json.dumps(lib) for lib in spec.get("libraries", [])]
    ups = ctx.pipeline_updates()
    run = ctx.run()
    md = [header("Evidence 01: Lakeflow pipeline run and expectation metrics",
                 "Proves that the Lakeflow Spark Declarative Pipeline `febar_pipeline` ran inside the final orchestrated "
                 f"job run `{run['run_id']}`, which flows it wrote, and how many records passed or failed each "
                 "data-quality expectation (from the pipeline event log). It also shows the rows per table, a duplicate "
                 "check on the conformed auth table, and that the ingest-free second update read zero new files.")]
    md.append("## Pipeline definition (Pipelines API)\n")
    md.append(kv({"name": spec.get("name"), "pipeline_id": pid, "serverless": spec.get("serverless"),
                  "continuous": spec.get("continuous", False), "channel": spec.get("channel"),
                  "publishes to": f"{spec.get('catalog')}.{spec.get('schema') or spec.get('target')}",
                  "libraries": "; ".join(os.path.basename(x) for x in libs if x),
                  "configuration keys": ", ".join(sorted((spec.get("configuration") or {}).keys())),
                  "state": p.get("state"), "health": p.get("health")}))
    md.append(f"\n## Updates in the final job run `{run['run_id']}`\n")
    rows = []
    for key, uid in ups.items():
        u = ctx.one(f"""SELECT min(timestamp) AS started, max(timestamp) AS ended,
                               round((unix_millis(max(timestamp)) - unix_millis(min(timestamp))) / 1000) AS seconds,
                               max_by(details:update_progress.state::string, timestamp) AS final_state
                        FROM event_log('{pid}') WHERE origin.update_id = '{uid}' AND event_type = 'update_progress'""")
        rows.append([key, uid, u.get("started"), u.get("ended"), u.get("seconds"), u.get("final_state")])
    md.append(table(["job task", "update_id", "started", "ended", "seconds", "final_state"], rows))

    for key, uid in ups.items():
        md.append(f"\n## Rows written per flow, update `{uid}` (task `{key}`)\n")
        c, r = ctx.sql(f"""SELECT replace(origin.flow_name, '{NS}.', '') AS flow,
                                  max_by(details:flow_progress.status::string, timestamp) AS final_status,
                                  sum(coalesce(details:flow_progress.metrics.num_output_rows::bigint, 0)) AS output_rows,
                                  sum(coalesce(details:flow_progress.metrics.num_upserted_rows::bigint, 0)) AS upserted_rows,
                                  sum(coalesce(details:flow_progress.metrics.num_deleted_rows::bigint, 0)) AS deleted_rows
                           FROM event_log('{pid}') WHERE origin.update_id = '{uid}' AND event_type = 'flow_progress'
                           GROUP BY 1 ORDER BY 1""")
        md.append(table(c, r))

    first = list(ups.values())[0] if ups else None
    if first:
        md.append(f"\n## Expectations evaluated in update `{first}` (records checked in this update)\n")
        c, r = ctx.sql(f"""SELECT replace(origin.flow_name, '{NS}.', '') AS flow, e.name AS expectation,
                                  sum(e.passed_records) AS passed, sum(e.failed_records) AS failed
                           FROM (SELECT origin, explode(from_json(details:flow_progress.data_quality.expectations,
                                   'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) e
                                 FROM event_log('{pid}') WHERE origin.update_id = '{first}' AND event_type = 'flow_progress'
                                   AND details:flow_progress.data_quality.expectations IS NOT NULL)
                           GROUP BY ALL ORDER BY 2""")
        md.append(table(c, r))
    md.append("\n## Expectations over the pipeline's whole history\n")
    md.append("Streaming tables (`stg_*`, `f_network_*`, `stg_cards`) check each landed record once, so their sums are "
              "the records ever checked. Materialized views (`silver_auth`, `silver_merchants`, `recon_file_control`, "
              "`chk_*`) recompute, so for them the last column (latest update) is the meaningful one.\n")
    c, r = ctx.sql(f"""WITH e AS (
                         SELECT origin.update_id AS update_id, timestamp, replace(origin.flow_name, '{NS}.', '') AS flow, x.*
                         FROM (SELECT origin, timestamp, explode(from_json(details:flow_progress.data_quality.expectations,
                                 'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) x
                               FROM event_log('{pid}') WHERE event_type = 'flow_progress'
                                 AND details:flow_progress.data_quality.expectations IS NOT NULL)),
                       per_update AS (SELECT flow, name, update_id, max(timestamp) ts, sum(passed_records) p, sum(failed_records) f FROM e GROUP BY ALL),
                       latest AS (SELECT flow, name, max_by(p, ts) lp, max_by(f, ts) lf FROM per_update WHERE p + f > 0 GROUP BY ALL)
                       SELECT u.flow, u.name AS expectation, count(DISTINCT u.update_id) AS updates, sum(u.p) AS passed_all_updates,
                              sum(u.f) AS failed_all_updates, l.lp AS passed_latest, l.lf AS failed_latest
                       FROM per_update u LEFT JOIN latest l USING (flow, name) GROUP BY u.flow, u.name, l.lp, l.lf ORDER BY 2""")
    md.append(table(c, r))

    md.append("\n## Rows per table (now)\n")
    tables = ["bronze_issuer_auth", "bronze_mrd_events", "bronze_atl_daily", "bronze_merchant_master", "bronze_card_portfolio",
              "bronze_acquirer_ref", "bronze_file_manifests", "ref_response_code_map", "ref_recovery_assumptions",
              "silver_issuer_auth", "silver_network_response", "silver_merchants", "silver_acquirers", "silver_cards",
              "silver_auth", "quarantine_auth", "recon_file_control", "gold_auth_daily", "gold_auth_hourly",
              "gold_baseline_gap", "gold_anomaly_scores", "gold_anomalies", "gold_case_status", "gold_wave_readiness"]
    c, r = ctx.sql(" UNION ALL ".join(f"SELECT '{t}' AS table_name, count(*) AS rows FROM {NS}.{t}" for t in tables))
    md.append(table(c, r))
    md.append("\n## Duplicate check on the conformed auth table\n")
    c, r = ctx.sql(f"""SELECT count(*) AS rows, count(DISTINCT auth_id) AS distinct_auth_id,
                              count(*) - count(DISTINCT auth_id) AS duplicate_rows, count_if(auth_id IS NULL) AS null_auth_id
                       FROM {NS}.silver_auth""")
    md.append(table(c, r))
    md.append("\n## Data landed vs data in gold\n")
    c, r = ctx.sql(f"""SELECT (SELECT max(to_date(_business_date)) FROM {NS}.bronze_issuer_auth) AS latest_landed_business_date,
                              (SELECT max(business_date) FROM {NS}.gold_auth_daily) AS latest_gold_business_date,
                              (SELECT count(DISTINCT business_date) FROM {NS}.gold_auth_daily) AS gold_days,
                              (SELECT max(_ingested_at) FROM {NS}.bronze_issuer_auth) AS last_ingest_ts""")
    md.append(table(c, r))
    return "\n".join(md)


# =============================================================================================== 02
def gen_02(ctx):
    pid = ctx.pipeline_id
    ak = ctx.ws.api("GET", f"/api/2.0/fs/files{LANDING}/_generator_truth/answer_key.json")
    md = [header("Evidence 02: Data quality and completeness",
                 "Proves that every planted data-quality issue in the synthetic files was caught by a named rule and "
                 "counted, by comparing the generator's answer key with what the pipeline actually quarantined, "
                 "flagged or reconciled; and that every source file was reconciled against its control totals, "
                 "with the one planted truncated file shown as a BREAK. 'match' is computed, not asserted.")]
    q = dict((r[0], int(r[1])) for r in ctx.sql(f"SELECT reason, count(*) FROM {NS}.quarantine_auth GROUP BY 1")[1])
    exp = dict(((r[0], r[1]), (int(r[2]), int(r[3]))) for r in ctx.sql(f"""
        SELECT replace(origin.flow_name, '{NS}.', ''), x.name, sum(x.passed_records), sum(x.failed_records)
        FROM (SELECT origin, explode(from_json(details:flow_progress.data_quality.expectations,
                'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) x
              FROM event_log('{pid}') WHERE event_type = 'flow_progress' AND details:flow_progress.data_quality.expectations IS NOT NULL)
        GROUP BY 1, 2""")[1])
    obs = ctx.one(f"""SELECT
        (SELECT count(*) - count(DISTINCT AUTH_ID) FROM {NS}.bronze_issuer_auth WHERE AUTH_ID IS NOT NULL) AS dup_landed,
        (SELECT count(*) FROM {NS}.bronze_issuer_auth) - (SELECT count(*) FROM {NS}.quarantine_auth WHERE source_system = 'iss_auth')
          - (SELECT count(*) FROM {NS}.silver_issuer_auth) AS dup_removed_by_dedup,
        (SELECT count(*) - count(DISTINCT q.record_key) FROM {NS}.quarantine_auth q
           JOIN (SELECT AUTH_ID FROM {NS}.bronze_issuer_auth WHERE AUTH_ID IS NOT NULL GROUP BY 1 HAVING count(*) > 1) d ON q.record_key = d.AUTH_ID
           WHERE q.source_system = 'iss_auth') AS dup_copies_quarantined,
        (SELECT count(*) FROM {NS}.silver_network_response WHERE network = 'MRD' AND std_category = 'UNMAPPED') AS unmapped_rows,
        (SELECT concat_ws(',', sort_array(collect_set(native_code))) FROM {NS}.silver_network_response WHERE network = 'MRD' AND std_category = 'UNMAPPED') AS unmapped_codes,
        (SELECT count(*) FROM {NS}.bronze_card_portfolio) - (SELECT count(*) FROM {NS}.silver_cards) AS card_records_not_applied,
        (SELECT count(DISTINCT merchant_num) FROM {NS}.silver_auth WHERE mcc <> master_mcc) AS stale_mcc_merchants,
        (SELECT concat_ws(',', collect_list(concat(system, '/', business_date, ' missing ', control_count - landed_rows)))
           FROM {NS}.recon_file_control WHERE status = 'BREAK') AS breaks,
        (SELECT concat_ws(',', sort_array(collect_list(concat(system, '/', business_date, ' +', hours_after_business_date, 'h'))))
           FROM {NS}.recon_file_control WHERE system = 'atl_daily' AND hours_after_business_date > 30) AS late_files,
        (SELECT count(DISTINCT m.merchant_num) FROM {NS}.silver_network_response n JOIN {NS}.silver_merchants m
           ON n.merchant_id_norm = m.mrd_mid_norm WHERE n.network = 'MRD' AND n.merchant_network_id <> m.mrd_mid) AS mrd_ids_normalised""")

    def m(a, b):
        return "match" if str(a) == str(b) else "differs"
    r12 = exp.get(("silver_auth", "r12_mrd_merchant_id_matches"), (None, None))
    rows = [
        ["DQ1 duplicate re-sent auths landed (rows beyond the first per AUTH_ID, bronze)", ak["DQ1_duplicate_rows"], obs["dup_landed"], "counted in bronze", m(ak["DQ1_duplicate_rows"], obs["dup_landed"])],
        ["DQ1 … removed before gold", ak["DQ1_duplicate_rows"], int(obs["dup_removed_by_dedup"]) + int(obs["dup_copies_quarantined"]),
         f"dedup in silver ({obs['dup_removed_by_dedup']}) + re-sent copies of bad rows quarantined by a DROP rule ({obs['dup_copies_quarantined']})",
         m(ak["DQ1_duplicate_rows"], int(obs["dup_removed_by_dedup"]) + int(obs["dup_copies_quarantined"]))],
        ["DQ2 bad amounts", ak["DQ2_bad_amount_rows"], q.get("r2_valid_amount"), "r2_valid_amount DROP → quarantine", m(ak["DQ2_bad_amount_rows"], q.get("r2_valid_amount"))],
        ["DQ3 future timestamps", ak["DQ3_future_ts_rows"], q.get("r3_ts_not_future"), "r3_ts_not_future DROP → quarantine", m(ak["DQ3_future_ts_rows"], q.get("r3_ts_not_future"))],
        ["DQ4 null AUTH_ID", ak["DQ4_null_auth_id_rows"], q.get("r1_auth_id_not_null"), "r1_auth_id_not_null DROP → quarantine", m(ak["DQ4_null_auth_id_rows"], q.get("r1_auth_id_not_null"))],
        ["DQ5 unmapped Meridian codes (rows)", ak["DQ5_unmapped_rows"], obs["unmapped_rows"], "r9_code_mapped WARN → UNMAPPED", m(ak["DQ5_unmapped_rows"], obs["unmapped_rows"])],
        ["DQ5 unmapped Meridian codes (codes)", ",".join(ak["DQ5_unmapped_codes"]), obs["unmapped_codes"], "same", m(",".join(ak["DQ5_unmapped_codes"]), obs["unmapped_codes"])],
        ["DQ6 Meridian merchant ID variants (merchants seen)", ak["DQ6_merchants_mid_variant_seen_on_mrd"], obs["mrd_ids_normalised"], f"normalised in silver; r12 failed after normalisation = {r12[1]}", m(ak["DQ6_merchants_mid_variant_seen_on_mrd"], obs["mrd_ids_normalised"])],
        ["DQ7 card updates out of sequence", ak["DQ7_out_of_sequence_card_records"], obs["card_records_not_applied"], "AUTO CDC SCD2 SEQUENCE BY update_ts (bronze rows − silver versions)", m(ak["DQ7_out_of_sequence_card_records"], obs["card_records_not_applied"])],
        ["DQ8 truncated file", f"{ak['DQ8_control_total_mismatch']['folder']} missing {ak['DQ8_control_total_mismatch']['rows_missing']}", obs["breaks"], "r17_file_reconciled WARN + recon BREAK", m(ak["DQ8_control_total_mismatch"]["folder"].replace("atl_daily/", "atl_daily/") + f" missing {ak['DQ8_control_total_mismatch']['rows_missing']}", obs["breaks"])],
        ["DQ9 late legacy files", ",".join(ak["DQ9_late_files"]), obs["late_files"], "r10_file_on_time WARN + as-of timing rule", "see list"],
        ["DQ10 stale MCC (merchants)", ak["DQ10_merchants_stale_mcc_seen"], obs["stale_mcc_merchants"], "r13_mcc_matches_master WARN", m(ak["DQ10_merchants_stale_mcc_seen"], obs["stale_mcc_merchants"])],
    ]
    md.append("## Planted (answer key) vs observed (pipeline)\n")
    md.append(f"Answer key: `{LANDING}/_generator_truth/answer_key.json`, landed dates {ak['landed_dates'][0]} → {ak['landed_dates'][1]} ({ak['n_landed_dates']} days).\n")
    md.append(table(["finding", "planted", "observed", "rule / mechanism", "result"], rows))
    md.append("\n## Quarantine (rows removed by DROP rules, kept with the reason)\n")
    c, r = ctx.sql(f"""SELECT source_system, reason, count(*) AS rows, min(business_date) AS first_day, max(business_date) AS last_day
                       FROM {NS}.quarantine_auth GROUP BY ALL ORDER BY 1, 2""")
    md.append(table(c, r))
    md.append("\nOne quarantined record per reason, verbatim (raw record as landed):\n")
    c, r = ctx.sql(f"""SELECT reason, min_by(record, coalesce(record_key, '') || _ingested_at) AS record FROM {NS}.quarantine_auth
                       WHERE record IS NOT NULL GROUP BY 1 ORDER BY 1""")
    md.append(table(c, r))
    md.append("\n## File reconciliation (`recon_file_control`: manifest control totals vs landed rows)\n")
    c, r = ctx.sql(f"""SELECT system, status, count(*) AS files, count(DISTINCT business_date) AS business_days,
                              min(business_date) AS first_day, max(business_date) AS last_day,
                              sum(control_count) AS control_rows, sum(landed_rows) AS landed_rows, sum(quarantined_rows) AS quarantined_rows,
                              sum(duplicates_superseded) AS duplicates_superseded, max(hours_after_business_date) AS max_hours_late
                       FROM {NS}.recon_file_control GROUP BY ALL ORDER BY 1, 2""")
    md.append(table(c, r))
    md.append("\nFiles not RECONCILED, or delivered more than 30 hours after the business date:\n")
    c, r = ctx.sql(f"""SELECT system, business_date, file_name, file_created_ts, hours_after_business_date, control_count, landed_rows,
                              control_amount, landed_amount, amount_diff, status, break_reason
                       FROM {NS}.recon_file_control WHERE status <> 'RECONCILED' OR hours_after_business_date > 30 ORDER BY 2""")
    md.append(table(c, r))
    md.append("\n## Completeness: business days with data, per source (expected 365 daily days 2025-11-20 → 2026-11-19)\n")
    c, r = ctx.sql(f"""SELECT 'issuer auths (silver_issuer_auth)' AS source, count(DISTINCT business_date) AS days, min(business_date) AS first_day, max(business_date) AS last_day FROM {NS}.silver_issuer_auth
                       UNION ALL SELECT 'network responses MRD', count(DISTINCT business_date), min(business_date), max(business_date) FROM {NS}.silver_network_response WHERE network = 'MRD'
                       UNION ALL SELECT 'network responses ATL', count(DISTINCT business_date), min(business_date), max(business_date) FROM {NS}.silver_network_response WHERE network = 'ATL'
                       UNION ALL SELECT 'gold_auth_daily', count(DISTINCT business_date), min(business_date), max(business_date) FROM {NS}.gold_auth_daily""")
    md.append(table(c, r))
    md.append("\nMeridian (MRD) has fewer days because the acquired network starts carrying traffic with migration wave 1; "
              "the first and last MRD day are shown above. Calendar gaps inside the gold range:\n")
    c, r = ctx.sql(f"""WITH b AS (SELECT min(business_date) AS d0, max(business_date) AS d1, count(DISTINCT business_date) AS n FROM {NS}.gold_auth_daily)
                       SELECT d0 AS first_day, d1 AS last_day, datediff(d1, d0) + 1 AS calendar_days, n AS days_with_data,
                              datediff(d1, d0) + 1 - n AS missing_days FROM b""")
    md.append(table(c, r))
    return "\n".join(md)


# =============================================================================================== 03
def gen_03(ctx):
    md = [header("Evidence 03: Business results (gold answers)",
                 "Proves the business answers the VP of Payment Network Integration and the Director of Payment Network "
                 "Operations need, computed live from the governed gold tables: the approval gap of migrated cards vs a "
                 "matched legacy baseline, the spend lost to excess declines, the incidents turned into cases, and the "
                 "GO/HOLD readiness gate for the next migration waves. All data is synthetic. 'Lost spend' is purchase "
                 "volume not recovered (a Finance assumption by segment), not bank revenue.")]
    last30 = f"business_date > (SELECT date_sub(max(business_date), 30) FROM {NS}.gold_baseline_gap)"
    md.append("## Headline: migrated cards vs matched baseline, last 30 days of data\n")
    c, r = ctx.sql(f"""SELECT min(business_date) AS from_date, max(business_date) AS to_date, sum(migrated_attempts) AS migrated_attempts,
                              round(100 * sum(migrated_approvals) / sum(migrated_attempts), 2) AS migrated_approval_rate_pct,
                              round(100 * sum(expected_approvals) / sum(migrated_attempts), 2) AS matched_baseline_rate_pct,
                              round(100 * (sum(expected_approvals) - sum(migrated_approvals)) / sum(migrated_attempts), 2) AS gap_pp,
                              round(sum(excess_declines)) AS excess_declines, round(sum(lost_spend), 2) AS lost_spend_usd
                       FROM {NS}.gold_baseline_gap WHERE {last30}""")
    md.append(table(c, r))
    md.append("\n## Gap by migration wave cohort, last 30 days\n")
    c, r = ctx.sql(f"""SELECT wave_cohort, sum(migrated_attempts) AS migrated_attempts,
                              round(100 * (sum(expected_approvals) - sum(migrated_approvals)) / sum(migrated_attempts), 2) AS gap_pp,
                              round(sum(excess_declines)) AS excess_declines, round(sum(lost_spend), 2) AS lost_spend_usd
                       FROM {NS}.gold_baseline_gap WHERE {last30} GROUP BY 1 ORDER BY 1""")
    md.append(table(c, r))
    md.append("\n## Matched vs unmatched baseline, last 30 days (why the matching matters)\n")
    c, r = ctx.sql(f"""SELECT round(100 * (sum(expected_approvals) - sum(migrated_approvals)) / sum(migrated_attempts), 2) AS gap_vs_matched_baseline_pp,
                              round(100 * (sum(unmatched_baseline_rate * migrated_attempts) - sum(migrated_approvals)) / sum(migrated_attempts), 2) AS gap_vs_unmatched_baseline_pp
                       FROM {NS}.gold_baseline_gap WHERE {last30}""")
    md.append(table(c, r))
    md.append("\n## Monthly trend (whole history)\n")
    c, r = ctx.sql(f"""SELECT date_format(business_date, 'yyyy-MM') AS month, sum(migrated_attempts) AS migrated_attempts,
                              round(100 * (sum(expected_approvals) - sum(migrated_approvals)) / sum(migrated_attempts), 2) AS gap_pp,
                              round(sum(lost_spend), 2) AS lost_spend_usd
                       FROM {NS}.gold_baseline_gap GROUP BY 1 ORDER BY 1""")
    md.append(table(c, r))
    md.append("\n## Acceptance declines on the acquired network by standard category, last 30 days\n")
    c, r = ctx.sql(f"""SELECT sum(attempts) AS attempts, sum(acceptance_declines) AS acceptance_declines,
                              sum(decl_acceptance_config) AS acceptance_config, sum(decl_token_provisioning) AS token_provisioning,
                              sum(decl_cross_border_block) AS cross_border_block, sum(decl_card_on_file_stale) AS card_on_file_stale,
                              sum(decl_processor_timeout) AS processor_timeout, sum(decl_system_error) AS system_error,
                              sum(unmapped_declines) AS unmapped
                       FROM {NS}.gold_auth_daily WHERE network = 'MRD'
                         AND business_date > (SELECT date_sub(max(business_date), 30) FROM {NS}.gold_auth_daily)""")
    md.append(table(c, r))
    md.append("\n## Top acquirers by acceptance declines on the acquired network, last 14 days\n")
    c, r = ctx.sql(f"""SELECT acquirer_id, acquirer_name, sum(attempts) AS attempts, sum(acceptance_declines) AS acceptance_declines,
                              round(100 * sum(acceptance_declines) / sum(attempts), 2) AS acceptance_decline_rate_pct
                       FROM {NS}.gold_auth_daily WHERE network = 'MRD'
                         AND business_date > (SELECT date_sub(max(business_date), 14) FROM {NS}.gold_auth_daily)
                       GROUP BY ALL ORDER BY acceptance_declines DESC LIMIT 10""")
    md.append(table(c, r))
    md.append("\n## Cases (incidents grouped into episodes; status from Lakebase via the back-sync)\n")
    c, r = ctx.sql(f"""SELECT case_id, root_cause, issuer_segment, region_scope, episode_start, episode_end, n_flags, max_score, severity,
                              round(exposure_usd, 2) AS exposure_usd, status, owner_team, resolution_code, recovered_spend_usd
                       FROM {NS}.gold_case_status ORDER BY case_id""")
    md.append(table(c, r))
    c, r = ctx.sql(f"""SELECT count(*) AS cases, count_if(status NOT IN ('RESOLVED','DISMISSED')) AS open_cases,
                              count_if(status NOT IN ('RESOLVED','DISMISSED') AND severity = 'HIGH') AS open_high,
                              round(sum(CASE WHEN status NOT IN ('RESOLVED','DISMISSED') THEN exposure_usd END), 2) AS open_exposure_usd
                       FROM {NS}.gold_case_status""")
    md.append("\n" + table(c, r))
    md.append("\n## Wave readiness gate (GO only if the segment gap ≤ 0.3 pp and no HIGH case is open)\n")
    c, r = ctx.sql(f"""SELECT wave_id, min(planned_migration_date) AS planned_migration_date, count(*) AS segments,
                              count_if(gate = 'GO') AS go, count_if(gate = 'HOLD') AS hold, sum(cards) AS cards,
                              round(sum(expected_daily_attempts)) AS expected_daily_attempts,
                              round(sum(at_risk_declines_per_day), 1) AS at_risk_declines_per_day,
                              round(sum(at_risk_spend_usd_per_day), 2) AS at_risk_spend_usd_per_day, max(as_of_date) AS as_of_date
                       FROM {NS}.gold_wave_readiness GROUP BY 1 ORDER BY 1""")
    md.append(table(c, r))
    md.append("\nWave 7 detail:\n")
    c, r = ctx.sql(f"""SELECT card_segment, issuer_segment, cards, round(expected_daily_attempts) AS expected_daily_attempts,
                              round(segment_gap_pp_14d, 2) AS segment_gap_pp_14d, open_high_cases, gate, gate_reason,
                              round(at_risk_declines_per_day, 1) AS at_risk_declines_per_day, round(at_risk_spend_usd_per_day, 2) AS at_risk_spend_usd_per_day
                       FROM {NS}.gold_wave_readiness WHERE wave_id = 7 ORDER BY issuer_segment, at_risk_spend_usd_per_day DESC""")
    md.append(table(c, r))
    md.append("\n## Recovery assumptions used for lost spend (Finance reference table)\n")
    c, r = ctx.sql(f"SELECT * FROM {NS}.ref_recovery_assumptions ORDER BY 1")
    md.append(table(c, r))
    return "\n".join(md)


# =============================================================================================== 04
def gen_04(ctx):
    md = [header("Evidence 04: AI output samples (verbatim, with the facts given)",
                 "Proves what the intelligent step produces: an explainable anomaly score (frozen threshold) that flags "
                 "slices, and an `ai_query` explanation per flag. For each case below, the representative flag shows the "
                 "exact facts JSON given to the model and the model's structured answer, copied from the tables, "
                 "unedited. The model only sees aggregated facts, never card-level data.")]
    md.append("## Detector configuration (frozen before the held-out evaluation)\n")
    c, r = ctx.sql(f"SELECT config_version, threshold, volume_floor, frozen_at_utc, protocol FROM {NS}.detector_config ORDER BY frozen_at_utc")
    md.append(table(c, r))
    md.append("\n## What was generated\n")
    ex = next((t for t in ctx.run()["tasks"] if t["task_key"] == "explain_anomalies"), None)
    params = ((ctx.ws.api("GET", "/api/2.2/jobs/get", query={"job_id": ctx.job_main})["settings"].get("tasks") or [{}]))
    p_ex = next((t.get("notebook_task", {}).get("base_parameters") for t in params if t.get("task_key") == "explain_anomalies"), {})
    md.append(f"Task `explain_anomalies` parameters in job `febar_main`: `{json.dumps(p_ex)}`. Rows with an empty prompt_version "
              "below are flags that were not sent to the model by those parameters.\n")
    c, r = ctx.sql(f"""SELECT prompt_version, llm_model, count(*) AS flags, count_if(llm_error IS NULL AND llm_summary IS NOT NULL) AS explained,
                              count_if(llm_error IS NOT NULL) AS errors, min(business_date) AS first_day, max(business_date) AS last_day
                       FROM {NS}.gold_anomalies GROUP BY ALL ORDER BY 1""")
    md.append(table(c, r))
    c, r = ctx.sql(f"""SELECT prompt_version, llm_model, count(*) AS explanations, min(explained_at) AS first_at, max(explained_at) AS last_at
                       FROM {NS}.anomaly_explanations GROUP BY ALL ORDER BY 1""")
    md.append("\nHistory table `anomaly_explanations` (every explanation ever generated, all prompt versions):\n\n" + table(c, r))
    md.append("\n## Flags by likely root cause\n")
    c, r = ctx.sql(f"""SELECT likely_root_cause, count(*) AS flags, min(business_date) AS first_day, max(business_date) AS last_day,
                              round(max(score), 1) AS max_score, round(sum(exposure_usd), 2) AS exposure_usd
                       FROM {NS}.gold_anomalies GROUP BY 1 ORDER BY flags DESC""")
    md.append(table(c, r))
    md.append("\n## One explained flag per case (highest score in the case's episode), verbatim\n")
    cases = ctx.sql(f"SELECT case_id, root_cause, issuer_segment, episode_start, episode_end FROM {NS}.gold_case_status ORDER BY case_id")[1]
    for case_id, rc, seg, d0, d1 in cases:
        c, r = ctx.sql(f"""SELECT anomaly_key, business_date, family, slice_value, round(score, 1) AS score, drivers, facts, llm_model, prompt_version,
                                  llm_summary, llm_likely_cause, llm_certainty, llm_next_step, llm_owner_team, llm_facts_used, llm_error
                           FROM {NS}.gold_anomalies
                           WHERE likely_root_cause = '{rc}' AND issuer_segment = '{seg}' AND business_date BETWEEN '{d0}' AND '{d1}'
                             AND llm_summary IS NOT NULL
                           ORDER BY score DESC LIMIT 1""")
        if not r:
            continue
        a = dict(zip(c, r[0]))
        try:
            facts = json.dumps(json.loads(a["facts"]), indent=1)
        except (TypeError, ValueError):
            facts = str(a["facts"])
        md.append(f"\n### Case {case_id}: {rc} / {seg} ({d0} → {d1})\n")
        md.append(kv({"anomaly_key": a["anomaly_key"], "business_date": a["business_date"], "slice": f"{a['family']}: {a['slice_value']}",
                      "score": a["score"], "drivers (score explanation)": a["drivers"], "model": a["llm_model"], "prompt_version": a["prompt_version"]}))
        md.append("\nFacts given to the model:\n\n" + code(facts, "json"))
        md.append("Model answer (structured output):\n\n" + kv({"summary": a["llm_summary"], "likely_cause": a["llm_likely_cause"],
                                                               "certainty": a["llm_certainty"], "next_step": a["llm_next_step"],
                                                               "owner_team": a["llm_owner_team"], "facts_used": a["llm_facts_used"],
                                                               "error": a["llm_error"]}))
    md.append("\n## The full prompt sent for one flag (latest prompt version), verbatim\n")
    c, r = ctx.sql(f"""SELECT anomaly_key, prompt_version, prompt_text FROM {NS}.anomaly_explanations
                       WHERE prompt_version = (SELECT max(prompt_version) FROM {NS}.gold_anomalies)
                       ORDER BY explained_at DESC, anomaly_key LIMIT 1""")
    if r:
        md.append(f"`{r[0][0]}`, prompt `{r[0][1]}`:\n\n" + code(r[0][2]))
    return "\n".join(md)


# =============================================================================================== 05
def gen_05(ctx):
    md = [header("Evidence 05: AI evaluation and iteration history",
                 "Proves how well the intelligent step works, measured against the answer key under the pre-registered "
                 "protocol (EVAL_PROTOCOL.md): detection precision and recall of the method vs a simple baseline on "
                 "tuning and held-out days, and LLM-judge plus rule-check pass rates of the explanations for each "
                 "prompt version (the iteration history). Every row comes from the `eval_runs` and `eval_judge_results` "
                 "tables written by `src/ai/evaluate.py`; failures are shown, not hidden.")]
    runs = [(r[0], json.loads(r[1])) for r in ctx.sql(f"SELECT run_label, summary FROM {NS}.eval_runs ORDER BY run_at_utc")[1]]
    md.append("## Evaluation runs\n")
    md.append(table(["run_label", "run_at_utc", "protocol", "detector", "threshold", "frozen_at_utc", "has detection", "has genai"],
                    [[lbl, s.get("run_at_utc"), s.get("protocol"), s.get("detector", {}).get("config_version"),
                      s.get("detector", {}).get("threshold"), s.get("detector", {}).get("frozen_at_utc"),
                      "detection" in s, "genai" in s] for lbl, s in runs]))
    md.append("\n## Detection: method vs baseline (counts of daily flags; a hit = the flag overlaps a planted incident)\n")
    det_rows = []
    for lbl, s in runs:
        for method, splits in (s.get("detection") or {}).items():
            for split, v in splits.items():
                det_rows.append([lbl, method, split, v.get("split"), v.get("flags"), v.get("hits"), round(v.get("precision") or 0, 3),
                                 "–".join(f"{x:.3f}" for x in v.get("precision_wilson95") or []),
                                 f"{len(v.get('incidents_caught') or [])}/{len(v.get('incidents') or [])}",
                                 round(v.get("incident_day_recall") or 0, 3), v.get("decoy_flags")])
    md.append(table(["run", "method", "split", "days", "flags", "hits", "precision", "precision 95% CI (Wilson)",
                     "incidents caught", "incident-day recall", "decoy flags"], det_rows))
    md.append("\n### Per incident (method)\n")
    pi = []
    for lbl, s in runs:
        for split, v in ((s.get("detection") or {}).get("method") or {}).items():
            for inc, d in (v.get("per_incident") or {}).items():
                pi.append([lbl, split, inc, d.get("caught"), d.get("first_flag"), d.get("delay_days"), d.get("incident_days_flagged"),
                           d.get("root_cause_first_flag"), d.get("root_cause_matches")])
    md.append(table(["run", "split", "incident", "caught", "first flag", "delay (days)", "days flagged", "root cause at first flag", "root cause correct"], pi))
    md.append("\n### No-claim conditions (EVAL_PROTOCOL §6: if a condition is TRUE, the matching claim is not made)\n")
    nc = []
    for lbl, s in runs:
        for k, v in ((s.get("detection_checks") or {}).get("no_claim_conditions") or {}).items():
            nc.append([lbl, k, v])
        g = s.get("genai") or {}
        if "no_claim_grounding_below_90pct" in g:
            nc.append([lbl, "no_claim_grounding_below_90pct", g["no_claim_grounding_below_90pct"]])
    md.append(table(["run", "condition", "value"], nc))
    md.append("\n## Explanations: judge and rule pass rates per prompt version (iteration history)\n")
    jr, judges = [], []
    for lbl, s in runs:
        g = s.get("genai")
        if not g:
            continue
        for j in g.get("per_judge", {}):
            if j not in judges:
                judges.append(j)
    for lbl, s in runs:
        g = s.get("genai")
        if not g:
            continue
        pj = g.get("per_judge", {})
        jr.append([lbl, g.get("generator_prompt_version"), g.get("judge_endpoint"), g.get("n_rows"), g.get("llm_errors_in_sample")] +
                  [f"{pj[j]['pass']}/{pj[j]['n']}" if j in pj else "" for j in judges] + [g.get("mlflow_run_id")])
    md.append(table(["run", "prompt", "judge model", "rows", "LLM errors"] + judges + ["MLflow run"], jr))
    md.append("\nJudges `actionable_next_step`, `no_invented_data`, `grounded_in_facts` and `cause_agreement` are MLflow 3 "
              "Guidelines judges (LLM); `rule_numbers_grounded` and `rule_cause_matches` are deterministic rule checks "
              "(every number in the text appears in the facts; the stated cause equals the computed root cause).\n")
    md.append("\n## Judge results as stored (latest run per prompt version)\n")
    c, r = ctx.sql(f"""WITH latest AS (SELECT prompt_version, max_by(run_label, run_at_utc) AS run_label FROM {NS}.eval_judge_results GROUP BY 1)
                       SELECT j.run_label, j.prompt_version, j.judge, count(*) AS n, count_if(lower(j.value) IN ('yes','true','pass')) AS pass
                       FROM {NS}.eval_judge_results j JOIN latest USING (prompt_version, run_label) GROUP BY ALL ORDER BY 2, 3""")
    md.append(table(c, r))
    md.append("\n## Failing judgements, verbatim (latest prompt version, up to 3 per judge)\n")
    c, r = ctx.sql(f"""WITH latest AS (SELECT max_by(run_label, run_at_utc) AS run_label, max(prompt_version) AS pv FROM {NS}.eval_judge_results),
                       f AS (SELECT j.*, row_number() OVER (PARTITION BY judge ORDER BY anomaly_key) AS rn FROM {NS}.eval_judge_results j, latest
                             WHERE j.run_label = latest.run_label AND lower(j.value) NOT IN ('yes','true','pass'))
                       SELECT run_label, prompt_version, judge, anomaly_key, value, rationale FROM f WHERE rn <= 3 ORDER BY judge, anomaly_key""")
    md.append(table(c, r))
    md.append("\n## Detection flags per method in the held-out window (latest run), by hit type\n")
    c, r = ctx.sql(f"""SELECT run_label, method, hit, count(*) AS flags FROM {NS}.eval_detection_flags
                       WHERE run_label = (SELECT max_by(run_label, run_at_utc) FROM {NS}.eval_detection_flags)
                       GROUP BY ALL ORDER BY 2, 3""")
    md.append(table(c, r))
    return "\n".join(md)


# =============================================================================================== 06
PERSONA_Q = f"""SELECT
  (SELECT persona FROM {NS}.entitlements WHERE principal = current_user()) AS persona,
  sum(attempts) AS attempts_visible,
  sum(CASE WHEN issuer_segment = 'OWN' THEN attempts END) AS own_attempts,
  sum(CASE WHEN issuer_segment = 'THIRD_PARTY' THEN attempts END) AS third_party_attempts,
  concat_ws(',', sort_array(collect_set(region))) AS regions_visible,
  (SELECT count(*) FROM {NS}.gold_case_status) AS cases_visible,
  (SELECT count(*) FROM {NS}.gold_wave_readiness) AS readiness_rows_visible,
  (SELECT count(*) FROM {NS}.auth_detail) AS detail_rows,
  (SELECT max_by(card_ref, auth_id) FROM {NS}.auth_detail) AS card_ref_sample
FROM {NS}.gold_auth_daily"""


def set_persona(ctx, persona, note):
    ctx.sql(f"""MERGE INTO {NS}.entitlements t USING (SELECT current_user() principal) s ON t.principal = s.principal
                WHEN MATCHED THEN UPDATE SET persona = '{persona}', granted_at = current_timestamp(), note = '{note}'
                WHEN NOT MATCHED THEN INSERT (principal, principal_type, persona, granted_at, note)
                VALUES (s.principal, 'USER', '{persona}', current_timestamp(), '{note}')""")


def gen_06(ctx):
    md = [header("Evidence 06: Unity Catalog governance per persona",
                 "Proves that access is enforced by Unity Catalog, not by the app: which tables carry the row filter and "
                 "the column mask, the tags, the grants, and, for each persona, what the same query returns when run by "
                 "a caller holding that persona (rows, segments, regions, masked card references). It also shows a "
                 "non-admin service principal's result and the lineage Unity Catalog recorded.")]
    md.append("## Policies attached (information_schema)\n")
    c, r = ctx.sql(f"""SELECT table_name, filter_name, target_columns FROM {CATALOG}.information_schema.row_filters
                       WHERE table_schema = '{SCHEMA}' ORDER BY 1""")
    md.append("Row filters:\n\n" + table(c, r))
    c, r = ctx.sql(f"""SELECT table_name, column_name, mask_name FROM {CATALOG}.information_schema.column_masks
                       WHERE table_schema = '{SCHEMA}' ORDER BY 1""")
    md.append("\nColumn masks:\n\n" + table(c, r))
    md.append("\n## Policy functions (definition as stored)\n")
    c, r = ctx.sql(f"""SELECT routine_name, routine_definition FROM {CATALOG}.information_schema.routines
                       WHERE routine_schema = '{SCHEMA}' AND routine_name IN ('f_row_filter', 'f_mask_card') ORDER BY 1""")
    for name, body in r:
        md.append(f"`{name}`:\n\n" + code(body or "", "sql"))
    md.append("\n## Personas and entitlements (data, not code)\n")
    c, r = ctx.sql(f"SELECT * FROM {NS}.personas ORDER BY 1")
    md.append(table(c, r))
    c, r = ctx.sql(f"SELECT principal_type, persona, count(*) AS principals FROM {NS}.entitlements GROUP BY ALL ORDER BY 2")
    md.append("\nEntitlement rows (principals counted, not named):\n\n" + table(c, r))
    md.append("\n## Same query, one persona at a time\n")
    md.append("The caller's own entitlement row is switched to each persona, the query below runs, and the row is restored "
              "to ADMIN at the end (in `finally`). Policies are evaluated by Unity Catalog at query time.\n")
    md.append(code(PERSONA_Q.replace(NS + ".", ""), "sql"))
    rows, cols = [], None
    try:
        for p in ["P1_DIRECTOR", "P2_REGIONAL", "P3_CARD_INV", "P4_PARTNER", "NONE", "ADMIN"]:
            if p == "NONE":
                ctx.sql(f"DELETE FROM {NS}.entitlements WHERE principal = current_user()")
            else:
                set_persona(ctx, p, "persona test (generate_evidence)")
            cols, rr = ctx.sql(PERSONA_Q)
            row = list(rr[0])
            row[0] = row[0] or "(no entitlement)"
            rows.append(row)
    finally:
        set_persona(ctx, "ADMIN", "Pipeline and job owner")
    md.append(table(cols, rows))
    md.append("\n## Non-admin service principal (separate identity, profile `%s`)\n" % ctx.args.sp_profile)
    sp_rows = []
    try:
        sp = Workspace(ctx.args.sp_profile)
        for label, q in [("current persona", f"SELECT persona FROM {NS}.entitlements WHERE principal = current_user()"),
                         ("rows visible in gold_auth_daily", f"SELECT count(*) FROM {NS}.gold_auth_daily"),
                         ("cases visible in gold_case_status", f"SELECT count(*) FROM {NS}.gold_case_status"),
                         ("direct read of silver_auth", f"SELECT count(*) FROM {NS}.silver_auth")]:
            try:
                c, r = sp.sql(q, ctx.warehouse)
                sp_rows.append([label, "SUCCEEDED", r[0][0] if r else "(no rows)"])
            except ApiError as e:
                cls = re.search(r"\[([A-Z_]+)\]", str(e))
                why = re.search(r"does not have ([A-Z ]+ on [A-Za-z]+ '[^']+')", str(e))
                sp_rows.append([label, "FAILED", (cls.group(1) if cls else str(e).split(":")[0]) + (f": does not have {why.group(1)}" if why else "")])
    except Exception as e:  # noqa: BLE001
        sp_rows.append(["service principal profile", "UNAVAILABLE", type(e).__name__])
    md.append(table(["query", "state", "result or error class"], sp_rows))
    md.append("\nThis is the service principal's state now. The full non-admin test (temporary grants, persona P2_REGIONAL, "
              "then clean-up) is recorded in `build_history/06_governance.md`; its grants were removed at the end of that test.\n")
    md.append("\n## Tags\n")
    c, r = ctx.sql(f"""SELECT table_name, tag_name, tag_value FROM {CATALOG}.information_schema.table_tags
                       WHERE schema_name = '{SCHEMA}' ORDER BY 1, 2""")
    md.append(table(c, r))
    c, r = ctx.sql(f"""SELECT table_name, column_name, tag_name, tag_value FROM {CATALOG}.information_schema.column_tags
                       WHERE schema_name = '{SCHEMA}' ORDER BY 1, 2, 3""")
    md.append("\nColumn tags:\n\n" + table(c, r))
    md.append("\n## Grants on the schema\n")
    try:
        c, r = ctx.sql(f"SHOW GRANTS ON SCHEMA {NS}")
        md.append(table(c, [[clean(v) for v in row] for row in r]))
    except ApiError as e:
        md.append(f"_SHOW GRANTS failed: {e}_\n")
    md.append("\n## Lineage recorded by Unity Catalog (system.access.table_lineage, distinct edges into gold)\n")
    try:
        c, r = ctx.sql(f"""SELECT DISTINCT replace(source_table_full_name, '{NS}.', '') AS source, replace(target_table_full_name, '{NS}.', '') AS target
                           FROM system.access.table_lineage
                           WHERE target_table_full_name LIKE '{NS}.gold%' AND source_table_full_name LIKE '{NS}.%'
                             AND event_date >= date_sub(current_date(), 30) ORDER BY 2, 1""")
        md.append(table(c, r))
    except ApiError as e:
        md.append(f"_Lineage query failed: {e}_\n")
    return "\n".join(md)


# =============================================================================================== 07
EDIT_TEST = """BEGIN;
DO $$
DECLARE c record; n int;
BEGIN
  SELECT case_id, version, status INTO c FROM ops.cases WHERE status NOT IN ('RESOLVED','DISMISSED') ORDER BY case_id LIMIT 1;
  RAISE NOTICE 'T0 test case % status % version %', c.case_id, c.status, c.version;
  UPDATE ops.cases SET status = 'IN_PROGRESS', updated_at = now(), version = version + 1 WHERE case_id = c.case_id AND version = c.version;
  GET DIAGNOSTICS n = ROW_COUNT;
  RAISE NOTICE 'T1 analyst A saves with the version they loaded (%): rows updated = % (expected 1)', c.version, n;
  UPDATE ops.cases SET status = 'WAITING_PARTNER', updated_at = now(), version = version + 1 WHERE case_id = c.case_id AND version = c.version;
  GET DIAGNOSTICS n = ROW_COUNT;
  RAISE NOTICE 'T2 analyst B saves with the same, now stale, version (%): rows updated = % (expected 0, B is told to reload)', c.version, n;
  BEGIN
    UPDATE ops.cases SET status = 'RESOLVED' WHERE case_id = c.case_id;
    RAISE NOTICE 'T3 RESOLVED without a resolution code: ACCEPTED (unexpected)';
  EXCEPTION WHEN check_violation THEN
    RAISE NOTICE 'T3 RESOLVED without a resolution code: refused by CHECK constraint (%)', SQLERRM;
  END;
  BEGIN
    UPDATE ops.cases SET recovered_spend_usd = -1 WHERE case_id = c.case_id;
    RAISE NOTICE 'T4 negative recovered spend: ACCEPTED (unexpected)';
  EXCEPTION WHEN check_violation THEN
    RAISE NOTICE 'T4 negative recovered spend: refused by CHECK constraint (%)', SQLERRM;
  END;
  BEGIN
    INSERT INTO ops.cases (case_key, root_cause, issuer_segment, region_scope, episode_start, episode_end, n_flags, max_score, severity)
    SELECT case_key, root_cause, issuer_segment, region_scope, episode_start, episode_end, n_flags, max_score, severity FROM ops.cases WHERE case_id = c.case_id;
    RAISE NOTICE 'T5 second case with the same case_key: ACCEPTED (unexpected)';
  EXCEPTION WHEN unique_violation THEN
    RAISE NOTICE 'T5 second case with the same case_key: refused by UNIQUE constraint (%)', SQLERRM;
  END;
END $$;
ROLLBACK;
"""


def gen_07(ctx):
    lb = ctx.lb()
    ep = lb.endpoint
    md = [header("Evidence 07: Lakebase case store (counts, history, edit test)",
                 "Proves that the operational case store runs on Lakebase (Autoscaling Postgres): the endpoint, the "
                 "tables and their constraints, how many cases, links and history rows exist, that analysts' edits "
                 "made through the App are recorded and survive the machine re-sync, that the copy in Unity Catalog "
                 "matches Lakebase, and an edit test (optimistic locking and constraints) run inside a transaction "
                 "that is rolled back, so it changes nothing. Identities are redacted; the connection uses a "
                 "short-lived OAuth credential that is never written down.")]
    md.append(f"Connection: {lb.mode}, OAuth database credential from `POST /api/2.0/postgres/credentials`, sslmode=require.\n")
    md.append("## Endpoint (Postgres API)\n")
    st = ep.get("status", {})
    md.append(kv({"name": ep.get("name"), "type": st.get("endpoint_type"), "state": st.get("current_state"),
                  "autoscaling CU": f"{st.get('autoscaling_limit_min_cu')} – {st.get('autoscaling_limit_max_cu')}",
                  "suspend timeout": st.get("suspend_timeout_duration"), "database": LB_DATABASE}))
    md.append("\n## Tables and row counts\n")
    c, r = lb.query("""SELECT 'ops.cases' AS table_name, count(*) AS rows FROM ops.cases
                       UNION ALL SELECT 'ops.case_anomalies', count(*) FROM ops.case_anomalies
                       UNION ALL SELECT 'ops.case_events', count(*) FROM ops.case_events""")
    md.append(table(c, r))
    md.append("\n## Constraints (pg_constraint)\n")
    c, r = lb.query("""SELECT conrelid::regclass::text AS table_name, conname, pg_get_constraintdef(oid) AS definition
                       FROM pg_constraint WHERE connamespace = 'ops'::regnamespace ORDER BY 1, 2""")
    md.append(table(c, r))
    md.append("\n## Cases (machine-owned and human-owned columns)\n")
    c, r = lb.query("""SELECT case_id, root_cause, issuer_segment, region_scope, episode_start, episode_end, n_flags, max_score, severity,
                              exposure_usd, status, CASE WHEN assignee IS NULL THEN NULL ELSE '<user>' END AS assignee, owner_team, due_date,
                              resolution_code, recovered_spend_usd, version, machine_refreshed_at, updated_at
                       FROM ops.cases ORDER BY case_id""")
    md.append(table(c, r))
    md.append("\n## History (ops.case_events) by type and actor type\n")
    c, r = lb.query("""SELECT event_type, actor_type, count(*) AS events, min(created_at) AS first_at, max(created_at) AS last_at
                       FROM ops.case_events GROUP BY 1, 2 ORDER BY 2, 1""")
    md.append(table(c, r))
    md.append("\n## Edits made by people through the App (actor redacted)\n")
    c, r = lb.query("""SELECT c.case_id, e.event_type, e.old_value, e.new_value, e.note, e.actor_type, e.created_at
                       FROM ops.case_events e JOIN ops.cases c USING (case_key)
                       WHERE e.actor_type = 'USER' ORDER BY e.created_at""")
    md.append(table(c, [[clean(v) for v in row] for row in r]))
    md.append("\n## Human edits survive the machine re-sync\n")
    sync = ctx.task("sync_cases")
    sync_at = ms_to_utc(sync.get("start_time"))
    c, r = lb.query("""WITH last_user AS (
                         SELECT DISTINCT ON (case_key) case_key, split_part(new_value, ' / ', 1) AS status_set_by_user, created_at
                         FROM ops.case_events WHERE actor_type = 'USER' AND event_type IN ('STATUS_CHANGE', 'RESOLVE')
                         ORDER BY case_key, created_at DESC, event_id DESC)
                       SELECT c.case_id, l.status_set_by_user, to_char(l.created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS edited_at_utc,
                              c.status AS status_now, c.status = l.status_set_by_user AS human_value_kept
                       FROM last_user l JOIN ops.cases c USING (case_key) ORDER BY 1""")
    r = [row + [sync_at, (str(row[2]) < sync_at) if row[2] else None] for row in r]
    md.append(f"`sync_cases` (the machine upsert) last ran in job run `{ctx.run()['run_id']}` at {sync_at}.\n\n")
    md.append(table(c + ["sync_cases_ran_at", "sync_ran_after_edit"], r))
    md.append("\n## Unity Catalog copy (gold_case_status, written by sync_cases_back) vs Lakebase\n")
    uc = {str(row[0]): row[1:] for row in ctx.sql(f"SELECT case_id, status, owner_team, version FROM {NS}.gold_case_status")[1]}
    lbr = {str(row[0]): row[1:] for row in lb.query("SELECT case_id, status, owner_team, version FROM ops.cases")[1]}
    comp = [[k, *(uc.get(k) or [None] * 3), *(lbr.get(k) or [None] * 3),
             [str(x) for x in (uc.get(k) or [])] == [str(x) for x in (lbr.get(k) or [])]] for k in sorted(set(uc) | set(lbr), key=int)]
    md.append(table(["case_id", "uc_status", "uc_owner_team", "uc_version", "lb_status", "lb_owner_team", "lb_version", "identical"], comp))
    md.append("\n## Edit test (inside a transaction that is rolled back)\n")
    md.append(code(EDIT_TEST, "sql"))
    before = lb.query("SELECT case_id, status, version FROM ops.cases WHERE status NOT IN ('RESOLVED','DISMISSED') ORDER BY case_id LIMIT 1")
    notes = lb.script(EDIT_TEST)
    after = lb.query(f"SELECT case_id, status, version FROM ops.cases WHERE case_id = {before[1][0][0]}") if before[1] else ([], [])
    md.append("Output (NOTICE lines, verbatim):\n\n" + code("\n".join(notes)))
    md.append("Test case before and after (unchanged, because of the ROLLBACK):\n\n" + table(before[0], before[1] + after[1]))
    md.append("\n## Read latency of the App's case-list query\n")
    ms, how = lb.timings("""SELECT case_id, root_cause, severity, exposure_usd, status, owner_team FROM ops.cases
                            WHERE status NOT IN ('RESOLVED','DISMISSED') ORDER BY (severity = 'HIGH') DESC, exposure_usd DESC NULLS LAST""", 30)
    if ms:
        ms_sorted = sorted(ms)
        md.append(kv({"executions": len(ms), "method": how, "p50 ms": round(statistics.median(ms), 1),
                      "p95 ms": round(ms_sorted[max(0, int(len(ms) * 0.95) - 1)], 1), "max ms": round(max(ms), 1)}))
    return "\n".join(md)


# =============================================================================================== 08
def genie_ask(ctx, question, timeout=300):
    base = f"/api/2.0/genie/spaces/{ctx.genie_space}"
    t0 = time.time()
    s = ctx.ws.api("POST", f"{base}/start-conversation", {"content": question})
    conv = s.get("conversation_id") or s.get("conversation", {}).get("id")
    msg = s.get("message_id") or s.get("message", {}).get("id")
    m = {}
    while time.time() - t0 < timeout:
        m = ctx.ws.api("GET", f"{base}/conversations/{conv}/messages/{msg}")
        if m.get("status") in ("COMPLETED", "FAILED", "CANCELLED"):
            break
        time.sleep(4)
    out = {"status": m.get("status"), "seconds": round(time.time() - t0), "text": None, "sql": None, "columns": [], "rows": []}
    for a in m.get("attachments") or []:
        if a.get("text"):
            out["text"] = a["text"].get("content")
        if a.get("query"):
            out["sql"] = a["query"].get("query")
            qr = ctx.ws.api("GET", f"{base}/conversations/{conv}/messages/{msg}/attachments/{a['attachment_id']}/query-result")
            sr = qr.get("statement_response", {})
            out["columns"] = [c["name"] for c in sr.get("manifest", {}).get("schema", {}).get("columns", [])]
            out["rows"] = sr.get("result", {}).get("data_array") or []
    return out


def _num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _same(e, g):
    if e is None:
        return True
    ne, ng = _num(e), _num(g)
    if ne is not None and ng is not None:
        return abs(ne - ng) <= max(0.011, 0.005 * abs(ne))
    return str(e).strip().lower() == str(g).strip().lower()


def _row_found(erow, grows):
    return any(all(any(_same(ev, gv) for gv in grow) for ev in erow) for grow in grows)


def gen_08(ctx):
    from benchmarks import BENCHMARKS
    sp = ctx.ws.api("GET", f"/api/2.0/genie/spaces/{ctx.genie_space}", query={"include_serialized_space": "true"})
    ser = json.loads(sp.get("serialized_space") or "{}")
    md = [header("Evidence 08: Genie benchmark comparison",
                 "Proves that the Genie space answers the sponsor's questions correctly: each benchmark question was "
                 "asked through the Genie Conversation API during this generation run, and Genie's result rows were "
                 "compared with a ground-truth SQL query run on the same warehouse at the same time. Match rule: every "
                 "expected row is found in Genie's result (numbers equal within max(0.011, 0.5%), strings "
                 "case-insensitive); 'exact' also requires the same number of rows.")]
    md.append("## Space\n")
    md.append(kv({"space_id": ctx.genie_space, "title": sp.get("title"), "warehouse_id": sp.get("warehouse_id"),
                  "tables": ", ".join(t["identifier"].split(".")[-1] for t in ser.get("data_sources", {}).get("tables", [])),
                  "text instructions": sum(len(t.get("content", [])) for t in ser.get("instructions", {}).get("text_instructions", [])),
                  "example SQL": len(ser.get("instructions", {}).get("example_question_sqls", [])),
                  "join specs": len(ser.get("instructions", {}).get("join_specs", [])),
                  "benchmarks stored in the space": len(ser.get("benchmarks", {}).get("questions", []))}))
    results = []
    for qid, question, gt_sql in BENCHMARKS:
        cols, exp = ctx.sql(gt_sql)
        g = genie_ask(ctx, question)
        found = [_row_found(r, g["rows"]) for r in exp]
        match = bool(exp) and all(found)
        results.append(dict(qid=qid, q=question, gt_sql=gt_sql, cols=cols, exp=exp, g=g, found=f"{sum(found)}/{len(found)}",
                            match=match, exact=match and len(g["rows"]) == len(exp)))
    n = len(results)
    md.append(f"\n## Result: {sum(r['match'] for r in results)}/{n} matched, {sum(r['exact'] for r in results)}/{n} exact\n")
    md.append(table(["id", "question", "Genie status", "seconds", "expected rows found", "match", "exact"],
                    [[r["qid"], r["q"], r["g"]["status"], r["g"]["seconds"], r["found"], r["match"], r["exact"]] for r in results]))
    for r in results:
        md.append(f"\n### {r['qid']}: {r['q']}\n")
        md.append("Ground truth SQL:\n\n" + code(r["gt_sql"].strip(), "sql"))
        md.append("Expected rows:\n\n" + table(r["cols"], r["exp"], 15))
        md.append("\nGenie SQL:\n\n" + code((r["g"]["sql"] or "(none)").strip(), "sql"))
        md.append("Genie rows:\n\n" + table(r["g"]["columns"] or ["(none)"], r["g"]["rows"], 15))
        if r["g"]["text"]:
            md.append("\nGenie text:\n\n> " + clean(r["g"]["text"]).replace("\n", "\n> ") + "\n")
        md.append(f"\nExpected rows found: {r['found']} · match: **{r['match']}** · exact: {r['exact']}\n")
    return "\n".join(md)


# =============================================================================================== 09
def notebook_html_to_md(html_text):
    """Convert one exported notebook (HTML with an encoded notebook model) to Markdown text."""
    mt = re.search(r"__DATABRICKS_NOTEBOOK_MODEL = '([^']+)'", html_text)
    if not mt:
        return "_(no notebook model in export)_\n"
    model = json.loads(urllib.parse.unquote(base64.b64decode(mt.group(1)).decode("utf-8")))
    out = []
    for i, cmd in enumerate(sorted(model.get("commands", []), key=lambda c: c.get("position", 0)), 1):
        src = cmd.get("command", "")
        out.append(f"#### Cell {i}\n\n" + code(src[:4000], "python"))
        res = cmd.get("results") or {}
        data = res.get("data")
        if res.get("type") == "table" and isinstance(data, list):
            names = [s.get("name") for s in res.get("schema", [])]
            out.append(table(names, data, 30))
        elif isinstance(data, list):
            txt = "\n".join(d.get("data", "") if isinstance(d, dict) else str(d) for d in data)
            if txt.strip():
                out.append("Output:\n\n" + code(re.sub(r"<[^>]+>", "", htmllib.unescape(txt))[:8000]))
        elif isinstance(data, str) and data.strip():
            out.append("Output:\n\n" + code(re.sub(r"<[^>]+>", "", htmllib.unescape(data))[:8000]))
        if cmd.get("error"):
            out.append("Error:\n\n" + code(re.sub(r"<[^>]+>", "", htmllib.unescape(str(cmd["error"])))[:3000]))
    return "\n".join(out)


def gen_09(ctx):
    job = ctx.ws.api("GET", "/api/2.2/jobs/get", query={"job_id": ctx.job_main})
    s = job["settings"]
    run = ctx.run()
    md = [header("Evidence 09: Orchestrated job run",
                 f"Proves that the whole flow runs as one Lakeflow job (`{s.get('name')}`): the task graph, the run "
                 f"used for every other evidence file (run `{run['run_id']}`), each task's state and duration, and what "
                 "each task returned (notebook exit values, the pipeline update it started, the SQL it ran). It also "
                 "lists the job's recent runs.")]
    md.append("## Job definition (Jobs API)\n")
    trig = s.get("trigger") or {}
    md.append(kv({"job_id": ctx.job_main, "name": s.get("name"), "max_concurrent_runs": s.get("max_concurrent_runs"),
                  "queue": (s.get("queue") or {}).get("enabled"),
                  "trigger": (("file_arrival " + (trig.get("file_arrival") or {}).get("url", "")) if trig.get("file_arrival") else json.dumps(trig) or "none")
                  + (f" (pause_status {trig.get('pause_status')})" if trig else ""),
                  "tasks": len(s.get("tasks", [])), "deployed by": "Declarative Automation Bundle (`resources/job.yml`)"}))
    md.append("\nTask graph:\n\n" + table(["task", "type", "depends on", "what it runs"],
                                         [[t["task_key"], next((k for k in t if k.endswith("_task")), ""),
                                           ", ".join(d["task_key"] for d in t.get("depends_on", [])),
                                           (t.get("notebook_task") or {}).get("notebook_path", "").split("/files/")[-1]
                                           or ((t.get("sql_task") or {}).get("file") or {}).get("path", "").split("/files/")[-1]
                                           or ("pipeline " + (t.get("pipeline_task") or {}).get("pipeline_id", "")
                                               + (" (full_refresh)" if (t.get("pipeline_task") or {}).get("full_refresh") else ""))]
                                          for t in s.get("tasks", [])]))
    md.append(f"\n## Final run `{run['run_id']}`\n")
    md.append(kv({"run_id": run["run_id"], "trigger": run.get("trigger"), "result": run["state"].get("result_state"),
                  "started": ms_to_utc(run.get("start_time")), "ended": ms_to_utc(run.get("end_time")),
                  "duration s": round((run.get("run_duration") or (run.get("end_time", 0) - run.get("start_time", 0))) / 1000),
                  "run page": run.get("run_page_url")}))
    md.append("\n" + table(["task", "task run id", "result", "started", "seconds"],
                           [[t["task_key"], t["run_id"], t["state"].get("result_state"), ms_to_utc(t.get("start_time")),
                             round(((t.get("end_time") or 0) - (t.get("start_time") or 0)) / 1000)] for t in run["tasks"]]))
    md.append("\n## What each task returned\n")
    for t in run["tasks"]:
        o = t["_output"]
        md.append(f"\n### {t['task_key']}\n")
        if o.get("notebook_output"):
            res = o["notebook_output"].get("result")
            try:
                res = json.dumps(json.loads(res), indent=1)
            except (TypeError, ValueError):
                pass
            md.append("Notebook exit value (`dbutils.notebook.exit`):\n\n" + code(clean(res or "(empty)"), "json"))
        elif o.get("pipeline_output") or "pipeline_task" in t:
            po = o.get("pipeline_output") or {}
            po = po if isinstance(po, dict) else json.loads(po.replace("'", '"'))
            uid = po.get("pipeline_update_id")
            u = ctx.one(f"""SELECT max_by(details:update_progress.state::string, timestamp) AS state, min(timestamp) AS started, max(timestamp) AS ended
                            FROM event_log('{ctx.pipeline_id}') WHERE origin.update_id = '{uid}' AND event_type = 'update_progress'""") if uid else {}
            md.append(kv({"pipeline update id": uid, "update final state (event log)": u.get("state"),
                          "update started": u.get("started"), "update ended": u.get("ended")}))
        elif o.get("sql_output"):
            so = o["sql_output"]
            q = (so.get("file_output") or {}).get("query_text") or (so.get("query_output") or {}).get("query_text") or ""
            md.append(f"SQL file task; Jobs API returns the statement text it ran ({len(q.splitlines())} lines). First lines:\n\n"
                      + code("\n".join(q.splitlines()[:12]), "sql"))
        if o.get("logs"):
            md.append("Logs:\n\n" + code(clean(o["logs"])[-6000:]))
        if o.get("error"):
            md.append("Error field: " + clean(o["error"]) + "\n")
    md.append("\n## Recent runs of the job\n")
    runs = ctx.ws.api("GET", "/api/2.2/jobs/runs/list", query={"job_id": ctx.job_main, "limit": 20})
    md.append(table(["run_id", "trigger", "result", "started", "seconds"],
                    [[r["run_id"], r.get("trigger"), r["state"].get("result_state") or r["state"].get("life_cycle_state"),
                      ms_to_utc(r.get("start_time")), round((r.get("run_duration") or 0) / 1000)] for r in runs.get("runs", [])]))
    if ctx.args.full_cell_outputs:
        md.append("\n## Full cell outputs of the notebook tasks\n\nConverted from `jobs/runs/export` (views_to_export=ALL) to Markdown "
                  "in `evidence/09_cells/`; the raw HTML export is not kept.\n")
        os.makedirs(os.path.join(EVID, "09_cells"), exist_ok=True)
        for t in run["tasks"]:
            if "notebook_task" not in t:
                continue
            ex = ctx.ws.api("GET", "/api/2.2/jobs/runs/export", query={"run_id": t["run_id"], "views_to_export": "ALL"})
            body = "\n".join(notebook_html_to_md(v.get("content", "")) for v in ex.get("views", []) if v.get("type") == "NOTEBOOK")
            fn = f"09_cells/{t['task_key']}.md"
            write(fn, header(f"Cell outputs: task {t['task_key']} (run {t['run_id']})",
                             "Every cell of this notebook task with its output, from the Jobs export API, converted to text.") + "\n" + body)
            md.append(f"- [{t['task_key']}]({fn})\n")
    return "\n".join(md)


# =============================================================================================== 10
def http(url, token, data=None):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"},
                                 data=urllib.parse.urlencode(data).encode() if data else None)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            body = r.read().decode("utf-8", "replace")
            return r.status, body, time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), time.time() - t0


def visible_text(page):
    page = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", " ", page)
    page = re.sub(r"(?s)<[^>]+>", " ", page)
    return clean(re.sub(r"\s+", " ", htmllib.unescape(page)).strip())


def gen_10(ctx):
    app = ctx.ws.api("GET", f"/api/2.0/apps/{ctx.app_name}")
    base = app["url"].rstrip("/")
    tok = ctx.ws.token()
    md = [header("Evidence 10: Databricks App route checks",
                 "Proves that the Databricks App is deployed and serves every screen from live data: the app's state and "
                 "resources (Apps API), then each route called over HTTPS with the signed-in user's OAuth token, with "
                 "status, size, time and the visible text of the page (identities redacted), and checks that the numbers "
                 "on the overview equal the gold tables and the case list equals Lakebase.")]
    md.append("## App (Apps API)\n")
    ad = app.get("active_deployment") or {}
    md.append(kv({"name": app.get("name"), "url": base, "app status": (app.get("app_status") or {}).get("state"),
                  "compute status": (app.get("compute_status") or {}).get("state"),
                  "active deployment": ad.get("deployment_id"), "deployed at": ad.get("create_time"),
                  "user API scopes": ", ".join(app.get("user_api_scopes") or []),
                  "resources": "; ".join(f"{r.get('name')} ({next((k for k in r if k not in ('name', 'description')), '')})"
                                         for r in app.get("resources") or [])}))
    first_case = ctx.sql(f"SELECT min(case_id) FROM {NS}.gold_case_status")[1][0][0]
    routes = [("GET", "/health", None), ("GET", "/", None), ("GET", "/cases", None), ("GET", "/cases?show=all", None),
              (f"GET", f"/cases/{first_case}", None), ("GET", "/ask", None),
              ("POST", "/ask", {"question": "What is the approval gap for migrated cards vs the matched baseline over the last 30 days?"})]
    rows, pages = [], {}
    for method, path, data in routes:
        st, body, sec = http(base + path, tok, data)
        rows.append([method, path, st, len(body), round(sec, 2)])
        pages[(method, path)] = visible_text(body)
    md.append("\n## Routes\n")
    md.append(table(["method", "route", "HTTP status", "bytes", "seconds"], rows))
    k = ctx.one(f"""WITH g AS (SELECT * FROM {NS}.gold_baseline_gap WHERE business_date > (SELECT date_sub(max(business_date), 30) FROM {NS}.gold_baseline_gap))
                    SELECT max(business_date) AS latest_date,
                           format_number(100 * (sum(expected_approvals) - sum(migrated_approvals)) / sum(migrated_attempts), 2) AS gap_pp,
                           format_number(sum(lost_spend), 0) AS lost_spend FROM g""")
    rd = ctx.one(f"""SELECT format_number(sum(at_risk_spend_usd_per_day), 0) AS at_risk, count_if(gate = 'HOLD') AS hold
                     FROM {NS}.gold_wave_readiness WHERE wave_id = 7""")
    lb_open = ctx.lb().query("SELECT case_id FROM ops.cases WHERE status NOT IN ('RESOLVED','DISMISSED') ORDER BY case_id")[1]
    ov, cl = pages[("GET", "/")], pages[("GET", "/cases")]
    case_ids_on_page = sorted(set(int(x) for x in re.findall(r"#\s?(\d+)\b", cl)))
    checks = [
        ["overview shows the latest data date from gold", k["latest_date"], k["latest_date"] in ov],
        ["overview shows the 30-day gap from gold (pp)", k["gap_pp"], k["gap_pp"] in ov],
        ["overview shows the 30-day lost spend from gold", "$" + k["lost_spend"], ("$" + k["lost_spend"]) in ov],
        ["overview shows the wave 7 at-risk spend per day", "$" + rd["at_risk"], ("$" + rd["at_risk"]) in ov],
        ["overview shows the wave 7 gate", "HOLD" if int(rd["hold"]) else "GO", ("HOLD" if int(rd["hold"]) else "GO") in ov],
        ["case list shows the open cases in Lakebase", ",".join(str(r[0]) for r in lb_open),
         (case_ids_on_page == sorted(int(r[0]) for r in lb_open)) if case_ids_on_page else
         all(re.search(rf"\b{r[0]}\b", cl) for r in lb_open)],
        ["Ask (POST) returned a Genie answer containing the gap", k["gap_pp"], k["gap_pp"] in pages[("POST", "/ask")]],
    ]
    md.append("\n## Checks: the App shows the same numbers as gold and Lakebase\n")
    md.append(table(["check", "expected value (queried now)", "found on the page"], checks))
    md.append("\n## Visible text of each page (HTML tags removed, identities redacted)\n")
    for (method, path), txt in pages.items():
        md.append(f"\n### {method} {path}\n\n" + code(txt[:3000] + (" …" if len(txt) > 3000 else "")))
    try:
        logs = ctx.ws.api("GET", f"/api/2.0/apps/{ctx.app_name}/deployments/{ad.get('deployment_id')}") if ad else {}
        md.append("\n## Active deployment (Apps API)\n\n" + kv({"status": (logs.get("status") or {}).get("state"),
                                                              "message": (logs.get("status") or {}).get("message"),
                                                              "source": "src/app (bundle)", "mode": logs.get("mode")}))
    except ApiError:
        pass
    return "\n".join(md)


# =============================================================================================== README + guard
FILES = {
    "00_answer_key.md": (gen_00, "Answer key of every planted data issue and incident (written by the generator; the pipeline never reads it)."),
    "01_pipeline_run.md": (gen_01, "Lakeflow pipeline updates in the final run, rows per flow, expectation metrics, rows per table, duplicate check."),
    "02_data_quality.md": (gen_02, "Planted vs observed data-quality issues, quarantine reasons, file reconciliation, completeness."),
    "03_business_results.md": (gen_03, "Gold answers: approval gap vs matched baseline, lost spend, cases, wave readiness gate."),
    "04_ai_output.md": (gen_04, "Frozen detector config; AI explanations verbatim with the facts given; the full prompt."),
    "05_ai_evaluation.md": (gen_05, "Detection precision/recall vs baseline on held-out days; judge pass rates per prompt version."),
    "06_governance.md": (gen_06, "Row filters, masks, tags, grants; the same query per persona; non-admin service principal; lineage."),
    "07_lakebase.md": (gen_07, "Lakebase endpoint, constraints, counts, history, human edits surviving re-sync, rolled-back edit test, latency."),
    "08_genie.md": (gen_08, "Genie benchmark questions asked live and compared with ground-truth SQL."),
    "09_job_run.md": (gen_09, "Job definition, final run, each task's state and exit value, recent runs."),
    "10_app.md": (gen_10, "App state, every route called live, page text, checks that the App equals gold and Lakebase."),
}


def consistency(ctx):
    """Nothing landed or refreshed after the final run ended."""
    run = ctx.run()
    end = ms_to_utc(run.get("end_time"))
    r = ctx.one(f"""SELECT (SELECT count(DISTINCT origin.update_id) FROM event_log('{ctx.pipeline_id}')
                            WHERE event_type = 'create_update' AND timestamp > '{end}') AS pipeline_updates_after_run,
                           (SELECT count(*) FROM {NS}.bronze_issuer_auth WHERE _ingested_at > '{end}') AS rows_ingested_after_run,
                           (SELECT max(business_date) FROM {NS}.gold_auth_daily) AS latest_gold_business_date""")
    return end, r


def write(name, text):
    path = os.path.join(EVID, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = clean(text)
    with open(path, "w") as fh:
        fh.write(text if text.endswith("\n") else text + "\n")
    return path


def gen_readme(ctx, written):
    run = ctx.run()
    end, cons = consistency(ctx)
    md = [header("Evidence index",
                 "Each file below was generated from the live workspace by `tools/generate_evidence.py` and is plain "
                 "text, so it can be read without opening the workspace. All files describe the same final state: the "
                 "orchestrated job run below, after which no data was landed and the pipeline was not refreshed.")]
    md.append("## Final state these files describe\n")
    md.append(kv({"final job run": f"{run['run_id']} ({run['state'].get('result_state')}, ended {end})",
                  "pipeline updates started after that run": cons.get("pipeline_updates_after_run"),
                  "auth rows ingested after that run": cons.get("rows_ingested_after_run"),
                  "latest business date in gold": cons.get("latest_gold_business_date"),
                  "API access used": ctx.ws.mode}))
    md.append("\n## Files\n")
    rows = []
    for fn, (_, what) in FILES.items():
        p = os.path.join(EVID, fn)
        if os.path.exists(p):
            first = open(p).read().splitlines()[2:3]
            rows.append([f"[{fn}]({fn})", what, first[0].replace("Generated ", "").split(" by ")[0] if first and SCRIPT in first[0] else "kept (written earlier, not regenerated)"])
    if os.path.exists(os.path.join(EVID, "HEADLINES.md")):
        rows.append(["[HEADLINES.md](HEADLINES.md)", "The headline figures used by the README and the deck, with wording, base, date, status and source.", ""])
    md.append(table(["file", "what it proves", "generated (UTC)"], rows))
    hist = os.path.join(EVID, "build_history")
    if os.path.isdir(hist):
        md.append("\n## Build history\n\n`build_history/` keeps the dated evidence captured while each step was built (with the "
                  "failures and fixes described in BUILD_LOG.md). Those files describe earlier states; the files above "
                  "describe the final state.\n")
    return "\n".join(md)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="febar")
    ap.add_argument("--sp-profile", default="febar-sp")
    ap.add_argument("--job-run-id", type=int)
    ap.add_argument("--only", help="one file, e.g. 03_business_results.md or 03")
    ap.add_argument("--full-cell-outputs", action="store_true")
    ap.add_argument("--skip-genie", action="store_true")
    args = ap.parse_args()
    ctx = Ctx(args)
    targets = list(FILES)
    if args.only:
        targets = [f for f in FILES if f == args.only or f.startswith(args.only.rstrip(".md") + "_") or f.split("_")[0] == args.only]
        if not targets:
            raise SystemExit(f"--only={args.only}: no such file. Choose from: {', '.join(FILES)}")
    if args.skip_genie and "08_genie.md" in targets:
        targets.remove("08_genie.md")
    print(f"API access: {ctx.ws.mode}; final job run: {ctx.run()['run_id']}", flush=True)
    written = []
    for fn in targets:
        t0 = time.time()
        text = FILES[fn][0](ctx)
        if text is None:
            print(f"{fn}: exists, kept", flush=True)
            continue
        write(fn, text)
        written.append(fn)
        print(f"{fn}: written ({len(text):,} chars, {time.time() - t0:.0f}s)", flush=True)
    write("README.md", gen_readme(ctx, written))
    print("README.md: written", flush=True)


if __name__ == "__main__":
    main()
