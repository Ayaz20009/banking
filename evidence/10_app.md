# Evidence 10: Databricks App route checks

Generated 2026-11-24T20:15:06Z by tools/generate_evidence.py from the live workspace.

Proves that the Databricks App is deployed and serves every screen from live data: the app's state and resources (Apps API), then each route called over HTTPS with the signed-in user's OAuth token, with status, size, time and the visible text of the page (identities redacted), and checks that the numbers on the overview equal the gold tables and the case list equals Lakebase.

## App (Apps API)

| item | value |
|---|---|
| name | febar-ops-app |
| url | https://febar-ops-app-7474654297305416.aws.databricksapps.com |
| app status | RUNNING |
| compute status | ACTIVE |
| active deployment | 01f1e714a3921237b1b4e42d21d54330 |
| deployed at | 2026-11-23T08:05:25Z |
| user API scopes | sql, genie |
| resources | sql-warehouse (sql_warehouse); genie-space (genie_space); database (postgres) |


## Routes

| method | route | HTTP status | bytes | seconds |
|---|---|---|---|---|
| GET | /health | 200 | 11 | 0.16 |
| GET | / | 200 | 8049 | 4.85 |
| GET | /cases | 200 | 7373 | 1.44 |
| GET | /cases?show=all | 200 | 7354 | 1.71 |
| GET | /cases/1 | 200 | 12088 | 2.54 |
| GET | /ask | 200 | 5788 | 0.65 |
| POST | /ask | 200 | 7233 | 16.33 |


## Checks: the App shows the same numbers as gold and Lakebase

| check | expected value (queried now) | found on the page |
|---|---|---|
| overview shows the latest data date from gold | 2026-11-19 | True |
| overview shows the 30-day gap from gold (pp) | 1.64 | True |
| overview shows the 30-day lost spend from gold | $107,948 | True |
| overview shows the wave 7 at-risk spend per day | $1,305 | True |
| overview shows the wave 7 gate | HOLD | True |
| case list shows the open cases in Lakebase | 1,2,3,4,5,6,7 | True |
| Ask (POST) returned a Genie answer containing the gap | 1.64 | True |


## Visible text of each page (HTML tags removed, identities redacted)


### GET /health

```
{"ok":true}
```


### GET /

```
Acceptance Risk Control Overview Priority list Ask Genie Signed in as <user> Your data access: OWN, THIRD_PARTY cards · regions INTL, MW, NE, SE, SW, W Migration overview Last 30 days to 2026-11-19 · migrated cards on the acquired network compared with similar cards still on the legacy network. Approval gap vs matched baseline 1.64 pp 95.94% migrated vs 97.58% baseline · limit 0.30 pp Lost spend (excess declines) $107,948 2,844 extra declines on 172,920 attempts Open cases 7 6 HIGH severity · $90,824 exposure Wave 7 gate HOLD $1,305 per day at risk if migrated today Wave 7 readiness by segment Card segment Issuer Gate Why Daily attempts At-risk declines/day At-risk spend/day ECOM_HEAVY OWN HOLD approval gap 2.48 pp > 0.3 pp limit; 4 HIGH-severity case(s) open 279.3 6.93 $365 RECURRING_HEAVY OWN HOLD approval gap 5.07 pp > 0.3 pp limit; 4 HIGH-severity case(s) open 241.5 12.24 $334 WALLET_HEAVY OWN HOLD approval gap 3.13 pp > 0.3 pp limit; 4 HIGH-severity case(s) open 208.3 6.52 $237 INTL_TRAVELER OWN HOLD approval gap 2.63 pp > 0.3 pp limit; 4 HIGH-severity case(s) open 151.0 3.97 $225 ECOM_HEAVY THIRD_PARTY HOLD approval gap 3.33 pp > 0.3 pp limit; 2 HIGH-severity case(s) open 34.4 1.14 $62 INTL_TRAVELER THIRD_PARTY HOLD approval gap 3.10 pp > 0.3 pp limit; 2 HIGH-severity case(s) open 16.6 0.52 $31 RECURRING_HEAVY THIRD_PARTY HOLD approval gap 4.16 pp > 0.3 pp limit; 2 HIGH-severity case(s) open 26.4 1.10 $31 WALLET_HEAVY THIRD_PARTY HOLD approval gap 2.73 pp > 0.3 pp limit; 2 HIGH-severity case(s) open 21.4 0.58 $20 Gate rule: GO only if the segment's approval gap on migrated cards over the last 14 days is ≤ 0.3 pp and no HIGH-severity case is open. How these numbers were produced 1 · Raw files Issuer, two networks, merchants, cards, acquirers land in a Unity Catalog volume → 2 · Lakeflow pipeline Quality rules, quarantine, two networks conformed, file reconciliation → 3 · Governed gold 10,992,550 attempts in 3,145,086 daily rows you can see, to 2026-11-19 → 4 · Score + AI 254 flagged anomalies, explained by an LLM → 5 · Cases (Lakebase) 7 cases worked by analysts → 6 · Readiness 32 wave × segment gates Data from: gold_baseline_gap, gold_wave_readiness, gold_case_status, gold_auth_daily, gold_anomalies (Unity Catalog) · Synthetic data. Gold tables and Genie are queried with your own identity, so Unity Catalog decides what you see.
```


### GET /cases

```
Acceptance Risk Control Overview Priority list Ask Genie Signed in as <user> Your data access: OWN, THIRD_PARTY cards · regions INTL, MW, NE, SE, SW, W Priority list Cases ranked by severity, then estimated lost spend. Each case groups the flagged anomalies with the same likely cause on consecutive days. Showing 7 open case(s) of the 7 your access allows · show closed too # Severity Likely cause Cards Days Flags Est. lost spend Why it was flagged Owner Status 3 HIGH Card On File Stale OWN 2026-11-02 → 2026-11-12 138 $36,968 CHANNEL: REC · MCC_GROUP_XB: BILLS / DOMESTIC · ACQUIRER_CHANNEL: ACQ-001 / REC Card Technology IN_PROGRESS analyst.card-inv.demo 1 HIGH Cross Border Block OWN · INTL 2026-10-12 → 2026-10-20 21 $19,315 MCC_GROUP_XB: TRAVEL_LODGING / CROSS_BORDER · REGION: INTL · CHANNEL: CP Network Integration CLAIMED analyst.A 5 HIGH Processor Timeout OWN · SE 2026-11-14 → 2026-11-16 40 $16,056 REGION: SE · CARD_SEGMENT: DOMESTIC · CHANNEL: CP Network Operations CLAIMED <user> 6 HIGH Acceptance Config OWN 2026-09-24 → 2026-10-08 21 $12,515 ACQUIRER_CHANNEL: ACQ-017 / ECOM · CHANNEL: ECOM Acquirer Relations OPEN 2 HIGH Card On File Stale THIRD_PARTY · SE 2026-11-02 → 2026-11-09 23 $4,100 CHANNEL: REC · MCC_GROUP_XB: BILLS / DOMESTIC · CARD_SEGMENT: DOMESTIC Card Technology OPEN 7 HIGH Processor Timeout THIRD_PARTY · SE 2026-11-14 → 2026-11-16 9 $1,581 REGION: SE · CHANNEL: CP · CARD_SEGMENT: DOMESTIC Network Operations OPEN 4 MEDIUM Acceptance Config OWN 2026-01-12 → 2026-01-12 2 $288 CARD_SEGMENT: DOMESTIC · CHANNEL: CP Acquirer Relations OPEN Data from: ops.cases (Lakebase, live) limited to the case_ids Unity Catalog lets you see in gold_case_status · Synthetic data. Gold tables and Genie are queried with your own identity, so Unity Catalog decides what you see.
```


### GET /cases?show=all

```
Acceptance Risk Control Overview Priority list Ask Genie Signed in as <user> Your data access: OWN, THIRD_PARTY cards · regions INTL, MW, NE, SE, SW, W Priority list Cases ranked by severity, then estimated lost spend. Each case groups the flagged anomalies with the same likely cause on consecutive days. Showing 7 case(s) of the 7 your access allows · open only # Severity Likely cause Cards Days Flags Est. lost spend Why it was flagged Owner Status 3 HIGH Card On File Stale OWN 2026-11-02 → 2026-11-12 138 $36,968 CHANNEL: REC · MCC_GROUP_XB: BILLS / DOMESTIC · ACQUIRER_CHANNEL: ACQ-001 / REC Card Technology IN_PROGRESS analyst.card-inv.demo 1 HIGH Cross Border Block OWN · INTL 2026-10-12 → 2026-10-20 21 $19,315 MCC_GROUP_XB: TRAVEL_LODGING / CROSS_BORDER · REGION: INTL · CHANNEL: CP Network Integration CLAIMED analyst.A 5 HIGH Processor Timeout OWN · SE 2026-11-14 → 2026-11-16 40 $16,056 REGION: SE · CARD_SEGMENT: DOMESTIC · CHANNEL: CP Network Operations CLAIMED <user> 6 HIGH Acceptance Config OWN 2026-09-24 → 2026-10-08 21 $12,515 ACQUIRER_CHANNEL: ACQ-017 / ECOM · CHANNEL: ECOM Acquirer Relations OPEN 2 HIGH Card On File Stale THIRD_PARTY · SE 2026-11-02 → 2026-11-09 23 $4,100 CHANNEL: REC · MCC_GROUP_XB: BILLS / DOMESTIC · CARD_SEGMENT: DOMESTIC Card Technology OPEN 7 HIGH Processor Timeout THIRD_PARTY · SE 2026-11-14 → 2026-11-16 9 $1,581 REGION: SE · CHANNEL: CP · CARD_SEGMENT: DOMESTIC Network Operations OPEN 4 MEDIUM Acceptance Config OWN 2026-01-12 → 2026-01-12 2 $288 CARD_SEGMENT: DOMESTIC · CHANNEL: CP Acquirer Relations OPEN Data from: ops.cases (Lakebase, live) limited to the case_ids Unity Catalog lets you see in gold_case_status · Synthetic data. Gold tables and Genie are queried with your own identity, so Unity Catalog decides what you see.
```


### GET /cases/1

```
Acceptance Risk Control Overview Priority list Ask Genie Signed in as <user> Your data access: OWN, THIRD_PARTY cards · regions INTL, MW, NE, SE, SW, W ← Priority list Case 1 · Cross Border Block HIGH OWN cards · INTL · 2026-10-12 → 2026-10-20 · 21 flagged slice-days · est. lost spend $19,315 · 52 merchants affected (peak day) AI explanation (likely cause, not confirmed · v3) On 2026-10-16, the TRAVEL_LODGING / CROSS_BORDER slice on the acquired network (cards already migrated) recorded 28 acceptance declines against an expected 4.8, producing 23.2 excess declines across 28 merchants and an estimated $2769.0 in lost spend. Every one of the 28 acceptance declines falls into the CROSS_BORDER_BLOCK category, meaning cross-border is likely not enabled for this merchant category group or product on the acquired network. The z-score of 9.6 confirms this is highly unusual relative to the prior 28 days, and the pattern has been elevated on 2 of the last 2 prior days, suggesting a persistent configuration gap rather than a one-off event. Suggested next step: Network Integration should check today whether cross-border acceptance is enabled on the acquired network for the TRAVEL_LODGING merchant category group in the CROSS_BORDER slice, then confirm with the network team whether the block is intended and, if not, request it is lifted. Evidence: flagged slices (top 12 by score) Day Slice Acceptance declines Expected z Lost spend Score 2026-10-16 MCC_GROUP_XB: TRAVEL_LODGING / CROSS_BORDER 28 4.8 9.6 $2,769 90.1 2026-10-17 MCC_GROUP_XB: TRAVEL_LODGING / CROSS_BORDER 29 5.4 9.3 $2,582 88.3 2026-10-14 MCC_GROUP_XB: TRAVEL_LODGING / CROSS_BORDER 20 2.4 9.5 $2,131 87.8 2026-10-17 REGION: INTL 34 8.1 8.6 $1,793 84.1 2026-10-12 MCC_GROUP_XB: TRAVEL_LODGING / CROSS_BORDER 27 1.8 15.2 $3,535 82.4 2026-10-12 REGION: INTL 32 3.9 12.7 $2,391 81.9 2026-10-16 REGION: INTL 31 7.6 8.0 $1,648 81.0 2026-10-14 REGION: INTL 23 5.4 7.0 $1,115 74.2 2026-10-13 MCC_GROUP_XB: TRAVEL_LODGING / CROSS_BORDER 17 2.5 7.8 $2,306 74.1 2026-10-18 MCC_GROUP_XB: TRAVEL_LODGING / CROSS_BORDER 20 4.6 6.5 $1,751 72.6 2026-10-18 REGION: INTL 22 7.3 5.1 $922 64.3 2026-10-13 REGION: INTL 19 4.8 5.9 $1,254 63.4 By day (largest slice that day) Day Acceptance declines Expected Lost spend 2026-10-12 42 19.9 $3,535 2026-10-13 19 4.8 $2,306 2026-10-14 23 5.4 $2,131 2026-10-15 14 6.0 $1,428 2026-10-16 52 25.5 $2,769 2026-10-17 34 8.1 $2,582 2026-10-18 22 7.3 $1,751 2026-10-19 16 8.0 $1,315 2026-10-20 19 9.3 $1,498 Status CLAIMED Assignee analyst.A Owner team Network Integration (suggested: Network Integration) Due — Version 2 Act on this case OPEN CLAIMED IN_PROGRESS WAITING_PARTNER Set status Acquirer Relations Network Integration Card Technology Network Operations Issuer Processing Set owner Set due date Add note ACQUIRER_FIX CONFIG_CHANGE CREDENTIAL_REFRESH PROCESSOR_FIX FALSE_POSITIVE OTHER Resolve Dismiss History 2026-11-23 07:30 MACHINE_UPDATE → {"n_flags": "21", "max_score": "90.1", "severity": "HI …
```


### GET /ask

```
Acceptance Risk Control Overview Priority list Ask Genie Signed in as <user> Your data access: OWN, THIRD_PARTY cards · regions INTL, MW, NE, SE, SW, W Ask Genie Plain-English questions over the governed gold tables. Genie runs the SQL with your identity, so you only get answers from data you are allowed to see. Ask What is the approval gap for migrated cards vs the matched baseline over the last 30 days? Is wave 7 ready to launch? Which acquirers had the most acceptance declines on the acquired network in the last 14 days? How many HIGH-severity cases are open, and who owns them? How much spend did we lose to excess declines in the last 30 days? Data from: Genie space "Network migration: acceptance and readiness" over gold_auth_daily, gold_baseline_gap, gold_anomalies, gold_case_status, gold_wave_readiness · Synthetic data. Gold tables and Genie are queried with your own identity, so Unity Catalog decides what you see.
```


### POST /ask

```
Acceptance Risk Control Overview Priority list Ask Genie Signed in as <user> Your data access: OWN, THIRD_PARTY cards · regions INTL, MW, NE, SE, SW, W Ask Genie Plain-English questions over the governed gold tables. Genie runs the SQL with your identity, so you only get answers from data you are allowed to see. Ask What is the approval gap for migrated cards vs the matched baseline over the last 30 days? Is wave 7 ready to launch? Which acquirers had the most acceptance declines on the acquired network in the last 14 days? How many HIGH-severity cases are open, and who owns them? How much spend did we lose to excess declines in the last 30 days? Genie (COMPLETED) Over the last 30 business days in the data, the approval gap for migrated cards versus the matched baseline was **1.64 percentage points**. This is based on **172,920** migrated attempts, with **165,891** migrated approvals versus **168,735.41** expected approvals, equal to **2,844.41** excess declines and **$107,948.23** in lost spend. approval_gap_pp migrated_attempts migrated_approvals expected_approvals excess_declines lost_spend 1.64 172920 165891 168735.40976126934 2844.4097612736814 107948.23 SQL Genie ran SELECT ROUND(try_divide(100 * (SUM(`expected_approvals`) - SUM(`migrated_approvals`)),SUM(`migrated_attempts`)), 2) AS `approval_gap_pp`, SUM(`migrated_attempts`) AS `migrated_attempts`, SUM(`migrated_approvals`) AS `migrated_approvals`, SUM(`expected_approvals`) AS `expected_approvals`, SUM(`excess_declines`) AS `excess_declines`, SUM(`lost_spend`) AS `lost_spend` FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_baseline_gap` WHERE `business_date` > (SELECT date_sub(MAX(`business_date`), 30) FROM `classic_stable_zjnu75_catalog`.`network_migration`.`gold_baseline_gap`) Data from: Genie space "Network migration: acceptance and readiness" over gold_auth_daily, gold_baseline_gap, gold_anomalies, gold_case_status, gold_wave_readiness · Synthetic data. Gold tables and Genie are queried with your own identity, so Unity Catalog decides what you see.
```


## Active deployment (Apps API)

| item | value |
|---|---|
| status | SUCCEEDED |
| message | App started successfully |
| source | src/app (bundle) |
| mode | SNAPSHOT |
