# Evidence 05: AI evaluation

- **Protocol:** EVAL_PROTOCOL.md v1 + Amendment 1 (12 months) + Amendment 2 (daily grain, own-history expected rate, 50% overlap rule) + Amendment 3 (held out = window days 41–58) + Errata 1.
- **Commit history:** every amendment, and the frozen threshold, were committed **before** the result they govern (see the git log).
- **Code:** `src/ai/tune_threshold.py`, `src/ai/explain_anomalies.py`, `src/ai/evaluate.py`, `src/ai/common.py`; job `febar_ai`.
- **Result tables (append-only):** `detector_config`, `eval_detection_flags`, `eval_judge_results`, `eval_runs`.

## 1. Detection: explainable score vs the dashboard rule, against the answer key

**Corrected run (Errata 1), the primary result** (run `eval_v1b`, 2026-11-23T06:59:57.706968Z, threshold 45 frozen 2026-11-23T06:37:57.166940Z)

| Split | Method | Flags | Hits | Precision (Wilson 95%) | Incidents caught | Incident-days flagged | Decoy-driven flags | Delay (days) | Root cause correct |
|---|---|---|---|---|---|---|---|---|---|
| tuning | method | 42 | 42 | 100.0% (91.6–100.0%) | 2/2 (INC1, INC2) | INC1 15/15, INC2 9/9 | 0 | INC1 0, INC2 0 | INC1 ✓, INC2 ✓ |
| tuning | baseline | 539 | 15 | 2.8% (1.7–4.5%) | 2/2 (INC1, INC2) | INC1 5/15, INC2 2/9 | 0 | INC1 0, INC2 0 | INC1 —, INC2 — |
| holdout | method | 210 | 210 | 100.0% (98.2–100.0%) | 2/2 (INC3, INC4) | INC3 11/11, INC4 3/3 | 0 | INC3 0, INC4 0 | INC3 ✓, INC4 ✓ |
| holdout | baseline | 296 | 31 | 10.5% (7.5–14.5%) | 2/2 (INC3, INC4) | INC3 10/11, INC4 3/3 | 125 | INC3 0, INC4 0 | INC3 —, INC4 — |

No-claim conditions: `beats_baseline_by_20pts_at_equal_or_better_precision` = **False**, `decoy_flagged_by_method` = **False**, `method_precision_below_50pct` = **False**, `look_ahead_detected` = **False**. Timing rule: 0 Meridian rows in the window arrived after decision time (excluded by construction).


Breakdown of held-out flags by what drove them (`eval_detection_flags`, `eval_v1b`):

| method | hit | flags |
|---|---|---|
| baseline |  | 140 |
| baseline | DECOY | 125 |
| baseline | INC3 | 21 |
| baseline | INC4 | 10 |
| method | INC3 | 161 |
| method | INC4 | 49 |

Method flags by slice family (held out):

| family | flags | days |
|---|---|---|
| REGION | 53 | 14 |
| ACQUIRER_CHANNEL | 53 | 14 |
| MCC_GROUP_XB | 48 | 14 |
| CARD_SEGMENT | 29 | 14 |
| CHANNEL | 27 | 14 |

**As first run (`eval_v1`, kept unchanged): the method labels counted the decoy's non-acceptance declines (Errata 1 §1)** (run `eval_v1`, 2026-11-23T06:51:52.536625Z, threshold 45 frozen 2026-11-23T06:37:57.166940Z)

| Split | Method | Flags | Hits | Precision (Wilson 95%) | Incidents caught | Incident-days flagged | Decoy-driven flags | Delay (days) | Root cause correct |
|---|---|---|---|---|---|---|---|---|---|
| tuning | method | 42 | 42 | 100.0% (91.6–100.0%) | 2/2 (INC1, INC2) | INC1 15/15, INC2 9/9 | 0 | INC1 0, INC2 0 | INC1 ✓, INC2 ✓ |
| tuning | baseline | 539 | 15 | 2.8% (1.7–4.5%) | 2/2 (INC1, INC2) | INC1 5/15, INC2 2/9 | 0 | INC1 0, INC2 0 | INC1 —, INC2 — |
| holdout | method | 210 | 196 | 93.3% (89.1–96.0%) | 2/2 (INC3, INC4) | INC3 11/11, INC4 3/3 | 14 | INC3 0, INC4 0 | INC3 ✓, INC4 ✓ |
| holdout | baseline | 296 | 31 | 10.5% (7.5–14.5%) | 2/2 (INC3, INC4) | INC3 10/11, INC4 3/3 | 125 | INC3 0, INC4 0 | INC3 —, INC4 — |

No-claim conditions: `beats_baseline_by_20pts_at_equal_or_better_precision` = **False**, `decoy_flagged_by_method` = **True**, `method_precision_below_50pct` = **False**, `look_ahead_detected` = **False**. Timing rule: 0 Meridian rows in the window arrived after decision time (excluded by construction).


### What we can and cannot claim (decided with the submitter, 2026-11-23)
- **No claim of higher recall.** Both the method and the dashboard rule caught **2/2** held-out incidents on day 0, so no-claim condition 1 is triggered as written.
- **Stated as facts:** at the frozen threshold, **100% of the method's held-out alerts were real** (210/210), against **10.5%** for the dashboard rule (31/296). The dashboard rule raised **125 alerts driven by the legitimate insufficient-funds decoy**; the method raised **0**.
- The method also names the root cause: **correct for 4/4 incidents** (tuning and held out). The dashboard rule gives no cause.
- **Read the precision with care.** The 210 flags are **not independent**: they cover only 2 incidents and 14 incident-days, flagged across 5 overlapping slice families. The Wilson interval treats the flags as independent, so it **overstates certainty**. The honest unit is the incident: 2/2 caught, 14/14 incident-days, 0 false-positive days.
- **Small sample** (stated in advance in the protocol): 2 held-out incidents. The result is indicative, not statistically significant.
- **Synthetic data:** the background noise in the generated data is regular, which makes clean separation easier than it would be on real traffic.

## 2. GenAI explanations: 30 held-out rows (same keys in every run), 4 MLflow Guidelines judges + 2 rule checks

- **Generator:** `databricks-claude-sonnet-4-6` (Anthropic). **Judge:** `databricks-gpt-5-4` (OpenAI), a different family.
- **Concurrency:** limited to 4 workers.
- **MLflow runs:** v1 `a5ce8d3c3ebc4040be53c89ef8ed149d`, v1b `de0ae0fe2e924cb58db5aa609d5a6eb1`, v2 `e11d3d759d394f37b3d5e371892bae7d` (experiment `febar_ai_evaluation`).

| Judge | Kind | v1 as run (`eval_v1`) | v1, corrected code (`eval_v1b`) | v2 (`eval_v2`) |
|---|---|---|---|---|
| `grounded_in_facts` | MLflow Guidelines, judge `databricks-gpt-5-4` | 0/30 | 0/30 | 0/30 |
| `cause_agreement` | MLflow Guidelines, judge `databricks-gpt-5-4` | 30/30 | 30/30 | 30/30 |
| `actionable_next_step` | MLflow Guidelines, judge `databricks-gpt-5-4` | 30/30 | 29/30 | 22/30 |
| `no_invented_data` | MLflow Guidelines, judge `databricks-gpt-5-4` | 0/30 | 0/30 | 4/30 |
| `rule_numbers_grounded` | rule (wins over judge for numbers) | 6/30 | 30/30 | 30/30 |
| `rule_cause_matches` | rule (wins over judge for numbers) | 30/30 | 30/30 | 30/30 |

**Protocol checks:**
- **Grounding no-claim (§6, the rule check is decisive):** 30/30 after the Errata fix, so this condition is **not** triggered for v1b or v2.
- **The LLM-judged `grounded_in_facts` fails 0/30 in every run.** See section 3 for why.

## 3. Iteration history (one iteration, as agreed)

| Step | Change | Effect |
|---|---|---|
| v1 | Prompt rules: only the facts, numbers from the facts, cause stated as likely, no rank/severity | Actionable 30/30, cause agreement 30/30. **But the judges found invented operational mechanics** ("account updater run", "PANs, expiry dates or network tokens", "credential-update pipeline", "before end of business"). The judges were **right**. |
| Errata 1 | Evaluation code only (decoy labels; numeric comparison) | Method decoy flags 14 → 0, held-out precision 93.3% → 100%; rule number check 6/30 → 30/30. Nothing about the model changed. |
| v2 | Facts gain a glossary; prompt adds 3 rules (cause only in the category's words, no new systems or processes, copy numbers exactly; next_step uses only facts) | Invented mechanics gone (no_invented_data 0 → 4/30). **Actionability regressed 29 → 22/30**: the "use only items in the facts" rule produced generic "review … and determine" next steps. The judge is **right**; my change caused it. |

### Where the judges are wrong (for the submitter to review; judges NOT changed)
- **`grounded_in_facts`** reads "every statement must be supported" literally. It rejects wording copied from the glossary inside the facts: "merchant category group slice" (the glossary says *MCC_GROUP_XB = merchant category group…*), "authorization attempts" (the glossary says *attempts = card authorization attempts*), and "highly unusual" for a z-score the facts describe as "how unusual…". These are **judge errors**. Some of its complaints are fair: "a persistent pattern since the card migration" is an inference the facts do not state.
- **`no_invented_data`** rejects "following the migration" although the facts say "cards already migrated". That is mostly a judge error.
- Protocol §5 defines criterion (a) as *every number cited matches the source row*. The `grounded_in_facts` guideline is **stricter** (every statement), so its 0/30 is not the protocol's criterion (a). Criterion (a) is decided by the rule check: 30/30.

### Items flagged for human review
`eval_v2` rows where `actionable_next_step` failed (8 rows):

- `2026-11-12|OWN|CARD_SEGMENT|DOMESTIC`
- `2026-11-12|OWN|CARD_SEGMENT|RECURRING_HEAVY`
- `2026-11-15|OWN|CARD_SEGMENT|DOMESTIC`
- `2026-11-15|OWN|CHANNEL|ECOM`
- `2026-11-15|OWN|MCC_GROUP_XB|RETAIL / DOMESTIC`
- `2026-11-16|OWN|CHANNEL|ECOM`
- `2026-11-16|OWN|MCC_GROUP_XB|FOOD_GROCERY / DOMESTIC`
- `2026-11-16|THIRD_PARTY|CARD_SEGMENT|DOMESTIC`

Every judge verdict and rationale, for all three runs, is in `eval_judge_results`.

## 4. Before / after in one line
**v1** was concrete but invented mechanics. **v2** is grounded but too generic. Neither prompt is clean on both. Which version to use in production, or whether to run a second iteration, is open for the submitter (see BUILD_LOG / DECISIONS).


## 5. Second iteration, v3 (approved by the submitter 2026-11-23): playbook in the facts

- **Change:** the facts gain `playbook_for_dominant_category`, two standard checks per root cause written by the team. The prompt asks the model to pick the most fitting check and make it specific with facts. Run `eval_v3`, MLflow run `502a6c985e9d480d9d9cc6e51d6b6ace`, same 30 keys, same judges.

| Judge | v1 (`eval_v1b`) | v2 | **v3** |
|---|---|---|---|
| `grounded_in_facts` | 0/30 | 0/30 | 1/30 |
| `cause_agreement` | 30/30 | 30/30 | 30/30 |
| `actionable_next_step` | 29/30 | 22/30 | 23/30 |
| `no_invented_data` | 0/30 | 4/30 | 9/30 |
| `rule_numbers_grounded` | 30/30 | 30/30 | 30/30 |
| `rule_cause_matches` | 30/30 | 30/30 | 30/30 |

- **Result:** v3 is the most grounded version (no_invented 9/30; v1's invented mechanics are gone). Actionability barely recovered (23/30).
- **Why the actionability failures:** the model **joins both playbook actions** ("check processor response times … and, if timeouts continue, open an incident"), which breaks the judge's "one concrete action" rule. **The judge is right.**
- **No third iteration was run.** v3 is used for the cases (`ops.cases.llm_next_step`).
- **Remaining weakness, stated openly:** explanation quality has not met the bar; the 90% grounding no-claim threshold is met only by the rule check (30/30), not by the LLM judges.
