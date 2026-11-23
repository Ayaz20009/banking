-- =============================================================================
-- T5: wave readiness gate (decision 2026-11-23: option A, simple gate)
-- One row per upcoming wave (7-10) x card segment x issuer segment.
--   GO   = the segment's matched-baseline approval gap on migrated cards over the last 14 days is <= 0.3 pp
--          AND no HIGH-severity case is open for that issuer segment.
--   HOLD = otherwise, with the reason in words.
-- At-risk volume = the wave's expected daily attempts x the segment's gap (declines/day and $/day).
-- Runs as the job owner (ADMIN persona); readers see it through the persona row filter.
-- =============================================================================
USE CATALOG classic_stable_zjnu75_catalog;
USE SCHEMA network_migration;

CREATE OR REPLACE TABLE gold_wave_readiness (
  as_of_date DATE COMMENT 'Latest business date in the data when the gate was computed',
  wave_id INT COMMENT 'Upcoming migration wave (7-10)',
  planned_migration_date DATE COMMENT 'Planned migration date of the wave',
  card_segment STRING COMMENT 'Cardholder spending segment (DOMESTIC, ECOM_HEAVY, RECURRING_HEAVY, WALLET_HEAVY, INTL_TRAVELER)',
  issuer_segment STRING COMMENT 'OWN = cards issued by this bank; THIRD_PARTY = cards of other issuers processed on the network',
  region STRING COMMENT 'Always ALL (waves are not regional); used by the persona row filter',
  cards INT COMMENT 'Cards planned to migrate in this wave and segment',
  expected_daily_attempts DOUBLE COMMENT 'Average daily authorization attempts of these cards over the last 28 days (still on the legacy network)',
  avg_ticket_usd DOUBLE COMMENT 'Average attempt amount of these cards over the last 28 days, USD',
  segment_gap_pp_14d DOUBLE COMMENT 'Approval-rate gap of already-migrated cards in the same card segment vs the matched legacy baseline, last 14 days, percentage points (positive = migrated cards approve less)',
  migrated_attempts_14d BIGINT COMMENT 'Migrated attempts behind segment_gap_pp_14d (evidence size)',
  open_high_cases INT COMMENT 'HIGH-severity cases not RESOLVED or DISMISSED for this issuer segment',
  gap_within_limit BOOLEAN COMMENT 'segment_gap_pp_14d <= 0.3',
  no_open_high_cases BOOLEAN COMMENT 'open_high_cases = 0',
  gate STRING COMMENT 'GO or HOLD',
  gate_reason STRING COMMENT 'Why the gate is GO or HOLD, in words',
  at_risk_declines_per_day DOUBLE COMMENT 'Expected extra declines per day if migrated today = expected_daily_attempts x max(gap, 0) / 100',
  at_risk_spend_usd_per_day DOUBLE COMMENT 'at_risk_declines_per_day x avg ticket x unrecovered rate (Finance assumption by segment)',
  computed_at TIMESTAMP COMMENT 'When this row was computed'
)
COMMENT 'Wave readiness gate for upcoming migration waves: GO only if the segment approval gap is within 0.3 pp and no HIGH-severity case is open. Includes at-risk volume. Row filter by persona.'
WITH ROW FILTER classic_stable_zjnu75_catalog.network_migration.f_row_filter ON (issuer_segment, region);

INSERT INTO gold_wave_readiness
WITH asof AS (SELECT max(business_date) AS d FROM silver_auth),
cards AS (
  SELECT card_ref, wave_id, planned_mig_dt, segment AS card_segment, issuer_seg AS issuer_segment
  FROM silver_cards WHERE __END_AT IS NULL AND wave_id >= 7),
activity AS (
  SELECT c.wave_id, c.card_segment, c.issuer_segment, count(*) / 28.0 AS expected_daily_attempts, avg(a.amount) AS avg_ticket
  FROM silver_auth a JOIN cards c ON c.card_ref = a.card_ref, asof
  WHERE a.business_date > date_sub(asof.d, 28) GROUP BY ALL),
plan AS (
  SELECT wave_id, card_segment, issuer_segment, min(planned_mig_dt) AS planned_migration_date, count(*) AS cards
  FROM cards GROUP BY ALL),
gap AS (
  SELECT g.card_segment, g.issuer_segment,
         100 * (sum(g.expected_approvals) - sum(g.migrated_approvals)) / sum(g.migrated_attempts) AS gap_pp,
         sum(g.migrated_attempts) AS migrated_attempts
  FROM gold_baseline_gap g, asof WHERE g.business_date > date_sub(asof.d, 14) GROUP BY ALL),
cases AS (
  SELECT issuer_segment, count(*) AS open_high
  FROM gold_case_status WHERE severity = 'HIGH' AND status NOT IN ('RESOLVED', 'DISMISSED') GROUP BY ALL),
j AS (
  SELECT asof.d AS as_of_date, p.wave_id, p.planned_migration_date, p.card_segment, p.issuer_segment, 'ALL' AS region, p.cards,
         coalesce(a.expected_daily_attempts, 0) AS expected_daily_attempts, a.avg_ticket AS avg_ticket_usd,
         g.gap_pp AS segment_gap_pp_14d, g.migrated_attempts AS migrated_attempts_14d,
         CAST(coalesce(cs.open_high, 0) AS INT) AS open_high_cases,
         coalesce(r.unrecovered_rate, d.unrecovered_rate) AS unrecovered_rate
  FROM plan p CROSS JOIN asof
  LEFT JOIN activity a USING (wave_id, card_segment, issuer_segment)
  LEFT JOIN gap g USING (card_segment, issuer_segment)
  LEFT JOIN cases cs USING (issuer_segment)
  LEFT JOIN ref_recovery_assumptions r ON r.segment = p.card_segment
  LEFT JOIN ref_recovery_assumptions d ON d.segment = 'DEFAULT'
)
SELECT as_of_date, wave_id, planned_migration_date, card_segment, issuer_segment, region, CAST(cards AS INT),
       expected_daily_attempts, avg_ticket_usd, segment_gap_pp_14d, migrated_attempts_14d, open_high_cases,
       coalesce(segment_gap_pp_14d <= 0.3, false) AS gap_within_limit,
       open_high_cases = 0 AS no_open_high_cases,
       CASE WHEN coalesce(segment_gap_pp_14d <= 0.3, false) AND open_high_cases = 0 THEN 'GO' ELSE 'HOLD' END AS gate,
       concat_ws('; ',
         CASE WHEN segment_gap_pp_14d IS NULL THEN 'no migrated cards in this segment to measure the gap'
              WHEN segment_gap_pp_14d > 0.3 THEN format_string('approval gap %.2f pp > 0.3 pp limit', segment_gap_pp_14d)
              ELSE format_string('approval gap %.2f pp within 0.3 pp limit', segment_gap_pp_14d) END,
         CASE WHEN open_high_cases > 0 THEN format_string('%d HIGH-severity case(s) open', open_high_cases)
              ELSE 'no HIGH-severity cases open' END) AS gate_reason,
       expected_daily_attempts * greatest(coalesce(segment_gap_pp_14d, 0), 0) / 100 AS at_risk_declines_per_day,
       expected_daily_attempts * greatest(coalesce(segment_gap_pp_14d, 0), 0) / 100 * coalesce(avg_ticket_usd, 0) * unrecovered_rate AS at_risk_spend_usd_per_day,
       current_timestamp() AS computed_at
FROM j;

ALTER TABLE gold_wave_readiness SET TAGS ('nm_layer' = 'gold', 'nm_data_class' = 'commercially_sensitive', 'nm_policy' = 'row_filter_persona');
