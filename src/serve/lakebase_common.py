"""Lakebase (Autoscaling Postgres) connection helper.

OAuth database credential from the Databricks SDK, generated per connection (tokens last about
an hour), used as the Postgres password with sslmode=require. No static password anywhere.
"""
import psycopg
from databricks.sdk import WorkspaceClient

PROJECT = "febar-ops"
BRANCH = f"projects/{PROJECT}/branches/production"
ENDPOINT = f"{BRANCH}/endpoints/primary"
DATABASE = "databricks_postgres"


def connect(autocommit=False):
    w = WorkspaceClient()
    host = w.postgres.get_endpoint(name=ENDPOINT).status.hosts.host
    token = w.postgres.generate_database_credential(endpoint=ENDPOINT).token
    user = w.current_user.me().user_name          # Postgres role = the Databricks identity running the job
    return psycopg.connect(host=host, dbname=DATABASE, user=user, password=token, sslmode="require",
                           autocommit=autocommit, connect_timeout=30)


DDL = """
CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS ops.cases (
  case_id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_key              TEXT NOT NULL UNIQUE,
  -- machine-owned (refreshed from gold by the sync task)
  root_cause            TEXT NOT NULL,
  issuer_segment        TEXT NOT NULL CHECK (issuer_segment IN ('OWN','THIRD_PARTY')),
  region_scope          TEXT NOT NULL,
  episode_start         DATE NOT NULL,
  episode_end           DATE NOT NULL,
  n_flags               INT  NOT NULL,
  max_score             NUMERIC(6,2) NOT NULL,
  severity              TEXT NOT NULL CHECK (severity IN ('HIGH','MEDIUM')),
  exposure_usd          NUMERIC(14,2),
  excess_declines       NUMERIC(12,1),
  merchants             INT,
  suggested_owner_team  TEXT,
  top_slices            TEXT[],
  llm_summary           TEXT,
  llm_next_step         TEXT,
  llm_certainty         TEXT,
  prompt_version        TEXT,
  detector_version      TEXT,
  machine_refreshed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- human-owned (App only; the sync never writes these after insert)
  status                TEXT NOT NULL DEFAULT 'OPEN'
                        CHECK (status IN ('OPEN','CLAIMED','IN_PROGRESS','WAITING_PARTNER','RESOLVED','DISMISSED')),
  assignee              TEXT,
  owner_team            TEXT,
  due_date              DATE,
  resolution_code       TEXT CHECK (resolution_code IN ('ACQUIRER_FIX','CONFIG_CHANGE','CREDENTIAL_REFRESH','PROCESSOR_FIX','FALSE_POSITIVE','OTHER')),
  recovered_spend_usd   NUMERIC(14,2) CHECK (recovered_spend_usd >= 0),
  resolved_at           TIMESTAMPTZ,
  updated_by            TEXT,
  updated_at            TIMESTAMPTZ,
  version               INT NOT NULL DEFAULT 1,
  CHECK ((status IN ('RESOLVED','DISMISSED')) = (resolution_code IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS ops.case_anomalies (
  case_key       TEXT NOT NULL REFERENCES ops.cases(case_key),
  anomaly_key    TEXT NOT NULL,
  business_date  DATE NOT NULL,
  family         TEXT NOT NULL,
  slice_value    TEXT NOT NULL,
  score          NUMERIC(6,2) NOT NULL,
  PRIMARY KEY (case_key, anomaly_key)
);

CREATE TABLE IF NOT EXISTS ops.case_events (
  event_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_key    TEXT NOT NULL REFERENCES ops.cases(case_key),
  event_type  TEXT NOT NULL CHECK (event_type IN ('CREATED','MACHINE_UPDATE','STATUS_CHANGE','ASSIGN','OWNER_CHANGE','NOTE','RESOLVE','DUE_DATE')),
  old_value   TEXT,
  new_value   TEXT,
  note        TEXT,
  actor       TEXT NOT NULL,
  actor_type  TEXT NOT NULL CHECK (actor_type IN ('SYSTEM','USER')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS case_events_case_idx ON ops.case_events (case_key, created_at);
CREATE INDEX IF NOT EXISTS cases_status_idx ON ops.cases (status, severity);
"""
