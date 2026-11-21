-- =============================================================================
-- RECONCILIATION: completeness against the source's control totals.
-- One row per landed file: control count/amount from _MANIFEST.json vs rows landed
-- (bronze), loaded (passed the DROP rules) and quarantined (failed a DROP rule).
--   RECONCILED = control_count = landed_rows AND landed_rows = loaded_rows + quarantined_rows
--                (and, for the two network feeds, the amount total matches within $0.05)
--   BREAK      = anything else, with break_reason.
-- R17 (WARN): a BREAK is counted in the event log but does not stop the pipeline.
-- Issuer amounts are not compared: the control total includes the planted unparseable
-- amounts, which have no numeric value once landed (they are quarantined instead).
-- =============================================================================

CREATE OR REFRESH MATERIALIZED VIEW recon_file_control (
  CONSTRAINT r17_file_reconciled EXPECT (status = 'RECONCILED')
)
COMMENT 'Per-file reconciliation of manifest control totals vs landed / loaded / quarantined rows. Status RECONCILED or BREAK.'
AS
WITH man AS (
  SELECT system, to_date(business_date) AS business_date, to_timestamp(file_created_ts) AS file_created_ts,
         file_name, record_count AS control_count, CAST(amount_total AS DECIMAL(16,2)) AS control_amount
  FROM bronze_file_manifests
),
landed AS (
  SELECT 'iss_auth' AS system, _file_name AS file_name, count(*) AS landed_rows, CAST(NULL AS DECIMAL(16,2)) AS landed_amount
  FROM bronze_issuer_auth GROUP BY ALL
  UNION ALL
  SELECT 'mrd_events', _file_name, count(*), CAST(sum(try_cast(amountMinor AS BIGINT)) / 100.0 AS DECIMAL(16,2))
  FROM bronze_mrd_events GROUP BY ALL
  UNION ALL
  SELECT 'atl_daily', _file_name, count(*), CAST(sum(try_cast(amt AS DECIMAL(12,2))) AS DECIMAL(16,2))
  FROM bronze_atl_daily GROUP BY ALL
  UNION ALL
  SELECT 'merchant_master', _file_name, count(*), NULL FROM bronze_merchant_master GROUP BY ALL
  UNION ALL
  SELECT 'card_portfolio', _file_name, count(*), NULL FROM bronze_card_portfolio GROUP BY ALL
  UNION ALL
  SELECT 'acquirer_ref', _file_name, count(*), NULL FROM bronze_acquirer_ref GROUP BY ALL
),
loaded AS (
  SELECT 'iss_auth' AS system, _file_name AS file_name, count(*) AS loaded_rows FROM stg_issuer_auth GROUP BY ALL
  UNION ALL
  SELECT CASE network WHEN 'MRD' THEN 'mrd_events' ELSE 'atl_daily' END, _file_name, count(*)
  FROM silver_network_response GROUP BY ALL
  UNION ALL
  SELECT 'card_portfolio', _file_name, count(*) FROM stg_cards GROUP BY ALL
),
quar AS (
  SELECT source_system AS system, _file_name AS file_name, count(*) AS quarantined_rows FROM quarantine_auth GROUP BY ALL
),
kept AS (  -- issuer rows that survived deduplication, per file
  SELECT 'iss_auth' AS system, _file_name AS file_name, count(*) AS kept_after_dedup FROM silver_issuer_auth GROUP BY ALL
),
j AS (
  SELECT
    man.system, man.business_date, man.file_name, man.file_created_ts,
    timestampdiff(HOUR, CAST(man.business_date AS TIMESTAMP), man.file_created_ts) AS hours_after_business_date,
    man.control_count,
    coalesce(l.landed_rows, 0) AS landed_rows,
    CASE WHEN man.system IN ('merchant_master', 'acquirer_ref') THEN coalesce(l.landed_rows, 0)   -- no DROP rules
         ELSE coalesce(ld.loaded_rows, 0) END AS loaded_rows,
    coalesce(q.quarantined_rows, 0) AS quarantined_rows,
    k.kept_after_dedup,
    CASE WHEN k.kept_after_dedup IS NOT NULL THEN coalesce(ld.loaded_rows, 0) - k.kept_after_dedup END AS duplicates_superseded,
    man.control_amount, l.landed_amount
  FROM man
  LEFT JOIN landed l ON l.system = man.system AND l.file_name = man.file_name
  LEFT JOIN loaded ld ON ld.system = man.system AND ld.file_name = man.file_name
  LEFT JOIN quar q ON q.system = man.system AND q.file_name = man.file_name
  LEFT JOIN kept k ON k.system = man.system AND k.file_name = man.file_name
)
SELECT
  *,
  control_amount - landed_amount AS amount_diff,
  CASE
    WHEN landed_rows <> control_count THEN concat('COUNT_MISMATCH: control ', control_count, ' vs landed ', landed_rows)
    WHEN landed_rows <> loaded_rows + quarantined_rows THEN concat('LOAD_MISMATCH: landed ', landed_rows, ' vs loaded+quarantined ', loaded_rows + quarantined_rows)
    WHEN system IN ('mrd_events', 'atl_daily') AND abs(control_amount - landed_amount) > 0.05 THEN concat('AMOUNT_MISMATCH: ', control_amount - landed_amount)
  END AS break_reason,
  CASE
    WHEN landed_rows = control_count
     AND landed_rows = loaded_rows + quarantined_rows
     AND NOT (system IN ('mrd_events', 'atl_daily') AND abs(control_amount - landed_amount) > 0.05)
    THEN 'RECONCILED' ELSE 'BREAK' END AS status
FROM j;
