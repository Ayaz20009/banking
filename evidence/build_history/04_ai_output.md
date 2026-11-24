# Evidence 04: AI output, verbatim

- **Generator:** `databricks-claude-sonnet-4-6` via `ai_query`, structured output (`json_schema`, strict), `temperature = 0.0`, `max_tokens = 700`, `failOnError => false`.
- **Inputs and storage:** the facts are built per row from `gold_anomaly_scores` (src/ai/explain_anomalies.py). Every row stores the model name, prompt version, raw response and error column (`anomaly_explanations`, append-only).
- **Ranking and severity stay in the explainable score;** the model never outputs either.
- **Scale:** 65 v1 and 30 v2 explanations, **0 errors**. The LLM ran only on flagged anomalies, newest and highest score first, capped by `top_n`.

Below: 4 held-out anomalies from the evaluation sample, each with the facts given, the v1 output and the v2 output (same facts plus a glossary).

## `2026-11-11|OWN|MCC_GROUP_XB|DIGITAL / DOMESTIC`

### Prompt v1 (databricks-claude-sonnet-4-6); error: `None`

Facts given:

```json
{
 "business_date": "2026-11-11",
 "card_issuer_segment": "the banks own cards",
 "slice_type": "MCC_GROUP_XB",
 "slice": "DIGITAL / DOMESTIC",
 "network": "acquired network (cards already migrated)",
 "attempts": 371,
 "acceptance_declines": 47,
 "expected_acceptance_declines": 15.5,
 "excess_declines": 31.5,
 "z_score": 7.8,
 "estimated_lost_spend_usd": 256.0,
 "merchants_with_acceptance_declines": 46,
 "decline_categories": {
  "ACCEPTANCE_CONFIG (merchant/acquirer acceptance profile not configured or rejected)": 2,
  "TOKEN_PROVISIONING (wallet or card-on-file token not provisioned)": 3,
  "CARD_ON_FILE_STALE (stored card credential not updated after reissue)": 42
 },
 "dominant_category": "CARD_ON_FILE_STALE",
 "dominant_category_share_pct": 89.0,
 "elevated_on_prior_days_of_last_2": 2,
 "candidate_owner_team": "Card Technology"
}
```

- **summary:** On 2026-11-11, the DIGITAL / DOMESTIC MCC group on the acquired network recorded 47 acceptance declines against an expected 15.5, producing 31.5 excess declines and a z-score of 7.8 across 371 attempts. The anomaly has been elevated on both prior days of the last 2, indicating a persistent issue rather than a one-off spike. The dominant decline category — CARD_ON_FILE_STALE at 89% (42 of 47 declines) — suggests that stored card credentials held by merchants or payment platforms were not updated following the card migration to the acquired network, leaving stale credentials that are now being rejected at authorization. This pattern spans 46 distinct merchants, pointing to a systemic credential refresh gap rather than an isolated merchant configuration problem. Estimated lost spend is $256.00.
- **likely_cause:** `CARD_ON_FILE_STALE` · **certainty:** `likely` · **owner_team:** Card Technology
- **next_step:** Card Technology should today audit the credential-update pipeline for cards migrated to the acquired network — specifically confirming whether updated PANs, expiry dates, or network tokens were pushed to the 46 affected merchants' card-on-file stores. If the push did not occur or failed silently, initiate a forced credential refresh or account updater run for the impacted card population and verify propagation before end of business.

### Prompt v2 (databricks-claude-sonnet-4-6); error: `None`

Facts given:

```json
{
 "business_date": "2026-11-11",
 "card_issuer_segment": "cards issued by this bank",
 "slice_type": "MCC_GROUP_XB",
 "slice": "DIGITAL / DOMESTIC",
 "network": "acquired network (cards already migrated)",
 "attempts": 371,
 "acceptance_declines": 47,
 "expected_acceptance_declines": 15.5,
 "excess_declines": 31.5,
 "z_score": 7.8,
 "estimated_lost_spend_usd": 256.0,
 "merchants_with_acceptance_declines": 46,
 "decline_categories": {
  "ACCEPTANCE_CONFIG (merchant/acquirer acceptance profile not configured or rejected)": 2,
  "TOKEN_PROVISIONING (wallet or card-on-file token not provisioned)": 3,
  "CARD_ON_FILE_STALE (stored card credential not updated after reissue)": 42
 },
 "dominant_category": "CARD_ON_FILE_STALE",
 "dominant_category_share_pct": 89.0,
 "elevated_on_prior_days_of_last_2": 2,
 "candidate_owner_team": "Card Technology",
 "glossary": {
  "attempts": "card authorization attempts",
  "acceptance_declines": "declines caused on the network or acquirer side (not the issuer credit decision); fixable",
  "acquired network": "the payment network the bank acquired; cards in this slice have already been migrated to it",
  "slice_types": "ACQUIRER_CHANNEL = acquirer and channel; MCC_GROUP_XB = merchant category group and domestic or cross-border; REGION = merchant region; CHANNEL = channel; CARD_SEGMENT = cardholder spending segment",
  "channels": "CP = card present; ECOM = e-commerce; REC = recurring or card-on-file charges; MANUAL = key-entered",
  "regions": "NE, SE, MW, SW, W = US regions; INTL = merchants outside the US",
  "z_score": "how unusual the acceptance declines are versus the same slice in the prior 28 days",
  "estimated_lost_spend_usd": "excess declines x average ticket x share of spend not recovered"
 }
}
```

- **summary:** On 2026-11-11, the DIGITAL / DOMESTIC merchant category group slice on the acquired network (cards already migrated) recorded 47 acceptance declines against an expected 15.5, producing 31.5 excess declines across 46 merchants — a z-score of 7.8, elevated on all 2 of the prior days checked, with an estimated lost spend of $256.0. The dominant decline category, at 89.0% share, is CARD_ON_FILE_STALE (stored card credential not updated after reissue), with smaller contributions from TOKEN_PROVISIONING (3 declines) and ACCEPTANCE_CONFIG (2 declines). Because this anomaly has persisted across 2 prior days and spans 46 merchants, it is likely a systemic issue affecting cards issued by this bank following migration to the acquired network rather than an isolated merchant problem.
- **likely_cause:** `CARD_ON_FILE_STALE` · **certainty:** `likely` · **owner_team:** Card Technology
- **next_step:** Card Technology should review the DIGITAL / DOMESTIC MCC_GROUP_XB slice on the acquired network for 2026-11-11 and the 2 prior elevated days, focusing on the 42 CARD_ON_FILE_STALE declines across the 46 affected merchants, to determine whether stored card credentials for cards issued by this bank were updated following migration to the acquired network.

## `2026-11-12|OWN|CARD_SEGMENT|DOMESTIC`

### Prompt v1 (databricks-claude-sonnet-4-6); error: `None`

Facts given:

```json
{
 "business_date": "2026-11-12",
 "card_issuer_segment": "the banks own cards",
 "slice_type": "CARD_SEGMENT",
 "slice": "DOMESTIC",
 "network": "acquired network (cards already migrated)",
 "attempts": 4636,
 "acceptance_declines": 114,
 "expected_acceptance_declines": 60.1,
 "excess_declines": 53.9,
 "z_score": 6.9,
 "estimated_lost_spend_usd": 1628.0,
 "merchants_with_acceptance_declines": 111,
 "decline_categories": {
  "ACCEPTANCE_CONFIG (merchant/acquirer acceptance profile not configured or rejected)": 9,
  "TOKEN_PROVISIONING (wallet or card-on-file token not provisioned)": 11,
  "CROSS_BORDER_BLOCK (cross-border not enabled for merchant category or product)": 2,
  "CARD_ON_FILE_STALE (stored card credential not updated after reissue)": 85,
  "SYSTEM_ERROR (network system error)": 7
 },
 "dominant_category": "CARD_ON_FILE_STALE",
 "dominant_category_share_pct": 75.0,
 "elevated_on_prior_days_of_last_2": 2,
 "candidate_owner_team": "Card Technology"
}
```

- **summary:** On 2026-11-12, the domestic card segment on the acquired network logged 114 acceptance declines against an expected 60.1, producing 53.9 excess declines and a z-score of 6.9 across 4,636 attempts. The dominant decline category is CARD_ON_FILE_STALE, accounting for 75% (85 of 114) of acceptance declines spread across 111 merchants, with an estimated $1,628.00 in lost spend. This pattern has been elevated on both of the prior 2 days, suggesting a persistent issue rather than a one-off spike. The likely root cause is that stored card credentials held by merchants and/or payment intermediaries were not updated following the card migration to the acquired network, causing recurring declines when those stale credentials are presented for authorization.
- **likely_cause:** `CARD_ON_FILE_STALE` · **certainty:** `likely` · **owner_team:** Card Technology
- **next_step:** Card Technology should today audit the credential-update push process for the migrated domestic card segment on the acquired network — specifically confirming whether account updater or credential-on-file notification messages were successfully delivered to the 111 affected merchants (or their acquirers) after migration, and identify any gaps or failures in that delivery pipeline so a remediation push can be initiated.

### Prompt v2 (databricks-claude-sonnet-4-6); error: `None`

Facts given:

```json
{
 "business_date": "2026-11-12",
 "card_issuer_segment": "cards issued by this bank",
 "slice_type": "CARD_SEGMENT",
 "slice": "DOMESTIC",
 "network": "acquired network (cards already migrated)",
 "attempts": 4636,
 "acceptance_declines": 114,
 "expected_acceptance_declines": 60.1,
 "excess_declines": 53.9,
 "z_score": 6.9,
 "estimated_lost_spend_usd": 1628.0,
 "merchants_with_acceptance_declines": 111,
 "decline_categories": {
  "ACCEPTANCE_CONFIG (merchant/acquirer acceptance profile not configured or rejected)": 9,
  "TOKEN_PROVISIONING (wallet or card-on-file token not provisioned)": 11,
  "CROSS_BORDER_BLOCK (cross-border not enabled for merchant category or product)": 2,
  "CARD_ON_FILE_STALE (stored card credential not updated after reissue)": 85,
  "SYSTEM_ERROR (network system error)": 7
 },
 "dominant_category": "CARD_ON_FILE_STALE",
 "dominant_category_share_pct": 75.0,
 "elevated_on_prior_days_of_last_2": 2,
 "candidate_owner_team": "Card Technology",
 "glossary": {
  "attempts": "card authorization attempts",
  "acceptance_declines": "declines caused on the network or acquirer side (not the issuer credit decision); fixable",
  "acquired network": "the payment network the bank acquired; cards in this slice have already been migrated to it",
  "slice_types": "ACQUIRER_CHANNEL = acquirer and channel; MCC_GROUP_XB = merchant category group and domestic or cross-border; REGION = merchant region; CHANNEL = channel; CARD_SEGMENT = cardholder spending segment",
  "channels": "CP = card present; ECOM = e-commerce; REC = recurring or card-on-file charges; MANUAL = key-entered",
  "regions": "NE, SE, MW, SW, W = US regions; INTL = merchants outside the US",
  "z_score": "how unusual the acceptance declines are versus the same slice in the prior 28 days",
  "estimated_lost_spend_usd": "excess declines x average ticket x share of spend not recovered"
 }
}
```

- **summary:** On 2026-11-12, the DOMESTIC card segment on the acquired network recorded 114 acceptance declines against an expected 60.1, yielding 53.9 excess declines across 111 merchants — a z-score of 6.9, indicating a highly unusual spike versus the prior 28 days. The dominant decline category is CARD_ON_FILE_STALE (stored card credential not updated after reissue), accounting for 75.0% of acceptance declines. The remaining declines are spread across TOKEN_PROVISIONING (11), ACCEPTANCE_CONFIG (9), SYSTEM_ERROR (7), and CROSS_BORDER_BLOCK (2). This pattern has been elevated on 2 of the prior 2 days, suggesting a persistent issue rather than a one-day spike. Estimated lost spend is $1,628.0.
- **likely_cause:** `CARD_ON_FILE_STALE` · **certainty:** `likely` · **owner_team:** Card Technology
- **next_step:** Card Technology should review the DOMESTIC slice for 2026-11-12 on the acquired network, focusing on the CARD_ON_FILE_STALE category (75.0% of acceptance declines, elevated on 2 of the prior 2 days) across the 111 affected merchants, and determine what is preventing stored card credentials from being updated after reissue on the acquired network.

## `2026-11-12|OWN|CARD_SEGMENT|RECURRING_HEAVY`

### Prompt v1 (databricks-claude-sonnet-4-6); error: `None`

Facts given:

```json
{
 "business_date": "2026-11-12",
 "card_issuer_segment": "the banks own cards",
 "slice_type": "CARD_SEGMENT",
 "slice": "RECURRING_HEAVY",
 "network": "acquired network (cards already migrated)",
 "attempts": 181,
 "acceptance_declines": 22,
 "expected_acceptance_declines": 6.4,
 "excess_declines": 15.6,
 "z_score": 5.7,
 "estimated_lost_spend_usd": 611.0,
 "merchants_with_acceptance_declines": 21,
 "decline_categories": {
  "CARD_ON_FILE_STALE (stored card credential not updated after reissue)": 22
 },
 "dominant_category": "CARD_ON_FILE_STALE",
 "dominant_category_share_pct": 100.0,
 "elevated_on_prior_days_of_last_2": 2,
 "candidate_owner_team": "Card Technology"
}
```

- **summary:** On 2026-11-12, the RECURRING_HEAVY segment of the bank's own cards on the acquired network logged 22 acceptance declines against an expected baseline of 6.4, producing 15.6 excess declines and a z-score of 5.7. All 22 declines (100%) fall into the CARD_ON_FILE_STALE category, meaning merchants are attempting to charge stored card credentials that were not updated following card reissuance during the migration. The issue spans 21 distinct merchants and has been elevated on both prior days in the last 2-day lookback window, indicating this is a persistent, multi-day problem rather than a one-off spike. Estimated lost spend is $611.00.
- **likely_cause:** `CARD_ON_FILE_STALE` · **certainty:** `likely` · **owner_team:** Card Technology
- **next_step:** Card Technology should today audit the card reissuance records tied to the acquired network migration and confirm whether updated card credentials (new PAN, expiry, or token) were successfully pushed to the 21 affected merchants' stored-credential vaults. If the credential update process was not triggered or failed silently, initiate a bulk credential-refresh or account-updater run for all migrated cards in the RECURRING_HEAVY segment to unblock pending recurring charges.

### Prompt v2 (databricks-claude-sonnet-4-6); error: `None`

Facts given:

```json
{
 "business_date": "2026-11-12",
 "card_issuer_segment": "cards issued by this bank",
 "slice_type": "CARD_SEGMENT",
 "slice": "RECURRING_HEAVY",
 "network": "acquired network (cards already migrated)",
 "attempts": 181,
 "acceptance_declines": 22,
 "expected_acceptance_declines": 6.4,
 "excess_declines": 15.6,
 "z_score": 5.7,
 "estimated_lost_spend_usd": 611.0,
 "merchants_with_acceptance_declines": 21,
 "decline_categories": {
  "CARD_ON_FILE_STALE (stored card credential not updated after reissue)": 22
 },
 "dominant_category": "CARD_ON_FILE_STALE",
 "dominant_category_share_pct": 100.0,
 "elevated_on_prior_days_of_last_2": 2,
 "candidate_owner_team": "Card Technology",
 "glossary": {
  "attempts": "card authorization attempts",
  "acceptance_declines": "declines caused on the network or acquirer side (not the issuer credit decision); fixable",
  "acquired network": "the payment network the bank acquired; cards in this slice have already been migrated to it",
  "slice_types": "ACQUIRER_CHANNEL = acquirer and channel; MCC_GROUP_XB = merchant category group and domestic or cross-border; REGION = merchant region; CHANNEL = channel; CARD_SEGMENT = cardholder spending segment",
  "channels": "CP = card present; ECOM = e-commerce; REC = recurring or card-on-file charges; MANUAL = key-entered",
  "regions": "NE, SE, MW, SW, W = US regions; INTL = merchants outside the US",
  "z_score": "how unusual the acceptance declines are versus the same slice in the prior 28 days",
  "estimated_lost_spend_usd": "excess declines x average ticket x share of spend not recovered"
 }
}
```

- **summary:** On 2026-11-12, the RECURRING_HEAVY card segment on the acquired network recorded 22 acceptance declines against an expected 6.4, producing 15.6 excess declines across 21 merchants and an estimated $611.0 in lost spend. All 22 acceptance declines (100.0% of the total) fall into the CARD_ON_FILE_STALE category (stored card credential not updated after reissue). The anomaly has been elevated on 2 of the prior 2 days, indicating this is not an isolated spike but a persistent pattern since the card migration.
- **likely_cause:** `CARD_ON_FILE_STALE` · **certainty:** `likely` · **owner_team:** Card Technology
- **next_step:** Card Technology should review the RECURRING_HEAVY slice on the acquired network for 2026-11-12 and the 2 prior elevated days, focusing on why stored card credentials are not being updated after reissue across the 21 affected merchants, and determine what action is needed to resolve the credential staleness on the acquired network.

## `2026-11-12|OWN|CHANNEL|REC`

### Prompt v1 (databricks-claude-sonnet-4-6); error: `None`

Facts given:

```json
{
 "business_date": "2026-11-12",
 "card_issuer_segment": "the banks own cards",
 "slice_type": "CHANNEL",
 "slice": "REC",
 "network": "acquired network (cards already migrated)",
 "attempts": 367,
 "acceptance_declines": 122,
 "expected_acceptance_declines": 39.1,
 "excess_declines": 82.9,
 "z_score": 13.1,
 "estimated_lost_spend_usd": 3288.0,
 "merchants_with_acceptance_declines": 114,
 "decline_categories": {
  "TOKEN_PROVISIONING (wallet or card-on-file token not provisioned)": 4,
  "CARD_ON_FILE_STALE (stored card credential not updated after reissue)": 118
 },
 "dominant_category": "CARD_ON_FILE_STALE",
 "dominant_category_share_pct": 97.0,
 "elevated_on_prior_days_of_last_2": 2,
 "candidate_owner_team": "Card Technology"
}
```

- **summary:** On 2026-11-12, the REC (recurring) channel on the acquired network (cards already migrated) recorded 367 authorization attempts for the bank's own cards, of which 122 were acceptance declines — well above the expected 39.1, yielding 82.9 excess declines and a z-score of 13.1. The dominant decline category is CARD_ON_FILE_STALE, accounting for 97.0% (118 of 122) of acceptance declines across 114 affected merchants, with a small residual of 4 TOKEN_PROVISIONING declines. Estimated lost spend is $3,288.00. The pattern has been elevated on both of the prior 2 days, indicating this is not an isolated spike but a persistent issue likely tied to the network migration.
- **likely_cause:** `CARD_ON_FILE_STALE` · **certainty:** `likely` · **owner_team:** Card Technology
- **next_step:** Card Technology should today audit whether migrated card credentials (PANs, expiry dates, or network tokens) were propagated to merchants' card-on-file stores as part of the acquired network migration — specifically checking whether an account updater or credential push process was triggered for recurring merchants. The 114 merchants with acceptance declines should be cross-referenced against the migration roster to confirm all are on the acquired network and to identify any whose stored credentials were not refreshed post-migration.

### Prompt v2 (databricks-claude-sonnet-4-6); error: `None`

Facts given:

```json
{
 "business_date": "2026-11-12",
 "card_issuer_segment": "cards issued by this bank",
 "slice_type": "CHANNEL",
 "slice": "REC",
 "network": "acquired network (cards already migrated)",
 "attempts": 367,
 "acceptance_declines": 122,
 "expected_acceptance_declines": 39.1,
 "excess_declines": 82.9,
 "z_score": 13.1,
 "estimated_lost_spend_usd": 3288.0,
 "merchants_with_acceptance_declines": 114,
 "decline_categories": {
  "TOKEN_PROVISIONING (wallet or card-on-file token not provisioned)": 4,
  "CARD_ON_FILE_STALE (stored card credential not updated after reissue)": 118
 },
 "dominant_category": "CARD_ON_FILE_STALE",
 "dominant_category_share_pct": 97.0,
 "elevated_on_prior_days_of_last_2": 2,
 "candidate_owner_team": "Card Technology",
 "glossary": {
  "attempts": "card authorization attempts",
  "acceptance_declines": "declines caused on the network or acquirer side (not the issuer credit decision); fixable",
  "acquired network": "the payment network the bank acquired; cards in this slice have already been migrated to it",
  "slice_types": "ACQUIRER_CHANNEL = acquirer and channel; MCC_GROUP_XB = merchant category group and domestic or cross-border; REGION = merchant region; CHANNEL = channel; CARD_SEGMENT = cardholder spending segment",
  "channels": "CP = card present; ECOM = e-commerce; REC = recurring or card-on-file charges; MANUAL = key-entered",
  "regions": "NE, SE, MW, SW, W = US regions; INTL = merchants outside the US",
  "z_score": "how unusual the acceptance declines are versus the same slice in the prior 28 days",
  "estimated_lost_spend_usd": "excess declines x average ticket x share of spend not recovered"
 }
}
```

- **summary:** On 2026-11-12, the REC (recurring or card-on-file charges) channel on the acquired network recorded 122 acceptance declines against an expected 39.1, yielding 82.9 excess declines across 114 merchants — a z-score of 13.1, indicating a highly unusual spike versus the prior 28 days. This anomaly has been elevated on 2 of the last 2 prior days, suggesting it is not a one-off event. The dominant decline category, accounting for 97.0% of acceptance declines (118 of 122), is CARD_ON_FILE_STALE (stored card credential not updated after reissue). The remaining 4 declines fall under TOKEN_PROVISIONING (wallet or card-on-file token not provisioned). The estimated lost spend from these excess declines is $3,288.0. Because cards in this slice have already been migrated to the acquired network, the concentration of CARD_ON_FILE_STALE declines likely reflects stored card credentials that were not updated after reissue following the migration.
- **likely_cause:** `CARD_ON_FILE_STALE` · **certainty:** `likely` · **owner_team:** Card Technology
- **next_step:** Card Technology should review the REC channel slice on the acquired network for 2026-11-12 and the 2 prior elevated days, focusing on the 114 merchants with acceptance declines and the 118 CARD_ON_FILE_STALE declines, to determine whether stored card credentials were updated after reissue for cards already migrated to the acquired network.
