# Evidence 01: Lakeflow pipeline run (`febar_pipeline`)

- **Pipeline:** `febar_pipeline` · id `9f46a185-fb6f-4e70-be6f-a4742066453b` · serverless · triggered · channel CURRENT · publishes to `classic_stable_zjnu75_catalog.network_migration`
- **Source:** `src/pipeline/01_bronze.sql`, `02_silver.sql`, `03_manifests.py`, `03_reconciliation.sql`, `04_gold.sql` (bundle resource `resources/pipeline.yml`; `landing_path` passed as pipeline configuration and used as `${landing_path}`)
- **Captured:** 2026-11-21 (UTC) from `event_log('9f46a185-fb6f-4e70-be6f-a4742066453b')` and SQL queries on the serverless SQL warehouse.

## Updates

| update_id | started | ended | seconds | final_state |
|---|---|---|---|---|
| 1ee54236-59a3-4c9f-a27b-817a8ad22d5c | 2026-11-21T03:43:11.171Z | 2026-11-21T03:47:39.027Z | 268.0 | COMPLETED |
| 38a9b33a-cca7-42f3-a6b1-588ce8317c9d | 2026-11-21T03:48:50.734Z | 2026-11-21T03:49:24.894Z | 34.0 | COMPLETED |
| e5c55467-a6a9-4eb3-9c9b-ed6bf91a5338 | 2026-11-21T03:49:48.144Z | 2026-11-21T03:50:21.363Z | 33.0 | COMPLETED |
| 53b189cb-fd94-4a51-b0cb-2a80a0b595e5 | 2026-11-21T03:51:11.352Z | 2026-11-21T03:55:06.009Z | 235.0 | COMPLETED |
| 7f9387fb-1f12-4d56-9c5c-bd32a9ef7dc5 | 2026-11-21T03:56:01.648Z | 2026-11-21T03:59:24.779Z | 203.0 | COMPLETED |

1. `1ee54236` was the first full load: ~22M rows across bronze, silver and gold, completed in 268 s.
2. `38a9b33a` and `e5c55467` were attempts to load the manifests with `read_files`; both loaded 0 rows (see BUILD_LOG).
3. `53b189cb` added `03_manifests.py`.
4. `7f9387fb` was a **plain rerun with no new files**, the idempotency check below.

## Rows per table (after the rerun, update `7f9387fb`)

| t | n |
|---|---|
| silver_cards (all SCD2 versions) | 54273 |
| silver_cards (current) | 45000 |
| bronze_issuer_auth | 11208018 |
| bronze_mrd_events | 1142716 |
| bronze_atl_daily | 9845467 |
| bronze_merchant_master | 58100 |
| bronze_card_portfolio | 54459 |
| bronze_acquirer_ref | 1120 |
| bronze_file_manifests | 1441 |
| ref_response_code_map | 134 |
| ref_recovery_assumptions | 6 |
| silver_issuer_auth | 10933861 |
| silver_network_response | 10988183 |
| silver_merchants | 40000 |
| silver_acquirers | 80 |
| silver_auth | 10933861 |
| quarantine_auth | 55613 |
| recon_file_control | 1441 |
| gold_auth_hourly | 7935859 |
| gold_baseline_gap | 31504 |

**How the numbers tie out:**
- `bronze_issuer_auth` = 10,988,625 attempts + 219,393 re-sent duplicates (DQ1).
- `quarantine_auth` = 33,715 + 11,059 + 10,839 = 55,613 (DQ2 + DQ3 + DQ4, exactly as in `00_answer_key.md`).
- `silver_issuer_auth` = 11,152,405 loaded − 218,544 superseded duplicates = 10,933,861, with **0 duplicate `auth_id`**. The other 849 duplicate copies were of records that were themselves quarantined.
- `silver_network_response` = 1,142,716 Meridian + 9,845,467 Atlas, with nothing dropped.
- `silver_cards` holds 54,273 history versions = 54,459 landed − **186 out-of-sequence re-sends ignored by SCD2 sequencing** (DQ7); 45,000 cards are current.

## Rerun safety (second run does not duplicate)

The row counts above were captured after update `7f9387fb`. They are identical to the counts after the first load for every table. The only exception is `recon_file_control`, which was empty before the manifest fix. Auto Loader read 0 new files; the materialized views recomputed to the same results.

## Expectation pass/fail counts (event log, latest update per dataset)

| dataset | expectation | passed | failed | update_id |
|---|---|---|---|---|
| chk_response_code_map | r16_map_not_empty | 1 | 0 | 7f9387fb-1f12-4d56-9c5c-bd32a9ef7dc5 |
| chk_response_code_map | r16_map_unique_codes | 1 | 0 | 7f9387fb-1f12-4d56-9c5c-bd32a9ef7dc5 |
| f_network_atl | r10_file_on_time | 9767922 | 77545 | 1ee54236-59a3-4c9f-a27b-817a8ad22d5c |
| f_network_atl | r8_auth_ref_not_null | 9845467 | 0 | 1ee54236-59a3-4c9f-a27b-817a8ad22d5c |
| f_network_atl | r9_code_mapped | 9845467 | 0 | 1ee54236-59a3-4c9f-a27b-817a8ad22d5c |
| f_network_mrd | r10_file_on_time | 1142716 | 0 | 1ee54236-59a3-4c9f-a27b-817a8ad22d5c |
| f_network_mrd | r8_auth_ref_not_null | 1142716 | 0 | 1ee54236-59a3-4c9f-a27b-817a8ad22d5c |
| f_network_mrd | r9_code_mapped | 1142494 | 222 | 1ee54236-59a3-4c9f-a27b-817a8ad22d5c |
| recon_file_control | r17_file_reconciled | 1440 | 1 | 7f9387fb-1f12-4d56-9c5c-bd32a9ef7dc5 |
| silver_auth | r12_mrd_merchant_id_matches | 10933861 | 0 | 7f9387fb-1f12-4d56-9c5c-bd32a9ef7dc5 |
| silver_auth | r13_mcc_matches_master | 10723777 | 210084 | 7f9387fb-1f12-4d56-9c5c-bd32a9ef7dc5 |
| silver_auth | r14_network_response_found | 10933420 | 441 | 7f9387fb-1f12-4d56-9c5c-bd32a9ef7dc5 |
| silver_merchants | r11_merchant_num_not_null | 40000 | 0 | 7f9387fb-1f12-4d56-9c5c-bd32a9ef7dc5 |
| stg_cards | r15_card_ref_not_null | 54459 | 0 | 1ee54236-59a3-4c9f-a27b-817a8ad22d5c |
| stg_issuer_auth | r1_auth_id_not_null | 11197179 | 10839 | 1ee54236-59a3-4c9f-a27b-817a8ad22d5c |
| stg_issuer_auth | r2_valid_amount | 11174303 | 33715 | 1ee54236-59a3-4c9f-a27b-817a8ad22d5c |
| stg_issuer_auth | r3_ts_not_future | 11196959 | 11059 | 1ee54236-59a3-4c9f-a27b-817a8ad22d5c |
| stg_issuer_auth | r4_valid_decision_network | 11208018 | 0 | 1ee54236-59a3-4c9f-a27b-817a8ad22d5c |
| stg_issuer_auth | r5_currency_840 | 11208018 | 0 | 1ee54236-59a3-4c9f-a27b-817a8ad22d5c |
| stg_issuer_auth | r6_mcc_present | 11095758 | 112260 | 1ee54236-59a3-4c9f-a27b-817a8ad22d5c |
| stg_issuer_auth | r7_term_country_present | 11152388 | 55630 | 1ee54236-59a3-4c9f-a27b-817a8ad22d5c |

Streaming datasets (`stg_*`, `f_network_*`) report their counts in the update that read the files (`1ee54236`). Later updates read no new rows.

**Rule outcomes vs the answer key:**

| Rule | Action | Failed | Planted finding | Result |
|---|---|---|---|---|
| R1 `r1_auth_id_not_null` | DROP → quarantine | 10,839 | DQ4 = 10,839 | ✓ |
| R2 `r2_valid_amount` | DROP → quarantine | 33,715 | DQ2 = 33,715 | ✓ |
| R3 `r3_ts_not_future` | DROP → quarantine | 11,059 | DQ3 = 11,059 | ✓ |
| R4 `r4_valid_decision_network` | FAIL | 0 | guard | ✓ |
| R5 `r5_currency_840` | WARN | 0 | 21,939 `USD` values, all standardised to `840` before the check | ✓ |
| R6 / R7 MCC / country present | WARN | 112,260 / 55,630 | blank-value messiness (includes duplicate copies) | ✓ |
| R8 `r8_auth_ref_not_null` | DROP → quarantine | 0 | guard | ✓ |
| R9 `r9_code_mapped` | WARN → `UNMAPPED` | 222 | DQ5 = 222 rows, 12 codes | ✓ |
| R10 `r10_file_on_time` | WARN | 77,545 rows | DQ9: the 3 late Atlas files | ✓ |
| R11 / R15 / R16 | FAIL | 0 | guards | ✓ |
| R12 `r12_mrd_merchant_id_matches` | WARN | 0 | DQ6: 5,840 merchants use a different ID format; **normalisation resolved all of them** | ✓ |
| R13 `r13_mcc_matches_master` | WARN | 210,084 rows | DQ10: 776 merchants with a stale MCC | ✓ |
| R14 `r14_network_response_found` | WARN | 441 | DQ8: the truncated Atlas file is missing 442 rows; 1 of those issuer rows was itself quarantined | ✓ |
| R17 `r17_file_reconciled` | WARN | 1 file | DQ8: the expected BREAK | ✓ |

## Quarantine (planted bad records, with reasons)

| source_system | reason | rows |
|---|---|---|
| iss_auth | r2_valid_amount | 33715 |
| iss_auth | r3_ts_not_future | 11059 |
| iss_auth | r1_auth_id_not_null | 10839 |

Samples (two per reason, raw values as landed):

| reason | business_date | record_key | record_json | _file_name |
|---|---|---|---|---|
| r1_auth_id_not_null | 2026-03-09 |  | {"auth_ts_raw":"2026-03-09 20:16:31","amount_raw":"71.57","card_ref":"CR15616966","merchant_num":"MR110644369","network":"MRD","auth_decision":"A","iss_resp_cd":"00"} | ISSAUTH_20260309_202603100030.csv |
| r1_auth_id_not_null | 2026-03-09 |  | {"auth_ts_raw":"2026-03-09 20:42:18","amount_raw":"73.82","card_ref":"CR75676345","merchant_num":"MR235843759","network":"MRD","auth_decision":"A","iss_resp_cd":"00"} | ISSAUTH_20260309_202603100030.csv |
| r2_valid_amount | 2025-11-20 | A20251120000096 | {"auth_id":"A20251120000096","auth_ts_raw":"2025-11-20 07:22:25","amount_raw":"0.00","card_ref":"CR98573124","merchant_num":"MR221542045","network":"ATL","auth_decision":"A","iss_resp_cd":"00"} | ISSAUTH_20251120_202511210030.csv |
| r2_valid_amount | 2025-11-20 | A20251120000480 | {"auth_id":"A20251120000480","auth_ts_raw":"2025-11-20 22:29:52","amount_raw":"0.00","card_ref":"CR99038471","merchant_num":"MR007356852","network":"ATL","auth_decision":"A","iss_resp_cd":"00"} | ISSAUTH_20251120_202511210030.csv |
| r3_ts_not_future | 2025-11-20 | A20251120000487 | {"auth_id":"A20251120000487","auth_ts_raw":"2026-11-20 22:36:20","amount_raw":"62.55","card_ref":"CR51099574","merchant_num":"MR220583846","network":"ATL","auth_decision":"A","iss_resp_cd":"00"} | ISSAUTH_20251120_202511210030.csv |
| r3_ts_not_future | 2025-11-20 | A20251120001211 | {"auth_id":"A20251120001211","auth_ts_raw":"2026-11-20 10:43:12","amount_raw":"60.60","card_ref":"CR42161988","merchant_num":"MR120653985","network":"ATL","auth_decision":"A","iss_resp_cd":"00"} | ISSAUTH_20251120_202511210030.csv |

## Reconciliation (`recon_file_control`, control totals vs landed / loaded / quarantined)

| system | status | files | control_rows | landed | loaded | quarantined | dups_superseded |
|---|---|---|---|---|---|---|---|
| acquirer_ref | RECONCILED | 14 | 1120 | 1120 | 1120 | 0 |  |
| atl_daily | BREAK | 1 | 24376 | 23934 | 23934 | 0 |  |
| atl_daily | RECONCILED | 362 | 9821533 | 9821533 | 9821533 | 0 |  |
| card_portfolio | RECONCILED | 28 | 54459 | 54459 | 54459 | 0 |  |
| iss_auth | RECONCILED | 363 | 11208018 | 11208018 | 11152405 | 55613 | 218544 |
| merchant_master | RECONCILED | 363 | 58100 | 58100 | 58100 | 0 |  |
| mrd_events | RECONCILED | 310 | 1142716 | 1142716 | 1142716 | 0 |  |

The only BREAK is the expected one:

| system | business_date | file_name | control_count | landed_rows | loaded_rows | quarantined_rows | control_amount | landed_amount | break_reason |
|---|---|---|---|---|---|---|---|---|---|
| atl_daily | 2026-08-05 | ATL_DAILY_20260805_202608060600.txt | 24376 | 23934 | 23934 | 0 | 1942921.72 | 1912549.30 | COUNT_MISMATCH: control 24376 vs landed 23934 |

Late files detected (`hours_after_business_date` > 48):

| system | business_date | file_created_ts | hours_after_business_date |
|---|---|---|---|
| atl_daily | 2026-03-10 | 2026-03-12T06:00:00.000Z | 54 |
| atl_daily | 2026-06-17 | 2026-06-19T06:00:00.000Z | 54 |
| atl_daily | 2026-10-14 | 2026-10-16T06:00:00.000Z | 54 |

## Gold sanity check: wave 6 cohort, first 30 days (2026-09-08 → 10-07)

| wave_cohort | attempts | approval_pct | matched_baseline_pct | matched_gap_pp | unmatched_gap_pp | excess_declines | lost_spend |
|---|---|---|---|---|---|---|---|
| W6 | 28657 | 96.83 | 97.79 | 0.96 | 0.95 | 275.0 | 13194 |

The matched-baseline gap (0.96 pp) agrees with the generator's calibration (0.94–0.95 pp). Wave 6 is mostly domestic, so the matched and unmatched gaps are close. Lost spend is at prototype scale (1:270).

## Decline categories (`silver_auth`, declined attempts only)

| std_category | decline_type | n |
|---|---|---|
| ISSUER_LEGIT_NSF | ISSUER_LEGIT | 100442 |
| ISSUER_LEGIT_DNH | ISSUER_LEGIT | 53830 |
| ISSUER_LEGIT_FRAUD | ISSUER_LEGIT | 28267 |
| ISSUER_LEGIT_EXPIRED | ISSUER_LEGIT | 16572 |
| ISSUER_LEGIT_NOT_PERMITTED | ISSUER_LEGIT | 16299 |
| ISSUER_LEGIT_INVALID | ISSUER_LEGIT | 11749 |
| ISSUER_LEGIT_LIMIT | ISSUER_LEGIT | 9478 |
| SYSTEM_ERROR | ACCEPTANCE | 6339 |
| ACCEPTANCE_CONFIG | ACCEPTANCE | 3024 |
| TOKEN_PROVISIONING | ACCEPTANCE | 2316 |
| CARD_ON_FILE_STALE | ACCEPTANCE | 1654 |
| CROSS_BORDER_BLOCK | ACCEPTANCE | 958 |
| PROCESSOR_TIMEOUT | ACCEPTANCE | 602 |
| UNMAPPED | UNMAPPED | 220 |

`decline_type` separates **acceptance failures** (network-side and fixable) from **legitimate issuer declines**. The detection step will work from this split.

## Gold grain change (update `dd8da74e`, 2026-11-21, decision in DECISIONS.md)

| t | n | attempts |
|---|---|---|
| gold_auth_daily | 3124425 | 10933861 |
| gold_auth_hourly | 521871 | 10933861 |
| silver_auth | 10933861 | 10933861 |

Both gold tables sum to the same 10,933,861 attempts as `silver_auth`.

INC1 is visible in `gold_auth_daily`: Meridian, ACQ-017, e-commerce, acceptance-decline rate by day.

| business_date | attempts | acc_declines | cfg | acc_rate_pct |
|---|---|---|---|---|
| 2026-09-20 | 27 | 0 | 0 | 0.0 |
| 2026-09-21 | 30 | 0 | 0 | 0.0 |
| 2026-09-22 | 31 | 0 | 0 | 0.0 |
| 2026-09-23 | 28 | 0 | 0 | 0.0 |
| 2026-09-24 | 30 | 12 | 12 | 40.0 |
| 2026-09-25 | 30 | 19 | 19 | 63.3 |
| 2026-09-26 | 26 | 17 | 17 | 65.4 |
| 2026-09-27 | 18 | 7 | 6 | 38.9 |
| 2026-09-28 | 33 | 21 | 21 | 63.6 |
| 2026-09-29 | 24 | 17 | 17 | 70.8 |
| 2026-09-30 | 30 | 18 | 18 | 60.0 |
| 2026-10-01 | 30 | 17 | 16 | 56.7 |
| 2026-10-02 | 28 | 12 | 11 | 42.9 |
| 2026-10-03 | 32 | 17 | 17 | 53.1 |
| 2026-10-04 | 19 | 11 | 11 | 57.9 |
| 2026-10-05 | 29 | 16 | 16 | 55.2 |
| 2026-10-06 | 34 | 25 | 24 | 73.5 |
| 2026-10-07 | 21 | 11 | 11 | 52.4 |
| 2026-10-08 | 35 | 21 | 21 | 60.0 |
| 2026-10-09 | 36 | 1 | 1 | 2.8 |
| 2026-10-10 | 28 | 0 | 0 | 0.0 |
| 2026-10-11 | 23 | 0 | 0 | 0.0 |

The rate is 0% before 2026-09-24, 39–74% during the incident window, and back to about 0% after 2026-10-08. This is the answer-key window (INC1: 2026-09-24 → 10-08). It is shown here as a data check only; the detection method has not been built yet.
