# Evidence 04: AI output samples (verbatim, with the facts given)

Generated 2026-11-24T20:08:41Z by tools/generate_evidence.py from the live workspace.

Proves what the intelligent step produces: an explainable anomaly score (frozen threshold) that flags slices, and an `ai_query` explanation per flag. For each case below, the representative flag shows the exact facts JSON given to the model and the model's structured answer, copied from the tables, unedited. The model only sees aggregated facts, never card-level data.

## Detector configuration (frozen before the held-out evaluation)

| config_version | threshold | volume_floor | frozen_at_utc | protocol |
|---|---|---|---|---|
| detector_v1 | 45.0 | 0 | 2026-11-23T06:37:57.166940Z | v1 + A1 + A2 |


## What was generated

Task `explain_anomalies` parameters in job `febar_main`: `{"llm_endpoint": "databricks-claude-sonnet-4-6", "prompt_version": "v3", "representatives_only": "true", "top_n": "60"}`. Rows with an empty prompt_version below are flags that were not sent to the model by those parameters.

| prompt_version | llm_model | flags | explained | errors | first_day | last_day |
|---|---|---|---|---|---|---|
|  |  | 185 | 0 | 0 | 2026-01-12 | 2026-11-11 |
| v1 | databricks-claude-sonnet-4-6 | 33 | 33 | 0 | 2026-11-11 | 2026-11-16 |
| v3 | databricks-claude-sonnet-4-6 | 36 | 36 | 0 | 2026-09-28 | 2026-11-16 |


History table `anomaly_explanations` (every explanation ever generated, all prompt versions):

| prompt_version | llm_model | explanations | first_at | last_at |
|---|---|---|---|---|
| v1 | databricks-claude-sonnet-4-6 | 65 | 2026-11-23T06:47:53.098Z | 2026-11-23T06:49:53.357Z |
| v2 | databricks-claude-sonnet-4-6 | 30 | 2026-11-23T07:02:29.971Z | 2026-11-23T07:02:29.971Z |
| v3 | databricks-claude-sonnet-4-6 | 36 | 2026-11-23T07:15:51.124Z | 2026-11-23T07:23:34.407Z |


## Flags by likely root cause

| likely_root_cause | flags | first_day | last_day | max_score | exposure_usd |
|---|---|---|---|---|---|
| CARD_ON_FILE_STALE | 161 | 2026-11-02 | 2026-11-12 | 92.8 | 146550.55 |
| PROCESSOR_TIMEOUT | 49 | 2026-11-14 | 2026-11-16 | 92.5 | 67617.13 |
| ACCEPTANCE_CONFIG | 23 | 2026-01-12 | 2026-10-08 | 88.5 | 18074.49 |
| CROSS_BORDER_BLOCK | 21 | 2026-10-12 | 2026-10-20 | 90.1 | 32166.87 |


## One explained flag per case (highest score in the case's episode), verbatim


### Case 1: CROSS_BORDER_BLOCK / OWN (2026-10-12 → 2026-10-20)

| item | value |
|---|---|
| anomaly_key | 2026-10-16\|OWN\|MCC_GROUP_XB\|TRAVEL_LODGING / CROSS_BORDER |
| business_date | 2026-10-16 |
| slice | MCC_GROUP_XB: TRAVEL_LODGING / CROSS_BORDER |
| score | 90.1 |
| drivers (score explanation) | ["28 acceptance declines vs 4.8 expected (z = 9.6)","$2,769 estimated lost spend","100% of them CROSS_BORDER_BLOCK","28 merchants affected","elevated on 2 of the prior 2 days"] |
| model | databricks-claude-sonnet-4-6 |
| prompt_version | v3 |


Facts given to the model:

```json
{
 "business_date": "2026-10-16",
 "card_issuer_segment": "cards issued by this bank",
 "slice_type": "MCC_GROUP_XB",
 "slice": "TRAVEL_LODGING / CROSS_BORDER",
 "network": "acquired network (cards already migrated)",
 "attempts": 71,
 "acceptance_declines": 28,
 "expected_acceptance_declines": 4.8,
 "excess_declines": 23.2,
 "z_score": 9.6,
 "estimated_lost_spend_usd": 2769.0,
 "merchants_with_acceptance_declines": 28,
 "decline_categories": {
  "CROSS_BORDER_BLOCK (cross-border not enabled for merchant category or product)": 28
 },
 "dominant_category": "CROSS_BORDER_BLOCK",
 "dominant_category_share_pct": 100.0,
 "elevated_on_prior_days_of_last_2": 2,
 "candidate_owner_team": "Network Integration",
 "playbook_for_dominant_category": [
  "Network Integration: check whether cross-border acceptance is enabled on the acquired network for the merchant category group in this slice",
  "Network Integration: confirm with the network team whether the block is intended and, if not, request it is lifted"
 ],
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

Model answer (structured output):

| item | value |
|---|---|
| summary | On 2026-10-16, the TRAVEL_LODGING / CROSS_BORDER slice on the acquired network (cards already migrated) recorded 28 acceptance declines against an expected 4.8, producing 23.2 excess declines across 28 merchants and an estimated $2769.0 in lost spend. Every one of the 28 acceptance declines falls into the CROSS_BORDER_BLOCK category, meaning cross-border is likely not enabled for this merchant category group or product on the acquired network. The z-score of 9.6 confirms this is highly unusual relative to the prior 28 days, and the pattern has been elevated on 2 of the last 2 prior days, suggesting a persistent configuration gap rather than a one-off event. |
| likely_cause | CROSS_BORDER_BLOCK |
| certainty | likely |
| next_step | Network Integration should check today whether cross-border acceptance is enabled on the acquired network for the TRAVEL_LODGING merchant category group in the CROSS_BORDER slice, then confirm with the network team whether the block is intended and, if not, request it is lifted. |
| owner_team | Network Integration |
| facts_used | ["business_date","slice_type","slice","network","attempts","acceptance_declines","expected_acceptance_declines","excess_declines","z_score","estimated_lost_spend_usd","merchants_with_acceptance_declines","decline_categories","dominant_category","dominant_category_share_pct","elevated_on_prior_days_of_last_2","candidate_owner_team","playbook_for_dominant_category"] |
| error |  |


### Case 2: CARD_ON_FILE_STALE / THIRD_PARTY (2026-11-02 → 2026-11-09)

| item | value |
|---|---|
| anomaly_key | 2026-11-05\|THIRD_PARTY\|CHANNEL\|REC |
| business_date | 2026-11-05 |
| slice | CHANNEL: REC |
| score | 87.7 |
| drivers (score explanation) | ["20 acceptance declines vs 2.0 expected (z = 10.4)","$614 estimated lost spend","100% of them CARD_ON_FILE_STALE","20 merchants affected","elevated on 2 of the prior 2 days"] |
| model | databricks-claude-sonnet-4-6 |
| prompt_version | v3 |


Facts given to the model:

```json
{
 "business_date": "2026-11-05",
 "card_issuer_segment": "cards of third-party issuers processed on the network",
 "slice_type": "CHANNEL",
 "slice": "REC",
 "network": "acquired network (cards already migrated)",
 "attempts": 51,
 "acceptance_declines": 20,
 "expected_acceptance_declines": 2.0,
 "excess_declines": 18.0,
 "z_score": 10.4,
 "estimated_lost_spend_usd": 614.0,
 "merchants_with_acceptance_declines": 20,
 "decline_categories": {
  "CARD_ON_FILE_STALE (stored card credential not updated after reissue)": 20
 },
 "dominant_category": "CARD_ON_FILE_STALE",
 "dominant_category_share_pct": 100.0,
 "elevated_on_prior_days_of_last_2": 2,
 "candidate_owner_team": "Card Technology",
 "playbook_for_dominant_category": [
  "Card Technology: pull the list of merchants in this slice with stored-credential declines on this date",
  "Card Technology: send those merchants refreshed stored credentials for the reissued cards"
 ],
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

Model answer (structured output):

| item | value |
|---|---|
| summary | On 2026-11-05, the REC (recurring or card-on-file charges) channel on the acquired network recorded 20 acceptance declines against an expected 2.0, producing 18.0 excess declines and a z_score of 10.4 — a highly unusual spike. All 20 declines fall into a single category: CARD_ON_FILE_STALE (stored card credential not updated after reissue), accounting for 100.0% of acceptance declines across 20 distinct merchants. This pattern has been elevated on 2 of the prior 2 days, indicating a persistent issue since the card migration. Estimated lost spend is $614.0. |
| likely_cause | CARD_ON_FILE_STALE |
| certainty | likely |
| next_step | Card Technology should pull the list of the 20 merchants in the REC slice with stored-credential declines on 2026-11-05, then send those merchants refreshed stored credentials for the reissued cards. |
| owner_team | Card Technology |
| facts_used | ["business_date","slice","slice_type","network","attempts","acceptance_declines","expected_acceptance_declines","excess_declines","z_score","estimated_lost_spend_usd","merchants_with_acceptance_declines","decline_categories","dominant_category","dominant_category_share_pct","elevated_on_prior_days_of_last_2","candidate_owner_team","playbook_for_dominant_category"] |
| error |  |


### Case 3: CARD_ON_FILE_STALE / OWN (2026-11-02 → 2026-11-12)

| item | value |
|---|---|
| anomaly_key | 2026-11-07\|OWN\|CHANNEL\|REC |
| business_date | 2026-11-07 |
| slice | CHANNEL: REC |
| score | 92.8 |
| drivers (score explanation) | ["128 acceptance declines vs 23.3 expected (z = 21.2)","$3,889 estimated lost spend","99% of them CARD_ON_FILE_STALE","126 merchants affected","elevated on 2 of the prior 2 days"] |
| model | databricks-claude-sonnet-4-6 |
| prompt_version | v3 |


Facts given to the model:

```json
{
 "business_date": "2026-11-07",
 "card_issuer_segment": "cards issued by this bank",
 "slice_type": "CHANNEL",
 "slice": "REC",
 "network": "acquired network (cards already migrated)",
 "attempts": 399,
 "acceptance_declines": 128,
 "expected_acceptance_declines": 23.3,
 "excess_declines": 104.7,
 "z_score": 21.2,
 "estimated_lost_spend_usd": 3889.0,
 "merchants_with_acceptance_declines": 126,
 "decline_categories": {
  "TOKEN_PROVISIONING (wallet or card-on-file token not provisioned)": 1,
  "CARD_ON_FILE_STALE (stored card credential not updated after reissue)": 127
 },
 "dominant_category": "CARD_ON_FILE_STALE",
 "dominant_category_share_pct": 99.0,
 "elevated_on_prior_days_of_last_2": 2,
 "candidate_owner_team": "Card Technology",
 "playbook_for_dominant_category": [
  "Card Technology: pull the list of merchants in this slice with stored-credential declines on this date",
  "Card Technology: send those merchants refreshed stored credentials for the reissued cards"
 ],
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

Model answer (structured output):

| item | value |
|---|---|
| summary | On 2026-11-07, the REC (recurring or card-on-file charges) channel on the acquired network showed a sharp spike in acceptance declines for cards issued by this bank. Of 399 authorization attempts, 128 resulted in acceptance declines against an expected 23.3, producing 104.7 excess declines and an estimated lost spend of $3,889.00. The anomaly spans 126 merchants and has been elevated on 2 of the prior 2 days. The dominant cause — accounting for 99.0% of acceptance declines across 127 decline events — is likely CARD_ON_FILE_STALE: stored card credentials not updated after reissue. A further 1 decline is possibly attributable to a wallet or card-on-file token not provisioned (TOKEN_PROVISIONING). The z-score of 21.2 confirms this pattern is highly unusual relative to the same slice over the prior 28 days. |
| likely_cause | CARD_ON_FILE_STALE |
| certainty | likely |
| next_step | Card Technology should pull the list of merchants in the REC slice on the acquired network with stored-credential declines on 2026-11-07 (126 merchants with acceptance declines, 127 CARD_ON_FILE_STALE events) and send those merchants refreshed stored credentials for the reissued cards. |
| owner_team | Card Technology |
| facts_used | ["business_date","slice","slice_type","network","attempts","acceptance_declines","expected_acceptance_declines","excess_declines","z_score","estimated_lost_spend_usd","merchants_with_acceptance_declines","decline_categories","dominant_category","dominant_category_share_pct","elevated_on_prior_days_of_last_2","candidate_owner_team","playbook_for_dominant_category"] |
| error |  |


### Case 5: PROCESSOR_TIMEOUT / OWN (2026-11-14 → 2026-11-16)

| item | value |
|---|---|
| anomaly_key | 2026-11-16\|OWN\|REGION\|SE |
| business_date | 2026-11-16 |
| slice | REGION: SE |
| score | 92.5 |
| drivers (score explanation) | ["165 acceptance declines vs 27.9 expected (z = 25.5)","$4,608 estimated lost spend","95% of them PROCESSOR_TIMEOUT","164 merchants affected","elevated on 2 of the prior 2 days"] |
| model | databricks-claude-sonnet-4-6 |
| prompt_version | v3 |


Facts given to the model:

```json
{
 "business_date": "2026-11-16",
 "card_issuer_segment": "cards issued by this bank",
 "slice_type": "REGION",
 "slice": "SE",
 "network": "acquired network (cards already migrated)",
 "attempts": 1164,
 "acceptance_declines": 165,
 "expected_acceptance_declines": 27.9,
 "excess_declines": 137.1,
 "z_score": 25.5,
 "estimated_lost_spend_usd": 4608.0,
 "merchants_with_acceptance_declines": 164,
 "decline_categories": {
  "ACCEPTANCE_CONFIG (merchant/acquirer acceptance profile not configured or rejected)": 3,
  "TOKEN_PROVISIONING (wallet or card-on-file token not provisioned)": 3,
  "PROCESSOR_TIMEOUT (issuer or switch timed out)": 156,
  "SYSTEM_ERROR (network system error)": 3
 },
 "dominant_category": "PROCESSOR_TIMEOUT",
 "dominant_category_share_pct": 95.0,
 "elevated_on_prior_days_of_last_2": 2,
 "candidate_owner_team": "Network Operations",
 "playbook_for_dominant_category": [
  "Network Operations: check processor response times on the acquired network for this slice and date",
  "Network Operations: open an incident with the processing team for this slice if timeouts continue"
 ],
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

Model answer (structured output):

| item | value |
|---|---|
| summary | On 2026-11-16, the SE merchant region on the acquired network (cards already migrated) recorded 165 acceptance declines against an expected 27.9, producing 137.1 excess declines across 164 merchants out of 1,164 authorization attempts. The anomaly is highly unusual (z_score 25.5) and has been elevated on 2 of the prior 2 days, suggesting a persistent issue rather than a one-off spike. The dominant decline category is PROCESSOR_TIMEOUT (issuer or switch timed out), accounting for 95.0% of acceptance declines (156 of 165), with estimated lost spend of $4,608.00. Smaller contributions came from ACCEPTANCE_CONFIG, TOKEN_PROVISIONING, and SYSTEM_ERROR (3 declines each). |
| likely_cause | PROCESSOR_TIMEOUT |
| certainty | likely |
| next_step | Network Operations should check processor response times on the acquired network for the SE slice on 2026-11-16; if timeouts are confirmed to be continuing, open an incident with the processing team for the SE slice. |
| owner_team | Network Operations |
| facts_used | ["business_date","slice","slice_type","network","attempts","acceptance_declines","expected_acceptance_declines","excess_declines","z_score","estimated_lost_spend_usd","merchants_with_acceptance_declines","decline_categories","dominant_category","dominant_category_share_pct","elevated_on_prior_days_of_last_2","candidate_owner_team","playbook_for_dominant_category"] |
| error |  |


### Case 6: ACCEPTANCE_CONFIG / OWN (2026-09-24 → 2026-10-08)

| item | value |
|---|---|
| anomaly_key | 2026-09-28\|OWN\|ACQUIRER_CHANNEL\|ACQ-017 / ECOM |
| business_date | 2026-09-28 |
| slice | ACQUIRER_CHANNEL: ACQ-017 / ECOM |
| score | 88.5 |
| drivers (score explanation) | ["20 acceptance declines vs 1.6 expected (z = 11.5)","$950 estimated lost spend","100% of them ACCEPTANCE_CONFIG","19 merchants affected","elevated on 2 of the prior 2 days"] |
| model | databricks-claude-sonnet-4-6 |
| prompt_version | v3 |


Facts given to the model:

```json
{
 "business_date": "2026-09-28",
 "card_issuer_segment": "cards issued by this bank",
 "slice_type": "ACQUIRER_CHANNEL",
 "slice": "ACQ-017 / ECOM",
 "network": "acquired network (cards already migrated)",
 "attempts": 31,
 "acceptance_declines": 20,
 "expected_acceptance_declines": 1.6,
 "excess_declines": 18.4,
 "z_score": 11.5,
 "estimated_lost_spend_usd": 950.0,
 "merchants_with_acceptance_declines": 19,
 "decline_categories": {
  "ACCEPTANCE_CONFIG (merchant/acquirer acceptance profile not configured or rejected)": 20
 },
 "dominant_category": "ACCEPTANCE_CONFIG",
 "dominant_category_share_pct": 100.0,
 "elevated_on_prior_days_of_last_2": 2,
 "candidate_owner_team": "Acquirer Relations",
 "acquirer": {
  "name": "Ridgeline Merchant Services",
  "last_configuration_change": "2026-09-22",
  "configuration_note": "Meridian profile update: e-commerce token cryptogram settings"
 },
 "playbook_for_dominant_category": [
  "Acquirer Relations: contact the acquirer in this slice to confirm its acceptance profile for this channel on the acquired network, citing its last configuration change if one is given",
  "Acquirer Relations: send the acquirer the list of merchants in this slice with acceptance declines on this date"
 ],
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

Model answer (structured output):

| item | value |
|---|---|
| summary | On 2026-09-28, the ACQ-017 / ECOM slice on the acquired network recorded 20 acceptance declines against an expected 1.6, producing 18.4 excess declines across 19 merchants and an estimated $950.00 in lost spend. All 20 declines (100.0% of the total) fall into the ACCEPTANCE_CONFIG category — meaning the merchant/acquirer acceptance profile is not configured or rejected — and the anomaly has been elevated on 2 of the prior 2 days. The last configuration change for acquirer Ridgeline Merchant Services was on 2026-09-22, noted as a Meridian profile update to e-commerce token cryptogram settings, which likely introduced the misconfiguration driving these declines. |
| likely_cause | ACCEPTANCE_CONFIG |
| certainty | likely |
| next_step | Acquirer Relations should contact Ridgeline Merchant Services today to confirm its acceptance profile for the e-commerce channel on the acquired network, citing the 2026-09-22 configuration change (Meridian profile update: e-commerce token cryptogram settings), and send them the list of the 19 merchants in the ACQ-017 / ECOM slice that received acceptance declines on 2026-09-28. |
| owner_team | Acquirer Relations |
| facts_used | ["business_date","slice_type","slice","network","attempts","acceptance_declines","expected_acceptance_declines","excess_declines","estimated_lost_spend_usd","merchants_with_acceptance_declines","decline_categories","dominant_category","dominant_category_share_pct","elevated_on_prior_days_of_last_2","candidate_owner_team","acquirer.name","acquirer.last_configuration_change","acquirer.configuration_note","playbook_for_dominant_category"] |
| error |  |


### Case 7: PROCESSOR_TIMEOUT / THIRD_PARTY (2026-11-14 → 2026-11-16)

| item | value |
|---|---|
| anomaly_key | 2026-11-16\|THIRD_PARTY\|REGION\|SE |
| business_date | 2026-11-16 |
| slice | REGION: SE |
| score | 84.9 |
| drivers (score explanation) | ["26 acceptance declines vs 4.2 expected (z = 9.5)","$612 estimated lost spend","92% of them PROCESSOR_TIMEOUT","26 merchants affected","elevated on 2 of the prior 2 days"] |
| model | databricks-claude-sonnet-4-6 |
| prompt_version | v3 |


Facts given to the model:

```json
{
 "business_date": "2026-11-16",
 "card_issuer_segment": "cards of third-party issuers processed on the network",
 "slice_type": "REGION",
 "slice": "SE",
 "network": "acquired network (cards already migrated)",
 "attempts": 162,
 "acceptance_declines": 26,
 "expected_acceptance_declines": 4.2,
 "excess_declines": 21.8,
 "z_score": 9.5,
 "estimated_lost_spend_usd": 612.0,
 "merchants_with_acceptance_declines": 26,
 "decline_categories": {
  "ACCEPTANCE_CONFIG (merchant/acquirer acceptance profile not configured or rejected)": 1,
  "TOKEN_PROVISIONING (wallet or card-on-file token not provisioned)": 1,
  "PROCESSOR_TIMEOUT (issuer or switch timed out)": 24
 },
 "dominant_category": "PROCESSOR_TIMEOUT",
 "dominant_category_share_pct": 92.0,
 "elevated_on_prior_days_of_last_2": 2,
 "candidate_owner_team": "Network Operations",
 "playbook_for_dominant_category": [
  "Network Operations: check processor response times on the acquired network for this slice and date",
  "Network Operations: open an incident with the processing team for this slice if timeouts continue"
 ],
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

Model answer (structured output):

| item | value |
|---|---|
| summary | On 2026-11-16, the SE region slice on the acquired network (cards already migrated) recorded 26 acceptance declines out of 162 attempts, against an expected 4.2 — an excess of 21.8 declines with a z-score of 9.5, representing $612.0 in estimated lost spend. 92.0% of those acceptance declines (24 out of 26) fall into the PROCESSOR_TIMEOUT category (issuer or switch timed out), making it the dominant and likely cause of the anomaly. The remaining declines are split between ACCEPTANCE_CONFIG (1) and TOKEN_PROVISIONING (1). The pattern is not isolated to this date: the slice was also elevated on 2 of the prior 2 days, suggesting a persistent issue rather than a one-time spike. All 26 merchants with acceptance declines are affected across the SE region. |
| likely_cause | PROCESSOR_TIMEOUT |
| certainty | likely |
| next_step | Network Operations should check processor response times on the acquired network for the SE region slice on 2026-11-16, and — given that the slice was elevated on all 2 of the prior 2 days — open an incident with the processing team for this slice if timeouts continue. |
| owner_team | Network Operations |
| facts_used | ["business_date","slice_type","slice","network","attempts","acceptance_declines","expected_acceptance_declines","excess_declines","z_score","estimated_lost_spend_usd","merchants_with_acceptance_declines","decline_categories","dominant_category","dominant_category_share_pct","elevated_on_prior_days_of_last_2","candidate_owner_team","playbook_for_dominant_category"] |
| error |  |


## The full prompt sent for one flag (latest prompt version), verbatim

`2026-09-28|OWN|ACQUIRER_CHANNEL|ACQ-017 / ECOM`, prompt `v3`:

```
You are assisting a payment network operations analyst at a card issuer that is migrating cards to an acquired payment network.
Below are the facts about ONE flagged authorization anomaly, as JSON. Write a short explanation and the next action.

Rules:
- Use ONLY the facts given. Do not invent people, merchants, amounts, dates, tickets, documents or systems that are not in the facts.
- Every number you write must appear in the facts.
- The cause is an inference from decline codes: present it as likely (or possible), never as a confirmed fact.
- Do not restate or change the score, rank or severity; do not rate priority.
- next_step: one concrete action an operations team can take today, naming what to check or whom to contact, based on the facts.
- owner_team: choose from the allowed list; prefer candidate_owner_team unless the facts clearly contradict it.
- facts_used: list the fact names you relied on.

- Describe the likely cause ONLY in the words of the decline category description given in the facts. Do not add
  mechanisms, systems, processes, data fields, files, deadlines or parties that are not in the facts
  (for example: no "pipeline", "account updater", "PAN", "token vault", "end of business").
- You may use the glossary wording for codes (e.g. REC = recurring or card-on-file charges).
- Copy every number exactly as it is written in the facts (no reformatting, no new percentages, ratios or totals).
- next_step: pick the most fitting action from playbook_for_dominant_category and make it specific with items from the
  facts (slice, date, decline categories, merchant count, acquirer name and configuration change if given).
  Do not add actions, systems or parties that are not in the playbook or the facts.

FACTS:
{"business_date":"2026-09-28","card_issuer_segment":"cards issued by this bank","slice_type":"ACQUIRER_CHANNEL","slice":"ACQ-017 / ECOM","network":"acquired network (cards already migrated)","attempts":31,"acceptance_declines":20,"expected_acceptance_declines":1.6,"excess_declines":18.4,"z_score":11.5,"estimated_lost_spend_usd":950.0,"merchants_with_acceptance_declines":19,"decline_categories":{"ACCEPTANCE_CONFIG (merchant/acquirer acceptance profile not configured or rejected)":20},"dominant_category":"ACCEPTANCE_CONFIG","dominant_category_share_pct":100.0,"elevated_on_prior_days_of_last_2":2,"candidate_owner_team":"Acquirer Relations","acquirer":{"name":"Ridgeline Merchant Services","last_configuration_change":"2026-09-22","configuration_note":"Meridian profile update: e-commerce token cryptogram settings"},"playbook_for_dominant_category":["Acquirer Relations: contact the acquirer in this slice to confirm its acceptance profile for this channel on the acquired network, citing its last configuration change if one is given","Acquirer Relations: send the acquirer the list of merchants in this slice with acceptance declines on this date"],"glossary":{"attempts":"card authorization attempts","acceptance_declines":"declines caused on the network or acquirer side (not the issuer credit decision); fixable","acquired network":"the payment network the bank acquired; cards in this slice have already been migrated to it","slice_types":"ACQUIRER_CHANNEL = acquirer and channel; MCC_GROUP_XB = merchant category group and domestic or cross-border; REGION = merchant region; CHANNEL = channel; CARD_SEGMENT = cardholder spending segment","channels":"CP = card present; ECOM = e-commerce; REC = recurring or card-on-file charges; MANUAL = key-entered","regions":"NE, SE, MW, SW, W = US regions; INTL = merchants outside the US","z_score":"how unusual the acceptance declines are versus the same slice in the prior 28 days","estimated_lost_spend_usd":"excess declines x average ticket x share of spend not recovered"}}
```
