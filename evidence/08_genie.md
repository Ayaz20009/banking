# Evidence 08: Genie agent (space `01f1e710e2f1183284ccb47bc5215473`)

- **Title:** "Network migration: acceptance and readiness". Definition exported to `src/genie/space.json`; built by `tools/create_genie.py`; benchmarks in `src/genie/benchmarks.py`; tests in `tools/test_genie.py` (Genie Conversation API: `start-conversation` → poll `get-message` → `get-message-attachment-query-result`).
- **Tables:** 5 governed gold tables only, all row-filtered: `gold_auth_daily`, `gold_baseline_gap`, `gold_anomalies`, `gold_case_status`, `gold_wave_readiness`. No bronze, silver or transaction-level tables; no metric views.
- **Configured:**
  - Business-word column descriptions; technical and LLM-plumbing columns excluded (e.g. `facts`, `llm_raw`, score components, versions).
  - 2 joins.
  - 1 text instruction with 14 rules (purpose, network codes, relative dates from the latest data date, ratio-of-sums rates, gap and lost-spend definitions, readiness rules, what not to answer).
  - 4 example SQLs, deliberately different from the benchmarks.
  - 8 benchmarks and 5 starter questions for the App.
- **Match rule:** every expected row must appear in Genie's result (numbers equal after rounding: |a−b| ≤ max(0.011, 0.5%); strings case-insensitive). *Exact* = also the same number of rows.

## Results by round

| Round | Change before the round | Matched | Exact |
|---|---|---|---|
| run1 | first version | 5/8 | 5/8 |
| run2 | + before/during/after = 14 days each side; readiness answers show issuer_segment and expected attempts | 7/8 | 7/8 |
| run3 | readiness rule split: gate answers per issuer segment; at-risk answers grouped only by the dimension asked | 8/8 | 8/8 |
| run4 | no change (stability rerun) | 7/8 | 7/8 |

### Mismatches and fixes
- **run1 q08:** Genie used 15-day before/after windows (0.47% / 1.31%) vs 14 days in the ground truth (0.51% / 1.38%). "During" matched (57.52%). The question did not define the window, so the definition was added to the instructions.
- **run1 q14:** all 8 HOLD gates and reasons correct, but no `issuer_segment` column, so own and third-party rows could not be told apart. Instruction added.
- **run1 q15:** at-risk declines and $ matched exactly, but `expected_daily_attempts` was missing. Instruction added.
- **run2 q15:** my run2 rule ("always show issuer_segment") made Genie split at-risk volume by issuer segment, although the question asks "by card segment". The rule was narrowed to gate answers only (run3: 8/8).
- **run4 q13 (stability rerun):** Genie returned the "days with acquired-network data" count **only for MRD** (30), which is what the question literally asks; the ground truth also counts the legacy network. This is a **ground-truth over-specification, not a Genie error**. Recorded, not tuned away.

## Per question (round run3, after the fixes)

### q01: What was the approval rate for migrated cards vs the matched legacy baseline over the last 30 days, and the gap in percentage points?

**Match: ✓ · exact: ✓** · rows found 1/1 · 11 s

Expected (ground-truth SQL in `src/genie/benchmarks.py`):

| migrated_approval_rate_pct | matched_baseline_approval_rate_pct | gap_pp |
|---|---|---|
| 95.9 | 97.58 | 1.68 |

Genie's result:

| migrated_approval_rate_pct | matched_baseline_approval_rate_pct | gap_pp | migrated_attempts |
|---|---|---|---|
| 95.9 | 97.58 | 1.68 | 172363 |

Genie's SQL:

```sql
SELECT ROUND(try_divide(100 * SUM(`migrated_approvals`),SUM(`migrated_attempts`)), 2) AS `migrated_approval_rate_pct`, ROUND(try_divide(100 * SUM(`expected_approvals`),SUM(`migrated_attempts`)), 2) AS `matched_baseline_approval_rate_pct`, ROUND(try_divide(100 * (SUM(`expected_approvals`) - SUM(`migrated_approvals`)),SUM(`migrated_attempts`)), 2) AS `gap_pp`, SUM(`migrated_attempts`) AS `migrated_attempts` FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_baseline_gap` WHERE `business_date` > (SELECT date_sub(MAX(`business_date`), 30) FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_baseline_gap`)
```

Genie's text answer: Over the last 30 days in the data, migrated cards had an approval rate of **95.90%**, compared with a matched legacy baseline approval rate of **97.58%**, for a gap of **1.68 percentage points**. This result is based on **172,363** migrated card attempts.

### q03: How much spend did we lose to excess declines on migrated cards in the last 30 days?

**Match: ✓ · exact: ✓** · rows found 1/1 · 11 s

Expected (ground-truth SQL in `src/genie/benchmarks.py`):

| lost_spend_usd | excess_declines |
|---|---|
| 112911.33 | 2891.7 |

Genie's result:

| lost_spend_usd | excess_declines |
|---|---|
| 112911.33 | 2891.71 |

Genie's SQL:

```sql
SELECT SUM(`lost_spend`) AS `lost_spend_usd`, SUM(`excess_declines`) AS `excess_declines` FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_baseline_gap` WHERE `business_date` > (SELECT date_sub(MAX(`business_date`), 30) FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_baseline_gap`)
```

Genie's text answer: In the last 30 business days covered by `gold_baseline_gap`, migrated cards lost **$112,911.33** in spend due to excess declines, with **2,891.71** excess declines recorded. This means the measured lost purchase volume tied to migrated-card underperformance over that period was **$112,911.33**.

### q04: What are the top 5 acquirers by acceptance declines on the acquired network in the last 14 days?

**Match: ✓ · exact: ✓** · rows found 5/5 · 17 s

Expected (ground-truth SQL in `src/genie/benchmarks.py`):

| acquirer_id | acquirer_name | acceptance_declines |
|---|---|---|
| ACQ-001 | Northgate Merchant Services | 344 |
| ACQ-002 | Clearpath Merchant Services | 211 |
| ACQ-003 | Bayside Merchant Services | 140 |
| ACQ-004 | Keystone Merchant Services | 93 |
| ACQ-005 | Lakemont Merchant Services | 84 |

Genie's result:

| acquirer_rank | acquirer_id | acquirer_name | acceptance_declines | attempts |
|---|---|---|---|---|
| 1 | ACQ-001 | Northgate Merchant Services | 344 | 12882 |
| 2 | ACQ-002 | Clearpath Merchant Services | 211 | 6996 |
| 3 | ACQ-003 | Bayside Merchant Services | 140 | 4793 |
| 4 | ACQ-004 | Keystone Merchant Services | 93 | 3763 |
| 5 | ACQ-005 | Lakemont Merchant Services | 84 | 3160 |

Genie's SQL:

```sql
WITH `acquirer_totals` AS (
  SELECT
    `acquirer_id`,
    `acquirer_name`,
    SUM(`acceptance_declines`) AS `acceptance_declines`,
    SUM(`attempts`) AS `attempts`
  FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_auth_daily`
  WHERE `network` = 'MRD'
    AND `business_date` > (
      SELECT date_sub(MAX(`business_date`), 14)
      FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_auth_daily`
    )
    AND `acquirer_id` IS NOT NULL
    AND `acquirer_name` IS NOT NULL
  GROUP BY `acquirer_id`, `acquirer_name`
), `ranked` AS (
  SELECT
    `acquirer_id`,
    `acquirer_name`,
    `acceptance_declines`,
    `attempts`,
    RANK() OVER (ORDER BY `acceptance_declines` DESC, `acquirer_id` ASC) AS `acquirer_rank`
  FROM `acquirer_totals`
)
SELECT
  `acquirer_rank`,
  `acquirer_id`,
  `acquirer_name`,
  `acceptance_declines`,
  `attempts`
FROM `ranked`
WHERE `acquirer_rank` <= 5
ORDER BY `acquirer_rank`, `acquirer_id`;
```

Genie's text answer: The top 5 acquirers on the acquired network by acceptance declines in the last 14 business days are: - **Northgate Merchant Services**: **344** acceptance declines from **12,882** attempts - **Clearpath Merchant Services**: **211** acceptance declines from **6,996** attempts - **Bayside Merchant Services**: **140** acceptance declines from **4,793** attempts - **Keystone Merchant Services**: **93** acceptance declines from **3,763** attempts - **Lakemont Merchant Services**: **84** acceptance declines from **3,160** attempts Across these 5 acquirers, acceptance declines fall steadily from **34

### q07: What is the acceptance-decline rate for cross-border travel and lodging on the acquired network vs the legacy network over the last 60 days?

**Match: ✓ · exact: ✓** · rows found 2/2 · 17 s

Expected (ground-truth SQL in `src/genie/benchmarks.py`):

| network | acceptance_decline_rate_pct | attempts |
|---|---|---|
| ATL | 0.04 | 25064 |
| MRD | 8.3 | 3686 |

Genie's result:

| network | acceptance_decline_rate_pct | attempts | acceptance_declines |
|---|---|---|---|
| ATL | 0.04 | 25064 | 9 |
| MRD | 8.3 | 3686 | 306 |

Genie's SQL:

```sql
SELECT
  `network`,
  ROUND(try_divide(100 * SUM(`acceptance_declines`),SUM(`attempts`)), 2) AS `acceptance_decline_rate_pct`,
  SUM(`attempts`) AS `attempts`,
  SUM(`acceptance_declines`) AS `acceptance_declines`
FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_auth_daily`
WHERE `business_date` > (
    SELECT date_sub(MAX(`business_date`), 60)
    FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_auth_daily`
  )
  AND `mcc_group` IS NOT NULL
  AND `network` IS NOT NULL
  AND `cross_border` = TRUE
  AND `mcc_group` ILIKE '%TRAVEL_LODGING%'
  AND `network` IN ('MRD', 'ATL')
GROUP BY `network`
ORDER BY `network`
```

Genie's text answer: Over the last **60 business days** in cross-border **travel and lodging**, the acceptance-decline rate was **8.30%** on the acquired network (**MRD**) versus **0.04%** on the legacy network (**ATL**). This came from **306** acceptance declines out of **3,686** attempts on **MRD**, compared with **9** out of **25,064** on **ATL**, so the acquired network’s rate was markedly higher in this segment.

### q08: How did ACQ-017's e-commerce acceptance-decline rate on the acquired network change before, during and after 24 September to 8 October 2026?

**Match: ✓ · exact: ✓** · rows found 3/3 · 17 s

Expected (ground-truth SQL in `src/genie/benchmarks.py`):

| period | acceptance_decline_rate_pct | attempts |
|---|---|---|
| 1_before | 0.51 | 392 |
| 2_during | 57.52 | 419 |
| 3_after | 1.38 | 363 |

Genie's result:

| period | acceptance_decline_rate_pct | acceptance_declines | attempts |
|---|---|---|---|
| 1_before | 0.51 | 2 | 392 |
| 2_during | 57.52 | 241 | 419 |
| 3_after | 1.38 | 5 | 363 |

Genie's SQL:

```sql
SELECT CASE WHEN `business_date` BETWEEN DATE '2026-09-10' AND DATE '2026-09-23' THEN '1_before' WHEN `business_date` BETWEEN DATE '2026-09-24' AND DATE '2026-10-08' THEN '2_during' WHEN `business_date` BETWEEN DATE '2026-10-09' AND DATE '2026-10-22' THEN '3_after' END AS `period`, ROUND(try_divide(100 * SUM(`acceptance_declines`),SUM(`attempts`)), 2) AS `acceptance_decline_rate_pct`, SUM(`acceptance_declines`) AS `acceptance_declines`, SUM(`attempts`) AS `attempts` FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_auth_daily` WHERE `network` = 'MRD' AND `acquirer_id` = 'ACQ-017' AND `channel` = 'ECOM' AND `business_date` BETWEEN DATE '2026-09-10' AND DATE '2026-10-22' GROUP BY 1 ORDER BY 1
```

Genie's text answer: For **ACQ-017** on the acquired network in **e-commerce**, the acceptance-decline rate rose sharply from **0.51%** before 24 September to **57.52%** during 24 September to 8 October, then fell back to **1.38%** after 8 October. That corresponds to **2 of 392** attempts before, **241 of 419** during, and **5 of 363** after, with the issue clearly concentrated in the during period.

### q13: What is the latest business date loaded for each network, and on how many of the last 30 days do we have acquired-network data?

**Match: ✓ · exact: ✓** · rows found 2/2 · 17 s

Expected (ground-truth SQL in `src/genie/benchmarks.py`):

| network | latest_business_date | days_with_data_last_30 |
|---|---|---|
| ATL | 2026-11-17 | 30 |
| MRD | 2026-11-17 | 30 |

Genie's result:

| network | latest_business_date | acquired_network_days_with_data_last_30 |
|---|---|---|
| ATL | 2026-11-17 | 30 |
| MRD | 2026-11-17 | 30 |

Genie's SQL:

```sql
WITH `latest_by_network` AS (
  SELECT
    `network`,
    MAX(`business_date`) AS `latest_business_date`
  FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_auth_daily`
  WHERE `network` IS NOT NULL
  GROUP BY `network`
),
`mrd_last_30` AS (
  SELECT
    COUNT(DISTINCT `business_date`) AS `acquired_network_days_with_data_last_30`
  FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_auth_daily`
  WHERE `network` = 'MRD'
    AND `business_date` > (
      SELECT DATE_SUB(MAX(`business_date`), 30)
      FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_auth_daily`
    )
    AND `attempts` > 0
)
SELECT
  l.`network`,
  l.`latest_business_date`,
  m.`acquired_network_days_with_data_last_30`
FROM `latest_by_network` l
CROSS JOIN `mrd_last_30` m
ORDER BY l.`network`
```

Genie's text answer: Both networks have data loaded through **2026-11-17**: **ATL** and **MRD**. For the acquired network (**MRD**), there is data on **30** of the last **30** days, so coverage is complete over that period.

### q14: Is wave 7 ready to launch? Show the gate result and the reason for each card segment.

**Match: ✓ · exact: ✓** · rows found 8/8 · 12 s

Expected (ground-truth SQL in `src/genie/benchmarks.py`):

| card_segment | issuer_segment | gate | gate_reason |
|---|---|---|---|
| ECOM_HEAVY | OWN | HOLD | approval gap 2.79 pp > 0.3 pp limit; 4 HIGH-severity case(s) open |
| INTL_TRAVELER | OWN | HOLD | approval gap 2.89 pp > 0.3 pp limit; 4 HIGH-severity case(s) open |
| RECURRING_HEAVY | OWN | HOLD | approval gap 6.68 pp > 0.3 pp limit; 4 HIGH-severity case(s) open |
| WALLET_HEAVY | OWN | HOLD | approval gap 3.56 pp > 0.3 pp limit; 4 HIGH-severity case(s) open |
| ECOM_HEAVY | THIRD_PARTY | HOLD | approval gap 3.93 pp > 0.3 pp limit; 2 HIGH-severity case(s) open |
| INTL_TRAVELER | THIRD_PARTY | HOLD | approval gap 4.73 pp > 0.3 pp limit; 2 HIGH-severity case(s) open |
| RECURRING_HEAVY | THIRD_PARTY | HOLD | approval gap 6.45 pp > 0.3 pp limit; 2 HIGH-severity case(s) open |
| WALLET_HEAVY | THIRD_PARTY | HOLD | approval gap 3.53 pp > 0.3 pp limit; 2 HIGH-severity case(s) open |

Genie's result:

| as_of_date | planned_migration_date | card_segment | issuer_segment | gate | gate_reason |
|---|---|---|---|---|---|
| 2026-11-17 | 2027-02-18 | ECOM_HEAVY | OWN | HOLD | approval gap 2.79 pp > 0.3 pp limit; 4 HIGH-severity case(s) open |
| 2026-11-17 | 2027-02-18 | ECOM_HEAVY | THIRD_PARTY | HOLD | approval gap 3.93 pp > 0.3 pp limit; 2 HIGH-severity case(s) open |
| 2026-11-17 | 2027-02-18 | INTL_TRAVELER | OWN | HOLD | approval gap 2.89 pp > 0.3 pp limit; 4 HIGH-severity case(s) open |
| 2026-11-17 | 2027-02-18 | INTL_TRAVELER | THIRD_PARTY | HOLD | approval gap 4.73 pp > 0.3 pp limit; 2 HIGH-severity case(s) open |
| 2026-11-17 | 2027-02-18 | RECURRING_HEAVY | OWN | HOLD | approval gap 6.68 pp > 0.3 pp limit; 4 HIGH-severity case(s) open |
| 2026-11-17 | 2027-02-18 | RECURRING_HEAVY | THIRD_PARTY | HOLD | approval gap 6.45 pp > 0.3 pp limit; 2 HIGH-severity case(s) open |
| 2026-11-17 | 2027-02-18 | WALLET_HEAVY | OWN | HOLD | approval gap 3.56 pp > 0.3 pp limit; 4 HIGH-severity case(s) open |
| 2026-11-17 | 2027-02-18 | WALLET_HEAVY | THIRD_PARTY | HOLD | approval gap 3.53 pp > 0.3 pp limit; 2 HIGH-severity case(s) open |

Genie's SQL:

```sql
SELECT `as_of_date`, `planned_migration_date`, `card_segment`, `issuer_segment`, `gate`, `gate_reason`
FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_wave_readiness`
WHERE `wave_id` = 7
  AND `card_segment` IS NOT NULL
  AND `issuer_segment` IS NOT NULL
ORDER BY `card_segment`, `issuer_segment`
```

Genie's text answer: **Wave 7 is not ready to launch** as of **2026-11-17**: all **8** card segment and issuer segment combinations are on **HOLD**, and each one is blocked by an approval gap above the **0.3 pp** limit plus open **HIGH-severity** cases. Examples include: - **ECOM_HEAVY / OWN** — **HOLD**; reason: approval gap **2.79 pp** and **4** open HIGH-severity cases - **ECOM_HEAVY / THIRD_PARTY** — **HOLD**; reason: approval gap **3.93 pp** and **2** open HIGH-severity cases - **INTL_TRAVELER / OWN** — **HOLD**; reason: approval gap **2.89 pp** and **4** open HIGH-severity cases - **INTL_TRAVELER / THIRD_PAR

### q15: How much transaction volume in wave 7 is at risk, by card segment?

**Match: ✓ · exact: ✓** · rows found 4/4 · 17 s

Expected (ground-truth SQL in `src/genie/benchmarks.py`):

| card_segment | expected_daily_attempts | at_risk_declines_per_day | at_risk_spend_usd_per_day |
|---|---|---|---|
| RECURRING_HEAVY | 268.3 | 17.86 | 492.04 |
| ECOM_HEAVY | 311.6 | 9.08 | 479.42 |
| WALLET_HEAVY | 231.0 | 8.21 | 296.31 |
| INTL_TRAVELER | 167.1 | 5.15 | 293.16 |

Genie's result:

| card_segment | expected_daily_attempts | at_risk_declines_per_day | at_risk_spend_usd_per_day |
|---|---|---|---|
| RECURRING_HEAVY | 268.29 | 17.86 | 492.04 |
| ECOM_HEAVY | 311.61 | 9.08 | 479.42 |
| WALLET_HEAVY | 230.96 | 8.21 | 296.31 |
| INTL_TRAVELER | 167.07 | 5.15 | 293.16 |

Genie's SQL:

```sql
SELECT `card_segment`, SUM(`expected_daily_attempts`) AS `expected_daily_attempts`, SUM(`at_risk_declines_per_day`) AS `at_risk_declines_per_day`, SUM(`at_risk_spend_usd_per_day`) AS `at_risk_spend_usd_per_day` FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_wave_readiness` WHERE `wave_id` = 7 AND `card_segment` IS NOT NULL GROUP BY `card_segment` ORDER BY `at_risk_spend_usd_per_day` DESC
```

Genie's text answer: Wave 7 has **4 card segments** with at-risk transaction volume. Some of the top values are: - **RECURRING_HEAVY**: **268.29** expected daily attempts, **17.86** at-risk declines per day, **$492.04/day** at-risk spend - **ECOM_HEAVY**: **311.61** expected daily attempts, **9.08** at-risk declines per day, **$479.42/day** at-risk spend - **WALLET_HEAVY**: **230.96** expected daily attempts, **8.21** at-risk declines per day, **$296.31/day** at-risk spend - **INTL_TRAVELER**: **167.07** expected daily attempts, **5.15** at-risk declines per day, **$293.16/day** at-risk spend **RECURRING_HEAVY** h

## Governance through Genie (row filter applies to the asking user)

The same question asked twice; my entitlement was switched to the Southeast analyst, then restored to ADMIN (verified).

### Asked as persona P2_REGIONAL

| issuer_segment | region | total_authorization_attempts |
|---|---|---|
| OWN | SE | 190836 |

### Asked as persona ADMIN

| issuer_segment | region | total_attempts |
|---|---|---|
| OWN | INTL | 26925 |
| OWN | MW | 132044 |
| OWN | NE | 154731 |
| OWN | SE | 190836 |
| OWN | SW | 113832 |
| OWN | W | 159102 |
| THIRD_PARTY | INTL | 2873 |
| THIRD_PARTY | MW | 14584 |
| THIRD_PARTY | NE | 16856 |
| THIRD_PARTY | SE | 21178 |
| THIRD_PARTY | SW | 12666 |
| THIRD_PARTY | W | 17878 |

