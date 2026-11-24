# Evidence 01: Lakeflow pipeline run and expectation metrics

Generated 2026-11-24T20:08:10Z by tools/generate_evidence.py from the live workspace.

Proves that the Lakeflow Spark Declarative Pipeline `febar_pipeline` ran inside the final orchestrated job run `143622898422721`, which flows it wrote, and how many records passed or failed each data-quality expectation (from the pipeline event log). It also shows the rows per table, a duplicate check on the conformed auth table, and that the ingest-free second update read zero new files.

## Pipeline definition (Pipelines API)

| item | value |
|---|---|
| name | febar_pipeline |
| pipeline_id | 9f46a185-fb6f-4e70-be6f-a4742066453b |
| serverless | True |
| continuous | False |
| channel | CURRENT |
| publishes to | classic_stable_zjnu75_catalog.network_migration |
| libraries | 01_bronze.sql; 02_silver.sql; 03_manifests.py; 03_reconciliation.sql; 04_gold.sql; 05_scores.sql |
| configuration keys | landing_path, pipelines.numUpdateRetryAttempts |
| state | IDLE |
| health |  |


## Updates in the final job run `143622898422721`

| job task | update_id | started | ended | seconds | final_state |
|---|---|---|---|---|---|
| refresh_pipeline | 76a63700-3ea5-449b-a2b4-f6581744e4f4 | 2026-11-23T17:44:10.832Z | 2026-11-23T17:47:45.453Z | 215.0 | COMPLETED |
| settle_pipeline | bdb37d30-faf7-44d4-a541-7b9e81022323 | 2026-11-23T17:47:54.631Z | 2026-11-23T17:52:00.025Z | 245.0 | COMPLETED |


## Rows written per flow, update `76a63700-3ea5-449b-a2b4-f6581744e4f4` (task `refresh_pipeline`)

| flow | final_status | output_rows | upserted_rows | deleted_rows |
|---|---|---|---|---|
| auth_detail |  | 1724941 | 0 | 0 |
| bronze_acquirer_ref | COMPLETED | 0 | 0 | 0 |
| bronze_atl_daily | COMPLETED | 0 | 0 | 0 |
| bronze_card_portfolio | COMPLETED | 0 | 0 | 0 |
| bronze_file_manifests |  | 1449 | 0 | 0 |
| bronze_issuer_auth | COMPLETED | 0 | 0 | 0 |
| bronze_merchant_master | COMPLETED | 0 | 0 | 0 |
| bronze_mrd_events | COMPLETED | 0 | 0 | 0 |
| chk_response_code_map |  | 1 | 0 | 0 |
| f_network_atl | COMPLETED | 0 | 0 | 0 |
| f_network_mrd | COMPLETED | 0 | 0 | 0 |
| f_silver_cards |  | 0 | 0 | 0 |
| gold_anomaly_scores |  | 119500 | 0 | 0 |
| gold_auth_daily |  | 3145086 | 0 | 0 |
| gold_auth_hourly |  | 525113 | 0 | 0 |
| gold_baseline_gap |  | 140753 | 0 | 0 |
| pipelines.flowTimeMetrics.missingFlowName |  | 0 | 0 | 0 |
| q_issuer_auth | COMPLETED | 0 | 0 | 0 |
| q_network_atl | COMPLETED | 0 | 0 | 0 |
| q_network_mrd | COMPLETED | 0 | 0 | 0 |
| recon_file_control |  | 1449 | 0 | 0 |
| ref_recovery_assumptions |  | 6 | 0 | 0 |
| ref_response_code_map |  | 134 | 0 | 0 |
| silver_acquirers | COMPLETED | 80 | 0 | 0 |
| silver_auth |  | 10992550 | 0 | 0 |
| silver_issuer_auth | COMPLETED | 10992550 | 0 | 0 |
| silver_merchants | COMPLETED | 40000 | 0 | 0 |
| stg_cards |  | 0 | 0 | 0 |
| stg_issuer_auth | COMPLETED | 0 | 0 | 0 |


## Rows written per flow, update `bdb37d30-faf7-44d4-a541-7b9e81022323` (task `settle_pipeline`)

| flow | final_status | output_rows | upserted_rows | deleted_rows |
|---|---|---|---|---|
| auth_detail |  | 1724941 | 0 | 0 |
| bronze_acquirer_ref | COMPLETED | 0 | 0 | 0 |
| bronze_atl_daily | COMPLETED | 0 | 0 | 0 |
| bronze_card_portfolio | COMPLETED | 0 | 0 | 0 |
| bronze_file_manifests |  | 1449 | 0 | 0 |
| bronze_issuer_auth | COMPLETED | 0 | 0 | 0 |
| bronze_merchant_master | COMPLETED | 0 | 0 | 0 |
| bronze_mrd_events | COMPLETED | 0 | 0 | 0 |
| chk_response_code_map |  | 1 | 0 | 0 |
| f_network_atl | COMPLETED | 0 | 0 | 0 |
| f_network_mrd | COMPLETED | 0 | 0 | 0 |
| f_silver_cards |  | 0 | 0 | 0 |
| gold_anomaly_scores |  | 119500 | 0 | 0 |
| gold_auth_daily |  | 3145086 | 0 | 0 |
| gold_auth_hourly |  | 525113 | 0 | 0 |
| gold_baseline_gap |  | 140753 | 0 | 0 |
| pipelines.flowTimeMetrics.missingFlowName |  | 0 | 0 | 0 |
| q_issuer_auth | COMPLETED | 0 | 0 | 0 |
| q_network_atl | COMPLETED | 0 | 0 | 0 |
| q_network_mrd | COMPLETED | 0 | 0 | 0 |
| recon_file_control |  | 1449 | 0 | 0 |
| ref_recovery_assumptions |  | 6 | 0 | 0 |
| ref_response_code_map |  | 134 | 0 | 0 |
| silver_acquirers | COMPLETED | 80 | 0 | 0 |
| silver_auth |  | 10992550 | 0 | 0 |
| silver_issuer_auth | COMPLETED | 10992550 | 0 | 0 |
| silver_merchants | COMPLETED | 40000 | 0 | 0 |
| stg_cards |  | 0 | 0 | 0 |
| stg_issuer_auth | COMPLETED | 0 | 0 | 0 |


## Expectations evaluated in update `76a63700-3ea5-449b-a2b4-f6581744e4f4` (records checked in this update)

| flow | expectation | passed | failed |
|---|---|---|---|
| silver_merchants | r11_merchant_num_not_null | 40000 | 0 |
| silver_auth | r12_mrd_merchant_id_matches | 10992550 | 0 |
| silver_auth | r13_mcc_matches_master | 10781327 | 211223 |
| silver_auth | r14_network_response_found | 10992109 | 441 |
| chk_response_code_map | r16_map_not_empty | 1 | 0 |
| chk_response_code_map | r16_map_unique_codes | 1 | 0 |
| recon_file_control | r17_file_reconciled | 1448 | 1 |


## Expectations over the pipeline's whole history

Streaming tables (`stg_*`, `f_network_*`, `stg_cards`) check each landed record once, so their sums are the records ever checked. Materialized views (`silver_auth`, `silver_merchants`, `recon_file_control`, `chk_*`) recompute, so for them the last column (latest update) is the meaningful one.

| flow | expectation | updates | passed_all_updates | failed_all_updates | passed_latest | failed_latest |
|---|---|---|---|---|---|---|
| f_network_mrd | r10_file_on_time | 2 | 1154588 | 0 | 11872 | 0 |
| f_network_atl | r10_file_on_time | 2 | 9815031 | 77545 | 47109 | 0 |
| silver_merchants | r11_merchant_num_not_null | 14 | 560000 | 0 | 40000 | 0 |
| silver_auth | r12_mrd_merchant_id_matches | 14 | 153250121 | 0 | 10992550 | 0 |
| silver_auth | r13_mcc_matches_master | 14 | 150305528 | 2944593 | 10781327 | 211223 |
| silver_auth | r14_network_response_found | 14 | 153243947 | 6174 | 10992109 | 441 |
| stg_cards | r15_card_ref_not_null | 1 | 54459 | 0 | 54459 | 0 |
| chk_response_code_map | r16_map_not_empty | 14 | 14 | 0 | 1 | 0 |
| chk_response_code_map | r16_map_unique_codes | 14 | 14 | 0 | 1 | 0 |
| recon_file_control | r17_file_reconciled | 14 | 18752 | 13 | 1448 | 1 |
| stg_issuer_auth | r1_auth_id_not_null | 2 | 11257413 | 10897 | 60234 | 58 |
| stg_issuer_auth | r2_valid_amount | 2 | 11234406 | 33904 | 60103 | 189 |
| stg_issuer_auth | r3_ts_not_future | 2 | 11257205 | 11105 | 60246 | 46 |
| stg_issuer_auth | r4_valid_decision_network | 2 | 11268310 | 0 | 60292 | 0 |
| stg_issuer_auth | r5_currency_840 | 2 | 11268310 | 0 | 60292 | 0 |
| stg_issuer_auth | r6_mcc_present | 2 | 11155411 | 112899 | 59653 | 639 |
| stg_issuer_auth | r7_term_country_present | 2 | 11212368 | 55942 | 59980 | 312 |
| f_network_mrd | r8_auth_ref_not_null | 2 | 1154588 | 0 | 11872 | 0 |
| f_network_atl | r8_auth_ref_not_null | 2 | 9892576 | 0 | 47109 | 0 |
| f_network_atl | r9_code_mapped | 2 | 9892576 | 0 | 47109 | 0 |
| f_network_mrd | r9_code_mapped | 2 | 1154366 | 222 | 11872 | 0 |


## Rows per table (now)

| table_name | rows |
|---|---|
| silver_cards | 54273 |
| gold_auth_daily | 3145086 |
| gold_auth_hourly | 525113 |
| gold_baseline_gap | 140753 |
| gold_anomaly_scores | 119500 |
| gold_anomalies | 254 |
| gold_case_status | 7 |
| gold_wave_readiness | 32 |
| bronze_issuer_auth | 11268310 |
| bronze_mrd_events | 1154588 |
| bronze_atl_daily | 9892576 |
| bronze_merchant_master | 58200 |
| bronze_card_portfolio | 54459 |
| bronze_acquirer_ref | 1120 |
| bronze_file_manifests | 1449 |
| ref_response_code_map | 134 |
| ref_recovery_assumptions | 6 |
| silver_issuer_auth | 10992550 |
| silver_network_response | 11047164 |
| silver_merchants | 40000 |
| silver_acquirers | 80 |
| silver_auth | 10992550 |
| quarantine_auth | 55906 |
| recon_file_control | 1449 |


## Duplicate check on the conformed auth table

| rows | distinct_auth_id | duplicate_rows | null_auth_id |
|---|---|---|---|
| 10992550 | 10992550 | 0 | 0 |


## Data landed vs data in gold

| latest_landed_business_date | latest_gold_business_date | gold_days | last_ingest_ts |
|---|---|---|---|
| 2026-11-19 | 2026-11-19 | 365 | 2026-11-23T16:36:18.734Z |
