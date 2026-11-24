# Evidence 02: Data quality and completeness

Generated 2026-11-24T20:08:20Z by tools/generate_evidence.py from the live workspace.

Proves that every planted data-quality issue in the synthetic files was caught by a named rule and counted, by comparing the generator's answer key with what the pipeline actually quarantined, flagged or reconciled; and that every source file was reconciled against its control totals, with the one planted truncated file shown as a BREAK. 'match' is computed, not asserted.

## Planted (answer key) vs observed (pipeline)

Answer key: `/Volumes/classic_stable_zjnu75_catalog/network_migration/landing/_generator_truth/answer_key.json`, landed dates 2025-11-20 → 2026-11-19 (365 days).

| finding | planted | observed | rule / mechanism | result |
|---|---|---|---|---|
| DQ1 duplicate re-sent auths landed (rows beyond the first per AUTH_ID, bronze) | 220704 | 220704 | counted in bronze | match |
| DQ1 … removed before gold | 220704 | 220704 | dedup in silver (219854) + re-sent copies of bad rows quarantined by a DROP rule (850) | match |
| DQ2 bad amounts | 33904 | 33904 | r2_valid_amount DROP → quarantine | match |
| DQ3 future timestamps | 11105 | 11105 | r3_ts_not_future DROP → quarantine | match |
| DQ4 null AUTH_ID | 10897 | 10897 | r1_auth_id_not_null DROP → quarantine | match |
| DQ5 unmapped Meridian codes (rows) | 222 | 222 | r9_code_mapped WARN → UNMAPPED | match |
| DQ5 unmapped Meridian codes (codes) | M201,M202,M203,M204,M205,M206,M207,M208,M209,M210,M211,M212 | M201,M202,M203,M204,M205,M206,M207,M208,M209,M210,M211,M212 | same | match |
| DQ6 Meridian merchant ID variants (merchants seen) | 5840 | 5840 | normalised in silver; r12 failed after normalisation = 0 | match |
| DQ7 card updates out of sequence | 186 | 186 | AUTO CDC SCD2 SEQUENCE BY update_ts (bronze rows − silver versions) | match |
| DQ8 truncated file | atl_daily/2026-08-05 missing 442 | atl_daily/2026-08-05 missing 442 | r17_file_reconciled WARN + recon BREAK | match |
| DQ9 late legacy files | atl_daily/2026-03-10,atl_daily/2026-06-17,atl_daily/2026-10-14 | atl_daily/2026-03-10 +54h,atl_daily/2026-06-17 +54h,atl_daily/2026-10-14 +54h | r10_file_on_time WARN + as-of timing rule | see list |
| DQ10 stale MCC (merchants) | 776 | 776 | r13_mcc_matches_master WARN | match |


## Quarantine (rows removed by DROP rules, kept with the reason)

| source_system | reason | rows | first_day | last_day |
|---|---|---|---|---|
| iss_auth | r1_auth_id_not_null | 10897 | 2025-11-20 | 2026-11-19 |
| iss_auth | r2_valid_amount | 33904 | 2025-11-20 | 2026-11-19 |
| iss_auth | r3_ts_not_future | 11105 | 2025-11-20 | 2026-11-19 |


One quarantined record per reason, verbatim (raw record as landed):

| reason | record |
|---|---|
| r1_auth_id_not_null | {"auth_ts_raw":"2025-11-20 06:00:44","amount_raw":"64.94","card_ref":"CR10952746","merchant_num":"MR050943028","network":"ATL","auth_decision":"A","iss_resp_cd":"00"} |
| r2_valid_amount | {"auth_id":"A20251120000096","auth_ts_raw":"2025-11-20 07:22:25","amount_raw":"0.00","card_ref":"CR98573124","merchant_num":"MR221542045","network":"ATL","auth_decision":"A","iss_resp_cd":"00"} |
| r3_ts_not_future | {"auth_id":"A20251120000487","auth_ts_raw":"2026-11-20 22:36:20","amount_raw":"62.55","card_ref":"CR51099574","merchant_num":"MR220583846","network":"ATL","auth_decision":"A","iss_resp_cd":"00"} |


## File reconciliation (`recon_file_control`: manifest control totals vs landed rows)

| system | status | files | business_days | first_day | last_day | control_rows | landed_rows | quarantined_rows | duplicates_superseded | max_hours_late |
|---|---|---|---|---|---|---|---|---|---|---|
| acquirer_ref | RECONCILED | 14 | 14 | 2025-11-20 | 2026-11-01 | 1120 | 1120 | 0 |  | 28 |
| atl_daily | BREAK | 1 | 1 | 2026-08-05 | 2026-08-05 | 24376 | 23934 | 0 |  | 30 |
| atl_daily | RECONCILED | 364 | 364 | 2025-11-20 | 2026-11-19 | 9868642 | 9868642 | 0 |  | 54 |
| card_portfolio | RECONCILED | 28 | 28 | 2025-11-20 | 2026-09-18 | 54459 | 54459 | 0 |  | 28 |
| iss_auth | RECONCILED | 365 | 365 | 2025-11-20 | 2026-11-19 | 11268310 | 11268310 | 55906 | 219854 | 24 |
| merchant_master | RECONCILED | 365 | 365 | 2025-11-20 | 2026-11-19 | 58200 | 58200 | 0 |  | 28 |
| mrd_events | RECONCILED | 312 | 312 | 2026-01-12 | 2026-11-19 | 1154588 | 1154588 | 0 |  | 24 |


Files not RECONCILED, or delivered more than 30 hours after the business date:

| system | business_date | file_name | file_created_ts | hours_after_business_date | control_count | landed_rows | control_amount | landed_amount | amount_diff | status | break_reason |
|---|---|---|---|---|---|---|---|---|---|---|---|
| atl_daily | 2026-03-10 | ATL_DAILY_20260310_202603120600.txt | 2026-03-12T06:00:00.000Z | 54 | 28154 | 28154 | 2201679.39 | 2201679.39 | 0.00 | RECONCILED |  |
| atl_daily | 2026-06-17 | ATL_DAILY_20260617_202606190600.txt | 2026-06-19T06:00:00.000Z | 54 | 26246 | 26246 | 2102036.23 | 2102036.23 | 0.00 | RECONCILED |  |
| atl_daily | 2026-08-05 | ATL_DAILY_20260805_202608060600.txt | 2026-08-06T06:00:00.000Z | 30 | 24376 | 23934 | 1942921.72 | 1912549.30 | 30372.42 | BREAK | COUNT_MISMATCH: control 24376 vs landed 23934 |
| atl_daily | 2026-10-14 | ATL_DAILY_20261014_202610160600.txt | 2026-10-16T06:00:00.000Z | 54 | 23145 | 23145 | 1859966.48 | 1859966.48 | 0.00 | RECONCILED |  |


## Completeness: business days with data, per source (expected 365 daily days 2025-11-20 → 2026-11-19)

| source | days | first_day | last_day |
|---|---|---|---|
| issuer auths (silver_issuer_auth) | 365 | 2025-11-20 | 2026-11-19 |
| network responses MRD | 312 | 2026-01-12 | 2026-11-19 |
| network responses ATL | 365 | 2025-11-20 | 2026-11-19 |
| gold_auth_daily | 365 | 2025-11-20 | 2026-11-19 |


Meridian (MRD) has fewer days because the acquired network starts carrying traffic with migration wave 1; the first and last MRD day are shown above. Calendar gaps inside the gold range:

| first_day | last_day | calendar_days | days_with_data | missing_days |
|---|---|---|---|---|
| 2025-11-20 | 2026-11-19 | 365 | 365 | 0 |
