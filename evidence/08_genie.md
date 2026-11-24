# Evidence 08: Genie benchmark comparison

Generated 2026-11-24T20:09:47Z by tools/generate_evidence.py from the live workspace.

Proves that the Genie space answers the sponsor's questions correctly: each benchmark question was asked through the Genie Conversation API during this generation run, and Genie's result rows were compared with a ground-truth SQL query run on the same warehouse at the same time. Match rule: every expected row is found in Genie's result (numbers equal within max(0.011, 0.5%), strings case-insensitive); 'exact' also requires the same number of rows.

## Space

| item | value |
|---|---|
| space_id | 01f1e710e2f1183284ccb47bc5215473 |
| title | Network migration: acceptance and readiness |
| warehouse_id | 34e45919b39491cf |
| tables | gold_anomalies, gold_auth_daily, gold_baseline_gap, gold_case_status, gold_wave_readiness |
| text instructions | 1 |
| example SQL | 4 |
| join specs | 2 |
| benchmarks stored in the space | 8 |


## Result: 8/8 matched, 8/8 exact

| id | question | Genie status | seconds | expected rows found | match | exact |
|---|---|---|---|---|---|---|
| q01 | What was the approval rate for migrated cards vs the matched legacy baseline over the last 30 days, and the gap in percentage points? | COMPLETED | 17 | 1/1 | True | True |
| q03 | How much spend did we lose to excess declines on migrated cards in the last 30 days? | COMPLETED | 13 | 1/1 | True | True |
| q04 | What are the top 5 acquirers by acceptance declines on the acquired network in the last 14 days? | COMPLETED | 18 | 5/5 | True | True |
| q07 | What is the acceptance-decline rate for cross-border travel and lodging on the acquired network vs the legacy network over the last 60 days? | COMPLETED | 187 | 2/2 | True | True |
| q08 | How did ACQ-017's e-commerce acceptance-decline rate on the acquired network change before, during and after 24 September to 8 October 2026? | COMPLETED | 18 | 3/3 | True | True |
| q13 | What is the latest business date loaded for each network, and on how many of the last 30 days do we have acquired-network data? | COMPLETED | 17 | 2/2 | True | True |
| q14 | Is wave 7 ready to launch? Show the gate result and the reason for each card segment. | COMPLETED | 13 | 8/8 | True | True |
| q15 | How much transaction volume in wave 7 is at risk, by card segment? | COMPLETED | 17 | 4/4 | True | True |


### q01: What was the approval rate for migrated cards vs the matched legacy baseline over the last 30 days, and the gap in percentage points?

Ground truth SQL:

```sql
SELECT round(100 * sum(migrated_approvals) / sum(migrated_attempts), 2) AS migrated_approval_rate_pct,
       round(100 * sum(expected_approvals) / sum(migrated_attempts), 2) AS matched_baseline_approval_rate_pct,
       round(100 * (sum(expected_approvals) - sum(migrated_approvals)) / sum(migrated_attempts), 2) AS gap_pp
FROM classic_stable_zjnu75_catalog.network_migration.gold_baseline_gap
WHERE business_date > (SELECT date_sub(max(business_date), 30) FROM classic_stable_zjnu75_catalog.network_migration.gold_baseline_gap)
```

Expected rows:

| migrated_approval_rate_pct | matched_baseline_approval_rate_pct | gap_pp |
|---|---|---|
| 95.94 | 97.58 | 1.64 |


Genie SQL:

```sql
SELECT ROUND(try_divide(100 * SUM(`migrated_approvals`),SUM(`migrated_attempts`)), 2) AS `migrated_approval_rate_pct`, ROUND(try_divide(100 * SUM(`expected_approvals`),SUM(`migrated_attempts`)), 2) AS `matched_legacy_baseline_rate_pct`, ROUND(try_divide(100 * (SUM(`expected_approvals`) - SUM(`migrated_approvals`)),SUM(`migrated_attempts`)), 2) AS `gap_pp`, SUM(`migrated_attempts`) AS `migrated_attempts` FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_baseline_gap` WHERE `business_date` > (SELECT date_sub(MAX(`business_date`), 30) FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_baseline_gap`)
```

Genie rows:

| migrated_approval_rate_pct | matched_legacy_baseline_rate_pct | gap_pp | migrated_attempts |
|---|---|---|---|
| 95.94 | 97.58 | 1.64 | 172920 |


Genie text:

> Over the last 30 days in the data queried, **migrated cards** had an approval rate of **95.94%** versus a **matched legacy baseline** approval rate of **97.58%**, based on **172,920 migrated attempts**. The approval gap was **1.64 percentage points**, meaning migrated cards approved less than the matched legacy baseline over this period.


Expected rows found: 1/1 · match: **True** · exact: True


### q03: How much spend did we lose to excess declines on migrated cards in the last 30 days?

Ground truth SQL:

```sql
SELECT round(sum(lost_spend), 2) AS lost_spend_usd, round(sum(excess_declines), 1) AS excess_declines
FROM classic_stable_zjnu75_catalog.network_migration.gold_baseline_gap
WHERE business_date > (SELECT date_sub(max(business_date), 30) FROM classic_stable_zjnu75_catalog.network_migration.gold_baseline_gap)
```

Expected rows:

| lost_spend_usd | excess_declines |
|---|---|
| 107948.23 | 2844.4 |


Genie SQL:

```sql
SELECT SUM(`lost_spend`) AS `lost_spend_usd`, SUM(`excess_declines`) AS `excess_declines` FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_baseline_gap` WHERE `business_date` > (SELECT date_sub(MAX(`business_date`), 30) FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_baseline_gap`)
```

Genie rows:

| lost_spend_usd | excess_declines |
|---|---|
| 107948.23 | 2844.4097612736814 |


Genie text:

> In the last 30 business days covered by the data, migrated cards lost **$107,948.23** in spend due to excess declines. Over the same period, the result also shows **2,844.41** excess declines, which is the volume associated with the **$107,948.23** lost spend.


Expected rows found: 1/1 · match: **True** · exact: True


### q04: What are the top 5 acquirers by acceptance declines on the acquired network in the last 14 days?

Ground truth SQL:

```sql
SELECT acquirer_id, acquirer_name, sum(acceptance_declines) AS acceptance_declines
FROM classic_stable_zjnu75_catalog.network_migration.gold_auth_daily
WHERE network = 'MRD' AND business_date > (SELECT date_sub(max(business_date), 14) FROM classic_stable_zjnu75_catalog.network_migration.gold_auth_daily)
GROUP BY acquirer_id, acquirer_name ORDER BY acceptance_declines DESC LIMIT 5
```

Expected rows:

| acquirer_id | acquirer_name | acceptance_declines |
|---|---|---|
| ACQ-001 | Northgate Merchant Services | 302 |
| ACQ-002 | Clearpath Merchant Services | 184 |
| ACQ-003 | Bayside Merchant Services | 132 |
| ACQ-004 | Keystone Merchant Services | 85 |
| ACQ-005 | Lakemont Merchant Services | 76 |


Genie SQL:

```sql
WITH `acquirer_totals` AS (
  SELECT
    `acquirer_id`,
    `acquirer_name`,
    SUM(`acceptance_declines`) AS `acceptance_declines`,
    SUM(`attempts`) AS `attempts`,
    ROUND(try_divide(100 * SUM(`acceptance_declines`),SUM(`attempts`)), 2) AS `acceptance_decline_rate_pct`
  FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_auth_daily`
  WHERE `network` = 'MRD'
    AND `business_date` > (
      SELECT date_sub(MAX(`business_date`), 14)
      FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_auth_daily`
    )
    AND `acquirer_id` IS NOT NULL
    AND `acquirer_name` IS NOT NULL
  GROUP BY `acquirer_id`, `acquirer_name`
), `ranked_acquirers` AS (
  SELECT
    `acquirer_id`,
    `acquirer_name`,
    `acceptance_declines`,
    `attempts`,
    `acceptance_decline_rate_pct`,
    RANK() OVER (ORDER BY `acceptance_declines` DESC) AS `acquirer_rank`
  FROM `acquirer_totals`
)
SELECT
  `acquirer_rank`,
  `acquirer_id`,
  `acquirer_name`,
  `acceptance_declines`,
  `attempts`,
  `acceptance_decline_rate_pct`
FROM `ranked_acquirers`
WHERE `acquirer_rank` <= 5
ORDER BY `acquirer_rank`, `acquirer_id`
```

Genie rows:

| acquirer_rank | acquirer_id | acquirer_name | acceptance_declines | attempts | acceptance_decline_rate_pct |
|---|---|---|---|---|---|
| 1 | ACQ-001 | Northgate Merchant Services | 302 | 12867 | 2.35 |
| 2 | ACQ-002 | Clearpath Merchant Services | 184 | 7009 | 2.63 |
| 3 | ACQ-003 | Bayside Merchant Services | 132 | 4814 | 2.74 |
| 4 | ACQ-004 | Keystone Merchant Services | 85 | 3757 | 2.26 |
| 5 | ACQ-005 | Lakemont Merchant Services | 76 | 3201 | 2.37 |


Genie text:

> The top 5 acquirers by **acceptance declines** on the acquired network over the last 14 business days are:
> - **Northgate Merchant Services**: **302** declines from **12,867** attempts (**2.35%**)
> - **Clearpath Merchant Services**: **184** declines from **7,009** attempts (**2.63%**)
> - **Bayside Merchant Services**: **132** declines from **4,814** attempts (**2.74%**)
> - **Keystone Merchant Services**: **85** declines from **3,757** attempts (**2.26%**)
> - **Lakemont Merchant Services**: **76** declines from **3,201** attempts (**2.37%**)
> Across these 5 acquirers, **Northgate Merchant Services** has the highest decline count, while **Bayside Merchant Services** has the highest decline rate.


Expected rows found: 5/5 · match: **True** · exact: True


### q07: What is the acceptance-decline rate for cross-border travel and lodging on the acquired network vs the legacy network over the last 60 days?

Ground truth SQL:

```sql
SELECT network, round(100 * sum(acceptance_declines) / sum(attempts), 2) AS acceptance_decline_rate_pct, sum(attempts) AS attempts
FROM classic_stable_zjnu75_catalog.network_migration.gold_auth_daily
WHERE mcc_group = 'TRAVEL_LODGING' AND cross_border
  AND business_date > (SELECT date_sub(max(business_date), 60) FROM classic_stable_zjnu75_catalog.network_migration.gold_auth_daily)
GROUP BY network ORDER BY network
```

Expected rows:

| network | acceptance_decline_rate_pct | attempts |
|---|---|---|
| ATL | 0.04 | 25212 |
| MRD | 8.25 | 3685 |


Genie SQL:

```sql
SELECT gold_auth_daily.network, ROUND(100 * TRY_DIVIDE(SUM(gold_auth_daily.acceptance_declines), SUM(gold_auth_daily.attempts)), 2) AS acceptance_decline_rate_pct, SUM(gold_auth_daily.attempts) AS attempts, SUM(gold_auth_daily.acceptance_declines) AS acceptance_declines FROM classic_stable_zjnu75_catalog.network_migration.gold_auth_daily WHERE gold_auth_daily.business_date > (SELECT date_sub(MAX(gold_auth_daily.business_date), 60) FROM classic_stable_zjnu75_catalog.network_migration.gold_auth_daily) AND gold_auth_daily.network IN ('MRD', 'ATL') AND gold_auth_daily.cross_border = TRUE AND gold_auth_daily.mcc_group = 'TRAVEL_LODGING' AND gold_auth_daily.network IS NOT NULL GROUP BY gold_auth_daily.network ORDER BY gold_auth_daily.network
```

Genie rows:

| network | acceptance_decline_rate_pct | attempts | acceptance_declines |
|---|---|---|---|
| ATL | 0.04 | 25212 | 9 |
| MRD | 8.25 | 3685 | 304 |


Genie text:

> Over the last **60 business days** in cross-border **travel and lodging**, the acceptance-decline rate was **8.25%** on the acquired network (**MRD**) versus **0.04%** on the legacy network (**ATL**). That reflects **304** acceptance declines out of **3,685** attempts on MRD, compared with **9** out of **25,212** on ATL; across the 2 networks shown, MRD’s rate is markedly higher.


Expected rows found: 2/2 · match: **True** · exact: True


### q08: How did ACQ-017's e-commerce acceptance-decline rate on the acquired network change before, during and after 24 September to 8 October 2026?

Ground truth SQL:

```sql
SELECT CASE WHEN business_date < '2026-09-24' THEN '1_before' WHEN business_date <= '2026-10-08' THEN '2_during' ELSE '3_after' END AS period,
       round(100 * sum(acceptance_declines) / sum(attempts), 2) AS acceptance_decline_rate_pct, sum(attempts) AS attempts
FROM classic_stable_zjnu75_catalog.network_migration.gold_auth_daily
WHERE network = 'MRD' AND acquirer_id = 'ACQ-017' AND channel = 'ECOM' AND business_date BETWEEN '2026-09-10' AND '2026-10-22'
GROUP BY 1 ORDER BY 1
```

Expected rows:

| period | acceptance_decline_rate_pct | attempts |
|---|---|---|
| 1_before | 0.51 | 392 |
| 2_during | 57.52 | 419 |
| 3_after | 1.38 | 363 |


Genie SQL:

```sql
SELECT CASE WHEN `business_date` BETWEEN DATE '2026-09-10' AND DATE '2026-09-23' THEN '1_before' WHEN `business_date` BETWEEN DATE '2026-09-24' AND DATE '2026-10-08' THEN '2_during' WHEN `business_date` BETWEEN DATE '2026-10-09' AND DATE '2026-10-22' THEN '3_after' END AS `period`, ROUND(try_divide(100 * SUM(`acceptance_declines`),SUM(`attempts`)), 2) AS `acceptance_decline_rate_pct`, SUM(`attempts`) AS `attempts`, SUM(`acceptance_declines`) AS `acceptance_declines` FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_auth_daily` WHERE `network` = 'MRD' AND `acquirer_id` = 'ACQ-017' AND `channel` ILIKE '%ECOM%' AND `business_date` BETWEEN DATE '2026-09-10' AND DATE '2026-10-22' GROUP BY 1 ORDER BY 1
```

Genie rows:

| period | acceptance_decline_rate_pct | attempts | acceptance_declines |
|---|---|---|---|
| 1_before | 0.51 | 392 | 2 |
| 2_during | 57.52 | 419 | 241 |
| 3_after | 1.38 | 363 | 5 |


Genie text:

> ACQ-017’s e-commerce acceptance-decline rate on the acquired network rose sharply **from 0.51% before** 24 September–8 October 2026 **to 57.52% during** that period, then fell back **to 1.38% after**. In volume terms, that was **2 of 392** attempts before, **241 of 419** during, and **5 of 363** after, showing the issue was concentrated in the period itself.


Expected rows found: 3/3 · match: **True** · exact: True


### q13: What is the latest business date loaded for each network, and on how many of the last 30 days do we have acquired-network data?

Ground truth SQL:

```sql
SELECT network, max(business_date) AS latest_business_date,
       count(DISTINCT CASE WHEN business_date > (SELECT date_sub(max(business_date), 30) FROM classic_stable_zjnu75_catalog.network_migration.gold_auth_daily) THEN business_date END) AS days_with_data_last_30
FROM classic_stable_zjnu75_catalog.network_migration.gold_auth_daily GROUP BY network ORDER BY network
```

Expected rows:

| network | latest_business_date | days_with_data_last_30 |
|---|---|---|
| ATL | 2026-11-19 | 30 |
| MRD | 2026-11-19 | 30 |


Genie SQL:

```sql
WITH `latest_date_cte` AS (
  SELECT MAX(`business_date`) AS `latest_business_date`
  FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_auth_daily`
),
`latest_by_network` AS (
  SELECT
    `network`,
    MAX(`business_date`) AS `latest_business_date`
  FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_auth_daily`
  WHERE `attempts` > 0
    AND `network` IS NOT NULL
  GROUP BY `network`
),
`mrd_30d` AS (
  SELECT COUNT(DISTINCT `business_date`) AS `acquired_network_days_with_data_last_30_days`
  FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_auth_daily`
  CROSS JOIN `latest_date_cte`
  WHERE `network` = 'MRD'
    AND `attempts` > 0
    AND `business_date` > date_sub(`latest_business_date`, 30)
)
SELECT
  l.`network`,
  l.`latest_business_date`,
  m.`acquired_network_days_with_data_last_30_days`
FROM `latest_by_network` l
CROSS JOIN `mrd_30d` m
ORDER BY l.`network`
```

Genie rows:

| network | latest_business_date | acquired_network_days_with_data_last_30_days |
|---|---|---|
| ATL | 2026-11-19 | 30 |
| MRD | 2026-11-19 | 30 |


Genie text:

> Both networks have data loaded through **2026-11-19**: **ATL** and **MRD**. For the acquired network (**MRD**), data is present on **30 of the last 30 days**, so coverage is complete over that period.


Expected rows found: 2/2 · match: **True** · exact: True


### q14: Is wave 7 ready to launch? Show the gate result and the reason for each card segment.

Ground truth SQL:

```sql
SELECT card_segment, issuer_segment, gate, gate_reason
FROM classic_stable_zjnu75_catalog.network_migration.gold_wave_readiness WHERE wave_id = 7 ORDER BY issuer_segment, card_segment
```

Expected rows:

| card_segment | issuer_segment | gate | gate_reason |
|---|---|---|---|
| ECOM_HEAVY | OWN | HOLD | approval gap 2.48 pp > 0.3 pp limit; 4 HIGH-severity case(s) open |
| INTL_TRAVELER | OWN | HOLD | approval gap 2.63 pp > 0.3 pp limit; 4 HIGH-severity case(s) open |
| RECURRING_HEAVY | OWN | HOLD | approval gap 5.07 pp > 0.3 pp limit; 4 HIGH-severity case(s) open |
| WALLET_HEAVY | OWN | HOLD | approval gap 3.13 pp > 0.3 pp limit; 4 HIGH-severity case(s) open |
| ECOM_HEAVY | THIRD_PARTY | HOLD | approval gap 3.33 pp > 0.3 pp limit; 2 HIGH-severity case(s) open |
| INTL_TRAVELER | THIRD_PARTY | HOLD | approval gap 3.10 pp > 0.3 pp limit; 2 HIGH-severity case(s) open |
| RECURRING_HEAVY | THIRD_PARTY | HOLD | approval gap 4.16 pp > 0.3 pp limit; 2 HIGH-severity case(s) open |
| WALLET_HEAVY | THIRD_PARTY | HOLD | approval gap 2.73 pp > 0.3 pp limit; 2 HIGH-severity case(s) open |


Genie SQL:

```sql
SELECT `card_segment`, `issuer_segment`, `gate`, `gate_reason`
FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_wave_readiness`
WHERE `wave_id` = 7
  AND `card_segment` IS NOT NULL
  AND `issuer_segment` IS NOT NULL
ORDER BY `card_segment`, `issuer_segment`
```

Genie rows:

| card_segment | issuer_segment | gate | gate_reason |
|---|---|---|---|
| ECOM_HEAVY | OWN | HOLD | approval gap 2.48 pp > 0.3 pp limit; 4 HIGH-severity case(s) open |
| ECOM_HEAVY | THIRD_PARTY | HOLD | approval gap 3.33 pp > 0.3 pp limit; 2 HIGH-severity case(s) open |
| INTL_TRAVELER | OWN | HOLD | approval gap 2.63 pp > 0.3 pp limit; 4 HIGH-severity case(s) open |
| INTL_TRAVELER | THIRD_PARTY | HOLD | approval gap 3.10 pp > 0.3 pp limit; 2 HIGH-severity case(s) open |
| RECURRING_HEAVY | OWN | HOLD | approval gap 5.07 pp > 0.3 pp limit; 4 HIGH-severity case(s) open |
| RECURRING_HEAVY | THIRD_PARTY | HOLD | approval gap 4.16 pp > 0.3 pp limit; 2 HIGH-severity case(s) open |
| WALLET_HEAVY | OWN | HOLD | approval gap 3.13 pp > 0.3 pp limit; 4 HIGH-severity case(s) open |
| WALLET_HEAVY | THIRD_PARTY | HOLD | approval gap 2.73 pp > 0.3 pp limit; 2 HIGH-severity case(s) open |


Genie text:

> **Wave 7 is not ready to launch**: all **8 of 8** card segment and issuer segment combinations are **HOLD**, so no segment meets the launch gate. Examples include:
> - **ECOM_HEAVY / OWN** — **HOLD**: approval gap **2.48 pp** exceeds the **0.3 pp** limit, with **4** open high-severity cases
> - **ECOM_HEAVY / THIRD_PARTY** — **HOLD**: approval gap **3.33 pp** exceeds the limit, with **2** open high-severity cases
> - **INTL_TRAVELER / OWN** — **HOLD**: approval gap **2.63 pp** exceeds the limit, with **4** open high-severity cases
> - **RECURRING_HEAVY / OWN** — **HOLD**: approval gap **5.07 pp** exceeds the limit, with **4** open high-severity cases
> - **WALLET_HEAVY / THIRD_PARTY** — **HOLD**: approval gap **2.73 pp** exceeds the limit, with **2** open high-severity cases
> 
> Across all shown segments, the common blockers are approval gaps above the **0.3 pp** threshold and open **HIGH-severity** cases; the largest gap shown is **5.07 pp** for **RECURRING_HEAVY / OWN**.


Expected rows found: 8/8 · match: **True** · exact: True


### q15: How much transaction volume in wave 7 is at risk, by card segment?

Ground truth SQL:

```sql
SELECT card_segment, round(sum(expected_daily_attempts), 1) AS expected_daily_attempts,
       round(sum(at_risk_declines_per_day), 2) AS at_risk_declines_per_day, round(sum(at_risk_spend_usd_per_day), 2) AS at_risk_spend_usd_per_day
FROM classic_stable_zjnu75_catalog.network_migration.gold_wave_readiness WHERE wave_id = 7 GROUP BY card_segment ORDER BY at_risk_spend_usd_per_day DESC
```

Expected rows:

| card_segment | expected_daily_attempts | at_risk_declines_per_day | at_risk_spend_usd_per_day |
|---|---|---|---|
| ECOM_HEAVY | 313.6 | 8.07 | 426.92 |
| RECURRING_HEAVY | 267.9 | 13.34 | 364.98 |
| WALLET_HEAVY | 229.7 | 7.1 | 256.65 |
| INTL_TRAVELER | 167.6 | 4.48 | 255.97 |


Genie SQL:

```sql
SELECT `card_segment`, SUM(`expected_daily_attempts`) AS `expected_daily_attempts`, SUM(`at_risk_declines_per_day`) AS `at_risk_declines_per_day`, SUM(`at_risk_spend_usd_per_day`) AS `at_risk_spend_usd_per_day`
FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_wave_readiness`
WHERE `wave_id` = 7
  AND `card_segment` IS NOT NULL
GROUP BY `card_segment`
ORDER BY `at_risk_spend_usd_per_day` DESC
```

Genie rows:

| card_segment | expected_daily_attempts | at_risk_declines_per_day | at_risk_spend_usd_per_day |
|---|---|---|---|
| ECOM_HEAVY | 313.642857 | 8.071953160641279 | 426.92358055384835 |
| RECURRING_HEAVY | 267.892857 | 13.341540667226768 | 364.9828368225314 |
| WALLET_HEAVY | 229.678572 | 7.101998856767598 | 256.65478197950694 |
| INTL_TRAVELER | 167.607143 | 4.4803484256558335 | 255.97392710812986 |


Genie text:

> Wave 7 has **4 card segments** with at-risk volume in the results, ranked by daily at-risk spend. Examples include:
> - **ECOM_HEAVY** — **313.64** expected daily attempts, **8.07** at-risk declines/day, **$426.92/day** at-risk spend
> - **RECURRING_HEAVY** — **267.89** expected daily attempts, **13.34** at-risk declines/day, **$364.98/day** at-risk spend
> - **WALLET_HEAVY** — **229.68** expected daily attempts, **7.10** at-risk declines/day, **$256.65/day** at-risk spend
> - **INTL_TRAVELER** — **167.61** expected daily attempts, **4.48** at-risk declines/day, **$255.97/day** at-risk spend
> Among these segments, **ECOM_HEAVY** has the highest at-risk spend, while **RECURRING_HEAVY** has the highest number of at-risk declines per day.


Expected rows found: 4/4 · match: **True** · exact: True
