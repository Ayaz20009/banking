-- =============================================================================
-- Unity Catalog governance for classic_stable_zjnu75_catalog.network_migration
-- Run by job task `setup_governance` (SQL file task on the serverless warehouse).
-- Idempotent: CREATE ... IF NOT EXISTS, MERGE, CREATE OR REPLACE FUNCTION, SET TAGS.
--
-- Model (approved 2026-11-21, DECISIONS.md):
--   personas      = what a persona may see (issuer scope, region scope, sensitive fields)
--   entitlements  = who holds which persona (user, service principal or account group)
--   Access changes are ROW CHANGES in `entitlements`; no identity is hard-coded in a function.
-- Policy functions run with the table owner's authority, so readers need no access to
-- these two tables. Policies are attached only to the tables people, Genie and the App
-- query (gold_*, auth_detail), never to tables the pipeline reads.
-- Function bodies must use literal object names (no parameters or IDENTIFIER()).
-- =============================================================================

USE CATALOG classic_stable_zjnu75_catalog;
USE SCHEMA network_migration;

-- ---------- 1. Entitlements as data ------------------------------------------
CREATE TABLE IF NOT EXISTS personas (
  persona            STRING  NOT NULL COMMENT 'Persona key',
  title              STRING  COMMENT 'Business role',
  issuer_scope       STRING  NOT NULL COMMENT 'OWN, THIRD_PARTY or ALL: which issuer segment rows are visible',
  region_scope       STRING  NOT NULL COMMENT 'NE, SE, MW, SW, W, INTL or ALL: which merchant regions are visible',
  can_see_sensitive  BOOLEAN NOT NULL COMMENT 'TRUE = card_ref shown in clear; FALSE = RESTRICTED',
  purpose            STRING  COMMENT 'Why this persona has this access'
) COMMENT 'Access personas for the network-migration data products. Read by the row-filter and mask functions.';

MERGE INTO personas t
USING (SELECT * FROM VALUES
  ('ADMIN',        'Platform owner (pipelines, jobs)',          'ALL',         'ALL', true,  'Owns and runs the pipeline and jobs; needs every row to compute results'),
  ('P1_DIRECTOR',  'Director of Payment Network Operations',    'OWN',         'ALL', false, 'Network-wide view of the bank\'s own portfolio; no cardholder identifiers'),
  ('P2_REGIONAL',  'Regional ops analyst (Southeast)',          'OWN',         'SE',  false, 'Investigates incidents in one region'),
  ('P3_CARD_INV',  'Card investigations specialist (cleared)',  'OWN',         'ALL', true,  'Needs card identifiers to fix card-on-file and token issues'),
  ('P4_PARTNER',   'Network partner operations',                'THIRD_PARTY', 'ALL', false, 'Serves third-party issuers on the network; never sees the bank\'s own portfolio')
  AS v(persona, title, issuer_scope, region_scope, can_see_sensitive, purpose)) s
ON t.persona = s.persona
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;

CREATE TABLE IF NOT EXISTS entitlements (
  principal       STRING    NOT NULL COMMENT 'User email, service principal application ID, or account group name',
  principal_type  STRING    NOT NULL COMMENT 'USER, SERVICE_PRINCIPAL or GROUP',
  persona         STRING    NOT NULL COMMENT 'FK to personas.persona',
  granted_at      TIMESTAMP COMMENT 'When this entitlement was added or changed',
  note            STRING    COMMENT 'Reason or ticket'
) COMMENT 'Who holds which persona. Changing access = changing a row here.';

-- The identity that runs this job (the pipeline/job owner) is the ADMIN persona.
-- current_user() is resolved at run time, so no identity is written into code.
MERGE INTO entitlements t
USING (SELECT current_user() AS principal, 'USER' AS principal_type, 'ADMIN' AS persona) s
ON t.principal = s.principal
WHEN NOT MATCHED THEN INSERT (principal, principal_type, persona, granted_at, note)
  VALUES (s.principal, s.principal_type, s.persona, current_timestamp(), 'Pipeline and job owner');

-- ---------- 2. Policy functions ------------------------------------------------
CREATE OR REPLACE FUNCTION f_row_filter(p_issuer_segment STRING, p_region STRING)
RETURNS BOOLEAN
COMMENT 'Row filter: TRUE when the caller (user, or a member of an entitled account group) holds a persona whose issuer and region scope cover this row. No entitlement = no rows.'
RETURN EXISTS (
  SELECT 1
  FROM classic_stable_zjnu75_catalog.network_migration.entitlements e
  JOIN classic_stable_zjnu75_catalog.network_migration.personas p ON p.persona = e.persona
  WHERE (e.principal = current_user() OR (e.principal_type = 'GROUP' AND is_account_group_member(e.principal)))
    AND (p.issuer_scope = 'ALL' OR p.issuer_scope = p_issuer_segment)
    AND (p.region_scope = 'ALL' OR p.region_scope = p_region)
);

CREATE OR REPLACE FUNCTION f_mask_card(card_ref STRING)
RETURNS STRING
COMMENT 'Column mask for card_ref: clear value only for personas with can_see_sensitive = TRUE; otherwise RESTRICTED.'
RETURN CASE
  WHEN EXISTS (
    SELECT 1
    FROM classic_stable_zjnu75_catalog.network_migration.entitlements e
    JOIN classic_stable_zjnu75_catalog.network_migration.personas p ON p.persona = e.persona
    WHERE (e.principal = current_user() OR (e.principal_type = 'GROUP' AND is_account_group_member(e.principal)))
      AND p.can_see_sensitive
  ) THEN card_ref
  ELSE 'RESTRICTED'
END;

-- ---------- 3. Comments and tags ----------------------------------------------
-- Tag keys are namespaced (nm_*): this shared metastore enforces governed tag policies on generic
-- keys such as data_domain / data_class with other teams' allowed values.
ALTER SCHEMA network_migration SET TAGS ('nm_domain' = 'payment_network_migration', 'nm_origin' = 'synthetic');
COMMENT ON SCHEMA network_migration IS 'Card migration to an acquired payment network: authorization acceptance, declines, incidents and wave readiness. Synthetic data only.';
ALTER TABLE personas SET TAGS ('nm_data_class' = 'access_control');
ALTER TABLE entitlements SET TAGS ('nm_data_class' = 'access_control');
