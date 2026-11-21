-- =============================================================================
-- GOLD (pipeline-owned): the two business tables the detection step reads.
-- gold_anomalies, gold_case_status and gold_wave_readiness are written by job tasks
-- T2-T5 (BUILD_PLAN.md section 5), not by this pipeline.
-- =============================================================================

-- Grain decision 2026-11-21 (DECISIONS.md): at prototype scale an hourly x 9-dimension grain is
-- almost row-level (7.9M rows), too sparse to score. Detection scores the DAILY table; the small
-- HOURLY table (network x region x channel) keeps intraday timing, e.g. a processor outage.

CREATE OR REFRESH MATERIALIZED VIEW gold_auth_daily
CLUSTER BY (business_date, network)
COMMENT 'Authorization outcomes per business day x wave cohort x network x acquirer x channel x MCC group x region x cross-border x tokenized x issuer segment. Attempts, approvals, declines by standard category, amounts. The table the detection step scores. Row filter: caller sees only the issuer segment and regions their persona allows.'
WITH ROW FILTER classic_stable_zjnu75_catalog.network_migration.f_row_filter ON (issuer_segment, region)
AS SELECT
  business_date, wave_cohort, network, acquirer_id, acquirer_name, channel, mcc_group, region,
  cross_border, tokenized, issuer_segment,
  count(*) AS attempts,
  count_if(approved) AS approvals,
  count_if(NOT approved) AS declines,
  count_if(decline_type = 'ACCEPTANCE') AS acceptance_declines,
  count_if(decline_type = 'ISSUER_LEGIT') AS issuer_legit_declines,
  count_if(decline_type = 'UNMAPPED') AS unmapped_declines,
  count_if(std_category = 'ACCEPTANCE_CONFIG') AS decl_acceptance_config,
  count_if(std_category = 'TOKEN_PROVISIONING') AS decl_token_provisioning,
  count_if(std_category = 'CROSS_BORDER_BLOCK') AS decl_cross_border_block,
  count_if(std_category = 'CARD_ON_FILE_STALE') AS decl_card_on_file_stale,
  count_if(std_category = 'PROCESSOR_TIMEOUT') AS decl_processor_timeout,
  count_if(std_category = 'SYSTEM_ERROR') AS decl_system_error,
  count_if(std_category = 'ISSUER_LEGIT_NSF') AS decl_insufficient_funds,
  count_if(stip_flag) AS stip_approvals,
  CAST(sum(amount) AS DECIMAL(16,2)) AS amount,
  CAST(sum(CASE WHEN NOT approved THEN amount END) AS DECIMAL(16,2)) AS declined_amount,
  max(available_ts) AS max_available_ts
FROM silver_auth
GROUP BY ALL;

CREATE OR REFRESH MATERIALIZED VIEW gold_auth_hourly
CLUSTER BY (auth_hour)
COMMENT 'Hourly authorization outcomes per network x region x channel x issuer segment (intraday timing, e.g. processor timeouts). Row filter by persona.'
WITH ROW FILTER classic_stable_zjnu75_catalog.network_migration.f_row_filter ON (issuer_segment, region)
AS SELECT
  auth_hour, business_date, network, region, channel, issuer_segment,
  count(*) AS attempts,
  count_if(approved) AS approvals,
  count_if(NOT approved) AS declines,
  count_if(decline_type = 'ACCEPTANCE') AS acceptance_declines,
  count_if(decline_type = 'ISSUER_LEGIT') AS issuer_legit_declines,
  count_if(decline_type = 'UNMAPPED') AS unmapped_declines,
  count_if(std_category = 'ACCEPTANCE_CONFIG') AS decl_acceptance_config,
  count_if(std_category = 'TOKEN_PROVISIONING') AS decl_token_provisioning,
  count_if(std_category = 'CROSS_BORDER_BLOCK') AS decl_cross_border_block,
  count_if(std_category = 'CARD_ON_FILE_STALE') AS decl_card_on_file_stale,
  count_if(std_category = 'PROCESSOR_TIMEOUT') AS decl_processor_timeout,
  count_if(std_category = 'SYSTEM_ERROR') AS decl_system_error,
  count_if(std_category = 'ISSUER_LEGIT_NSF') AS decl_insufficient_funds,
  count_if(stip_flag) AS stip_approvals,
  CAST(sum(amount) AS DECIMAL(16,2)) AS amount,
  CAST(sum(CASE WHEN NOT approved THEN amount END) AS DECIMAL(16,2)) AS declined_amount,
  max(available_ts) AS max_available_ts
FROM silver_auth
GROUP BY ALL;

-- Migrated cohorts vs a MATCHED baseline: same day, same card segment, channel, MCC group and
-- cross-border flag, on Atlas. Thin segments (< 50 baseline attempts) fall back to
-- card segment x channel. The unmatched (all-Atlas) rate is kept for comparison.
CREATE OR REFRESH MATERIALIZED VIEW gold_baseline_gap
CLUSTER BY (business_date, wave_cohort)
COMMENT 'Per day x migrated wave cohort x match segment x issuer segment x region: approval rate vs matched Atlas baseline (matched on day, card segment, channel, MCC group, cross-border), gap (pp), excess declines and lost spend (excess declines x avg ticket x unrecovered rate). Row filter by persona.'
WITH ROW FILTER classic_stable_zjnu75_catalog.network_migration.f_row_filter ON (issuer_segment, region)
AS
WITH seg AS (
  SELECT business_date, wave_cohort, card_segment, channel, mcc_group, cross_border, issuer_segment, region,
         count(*) AS attempts, count_if(approved) AS approvals,
         count_if(decline_type = 'ACCEPTANCE') AS acceptance_declines,
         avg(amount) AS avg_ticket
  FROM silver_auth
  WHERE card_segment IS NOT NULL
  GROUP BY ALL
),
b_fine AS (
  SELECT business_date, card_segment, channel, mcc_group, cross_border,
         sum(attempts) AS b_attempts, sum(approvals) / sum(attempts) AS b_rate
  FROM seg WHERE wave_cohort = 'BASELINE' GROUP BY ALL
),
b_coarse AS (
  SELECT business_date, card_segment, channel, sum(attempts) AS b_attempts, sum(approvals) / sum(attempts) AS b_rate
  FROM seg WHERE wave_cohort = 'BASELINE' GROUP BY ALL
),
b_all AS (
  SELECT business_date, sum(approvals) / sum(attempts) AS unmatched_rate
  FROM seg WHERE wave_cohort = 'BASELINE' GROUP BY ALL
),
j AS (
  SELECT
    m.business_date, m.wave_cohort,
    concat_ws('|', m.card_segment, m.channel, m.mcc_group, IF(m.cross_border, 'XB', 'DOM')) AS match_segment,
    m.card_segment, m.channel, m.mcc_group, m.cross_border, m.issuer_segment, m.region,
    m.attempts AS migrated_attempts, m.approvals AS migrated_approvals, m.acceptance_declines,
    m.approvals / m.attempts AS migrated_approval_rate,
    CASE WHEN f.b_attempts >= 50 THEN f.b_rate ELSE c.b_rate END AS matched_baseline_rate,
    CASE WHEN f.b_attempts >= 50 THEN 'FINE' ELSE 'COARSE' END AS baseline_level,
    coalesce(CASE WHEN f.b_attempts >= 50 THEN f.b_attempts ELSE c.b_attempts END, 0) AS baseline_attempts,
    a.unmatched_rate AS unmatched_baseline_rate,
    m.avg_ticket,
    coalesce(r.unrecovered_rate, d.unrecovered_rate) AS unrecovered_rate
  FROM seg m
  LEFT JOIN b_fine f USING (business_date, card_segment, channel, mcc_group, cross_border)
  LEFT JOIN b_coarse c USING (business_date, card_segment, channel)
  LEFT JOIN b_all a USING (business_date)
  LEFT JOIN ref_recovery_assumptions r ON r.segment = m.card_segment
  LEFT JOIN ref_recovery_assumptions d ON d.segment = 'DEFAULT'
  WHERE m.wave_cohort <> 'BASELINE'
)
SELECT
  *,
  migrated_attempts * matched_baseline_rate AS expected_approvals,
  migrated_attempts * matched_baseline_rate - migrated_approvals AS excess_declines,
  (matched_baseline_rate - migrated_approval_rate) * 100 AS gap_pp,
  (unmatched_baseline_rate - migrated_approval_rate) * 100 AS unmatched_gap_pp,
  CAST((migrated_attempts * matched_baseline_rate - migrated_approvals) * avg_ticket * unrecovered_rate AS DECIMAL(16,2)) AS lost_spend
FROM j;

-- Transaction-level detail for the App's case workbench and investigations: last 60 business days.
-- card_ref is masked unless the caller's persona can see sensitive fields.
CREATE OR REFRESH MATERIALIZED VIEW auth_detail (
  auth_id STRING COMMENT 'Authorization attempt ID (issuer system)',
  business_date DATE COMMENT 'Business date of the attempt (merchant local)',
  auth_ts_local TIMESTAMP COMMENT 'Attempt time, merchant local time',
  network STRING COMMENT 'MRD = acquired network (migrated card), ATL = legacy network',
  wave_cohort STRING COMMENT 'W1..W6 = migration wave of the card (migrated); BASELINE = not yet migrated',
  card_ref STRING MASK classic_stable_zjnu75_catalog.network_migration.f_mask_card COMMENT 'Cardholder card reference. SENSITIVE: shown only to personas cleared for sensitive fields; otherwise RESTRICTED',
  card_segment STRING COMMENT 'Card spending segment (DOMESTIC, ECOM_HEAVY, RECURRING_HEAVY, WALLET_HEAVY, INTL_TRAVELER)',
  issuer_segment STRING COMMENT 'OWN = the bank''s cards; THIRD_PARTY = other issuers'' cards processed on the network (commercially sensitive)',
  merchant_num STRING COMMENT 'Merchant number (issuer view)',
  dba_name STRING COMMENT 'Merchant trading name',
  acquirer_id STRING COMMENT 'Acquirer (merchant bank / processor)',
  acquirer_name STRING COMMENT 'Acquirer name',
  channel STRING COMMENT 'CP card present, ECOM e-commerce, REC recurring / card-on-file, MANUAL key-entered',
  mcc INT COMMENT 'Merchant category code as sent in the authorization',
  mcc_group STRING COMMENT 'Merchant category group (e.g. TRAVEL_LODGING)',
  region STRING COMMENT 'Merchant region: NE, SE, MW, SW, W or INTL',
  cross_border BOOLEAN COMMENT 'Merchant outside the US',
  tokenized BOOLEAN COMMENT 'Wallet or card-on-file token used',
  is_recurring BOOLEAN COMMENT 'Recurring / stored-credential charge',
  amount DECIMAL(12,2) COMMENT 'Attempted amount, USD',
  approved BOOLEAN COMMENT 'Authorization approved (including network stand-in approvals)',
  std_category STRING COMMENT 'Standard decline category (APPROVED, ISSUER_LEGIT_*, ACCEPTANCE_CONFIG, TOKEN_PROVISIONING, CROSS_BORDER_BLOCK, CARD_ON_FILE_STALE, PROCESSOR_TIMEOUT, SYSTEM_ERROR, UNMAPPED)',
  decline_type STRING COMMENT 'APPROVED, ACCEPTANCE (network-side, fixable), ISSUER_LEGIT (legitimate issuer decline) or UNMAPPED',
  iss_resp_cd STRING COMMENT 'Issuer response code (ISO style)',
  network_code STRING COMMENT 'Native network response code',
  stip_flag BOOLEAN COMMENT 'Approved by network stand-in because the issuer was unreachable'
)
CLUSTER BY (business_date, acquirer_id)
COMMENT 'Transaction-level authorization detail for the last 60 business days, for investigations and the App case workbench. Row filter by persona; card_ref masked.'
WITH ROW FILTER classic_stable_zjnu75_catalog.network_migration.f_row_filter ON (issuer_segment, region)
AS SELECT
  auth_id, business_date, auth_ts_local, network, wave_cohort, card_ref, card_segment, issuer_segment,
  merchant_num, dba_name, acquirer_id, acquirer_name, channel, mcc, mcc_group, region, cross_border,
  tokenized, is_recurring, amount, approved, std_category, decline_type, iss_resp_cd, network_code, stip_flag
FROM silver_auth
WHERE business_date >= date_sub((SELECT max(business_date) FROM silver_auth), 59);
