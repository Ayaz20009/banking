-- =============================================================================
-- GOLD (pipeline-owned): the two business tables the detection step reads.
-- gold_anomalies, gold_case_status and gold_wave_readiness are written by job tasks
-- T2-T5 (BUILD_PLAN.md section 5), not by this pipeline.
-- =============================================================================

CREATE OR REFRESH MATERIALIZED VIEW gold_auth_hourly
CLUSTER BY (business_date, network)
COMMENT 'Authorization outcomes per local hour x wave cohort x network x acquirer x channel x MCC group x region x cross-border x tokenized x issuer segment. Attempts, approvals, declines by standard category, amounts.'
AS SELECT
  auth_hour, business_date, wave_cohort, network, acquirer_id, acquirer_name, channel, mcc_group, region,
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

-- Migrated cohorts vs a MATCHED baseline: same day, same card segment, channel, MCC group and
-- cross-border flag, on Atlas. Thin segments (< 50 baseline attempts) fall back to
-- card segment x channel. The unmatched (all-Atlas) rate is kept for comparison.
CREATE OR REFRESH MATERIALIZED VIEW gold_baseline_gap
CLUSTER BY (business_date, wave_cohort)
COMMENT 'Per day x migrated wave cohort x match segment: approval rate vs matched Atlas baseline, gap (pp), excess declines and lost spend (excess declines x avg ticket x unrecovered rate).'
AS
WITH seg AS (
  SELECT business_date, wave_cohort, card_segment, channel, mcc_group, cross_border,
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
    m.card_segment, m.channel, m.mcc_group, m.cross_border,
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
