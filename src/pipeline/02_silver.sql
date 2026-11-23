-- =============================================================================
-- SILVER: cleaned and conformed.
-- Quality rules R1-R15 (decided 2026-11-20, DECISIONS.md):
--   DROP rows go to quarantine_auth with the failing rule name(s), never silently lost.
--   WARN rows are kept and counted in the event log. FAIL rules stop the update.
-- =============================================================================

-- ---------- Issuer authorizations ------------------------------------------
CREATE TEMPORARY VIEW v_issuer_parsed AS
SELECT
  nullif(trim(AUTH_ID), '') AS auth_id,
  try_to_timestamp(AUTH_TS_LOCAL, 'yyyy-MM-dd HH:mm:ss') AS auth_ts_local,
  AUTH_TS_LOCAL AS auth_ts_raw,
  trim(AUTH_TZ) AS auth_tz,
  trim(CARD_REF) AS card_ref,
  trim(CARD_ACCEPTOR_ID) AS merchant_num,
  trim(ACQ_INST_ID) AS acq_bin,
  try_cast(nullif(trim(MCC), '') AS INT) AS mcc,
  trim(POS_ENTRY_MODE) AS pos_entry_mode,
  TRAN_AMT AS amount_raw,
  CASE WHEN TRAN_AMT RLIKE '^[0-9]+[.][0-9]{2}$' THEN CAST(TRAN_AMT AS DECIMAL(12,2)) END AS amount,
  CASE WHEN trim(CURR_CD) = 'USD' THEN '840' ELSE trim(CURR_CD) END AS currency_cd,   -- standardise alpha -> numeric
  nullif(trim(TERM_CNTRY), '') AS term_country,
  trim(NETWORK_ID) AS network,
  trim(WALLET_IND) AS wallet_ind,
  trim(RECUR_IND) = 'Y' AS is_recurring,
  trim(AUTH_DECISION) AS auth_decision,
  trim(ISS_RESP_CD) AS iss_resp_cd,
  to_date(_business_date) AS business_date,
  _file_created_ts, _file_name, _source_file, _ingested_at
FROM STREAM(bronze_issuer_auth);

-- Staging with expectations (pipeline-private). Duplicates are still present here.
CREATE OR REFRESH PRIVATE STREAMING TABLE stg_issuer_auth (
  CONSTRAINT r1_auth_id_not_null   EXPECT (auth_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT r2_valid_amount       EXPECT (coalesce(amount > 0, false)) ON VIOLATION DROP ROW,
  CONSTRAINT r3_ts_not_future      EXPECT (coalesce(to_date(auth_ts_local) <= date_add(business_date, 1), false)) ON VIOLATION DROP ROW,
  CONSTRAINT r4_valid_decision_network EXPECT (auth_decision IN ('A', 'D') AND network IN ('MRD', 'ATL')) ON VIOLATION FAIL UPDATE,
  CONSTRAINT r5_currency_840       EXPECT (currency_cd = '840'),
  CONSTRAINT r6_mcc_present        EXPECT (mcc IS NOT NULL),
  CONSTRAINT r7_term_country_present EXPECT (term_country IS NOT NULL)
)
AS SELECT * EXCEPT (amount_raw, auth_ts_raw) FROM STREAM(v_issuer_parsed);

-- Deduplicate re-sent records on the business key: keep the latest landed copy.
CREATE OR REFRESH MATERIALIZED VIEW silver_issuer_auth
CLUSTER BY (business_date)
COMMENT 'Issuer authorization attempts, cleaned and deduplicated. One row per AUTH_ID (latest landed copy). first_available_ts = when the FIRST copy landed (used by the as-of timing rule).'
AS SELECT * EXCEPT (rn)
FROM (
  SELECT *,
    min(_file_created_ts) OVER (PARTITION BY auth_id) AS first_available_ts,
    row_number() OVER (PARTITION BY auth_id ORDER BY _file_created_ts DESC, _ingested_at DESC, _source_file DESC) AS rn
  FROM stg_issuer_auth
)
WHERE rn = 1;

-- ---------- Quarantine: every DROP-ROW failure, with reason -----------------
CREATE OR REFRESH STREAMING TABLE quarantine_auth (
  source_system STRING, record_key STRING, reasons ARRAY<STRING>, reason STRING,
  business_date DATE, record STRING, _file_name STRING, _source_file STRING, _ingested_at TIMESTAMP
)
COMMENT 'Rows removed by a DROP ROW rule (R1-R3 issuer, R8 networks), with the rule name(s) and the raw record as JSON.';

CREATE FLOW q_issuer_auth AS INSERT INTO quarantine_auth BY NAME
SELECT source_system, record_key, reasons, array_join(reasons, ', ') AS reason, business_date, record,
       _file_name, _source_file, _ingested_at
FROM (
  SELECT 'iss_auth' AS source_system, auth_id AS record_key,
    filter(array(
      CASE WHEN auth_id IS NULL THEN 'r1_auth_id_not_null' END,
      CASE WHEN NOT coalesce(amount > 0, false) THEN 'r2_valid_amount' END,
      CASE WHEN NOT coalesce(to_date(auth_ts_local) <= date_add(business_date, 1), false) THEN 'r3_ts_not_future' END
    ), x -> x IS NOT NULL) AS reasons,
    business_date,
    to_json(named_struct('auth_id', auth_id, 'auth_ts_raw', auth_ts_raw, 'amount_raw', amount_raw,
                         'card_ref', card_ref, 'merchant_num', merchant_num, 'network', network,
                         'auth_decision', auth_decision, 'iss_resp_cd', iss_resp_cd)) AS record,
    _file_name, _source_file, _ingested_at
  FROM STREAM(v_issuer_parsed)
)
WHERE size(reasons) > 0;

-- ---------- Network responses: two sources, one conformed table -------------
CREATE TEMPORARY VIEW v_mrd_parsed AS
SELECT
  nullif(trim(issuerAuthRef), '') AS auth_id,
  'MRD' AS network,
  netTxnId AS network_txn_id,
  try_to_timestamp(eventTimeUtc) AS event_ts_utc,
  CAST(NULL AS TIMESTAMP) AS event_ts_local,
  merchantNetworkId AS merchant_network_id,
  try_cast(regexp_replace(merchantNetworkId, '[^0-9]', '') AS BIGINT) AS merchant_id_norm,
  acquirerCode AS acquirer_ref,
  'ACQUIRER_ID' AS acquirer_ref_type,
  CAST(try_cast(amountMinor AS BIGINT) / 100.0 AS DECIMAL(12,2)) AS amount,   -- minor units -> dollars
  trim(responseCode) AS native_code,
  CAST(NULL AS STRING) AS reason_cd,
  lower(crossBorder) = 'true' AS cross_border,
  coalesce(lower(stipFlag) = 'true', false) AS stip_flag,
  processingPath AS processing_path,
  tokenRequestorId AS token_requestor_id,
  to_date(_business_date) AS business_date,
  _file_created_ts, _file_name, _source_file, _ingested_at
FROM STREAM(bronze_mrd_events);

CREATE TEMPORARY VIEW v_atl_parsed AS
SELECT
  nullif(trim(auth_reference), '') AS auth_id,
  'ATL' AS network,
  txn_ref AS network_txn_id,
  CAST(NULL AS TIMESTAMP) AS event_ts_utc,
  try_to_timestamp(concat(txn_date, ' ', txn_time), 'MM/dd/yyyy HHmmss') AS event_ts_local,
  mer_id AS merchant_network_id,
  try_cast(mer_id AS BIGINT) AS merchant_id_norm,                              -- strips zero padding
  acq_bin AS acquirer_ref,
  'BIN' AS acquirer_ref_type,
  try_cast(amt AS DECIMAL(12,2)) AS amount,
  trim(resp_cd) AS native_code,
  nullif(trim(rsn_cd), '') AS reason_cd,
  xb_flag = 'Y' AS cross_border,
  false AS stip_flag,
  CAST(NULL AS STRING) AS processing_path,
  CAST(NULL AS STRING) AS token_requestor_id,
  to_date(_business_date) AS business_date,
  _file_created_ts, _file_name, _source_file, _ingested_at
FROM STREAM(bronze_atl_daily);

CREATE OR REFRESH STREAMING TABLE silver_network_response (
  auth_id STRING, network STRING, network_txn_id STRING, event_ts_utc TIMESTAMP, event_ts_local TIMESTAMP,
  merchant_network_id STRING, merchant_id_norm BIGINT, acquirer_ref STRING, acquirer_ref_type STRING,
  amount DECIMAL(12,2), native_code STRING, reason_cd STRING, cross_border BOOLEAN, stip_flag BOOLEAN,
  processing_path STRING, token_requestor_id STRING, std_category STRING, is_acceptance_failure BOOLEAN,
  business_date DATE, _file_created_ts TIMESTAMP, _file_name STRING, _source_file STRING, _ingested_at TIMESTAMP,
  CONSTRAINT r8_auth_ref_not_null EXPECT (auth_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT r9_code_mapped       EXPECT (std_category <> 'UNMAPPED'),
  CONSTRAINT r10_file_on_time     EXPECT (_file_created_ts <= CAST(date_add(business_date, 2) AS TIMESTAMP))
)
CLUSTER BY (business_date)
COMMENT 'Network responses from both networks (Meridian + Atlas) in one conformed schema, with the standard decline category. One row per auth_id per network.';

CREATE FLOW f_network_mrd AS INSERT INTO silver_network_response BY NAME
SELECT p.*, coalesce(m.std_category, 'UNMAPPED') AS std_category, m.is_acceptance_failure
FROM STREAM(v_mrd_parsed) p
LEFT JOIN ref_response_code_map m ON m.network_cd = p.network AND m.native_cd = p.native_code;

CREATE FLOW f_network_atl AS INSERT INTO silver_network_response BY NAME
SELECT p.*, coalesce(m.std_category, 'UNMAPPED') AS std_category, m.is_acceptance_failure
FROM STREAM(v_atl_parsed) p
LEFT JOIN ref_response_code_map m ON m.network_cd = p.network AND m.native_cd = p.native_code;

CREATE FLOW q_network_mrd AS INSERT INTO quarantine_auth BY NAME
SELECT 'mrd_events' AS source_system, network_txn_id AS record_key, array('r8_auth_ref_not_null') AS reasons,
       'r8_auth_ref_not_null' AS reason, business_date, to_json(struct(*)) AS record, _file_name, _source_file, _ingested_at
FROM STREAM(v_mrd_parsed) WHERE auth_id IS NULL;

CREATE FLOW q_network_atl AS INSERT INTO quarantine_auth BY NAME
SELECT 'atl_daily' AS source_system, network_txn_id AS record_key, array('r8_auth_ref_not_null') AS reasons,
       'r8_auth_ref_not_null' AS reason, business_date, to_json(struct(*)) AS record, _file_name, _source_file, _ingested_at
FROM STREAM(v_atl_parsed) WHERE auth_id IS NULL;

-- ---------- Merchants, acquirers (latest state) ------------------------------
CREATE OR REFRESH MATERIALIZED VIEW silver_merchants (
  CONSTRAINT r11_merchant_num_not_null EXPECT (merchant_num IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT 'Merchant master, latest record per merchant, with both networks'' merchant IDs normalised to integers for matching.'
AS SELECT
  trim(MRCH_NUM) AS merchant_num,
  trim(DBA_NAME) AS dba_name,                                   -- trailing spaces removed
  try_cast(MCC AS INT) AS mcc,
  trim(CITY) AS city, nullif(trim(STATE), '') AS state, trim(CNTRY) AS country,
  trim(ACQ_INST_ID) AS acq_bin,
  trim(MRD_MID) AS mrd_mid,
  try_cast(regexp_replace(MRD_MID, '[^0-9]', '') AS BIGINT) AS mrd_mid_norm,
  trim(ATL_MID) AS atl_mid,
  try_cast(ATL_MID AS BIGINT) AS atl_mid_norm,
  trim(STATUS) AS status,
  to_date(EFF_DT) AS eff_dt,
  to_date(_business_date) AS last_change_date,
  _source_file
FROM bronze_merchant_master
QUALIFY row_number() OVER (PARTITION BY trim(MRCH_NUM) ORDER BY _business_date DESC, EFF_DT DESC, _ingested_at DESC) = 1;

CREATE OR REFRESH MATERIALIZED VIEW silver_acquirers
COMMENT 'Acquirer reference, latest snapshot per acquirer (ID, name, BIN, region, last configuration change).'
AS SELECT
  acquirerId AS acquirer_id, acquirerName AS acquirer_name, bin, region AS acquirer_region,
  lower(mrdCertified) = 'true' AS mrd_certified, to_date(certifiedDate) AS certified_date,
  to_date(lastConfigChange) AS last_config_change, configNote AS config_note,
  to_date(_business_date) AS snapshot_date
FROM bronze_acquirer_ref
QUALIFY row_number() OVER (PARTITION BY acquirerId ORDER BY _business_date DESC, _ingested_at DESC) = 1;

-- ---------- Cards: SCD Type 2 history; out-of-sequence re-sends are ignored --
CREATE TEMPORARY VIEW v_cards AS
SELECT
  trim(CARD_REF) AS card_ref, trim(PRODUCT_CD) AS product_cd, trim(SEGMENT) AS segment, trim(HOME_ST) AS home_st,
  try_cast(WAVE_ID AS INT) AS wave_id, to_date(PLANNED_MIG_DT) AS planned_mig_dt, to_date(ACTUAL_MIG_DT) AS actual_mig_dt,
  trim(ISSUER_SEG) AS issuer_seg, trim(STATUS) AS status, to_timestamp(UPDATE_TS) AS update_ts,
  to_date(_business_date) AS business_date, _file_name, _source_file
FROM STREAM(bronze_card_portfolio);

CREATE OR REFRESH PRIVATE STREAMING TABLE stg_cards (
  CONSTRAINT r15_card_ref_not_null EXPECT (card_ref IS NOT NULL) ON VIOLATION FAIL UPDATE
)
AS SELECT * FROM STREAM(v_cards);

CREATE OR REFRESH STREAMING TABLE silver_cards
COMMENT 'Card portfolio history (SCD Type 2 on UPDATE_TS). Current state: __END_AT IS NULL. Stale re-sends with an older UPDATE_TS never become current.';

CREATE FLOW f_silver_cards AS AUTO CDC INTO silver_cards
FROM STREAM(stg_cards)
KEYS (card_ref)
SEQUENCE BY update_ts
STORED AS SCD TYPE 2
TRACK HISTORY ON * EXCEPT (business_date, _file_name, _source_file);

-- ---------- Conformed authorization fact ------------------------------------
CREATE OR REFRESH MATERIALIZED VIEW silver_auth (
  CONSTRAINT r12_mrd_merchant_id_matches EXPECT (network <> 'MRD' OR NOT network_response_found OR coalesce(merchant_id_match, false)),
  CONSTRAINT r13_mcc_matches_master      EXPECT (mcc IS NULL OR master_mcc IS NULL OR mcc = master_mcc),
  CONSTRAINT r14_network_response_found  EXPECT (network_response_found)
)
CLUSTER BY (business_date, network)
COMMENT 'One row per authorization attempt, conformed across issuer, both networks, merchant, acquirer and card. decline_type separates acceptance failures from legitimate issuer declines.'
AS
WITH cards AS (SELECT * FROM silver_cards WHERE __END_AT IS NULL),
iss_codes AS (SELECT native_cd, std_category, is_acceptance_failure FROM ref_response_code_map WHERE network_cd = 'ISS'),
base AS (
  SELECT
    i.auth_id, i.business_date, i.auth_ts_local, i.auth_tz,
    to_utc_timestamp(i.auth_ts_local, i.auth_tz) AS auth_ts_utc,
    date_trunc('HOUR', i.auth_ts_local) AS auth_hour,
    i.card_ref, c.segment AS card_segment, c.product_cd, coalesce(c.issuer_seg, 'OWN') AS issuer_segment,
    c.wave_id, c.planned_mig_dt, c.actual_mig_dt,
    i.network,
    CASE WHEN i.network = 'MRD' THEN concat('W', c.wave_id) ELSE 'BASELINE' END AS wave_cohort,
    i.merchant_num, m.dba_name, i.mcc, m.mcc AS master_mcc,
    CASE
      WHEN coalesce(i.mcc, m.mcc) IN (5411, 5812, 5814) THEN 'FOOD_GROCERY'
      WHEN coalesce(i.mcc, m.mcc) = 5541 THEN 'FUEL'
      WHEN coalesce(i.mcc, m.mcc) IN (5311, 5651, 5999, 5200, 5732, 5912) THEN 'RETAIL'
      WHEN coalesce(i.mcc, m.mcc) IN (5815, 5818, 4899, 5968) THEN 'DIGITAL'
      WHEN coalesce(i.mcc, m.mcc) IN (4511, 4722, 7011, 7512) THEN 'TRAVEL_LODGING'
      WHEN coalesce(i.mcc, m.mcc) = 4111 THEN 'TRANSIT'
      WHEN coalesce(i.mcc, m.mcc) IN (4900, 4814, 6300) THEN 'BILLS'
      ELSE 'OTHER' END AS mcc_group,
    m.state AS merchant_state, m.country AS merchant_country,
    CASE
      WHEN coalesce(m.country, i.term_country) <> 'USA' THEN 'INTL'
      WHEN m.state IN ('NY','NJ','PA','MA','CT') THEN 'NE'
      WHEN m.state IN ('FL','GA','NC','VA','TN','SC') THEN 'SE'
      WHEN m.state IN ('IL','OH','MI','MN','WI','MO') THEN 'MW'
      WHEN m.state IN ('TX','AZ','OK','NM') THEN 'SW'
      WHEN m.state IN ('CA','WA','OR','CO','NV','UT') THEN 'W'
      ELSE 'UNKNOWN' END AS region,
    coalesce(n.cross_border, coalesce(i.term_country, m.country) <> 'USA') AS cross_border,
    a.acquirer_id, a.acquirer_name,
    i.pos_entry_mode,
    CASE i.pos_entry_mode WHEN '05' THEN 'CP' WHEN '07' THEN 'CP' WHEN '81' THEN 'ECOM' WHEN '10' THEN 'REC' WHEN '01' THEN 'MANUAL' ELSE 'OTHER' END AS channel,
    i.wallet_ind <> 'N' AS tokenized, i.is_recurring,
    i.amount, i.currency_cd,
    i.auth_decision = 'A' AS approved, i.iss_resp_cd, ic.std_category AS issuer_category, ic.is_acceptance_failure AS issuer_acceptance_failure,
    n.native_code AS network_code, n.std_category AS network_category, n.is_acceptance_failure AS network_acceptance_failure,
    coalesce(n.stip_flag, false) AS stip_flag, n.processing_path, n.token_requestor_id,
    n.auth_id IS NOT NULL AS network_response_found,
    n.merchant_id_norm = m.mrd_mid_norm AS merchant_id_match,
    greatest(i.first_available_ts, n._file_created_ts) AS available_ts,   -- when this row was knowable
    i._source_file
  FROM silver_issuer_auth i
  LEFT JOIN silver_network_response n ON n.auth_id = i.auth_id
  LEFT JOIN silver_merchants m ON m.merchant_num = i.merchant_num
  LEFT JOIN silver_acquirers a ON a.bin = i.acq_bin
  LEFT JOIN cards c ON c.card_ref = i.card_ref
  LEFT JOIN iss_codes ic ON ic.native_cd = i.iss_resp_cd
)
SELECT
  b.*,
  CASE
    WHEN b.approved THEN 'APPROVED'
    WHEN b.network_category = 'UNMAPPED' THEN 'UNMAPPED'
    WHEN b.network_acceptance_failure THEN b.network_category      -- the network code reveals the real cause
    ELSE coalesce(b.issuer_category, 'UNMAPPED') END AS std_category,
  CASE
    WHEN b.approved THEN 'APPROVED'
    WHEN b.network_category = 'UNMAPPED' THEN 'UNMAPPED'
    WHEN coalesce(b.network_acceptance_failure, false) OR coalesce(b.issuer_acceptance_failure, false) THEN 'ACCEPTANCE'
    ELSE 'ISSUER_LEGIT' END AS decline_type
FROM base b;
