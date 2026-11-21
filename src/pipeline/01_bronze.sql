-- =============================================================================
-- BRONZE: raw as landed. Every source column is kept as STRING exactly as exported
-- (inferColumnTypes => false), plus file lineage on every row.
-- Auto Loader (STREAM read_files) reads each file exactly once, so reruns add no rows.
-- ${landing_path} comes from the pipeline configuration (resources/pipeline.yml).
-- =============================================================================

CREATE OR REFRESH STREAMING TABLE bronze_issuer_auth
COMMENT 'Issuer authorization system daily export (CSV), as landed. One row per landed record; re-sent duplicates are kept here and removed in silver.'
AS SELECT
  *,
  _metadata.file_path AS _source_file,
  _metadata.file_name AS _file_name,
  regexp_extract(_metadata.file_path, '/([0-9]{4}-[0-9]{2}-[0-9]{2})/', 1) AS _business_date,
  to_timestamp(regexp_extract(_metadata.file_name, '_([0-9]{12})[.]', 1), 'yyyyMMddHHmm') AS _file_created_ts,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '${landing_path}/iss_auth/',
  format => 'csv', header => true, inferColumnTypes => false, pathGlobFilter => '*.csv',
  ignoreLeadingWhiteSpace => false, ignoreTrailingWhiteSpace => false);

CREATE OR REFRESH STREAMING TABLE bronze_mrd_events
COMMENT 'Acquired network (Meridian) authorization events (JSON Lines), as landed.'
AS SELECT
  *,
  _metadata.file_path AS _source_file,
  _metadata.file_name AS _file_name,
  regexp_extract(_metadata.file_path, '/([0-9]{4}-[0-9]{2}-[0-9]{2})/', 1) AS _business_date,
  to_timestamp(regexp_extract(_metadata.file_name, '_([0-9]{12})[.]', 1), 'yyyyMMddHHmm') AS _file_created_ts,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '${landing_path}/mrd_events/',
  format => 'json', inferColumnTypes => false, pathGlobFilter => '*.jsonl');

CREATE OR REFRESH STREAMING TABLE bronze_atl_daily
COMMENT 'Legacy network (Atlas) daily reporting file (pipe-delimited), as landed. Some files arrive late (see _file_created_ts).'
AS SELECT
  *,
  _metadata.file_path AS _source_file,
  _metadata.file_name AS _file_name,
  regexp_extract(_metadata.file_path, '/([0-9]{4}-[0-9]{2}-[0-9]{2})/', 1) AS _business_date,
  to_timestamp(regexp_extract(_metadata.file_name, '_([0-9]{12})[.]', 1), 'yyyyMMddHHmm') AS _file_created_ts,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '${landing_path}/atl_daily/',
  format => 'csv', sep => '|', header => true, inferColumnTypes => false, pathGlobFilter => '*.txt',
  ignoreLeadingWhiteSpace => false, ignoreTrailingWhiteSpace => false);

CREATE OR REFRESH STREAMING TABLE bronze_merchant_master
COMMENT 'Merchant master: full load on day 1, then daily change files (CSV), as landed.'
AS SELECT
  *,
  _metadata.file_path AS _source_file,
  _metadata.file_name AS _file_name,
  regexp_extract(_metadata.file_path, '/([0-9]{4}-[0-9]{2}-[0-9]{2})/', 1) AS _business_date,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '${landing_path}/merchant_master/',
  format => 'csv', header => true, inferColumnTypes => false, pathGlobFilter => '*.csv',
  ignoreLeadingWhiteSpace => false, ignoreTrailingWhiteSpace => false);

CREATE OR REFRESH STREAMING TABLE bronze_card_portfolio
COMMENT 'Card portfolio: full load + change records (wave, migration dates, issuer segment) (CSV), as landed. Includes out-of-sequence re-sends.'
AS SELECT
  *,
  _metadata.file_path AS _source_file,
  _metadata.file_name AS _file_name,
  regexp_extract(_metadata.file_path, '/([0-9]{4}-[0-9]{2}-[0-9]{2})/', 1) AS _business_date,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '${landing_path}/card_portfolio/',
  format => 'csv', header => true, inferColumnTypes => false, pathGlobFilter => '*.csv');

CREATE OR REFRESH STREAMING TABLE bronze_acquirer_ref
COMMENT 'Acquirer reference snapshots (JSON Lines), as landed.'
AS SELECT
  *,
  _metadata.file_path AS _source_file,
  _metadata.file_name AS _file_name,
  regexp_extract(_metadata.file_path, '/([0-9]{4}-[0-9]{2}-[0-9]{2})/', 1) AS _business_date,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '${landing_path}/acquirer_ref/',
  format => 'json', inferColumnTypes => false, pathGlobFilter => '*.jsonl');

-- Manifests (_MANIFEST.json control totals) are read in 03_manifests.py: files starting with "_"
-- are hidden from read_files / Auto Loader.

-- Static reference files (governed by us), small: materialized views with a batch read.
CREATE OR REFRESH MATERIALIZED VIEW ref_response_code_map
COMMENT 'Crosswalk: native response code per network (ISS issuer, ATL legacy, MRD acquired) -> standard decline category.'
AS SELECT
  trim(network_cd) AS network_cd,
  trim(native_cd) AS native_cd,
  description,
  trim(std_category) AS std_category,
  trim(is_acceptance_failure) = 'Y' AS is_acceptance_failure,
  _metadata.file_path AS _source_file
FROM read_files('${landing_path}/ref/*/RESPONSE_CODE_MAP_*.csv', format => 'csv', header => true, inferColumnTypes => false);

CREATE OR REFRESH MATERIALIZED VIEW ref_recovery_assumptions
COMMENT 'Finance assumption: share of declined spend not recovered on our cards, by card segment (synthetic, versioned).'
AS SELECT
  trim(segment) AS segment,
  CAST(unrecovered_rate AS DECIMAL(5,3)) AS unrecovered_rate,
  version, to_date(effective_dt) AS effective_dt, source,
  _metadata.file_path AS _source_file
FROM read_files('${landing_path}/ref/*/RECOVERY_ASSUMPTIONS_*.csv', format => 'csv', header => true, inferColumnTypes => false);

-- R16 (FAIL): the code map must exist and hold one row per (network, code).
CREATE OR REFRESH PRIVATE MATERIALIZED VIEW chk_response_code_map (
  CONSTRAINT r16_map_not_empty EXPECT (n_rows > 0) ON VIOLATION FAIL UPDATE,
  CONSTRAINT r16_map_unique_codes EXPECT (n_rows = n_keys) ON VIOLATION FAIL UPDATE
)
AS SELECT count(*) AS n_rows, count(DISTINCT network_cd, native_cd) AS n_keys FROM ref_response_code_map;
