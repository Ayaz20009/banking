-- =============================================================================
-- EXPLAINABLE ANOMALY SCORE (D7, option A; EVAL_PROTOCOL v1 + Amendments 1-2)
-- One row per acquired-network (Meridian) slice x business day x issuer segment, for five
-- slice families. Every row stores its five named point components, the total and
-- the drivers in plain words. The flag threshold is NOT applied here: it is tuned on the
-- tuning days only and frozen by the job (src/ai/tune_threshold.py).
--
-- Timing rule: day D is scored at D+1 07:00 using only rows whose source files had
-- landed by then (silver_auth.available_ts). The expected rate uses the prior 28 days
-- only, counting each prior day's rows that were on time for that day (conservative:
-- never uses anything known after the decision time).
-- Only ACCEPTANCE declines count. Legitimate issuer declines (insufficient funds, fraud...)
-- are excluded by construction.
-- =============================================================================

CREATE OR REFRESH MATERIALIZED VIEW gold_anomaly_scores
CLUSTER BY (business_date, family)
COMMENT 'Explainable anomaly score (0-100) per Meridian slice-day: excess acceptance declines vs the slice''s own prior-28-day rate, with named point components, drivers, likely root cause and owner team. Row filter by persona (region-family rows carry their region; other families carry ALL).'
WITH ROW FILTER classic_stable_zjnu75_catalog.network_migration.f_row_filter ON (issuer_segment, region)
AS
WITH base AS (
  SELECT business_date, issuer_segment, acquirer_id, channel, mcc_group, cross_border, region, card_segment,
         decline_type, std_category, merchant_num, amount
  FROM silver_auth
  WHERE network = 'MRD'
    AND available_ts <= CAST(date_add(business_date, 1) AS TIMESTAMP) + INTERVAL 7 HOURS   -- known at decision time
),
exploded AS (
  SELECT b.*, f.family, f.slice_value, f.region_key
  FROM base b
  LATERAL VIEW explode(array(
    named_struct('family', 'ACQUIRER_CHANNEL', 'slice_value', concat(acquirer_id, ' / ', channel), 'region_key', 'ALL'),
    named_struct('family', 'MCC_GROUP_XB', 'slice_value', concat(mcc_group, ' / ', IF(cross_border, 'CROSS_BORDER', 'DOMESTIC')), 'region_key', 'ALL'),
    named_struct('family', 'REGION', 'slice_value', region, 'region_key', region),
    named_struct('family', 'CHANNEL', 'slice_value', channel, 'region_key', 'ALL'),
    named_struct('family', 'CARD_SEGMENT', 'slice_value', card_segment, 'region_key', 'ALL')
  )) t AS f
),
daily AS (
  SELECT business_date, issuer_segment, family, slice_value, region_key,
    count(*) AS attempts,
    count_if(decline_type = 'ACCEPTANCE') AS acc_declines,
    count_if(std_category = 'ACCEPTANCE_CONFIG') AS c_acceptance_config,
    count_if(std_category = 'TOKEN_PROVISIONING') AS c_token_provisioning,
    count_if(std_category = 'CROSS_BORDER_BLOCK') AS c_cross_border_block,
    count_if(std_category = 'CARD_ON_FILE_STALE') AS c_card_on_file_stale,
    count_if(std_category = 'PROCESSOR_TIMEOUT') AS c_processor_timeout,
    count_if(std_category = 'SYSTEM_ERROR') AS c_system_error,
    count(DISTINCT CASE WHEN decline_type = 'ACCEPTANCE' THEN merchant_num END) AS acc_merchants,
    CAST(avg(amount) AS DOUBLE) AS avg_ticket
  FROM exploded
  GROUP BY ALL
),
net AS (  -- network-wide daily totals per issuer segment (the CHANNEL family partitions all rows)
  SELECT business_date, issuer_segment, sum(attempts) AS n_att, sum(acc_declines) AS n_acc
  FROM daily WHERE family = 'CHANNEL' GROUP BY ALL
),
net_prior AS (
  SELECT business_date, issuer_segment,
    sum(n_acc) OVER w / nullif(sum(n_att) OVER w, 0) AS net_prior_rate
  FROM net
  WINDOW w AS (PARTITION BY issuer_segment ORDER BY unix_date(business_date) RANGE BETWEEN 28 PRECEDING AND 1 PRECEDING)
),
prior AS (
  SELECT d.*,
    coalesce(sum(attempts) OVER w, 0) AS prior_attempts,
    coalesce(sum(acc_declines) OVER w, 0) AS prior_acc_declines
  FROM daily d
  WINDOW w AS (PARTITION BY issuer_segment, family, slice_value ORDER BY unix_date(business_date) RANGE BETWEEN 28 PRECEDING AND 1 PRECEDING)
),
stats AS (
  SELECT p.*, np.net_prior_rate,
    -- expected rate: slice's own prior-28-day rate shrunk toward the network rate (pseudo-count 500)
    (p.prior_acc_declines + 500 * coalesce(np.net_prior_rate, 0)) / (p.prior_attempts + 500) AS expected_rate
  FROM prior p
  LEFT JOIN net_prior np USING (business_date, issuer_segment)
),
z AS (
  SELECT s.*,
    s.attempts * s.expected_rate AS expected_declines,
    s.acc_declines - s.attempts * s.expected_rate AS excess_declines,
    (s.acc_declines - s.attempts * s.expected_rate) / sqrt(s.attempts * s.expected_rate + 1) AS z_score,
    array_max(array(
      named_struct('n', c_acceptance_config, 'cat', 'ACCEPTANCE_CONFIG'),
      named_struct('n', c_token_provisioning, 'cat', 'TOKEN_PROVISIONING'),
      named_struct('n', c_cross_border_block, 'cat', 'CROSS_BORDER_BLOCK'),
      named_struct('n', c_card_on_file_stale, 'cat', 'CARD_ON_FILE_STALE'),
      named_struct('n', c_processor_timeout, 'cat', 'PROCESSOR_TIMEOUT'),
      named_struct('n', c_system_error, 'cat', 'SYSTEM_ERROR'))) AS dom
  FROM stats s
),
persist AS (
  SELECT z.*,
    coalesce(sum(CASE WHEN z_score >= 3 THEN 1 ELSE 0 END) OVER (
      PARTITION BY issuer_segment, family, slice_value ORDER BY unix_date(business_date)
      RANGE BETWEEN 2 PRECEDING AND 1 PRECEDING), 0) AS prior_elevated_days
  FROM z
),
pts AS (
  SELECT p.*,
    CASE WHEN p.acc_declines > 0 THEN p.dom.cat END AS likely_root_cause,
    CASE WHEN p.acc_declines > 0 THEN p.dom.n / p.acc_declines ELSE 0 END AS dominant_share,
    greatest(p.excess_declines, 0) * coalesce(p.avg_ticket, 0) * 0.45 AS exposure_usd,     -- 0.45 = DEFAULT unrecovered rate
    -- named components (points); clarity / breadth / persistence only count when the excess is material (z >= 2)
    least(40.0, greatest(0.0, (p.z_score - 2) * 5)) AS excess_points,
    least(25.0, greatest(0.0, 5 * log10(1 + greatest(p.excess_declines, 0) * coalesce(p.avg_ticket, 0) * 0.45))) AS impact_points,
    CASE WHEN p.z_score >= 2 AND p.acc_declines > 0 THEN 15.0 * p.dom.n / p.acc_declines ELSE 0.0 END AS clarity_points,
    CASE WHEN p.z_score >= 2 THEN least(10.0, 2 * log2(1 + p.acc_merchants)) ELSE 0.0 END AS breadth_points,
    CASE WHEN p.z_score >= 2 THEN 5.0 * p.prior_elevated_days ELSE 0.0 END AS persistence_points
  FROM persist p
)
SELECT
  concat_ws('|', CAST(business_date AS STRING), issuer_segment, family, slice_value) AS anomaly_key,
  business_date, issuer_segment, family, slice_value, region_key AS region,
  attempts, acc_declines, expected_rate, expected_declines, excess_declines, z_score,
  prior_attempts, prior_acc_declines, net_prior_rate,
  c_acceptance_config, c_token_provisioning, c_cross_border_block, c_card_on_file_stale, c_processor_timeout, c_system_error,
  acc_merchants, avg_ticket, exposure_usd, prior_elevated_days,
  likely_root_cause, dominant_share,
  CASE likely_root_cause
    WHEN 'ACCEPTANCE_CONFIG' THEN 'Acquirer Relations'
    WHEN 'TOKEN_PROVISIONING' THEN 'Card Technology'
    WHEN 'CROSS_BORDER_BLOCK' THEN 'Network Integration'
    WHEN 'CARD_ON_FILE_STALE' THEN 'Card Technology'
    WHEN 'PROCESSOR_TIMEOUT' THEN 'Network Operations'
    WHEN 'SYSTEM_ERROR' THEN 'Network Operations' END AS owner_team,
  excess_points, impact_points, clarity_points, breadth_points, persistence_points,
  excess_points + impact_points + clarity_points + breadth_points + persistence_points AS score,
  filter(array(
    format_string('%d acceptance declines vs %.1f expected (z = %.1f)', acc_declines, expected_declines, z_score),
    CASE WHEN exposure_usd >= 1 THEN format_string('$%,.0f estimated lost spend', exposure_usd) END,
    CASE WHEN acc_declines > 0 THEN format_string('%.0f%% of them %s', 100 * dominant_share, likely_root_cause) END,
    CASE WHEN acc_merchants > 0 THEN format_string('%d merchants affected', acc_merchants) END,
    CASE WHEN prior_elevated_days > 0 THEN format_string('elevated on %d of the prior 2 days', prior_elevated_days) END
  ), x -> x IS NOT NULL) AS drivers,
  'score_v1' AS score_version
FROM pts
WHERE business_date >= DATE'2026-01-12';
