# Evidence 03: Business results (gold answers)

Generated 2026-11-24T20:08:28Z by tools/generate_evidence.py from the live workspace.

Proves the business answers the VP of Payment Network Integration and the Director of Payment Network Operations need, computed live from the governed gold tables: the approval gap of migrated cards vs a matched legacy baseline, the spend lost to excess declines, the incidents turned into cases, and the GO/HOLD readiness gate for the next migration waves. All data is synthetic. 'Lost spend' is purchase volume not recovered (a Finance assumption by segment), not bank revenue.

## Headline: migrated cards vs matched baseline, last 30 days of data

| from_date | to_date | migrated_attempts | migrated_approval_rate_pct | matched_baseline_rate_pct | gap_pp | excess_declines | lost_spend_usd |
|---|---|---|---|---|---|---|---|
| 2026-10-21 | 2026-11-19 | 172920 | 95.94 | 97.58 | 1.64 | 2844.0 | 107948.23 |


## Gap by migration wave cohort, last 30 days

| wave_cohort | migrated_attempts | gap_pp | excess_declines | lost_spend_usd |
|---|---|---|---|---|
| W1 | 28502 | 1.3 | 371.0 | 13243.93 |
| W2 | 28752 | 1.46 | 419.0 | 15835.65 |
| W3 | 28952 | 1.56 | 451.0 | 16346.85 |
| W4 | 28681 | 1.47 | 420.0 | 13125.38 |
| W5 | 28934 | 2.15 | 621.0 | 26206.99 |
| W6 | 29099 | 1.93 | 562.0 | 23189.43 |


## Matched vs unmatched baseline, last 30 days (why the matching matters)

| gap_vs_matched_baseline_pp | gap_vs_unmatched_baseline_pp |
|---|---|
| 1.64 | 1.62 |


## Monthly trend (whole history)

| month | migrated_attempts | gap_pp | lost_spend_usd |
|---|---|---|---|
| 2026-01 | 19957 | 0.7 | 5301.05 |
| 2026-02 | 34101 | 0.63 | 7513.74 |
| 2026-03 | 63558 | 0.61 | 10827.29 |
| 2026-04 | 80195 | 0.64 | 17187.60 |
| 2026-05 | 95250 | 0.65 | 19308.33 |
| 2026-06 | 119521 | 0.67 | 26617.76 |
| 2026-07 | 134514 | 0.66 | 28742.73 |
| 2026-08 | 149285 | 0.67 | 38036.18 |
| 2026-09 | 164425 | 0.77 | 52452.53 |
| 2026-10 | 179422 | 0.87 | 84947.15 |
| 2026-11 | 108572 | 2.21 | 88581.15 |


## Acceptance declines on the acquired network by standard category, last 30 days

| attempts | acceptance_declines | acceptance_config | token_provisioning | cross_border_block | card_on_file_stale | processor_timeout | system_error | unmapped |
|---|---|---|---|---|---|---|---|---|
| 172920 | 3087 | 431 | 391 | 131 | 1312 | 602 | 220 | 33 |


## Top acquirers by acceptance declines on the acquired network, last 14 days

| acquirer_id | acquirer_name | attempts | acceptance_declines | acceptance_decline_rate_pct |
|---|---|---|---|---|
| ACQ-001 | Northgate Merchant Services | 12867 | 302 | 2.35 |
| ACQ-002 | Clearpath Merchant Services | 7009 | 184 | 2.63 |
| ACQ-003 | Bayside Merchant Services | 4814 | 132 | 2.74 |
| ACQ-004 | Keystone Merchant Services | 3757 | 85 | 2.26 |
| ACQ-005 | Lakemont Merchant Services | 3201 | 76 | 2.37 |
| ACQ-007 | Summitline Merchant Services | 2314 | 55 | 2.38 |
| ACQ-009 | Harborpoint Merchant Services | 1831 | 51 | 2.79 |
| ACQ-008 | Crestwave Merchant Services | 2076 | 50 | 2.41 |
| ACQ-006 | Ridgeview Merchant Services | 2682 | 46 | 1.72 |
| ACQ-012 | Eastfield Merchant Services | 1427 | 44 | 3.08 |


## Cases (incidents grouped into episodes; status from Lakebase via the back-sync)

| case_id | root_cause | issuer_segment | region_scope | episode_start | episode_end | n_flags | max_score | severity | exposure_usd | status | owner_team | resolution_code | recovered_spend_usd |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | CROSS_BORDER_BLOCK | OWN | INTL | 2026-10-12 | 2026-10-20 | 21 | 90.1 | HIGH | 19314.88 | CLAIMED | Network Integration |  |  |
| 2 | CARD_ON_FILE_STALE | THIRD_PARTY | SE | 2026-11-02 | 2026-11-09 | 23 | 87.73 | HIGH | 4100.3 | OPEN | Card Technology |  |  |
| 3 | CARD_ON_FILE_STALE | OWN | ALL | 2026-11-02 | 2026-11-12 | 138 | 92.83 | HIGH | 36968.09 | IN_PROGRESS | Card Technology |  |  |
| 4 | ACCEPTANCE_CONFIG | OWN | ALL | 2026-01-12 | 2026-01-12 | 2 | 62.29 | MEDIUM | 288.46 | OPEN | Acquirer Relations |  |  |
| 5 | PROCESSOR_TIMEOUT | OWN | SE | 2026-11-14 | 2026-11-16 | 40 | 92.5 | HIGH | 16056.23 | CLAIMED | Network Operations |  |  |
| 6 | ACCEPTANCE_CONFIG | OWN | ALL | 2026-09-24 | 2026-10-08 | 21 | 88.54 | HIGH | 12515.42 | OPEN | Acquirer Relations |  |  |
| 7 | PROCESSOR_TIMEOUT | THIRD_PARTY | SE | 2026-11-14 | 2026-11-16 | 9 | 84.92 | HIGH | 1580.69 | OPEN | Network Operations |  |  |


| cases | open_cases | open_high | open_exposure_usd |
|---|---|---|---|
| 7 | 7 | 6 | 90824.07 |


## Wave readiness gate (GO only if the segment gap ≤ 0.3 pp and no HIGH case is open)

| wave_id | planned_migration_date | segments | go | hold | cards | expected_daily_attempts | at_risk_declines_per_day | at_risk_spend_usd_per_day | as_of_date |
|---|---|---|---|---|---|---|---|---|---|
| 7 | 2027-02-18 | 8 | 0 | 8 | 1500 | 979.0 | 33.0 | 1304.54 | 2026-11-19 |
| 8 | 2027-04-15 | 8 | 0 | 8 | 1500 | 968.0 | 32.1 | 1321.92 | 2026-11-19 |
| 9 | 2027-06-10 | 8 | 0 | 8 | 1500 | 955.0 | 31.9 | 1309.02 | 2026-11-19 |
| 10 | 2027-08-05 | 8 | 0 | 8 | 1500 | 961.0 | 32.7 | 1317.09 | 2026-11-19 |


Wave 7 detail:

| card_segment | issuer_segment | cards | expected_daily_attempts | segment_gap_pp_14d | open_high_cases | gate | gate_reason | at_risk_declines_per_day | at_risk_spend_usd_per_day |
|---|---|---|---|---|---|---|---|---|---|
| ECOM_HEAVY | OWN | 434 | 279.0 | 2.48 | 4 | HOLD | approval gap 2.48 pp > 0.3 pp limit; 4 HIGH-severity case(s) open | 6.9 | 364.77 |
| RECURRING_HEAVY | OWN | 376 | 241.0 | 5.07 | 4 | HOLD | approval gap 5.07 pp > 0.3 pp limit; 4 HIGH-severity case(s) open | 12.2 | 334.41 |
| WALLET_HEAVY | OWN | 318 | 208.0 | 3.13 | 4 | HOLD | approval gap 3.13 pp > 0.3 pp limit; 4 HIGH-severity case(s) open | 6.5 | 236.85 |
| INTL_TRAVELER | OWN | 228 | 151.0 | 2.63 | 4 | HOLD | approval gap 2.63 pp > 0.3 pp limit; 4 HIGH-severity case(s) open | 4.0 | 225.07 |
| ECOM_HEAVY | THIRD_PARTY | 53 | 34.0 | 3.33 | 2 | HOLD | approval gap 3.33 pp > 0.3 pp limit; 2 HIGH-severity case(s) open | 1.1 | 62.16 |
| INTL_TRAVELER | THIRD_PARTY | 24 | 17.0 | 3.1 | 2 | HOLD | approval gap 3.10 pp > 0.3 pp limit; 2 HIGH-severity case(s) open | 0.5 | 30.9 |
| RECURRING_HEAVY | THIRD_PARTY | 36 | 26.0 | 4.16 | 2 | HOLD | approval gap 4.16 pp > 0.3 pp limit; 2 HIGH-severity case(s) open | 1.1 | 30.57 |
| WALLET_HEAVY | THIRD_PARTY | 31 | 21.0 | 2.73 | 2 | HOLD | approval gap 2.73 pp > 0.3 pp limit; 2 HIGH-severity case(s) open | 0.6 | 19.8 |


## Recovery assumptions used for lost spend (Finance reference table)

| segment | unrecovered_rate | version | effective_dt | source | _source_file |
|---|---|---|---|---|---|
| DEFAULT | 0.450 | v1 | 2026-01-01 | Finance estimate (synthetic) | dbfs:/Volumes/classic_stable_zjnu75_catalog/network_migration/landing/ref/2025-11-20/RECOVERY_ASSUMPTIONS_v1.csv |
| DOMESTIC | 0.400 | v1 | 2026-01-01 | Finance estimate (synthetic) | dbfs:/Volumes/classic_stable_zjnu75_catalog/network_migration/landing/ref/2025-11-20/RECOVERY_ASSUMPTIONS_v1.csv |
| ECOM_HEAVY | 0.550 | v1 | 2026-01-01 | Finance estimate (synthetic) | dbfs:/Volumes/classic_stable_zjnu75_catalog/network_migration/landing/ref/2025-11-20/RECOVERY_ASSUMPTIONS_v1.csv |
| INTL_TRAVELER | 0.600 | v1 | 2026-01-01 | Finance estimate (synthetic) | dbfs:/Volumes/classic_stable_zjnu75_catalog/network_migration/landing/ref/2025-11-20/RECOVERY_ASSUMPTIONS_v1.csv |
| RECURRING_HEAVY | 0.350 | v1 | 2026-01-01 | Finance estimate (synthetic) | dbfs:/Volumes/classic_stable_zjnu75_catalog/network_migration/landing/ref/2025-11-20/RECOVERY_ASSUMPTIONS_v1.csv |
| WALLET_HEAVY | 0.450 | v1 | 2026-01-01 | Finance estimate (synthetic) | dbfs:/Volumes/classic_stable_zjnu75_catalog/network_migration/landing/ref/2025-11-20/RECOVERY_ASSUMPTIONS_v1.csv |
