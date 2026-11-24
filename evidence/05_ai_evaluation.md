# Evidence 05: AI evaluation and iteration history

Generated 2026-11-24T20:08:54Z by tools/generate_evidence.py from the live workspace.

Proves how well the intelligent step works, measured against the answer key under the pre-registered protocol (EVAL_PROTOCOL.md): detection precision and recall of the method vs a simple baseline on tuning and held-out days, and LLM-judge plus rule-check pass rates of the explanations for each prompt version (the iteration history). Every row comes from the `eval_runs` and `eval_judge_results` tables written by `src/ai/evaluate.py`; failures are shown, not hidden.

## Evaluation runs

| run_label | run_at_utc | protocol | detector | threshold | frozen_at_utc | has detection | has genai |
|---|---|---|---|---|---|---|---|
| eval_v1 | 2026-11-23T06:51:52.536625Z | v1 + A1 + A2 | detector_v1 | 45 | 2026-11-23T06:37:57.166940Z | True | True |
| eval_v1b | 2026-11-23T06:59:57.706968Z | v1 + A1 + A2 | detector_v1 | 45 | 2026-11-23T06:37:57.166940Z | True | True |
| eval_v2 | 2026-11-23T07:03:39.187490Z | v1 + A1 + A2 | detector_v1 | 45 | 2026-11-23T06:37:57.166940Z | False | True |
| eval_v3 | 2026-11-23T07:17:03.503932Z | v1 + A1 + A2 | detector_v1 | 45 | 2026-11-23T06:37:57.166940Z | False | True |
| eval_supp_41_60 | 2026-11-23T16:50:26.261269Z | v1 + A1 + A2 + A3 + Errata 1 | detector_v1 | 45 | 2026-11-23T06:37:57.166940Z | True | False |


## Detection: method vs baseline (counts of daily flags; a hit = the flag overlaps a planted incident)

| run | method | split | days | flags | hits | precision | precision 95% CI (Wilson) | incidents caught | incident-day recall | decoy flags |
|---|---|---|---|---|---|---|---|---|---|---|
| eval_v1 | method | tuning | 2026-09-21..2026-10-30 | 42 | 42 | 1 | 0.916–1.000 | 2/2 | 1 | 0 |
| eval_v1 | method | holdout | 2026-10-31..2026-11-17 | 210 | 196 | 0.933 | 0.891–0.960 | 2/2 | 1 | 14 |
| eval_v1 | baseline | tuning | 2026-09-21..2026-10-30 | 539 | 15 | 0.028 | 0.017–0.045 | 2/2 | 0.292 | 0 |
| eval_v1 | baseline | holdout | 2026-10-31..2026-11-17 | 296 | 31 | 0.105 | 0.075–0.145 | 2/2 | 0.929 | 125 |
| eval_v1b | method | tuning | 2026-09-21..2026-10-30 | 42 | 42 | 1 | 0.916–1.000 | 2/2 | 1 | 0 |
| eval_v1b | method | holdout | 2026-10-31..2026-11-17 | 210 | 210 | 1 | 0.982–1.000 | 2/2 | 1 | 0 |
| eval_v1b | baseline | tuning | 2026-09-21..2026-10-30 | 539 | 15 | 0.028 | 0.017–0.045 | 2/2 | 0.292 | 0 |
| eval_v1b | baseline | holdout | 2026-10-31..2026-11-17 | 296 | 31 | 0.105 | 0.075–0.145 | 2/2 | 0.929 | 125 |
| eval_supp_41_60 | method | tuning | 2026-09-21..2026-10-30 | 42 | 42 | 1 | 0.916–1.000 | 2/2 | 1 | 0 |
| eval_supp_41_60 | method | holdout | 2026-10-31..2026-11-19 | 210 | 210 | 1 | 0.982–1.000 | 2/2 | 1 | 0 |
| eval_supp_41_60 | baseline | tuning | 2026-09-21..2026-10-30 | 539 | 15 | 0.028 | 0.017–0.045 | 2/2 | 0.292 | 0 |
| eval_supp_41_60 | baseline | holdout | 2026-10-31..2026-11-19 | 304 | 31 | 0.102 | 0.073–0.141 | 2/2 | 0.929 | 125 |


### Per incident (method)

| run | split | incident | caught | first flag | delay (days) | days flagged | root cause at first flag | root cause correct |
|---|---|---|---|---|---|---|---|---|
| eval_v1 | tuning | INC1 | True | 2026-09-24 | 0 | 15/15 | ACCEPTANCE_CONFIG | True |
| eval_v1 | tuning | INC2 | True | 2026-10-12 | 0 | 9/9 | CROSS_BORDER_BLOCK | True |
| eval_v1 | holdout | INC3 | True | 2026-11-02 | 0 | 11/11 | CARD_ON_FILE_STALE | True |
| eval_v1 | holdout | INC4 | True | 2026-11-14 | 0 | 3/3 | PROCESSOR_TIMEOUT | True |
| eval_v1b | tuning | INC1 | True | 2026-09-24 | 0 | 15/15 | ACCEPTANCE_CONFIG | True |
| eval_v1b | tuning | INC2 | True | 2026-10-12 | 0 | 9/9 | CROSS_BORDER_BLOCK | True |
| eval_v1b | holdout | INC3 | True | 2026-11-02 | 0 | 11/11 | CARD_ON_FILE_STALE | True |
| eval_v1b | holdout | INC4 | True | 2026-11-14 | 0 | 3/3 | PROCESSOR_TIMEOUT | True |
| eval_supp_41_60 | tuning | INC1 | True | 2026-09-24 | 0 | 15/15 | ACCEPTANCE_CONFIG | True |
| eval_supp_41_60 | tuning | INC2 | True | 2026-10-12 | 0 | 9/9 | CROSS_BORDER_BLOCK | True |
| eval_supp_41_60 | holdout | INC3 | True | 2026-11-02 | 0 | 11/11 | CARD_ON_FILE_STALE | True |
| eval_supp_41_60 | holdout | INC4 | True | 2026-11-14 | 0 | 3/3 | PROCESSOR_TIMEOUT | True |


### No-claim conditions (EVAL_PROTOCOL §6: if a condition is TRUE, the matching claim is not made)

| run | condition | value |
|---|---|---|
| eval_v1 | beats_baseline_by_20pts_at_equal_or_better_precision | False |
| eval_v1 | decoy_flagged_by_method | True |
| eval_v1 | method_precision_below_50pct | False |
| eval_v1 | look_ahead_detected | False |
| eval_v1 | no_claim_grounding_below_90pct | True |
| eval_v1b | beats_baseline_by_20pts_at_equal_or_better_precision | False |
| eval_v1b | decoy_flagged_by_method | False |
| eval_v1b | method_precision_below_50pct | False |
| eval_v1b | look_ahead_detected | False |
| eval_v1b | no_claim_grounding_below_90pct | False |
| eval_v2 | no_claim_grounding_below_90pct | False |
| eval_v3 | no_claim_grounding_below_90pct | False |
| eval_supp_41_60 | beats_baseline_by_20pts_at_equal_or_better_precision | False |
| eval_supp_41_60 | decoy_flagged_by_method | False |
| eval_supp_41_60 | method_precision_below_50pct | False |
| eval_supp_41_60 | look_ahead_detected | False |


## Explanations: judge and rule pass rates per prompt version (iteration history)

| run | prompt | judge model | rows | LLM errors | cause_agreement | grounded_in_facts | actionable_next_step | no_invented_data | rule_numbers_grounded | rule_cause_matches | MLflow run |
|---|---|---|---|---|---|---|---|---|---|---|---|
| eval_v1 | v1 | databricks-gpt-5-4 | 30 | 0 | 30/30 | 0/30 | 30/30 | 0/30 | 6/30 | 30/30 | a5ce8d3c3ebc4040be53c89ef8ed149d |
| eval_v1b | v1 | databricks-gpt-5-4 | 30 | 0 | 30/30 | 0/30 | 29/30 | 0/30 | 30/30 | 30/30 | de0ae0fe2e924cb58db5aa609d5a6eb1 |
| eval_v2 | v2 | databricks-gpt-5-4 | 30 | 0 | 30/30 | 0/30 | 22/30 | 4/30 | 30/30 | 30/30 | e11d3d759d394f37b3d5e371892bae7d |
| eval_v3 | v3 | databricks-gpt-5-4 | 30 | 0 | 30/30 | 1/30 | 23/30 | 9/30 | 30/30 | 30/30 | 502a6c985e9d480d9d9cc6e51d6b6ace |


Judges `actionable_next_step`, `no_invented_data`, `grounded_in_facts` and `cause_agreement` are MLflow 3 Guidelines judges (LLM); `rule_numbers_grounded` and `rule_cause_matches` are deterministic rule checks (every number in the text appears in the facts; the stated cause equals the computed root cause).


## Judge results as stored (latest run per prompt version)

| run_label | prompt_version | judge | n | pass |
|---|---|---|---|---|
| eval_v1b | v1 | actionable_next_step | 30 | 29 |
| eval_v1b | v1 | cause_agreement | 30 | 30 |
| eval_v1b | v1 | grounded_in_facts | 30 | 0 |
| eval_v1b | v1 | no_invented_data | 30 | 0 |
| eval_v1b | v1 | rule_cause_matches | 30 | 30 |
| eval_v1b | v1 | rule_numbers_grounded | 30 | 30 |
| eval_v2 | v2 | actionable_next_step | 30 | 22 |
| eval_v2 | v2 | cause_agreement | 30 | 30 |
| eval_v2 | v2 | grounded_in_facts | 30 | 0 |
| eval_v2 | v2 | no_invented_data | 30 | 4 |
| eval_v2 | v2 | rule_cause_matches | 30 | 30 |
| eval_v2 | v2 | rule_numbers_grounded | 30 | 30 |
| eval_v3 | v3 | actionable_next_step | 30 | 23 |
| eval_v3 | v3 | cause_agreement | 30 | 30 |
| eval_v3 | v3 | grounded_in_facts | 30 | 1 |
| eval_v3 | v3 | no_invented_data | 30 | 9 |
| eval_v3 | v3 | rule_cause_matches | 30 | 30 |
| eval_v3 | v3 | rule_numbers_grounded | 30 | 30 |


## Failing judgements, verbatim (latest prompt version, up to 3 per judge)

| run_label | prompt_version | judge | anomaly_key | value | rationale |
|---|---|---|---|---|---|
| eval_v3 | v3 | actionable_next_step | 2026-11-14\|OWN\|MCC_GROUP_XB\|FUEL / DOMESTIC | no | The guideline requires next_step to be one concrete action an operations team could start today. The provided next_step contains two actions joined together: first, check processor response times on the acquired network for the FUEL / DOMESTIC slice on 2026-11-14, and second, if timeouts continue, open an incident with the processing team. Because it is not a single concrete action, it does not fully satisfy the guideline. The response does avoid purely generic advice, since it specifies what to check and whom to contact, but it still fails the requirement that next_step be one concrete action. |
| eval_v3 | v3 | actionable_next_step | 2026-11-15\|OWN\|CARD_SEGMENT\|DOMESTIC | no | The applicable guideline is that next_step must be one concrete action an operations team could start today, stating what to check or whom to contact, and fitting the likely cause and owner_team. The provided next_step includes two actions joined by a conditional: first checking processor response times, and then, if timeouts continue, opening an incident with the processing team. Because it is not one concrete action, it does not fully satisfy the guideline. The second guideline about avoiding generic advice is satisfied, since the response specifies what to check and whom to contact rather than saying only to monitor or investigate further. |
| eval_v3 | v3 | actionable_next_step | 2026-11-16\|OWN\|ACQUIRER_CHANNEL\|ACQ-003 / CP | no | The key guideline requires next_step to be one concrete action an operations team could start today. The provided next_step contains two actions: first, check processor response times on the acquired network for the ACQ-003 / CP slice on 2026-11-16, and second, if timeouts continue, open an incident with the processing team. Because it includes multiple actions rather than one concrete action, it does not fully satisfy the guideline. The second guideline says generic advice without saying what to check fails; that part is satisfied because it specifies what to check. However, full compliance fails due to the next_step not being a single concrete action. |
| eval_v3 | v3 | grounded_in_facts | 2026-11-11\|OWN\|MCC_GROUP_XB\|DIGITAL / DOMESTIC | no | Guideline 1 is not fully satisfied because every statement in the summary and next_step must be supported by the facts in the request. Most statements are supported, but the summary says the issue is "highly unusual relative to the prior 28 days." The facts define z_score as measuring unusualness versus the prior 28 days, but they do not state the qualitative characterization "highly unusual." That wording is an unsupported interpretation rather than a stated fact. The rest of the summary and next_step are supported by the provided facts, including the date, slice, network, counts, dominant category, merchant count, prior-day elevation count, lost spend, owner team, and the playbook actions. Guideline 2 is satisfied because all numbers appearing in the response are present in the request facts with the same values: 2026-11-11, 47, 15.5, 31.5, 7.8, 2, 89.0%, 42, 46, 3, 2, and 256.0. Because at least one guideline is not satisfied, the overall result is no. |
| eval_v3 | v3 | grounded_in_facts | 2026-11-12\|OWN\|CARD_SEGMENT\|DOMESTIC | no | The response does not fully comply with the guidelines. Guideline 1 requires every statement in the summary and next_step to be supported by the facts in the request. Several statements are unsupported or overstate the facts: in the summary, "indicating this level of decline activity is highly unusual relative to the prior 28 days" is not directly supported by the facts, which only define z_score as how unusual declines are versus the same slice in the prior 28 days, not that a z_score of 6.9 specifically means "highly unusual." Also in the summary, "is elevated across all 2 of the last 2 prior days" is unsupported because the fact only says elevated_on_prior_days_of_last_2 = 2, which supports elevation on 2 prior days out of the last 2, but not necessarily the phrasing "across all 2 of the last 2 prior days." In next_step, "85 declines across 111 merchants on the acquired network" is not fully supported for the dominant category: 85 is the count for CARD_ON_FILE_STALE declines, and 111 is the total merchants with acceptance declines overall, but the facts do not state that all 111 merchants correspond to the stored-credential declines category. Guideline 2 requires every number in the response to appear in the request's facts. This is satisfied: 2026-11-12, 114, 60.1, 53.9, 6.9, 75.0, 2, 111, 1,628.00/1628.0, and 85 all appear in the request facts with acceptable formatting. Because guideline 1 is violated, the overall result is no. |
| eval_v3 | v3 | grounded_in_facts | 2026-11-12\|OWN\|CARD_SEGMENT\|RECURRING_HEAVY | no | The response does not fully comply with the guidelines. Guideline 1 is violated because some statements in the summary and next_step are not fully supported by the request facts. In the summary, "highly unusual relative to the prior 28 days" is an interpretation not explicitly stated in the facts; the facts only define z_score as how unusual the declines are versus the same slice in the prior 28 days. "indicating a persistent issue rather than a one-day spike" is also an unsupported inference from the fact that it was elevated on 2 of the last 2 prior days. "the likely cause is that stored card credentials held by recurring/card-on-file merchants were not updated after the cards were reissued during or following migration" goes beyond the stated facts; while the dominant decline category definition mentions not updated after reissue and the network is already migrated, the causal phrasing "during or following migration" is not stated. In next_step, the word "today" is unsupported by the request facts. Guideline 2 is satisfied because the numbers used in the response—2026-11-12, 22, 6.4, 15.6, 5.7, 100.0, 21, 2, 2, and 611.0—all appear in the request facts. |
| eval_v3 | v3 | no_invented_data | 2026-11-11\|OWN\|MCC_GROUP_XB\|DIGITAL / DOMESTIC | no | Guideline 1 is not fully satisfied because the response mentions a field not present in the request facts as stated: "46 merchants" in the next_step. The facts include "merchants_with_acceptance_declines": 46, but do not provide a list of merchants, so referring to "the 46 merchants" introduces a more specific merchant reference than the request facts explicitly contain. Guideline 2 is also not fully satisfied because the summary states the dominant category "meaning stored card credentials were not updated after reissue," which presents the cause as a confirmed fact rather than as likely or possible. Although the response includes "certainty": "likely," the explanatory sentence is still framed too definitively. Therefore the inputs do not fully comply with all provided guidelines. |
| eval_v3 | v3 | no_invented_data | 2026-11-12\|OWN\|CARD_SEGMENT\|DOMESTIC | no | Guideline 1 is not fully satisfied because the response mentions details not present in the request's facts. In particular, the summary says the pattern is "elevated across all 2 of the last 2 prior days," but the facts only say elevated_on_prior_days_of_last_2 = 2 and do not state "all" explicitly. More clearly, the next_step says "85 declines across 111 merchants on the acquired network." While 85 is the count for the dominant decline category and 111 is the total merchants with acceptance declines, the facts do not state that those 85 dominant-category declines occurred across 111 merchants, so this introduces an unsupported combined assertion. Guideline 2 is satisfied because the response frames cause as likely via the fields "likely_cause" and "certainty": "likely," rather than as a confirmed fact. Because at least one guideline is not satisfied, the overall result is "no". |
| eval_v3 | v3 | no_invented_data | 2026-11-12\|OWN\|CARD_SEGMENT\|RECURRING_HEAVY | no | Guideline 1 is not fully satisfied because the response mentions details not present in the request's facts. In the summary, it says recurring/card-on-file merchants were not updated "during or following migration," but the request facts do not mention any reissue timing during or after migration. In the next_step, it adds "today," which is not a date or timing stated in the request facts. Guideline 2 is satisfied because the response presents the cause as likely rather than confirmed, using phrases such as "the likely cause is." Because at least one guideline is not satisfied, the overall result is no. |


## Detection flags per method in the held-out window (latest run), by hit type

| run_label | method | hit | flags |
|---|---|---|---|
| eval_supp_41_60 | baseline |  | 672 |
| eval_supp_41_60 | baseline | DECOY | 125 |
| eval_supp_41_60 | baseline | INC1 | 5 |
| eval_supp_41_60 | baseline | INC2 | 10 |
| eval_supp_41_60 | baseline | INC3 | 21 |
| eval_supp_41_60 | baseline | INC4 | 10 |
| eval_supp_41_60 | method | INC1 | 21 |
| eval_supp_41_60 | method | INC2 | 21 |
| eval_supp_41_60 | method | INC3 | 161 |
| eval_supp_41_60 | method | INC4 | 49 |
