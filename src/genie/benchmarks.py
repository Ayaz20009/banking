"""The 8 benchmark questions chosen by the submitter (2026-11-23), with their ground-truth SQL.
Relative periods are measured back from the latest business_date in the table, not from today."""
NS = "classic_stable_zjnu75_catalog.network_migration"
BENCHMARKS = [
 ("q01", "What was the approval rate for migrated cards vs the matched legacy baseline over the last 30 days, and the gap in percentage points?",
  f"""SELECT round(100 * sum(migrated_approvals) / sum(migrated_attempts), 2) AS migrated_approval_rate_pct,
       round(100 * sum(expected_approvals) / sum(migrated_attempts), 2) AS matched_baseline_approval_rate_pct,
       round(100 * (sum(expected_approvals) - sum(migrated_approvals)) / sum(migrated_attempts), 2) AS gap_pp
FROM {NS}.gold_baseline_gap
WHERE business_date > (SELECT date_sub(max(business_date), 30) FROM {NS}.gold_baseline_gap)"""),
 ("q03", "How much spend did we lose to excess declines on migrated cards in the last 30 days?",
  f"""SELECT round(sum(lost_spend), 2) AS lost_spend_usd, round(sum(excess_declines), 1) AS excess_declines
FROM {NS}.gold_baseline_gap
WHERE business_date > (SELECT date_sub(max(business_date), 30) FROM {NS}.gold_baseline_gap)"""),
 ("q04", "What are the top 5 acquirers by acceptance declines on the acquired network in the last 14 days?",
  f"""SELECT acquirer_id, acquirer_name, sum(acceptance_declines) AS acceptance_declines
FROM {NS}.gold_auth_daily
WHERE network = 'MRD' AND business_date > (SELECT date_sub(max(business_date), 14) FROM {NS}.gold_auth_daily)
GROUP BY acquirer_id, acquirer_name ORDER BY acceptance_declines DESC LIMIT 5"""),
 ("q07", "What is the acceptance-decline rate for cross-border travel and lodging on the acquired network vs the legacy network over the last 60 days?",
  f"""SELECT network, round(100 * sum(acceptance_declines) / sum(attempts), 2) AS acceptance_decline_rate_pct, sum(attempts) AS attempts
FROM {NS}.gold_auth_daily
WHERE mcc_group = 'TRAVEL_LODGING' AND cross_border
  AND business_date > (SELECT date_sub(max(business_date), 60) FROM {NS}.gold_auth_daily)
GROUP BY network ORDER BY network"""),
 ("q08", "How did ACQ-017's e-commerce acceptance-decline rate on the acquired network change before, during and after 24 September to 8 October 2026?",
  f"""SELECT CASE WHEN business_date < '2026-09-24' THEN '1_before' WHEN business_date <= '2026-10-08' THEN '2_during' ELSE '3_after' END AS period,
       round(100 * sum(acceptance_declines) / sum(attempts), 2) AS acceptance_decline_rate_pct, sum(attempts) AS attempts
FROM {NS}.gold_auth_daily
WHERE network = 'MRD' AND acquirer_id = 'ACQ-017' AND channel = 'ECOM' AND business_date BETWEEN '2026-09-10' AND '2026-10-22'
GROUP BY 1 ORDER BY 1"""),
 ("q13", "What is the latest business date loaded for each network, and on how many of the last 30 days do we have acquired-network data?",
  f"""SELECT network, max(business_date) AS latest_business_date,
       count(DISTINCT CASE WHEN business_date > (SELECT date_sub(max(business_date), 30) FROM {NS}.gold_auth_daily) THEN business_date END) AS days_with_data_last_30
FROM {NS}.gold_auth_daily GROUP BY network ORDER BY network"""),
 ("q14", "Is wave 7 ready to launch? Show the gate result and the reason for each card segment.",
  f"""SELECT card_segment, issuer_segment, gate, gate_reason
FROM {NS}.gold_wave_readiness WHERE wave_id = 7 ORDER BY issuer_segment, card_segment"""),
 ("q15", "How much transaction volume in wave 7 is at risk, by card segment?",
  f"""SELECT card_segment, round(sum(expected_daily_attempts), 1) AS expected_daily_attempts,
       round(sum(at_risk_declines_per_day), 2) AS at_risk_declines_per_day, round(sum(at_risk_spend_usd_per_day), 2) AS at_risk_spend_usd_per_day
FROM {NS}.gold_wave_readiness WHERE wave_id = 7 GROUP BY card_segment ORDER BY at_risk_spend_usd_per_day DESC"""),
]
