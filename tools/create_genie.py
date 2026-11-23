"""Build the Genie space definition, create or update the space, and export it to src/genie/space.json.

Usage: python3 -I tools/create_genie.py      (profile febar; warehouse from databricks.yml default)
IDs are deterministic (md5 of a key), so the definition is reproducible.
"""
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src", "genie"))
from benchmarks import BENCHMARKS, NS  # noqa: E402

P = ["--profile", "febar"]
WAREHOUSE = "34e45919b39491cf"
TITLE = "Network migration: acceptance and readiness"
ID_FILE = os.path.join(ROOT, "src", "genie", "space_id.txt")


def hid(key):
    return hashlib.md5(key.encode()).hexdigest()


def col(name, desc=None, exclude=False, synonyms=None, entity=False):
    c = {"column_name": name}
    if desc:
        c["description"] = [desc]
    if synonyms:
        c["synonyms"] = synonyms
    if entity:
        c["enable_entity_matching"] = True
        c["enable_format_assistance"] = True
    if exclude:
        c["exclude"] = True
    return c


COMMON = [
    col("issuer_segment", "OWN = cards issued by this bank; THIRD_PARTY = other issuers' cards processed on the network", entity=True),
    col("region", "Merchant region: NE, SE, MW, SW, W (US) or INTL (outside the US); ALL when the row is not regional", entity=True),
]
TABLES = {
    "gold_auth_daily": [
        col("business_date", "Business day of the authorization attempts"),
        col("wave_cohort", "W1..W6 = migration wave of the card (card already migrated to the acquired network); BASELINE = card not yet migrated", entity=True),
        col("network", "MRD = the acquired network (migrated cards); ATL = the legacy network", synonyms=["acquired network", "legacy network", "new network", "old network"], entity=True),
        col("acquirer_id", "Acquirer (merchant bank / processor) code, e.g. ACQ-017", entity=True),
        col("acquirer_name", "Acquirer name"),
        col("channel", "CP = card present, ECOM = e-commerce, REC = recurring / card-on-file, MANUAL = key-entered", synonyms=["e-commerce", "recurring", "card present"], entity=True),
        col("mcc_group", "Merchant category group, e.g. TRAVEL_LODGING (airlines, hotels, car rental, travel agencies), FOOD_GROCERY, RETAIL, DIGITAL, BILLS", synonyms=["merchant category", "travel and lodging"], entity=True),
        col("cross_border", "TRUE when the merchant is outside the US", synonyms=["international", "cross-border"]),
        col("tokenized", "TRUE when a wallet or card-on-file token was used"),
        col("attempts", "Number of authorization attempts"),
        col("approvals", "Approved attempts (including network stand-in approvals)"),
        col("declines", "Declined attempts (all reasons)"),
        col("acceptance_declines", "Declines caused on the network or acquirer side (acceptance failures, fixable); excludes legitimate issuer declines", synonyms=["acceptance failures", "network declines"]),
        col("issuer_legit_declines", "Legitimate issuer declines (insufficient funds, fraud, expired card...)"),
        col("unmapped_declines", "Declines whose network code is not in the code map"),
        col("decl_acceptance_config", "Acceptance declines: acceptance profile not configured or rejected"),
        col("decl_token_provisioning", "Acceptance declines: token not provisioned"),
        col("decl_cross_border_block", "Acceptance declines: cross-border not enabled"),
        col("decl_card_on_file_stale", "Acceptance declines: stored card credential not updated after reissue"),
        col("decl_processor_timeout", "Acceptance declines: issuer or switch timed out"),
        col("decl_system_error", "Acceptance declines: network system error"),
        col("decl_insufficient_funds", "Legitimate insufficient-funds declines"),
        col("stip_approvals", "Approvals made by network stand-in because the issuer was unreachable"),
        col("amount", "Attempted amount, USD"),
        col("declined_amount", "Declined amount, USD"),
        col("max_available_ts", exclude=True),
    ] + COMMON,
    "gold_baseline_gap": [
        col("business_date", "Business day"),
        col("wave_cohort", "Migrated wave cohort W1..W6", entity=True),
        col("match_segment", "Matching key: card segment | channel | merchant category group | DOM/XB"),
        col("card_segment", "Cardholder spending segment", entity=True),
        col("migrated_attempts", "Attempts on migrated cards in this segment and day"),
        col("migrated_approvals", "Approvals on migrated cards"),
        col("expected_approvals", "Approvals the migrated cards would have had at the matched legacy baseline rate"),
        col("excess_declines", "Extra declines on migrated cards vs the matched baseline = expected_approvals - migrated_approvals"),
        col("lost_spend", "Estimated lost spend, USD = excess declines x average ticket x share of spend not recovered (Finance assumption)", synonyms=["lost spend", "lost purchase volume"]),
        col("gap_pp", "Approval gap of this row in percentage points (do not average across rows; recompute from sums)"),
        col("matched_baseline_rate", "Legacy-network approval rate of comparable cards (same day, card segment, channel, merchant category group, cross-border)"),
        col("migrated_approval_rate", "Approval rate of migrated cards in this row"),
        col("unmatched_baseline_rate", "Legacy-network approval rate of all cards that day (not matched)"),
        col("unmatched_gap_pp", "Gap vs the unmatched baseline (for comparison only)"),
        col("baseline_level", exclude=True), col("baseline_attempts", exclude=True), col("unrecovered_rate", exclude=True),
    ] + COMMON,
    "gold_anomalies": [
        col("business_date", "Day the anomaly was flagged for"),
        col("family", "Slice type: ACQUIRER_CHANNEL, MCC_GROUP_XB, REGION, CHANNEL, CARD_SEGMENT", entity=True),
        col("slice_value", "The slice, e.g. 'ACQ-017 / ECOM'"),
        col("score", "Explainable anomaly score 0-100 (flagged when >= 45); higher = more unusual and costly", synonyms=["anomaly score"]),
        col("likely_root_cause", "Likely root cause from the dominant acceptance-decline category", entity=True),
        col("owner_team", "Suggested owner team", entity=True),
        col("exposure_usd", "Estimated lost spend of this flag, USD"),
        col("excess_declines", "Acceptance declines above expected"),
        col("llm_summary", "AI-drafted explanation (likely cause, not confirmed)"),
        col("llm_next_step", "AI-drafted next step"),
        col("facts", exclude=True), col("llm_raw", exclude=True), col("llm_error", exclude=True), col("llm_facts_used", exclude=True),
        col("llm_model", exclude=True), col("prompt_version", exclude=True), col("score_version", exclude=True),
        col("detector_version", exclude=True), col("drivers", "Why it was flagged, in words"),
        col("excess_points", exclude=True), col("impact_points", exclude=True), col("clarity_points", exclude=True),
        col("breadth_points", exclude=True), col("persistence_points", exclude=True), col("explained_at", exclude=True), col("flagged_at", exclude=True),
    ] + COMMON,
    "gold_case_status": [
        col("case_id", "Case number"),
        col("case_key", exclude=True),
        col("root_cause", "Likely root cause of the case", entity=True),
        col("status", "OPEN, CLAIMED, IN_PROGRESS, WAITING_PARTNER, RESOLVED or DISMISSED (RESOLVED and DISMISSED are closed)", entity=True),
        col("severity", "HIGH (max anomaly score >= 70) or MEDIUM", entity=True),
        col("exposure_usd", "Estimated lost spend of the case, USD"),
        col("recovered_spend_usd", "Spend recovered after the fix, USD (entered by analysts)"),
        col("owner_team", "Team that owns the case", entity=True),
        col("region_scope", "Region of the case (ALL when not regional)"),
        col("version", exclude=True), col("machine_refreshed_at", exclude=True),
    ] + [COMMON[0]],
    "gold_wave_readiness": [
        col("wave_id", "Upcoming migration wave number (7-10)"),
        col("gate", "GO or HOLD for this wave and card segment", entity=True),
        col("gate_reason", "Why GO or HOLD, in words"),
        col("segment_gap_pp_14d", "Approval gap of already-migrated cards in the same card segment, last 14 days, percentage points"),
        col("expected_daily_attempts", "Daily authorization attempts of the wave's cards (today, on the legacy network)"),
        col("at_risk_declines_per_day", "Expected extra declines per day if migrated today", synonyms=["at-risk volume", "at risk transactions"]),
        col("at_risk_spend_usd_per_day", "Expected lost spend per day if migrated today, USD", synonyms=["at-risk spend"]),
        col("card_segment", "Cardholder spending segment", entity=True),
        col("computed_at", exclude=True),
    ] + COMMON,
}

TEXT = [
    "PURPOSE: answer questions from the VP of Payment Network Integration and the Director of Payment Network Operations about card authorization acceptance during the migration of cards to the acquired payment network, incidents (cases) and readiness of upcoming migration waves. Data is synthetic.",
    "NETWORKS: network 'MRD' = the acquired network (cards already migrated). network 'ATL' = the legacy network. 'Migrated cards' = network = 'MRD'.",
    "TIME: 'last N days' means the N business days ending at the LATEST business_date in the table being queried (business_date > date_sub(max(business_date), N)), never current_date(). Data is daily; there is no hourly detail.",
    "RATES: always compute rates as ratios of sums: approval rate = SUM(approvals)/SUM(attempts); acceptance-decline rate = SUM(acceptance_declines)/SUM(attempts). Never average a rate column across rows. Show rates as percentages rounded to 2 decimals.",
    "APPROVAL GAP vs MATCHED BASELINE: use gold_baseline_gap. Migrated approval rate = SUM(migrated_approvals)/SUM(migrated_attempts); matched baseline approval rate = SUM(expected_approvals)/SUM(migrated_attempts); gap in percentage points = 100*(SUM(expected_approvals)-SUM(migrated_approvals))/SUM(migrated_attempts). Positive gap = migrated cards approve less.",
    "LOST SPEND: SUM(gold_baseline_gap.lost_spend) in USD (net of segments where migrated cards did better). It is lost purchase volume, NOT bank revenue.",
    "ACCEPTANCE vs ISSUER: acceptance_declines are network/acquirer-side failures (fixable). issuer_legit_declines are the issuer's legitimate decisions (insufficient funds, fraud...). Questions about acceptance problems use acceptance_declines only.",
    "READINESS: use gold_wave_readiness. A wave segment is GO only if segment_gap_pp_14d <= 0.3 pp AND there are no open HIGH-severity cases; otherwise HOLD. 'At risk' = at_risk_declines_per_day (transactions) and at_risk_spend_usd_per_day (USD), summed over the segments asked about.",
    "CASES: open = status NOT IN ('RESOLVED','DISMISSED'). Rank cases by exposure_usd. Rank acquirers or slices by the measure asked (e.g. acceptance_declines), descending, and show the top N asked for.",
    "COMPLETENESS: the latest data date is MAX(business_date); a day 'has data' for a network when it has attempts for that network.",
    "BEFORE / DURING / AFTER a period: 'before' = the 14 days immediately before the period's first day; 'after' = the 14 days immediately after its last day; 'during' = the period itself (inclusive). Label the buckets 1_before, 2_during, 3_after.",
    "READINESS GATE answers (GO/HOLD, gate_reason): show one row per card_segment AND issuer_segment (OWN vs THIRD_PARTY), because the gate is computed per issuer segment.",
    "AT-RISK VOLUME answers: group only by the dimension asked (e.g. 'by card segment' = GROUP BY card_segment, summing OWN and THIRD_PARTY together) and show SUM(expected_daily_attempts), SUM(at_risk_declines_per_day) and SUM(at_risk_spend_usd_per_day).",
    "DO NOT: answer about individual cardholders or card numbers (not in these tables); invent figures; forecast beyond the data; or name people. AI-drafted explanations (llm_summary, llm_next_step) are likely causes, not confirmed facts; say so if you quote them.",
]
EXAMPLES = [
    ("Show the approval gap vs the matched baseline by wave cohort for the last 14 days.",
     f"SELECT wave_cohort, round(100 * (sum(expected_approvals) - sum(migrated_approvals)) / sum(migrated_attempts), 2) AS gap_pp, sum(migrated_attempts) AS migrated_attempts FROM {NS}.gold_baseline_gap WHERE business_date > (SELECT date_sub(max(business_date), 14) FROM {NS}.gold_baseline_gap) GROUP BY wave_cohort ORDER BY wave_cohort"),
    ("What is the acceptance-decline rate by channel on the acquired network over the last 7 days?",
     f"SELECT channel, round(100 * sum(acceptance_declines) / sum(attempts), 2) AS acceptance_decline_rate_pct, sum(attempts) AS attempts FROM {NS}.gold_auth_daily WHERE network = 'MRD' AND business_date > (SELECT date_sub(max(business_date), 7) FROM {NS}.gold_auth_daily) GROUP BY channel ORDER BY acceptance_decline_rate_pct DESC"),
    ("Compare ACQ-001's recurring acceptance-decline rate before and after 2 November 2026 on the acquired network.",
     f"SELECT CASE WHEN business_date < '2026-11-02' THEN '1_before' ELSE '2_after' END AS period, round(100 * sum(acceptance_declines) / sum(attempts), 2) AS acceptance_decline_rate_pct, sum(attempts) AS attempts FROM {NS}.gold_auth_daily WHERE network = 'MRD' AND acquirer_id = 'ACQ-001' AND channel = 'REC' AND business_date BETWEEN '2026-10-19' AND '2026-11-15' GROUP BY 1 ORDER BY 1"),
    ("Which segments of wave 8 are on hold and why?",
     f"SELECT card_segment, issuer_segment, gate, gate_reason, round(at_risk_spend_usd_per_day, 2) AS at_risk_spend_usd_per_day FROM {NS}.gold_wave_readiness WHERE wave_id = 8 AND gate = 'HOLD' ORDER BY at_risk_spend_usd_per_day DESC"),
]
SAMPLES = [
    "What is the approval gap for migrated cards vs the matched baseline over the last 30 days?",
    "Is wave 7 ready to launch?",
    "Which acquirers had the most acceptance declines on the acquired network in the last 14 days?",
    "How many HIGH-severity cases are open, and who owns them?",
    "How much spend did we lose to excess declines in the last 30 days?",
]


def build():
    tables = [{"identifier": f"{NS}.{t}", "column_configs": sorted(cols, key=lambda c: c["column_name"])} for t, cols in TABLES.items()]
    joins = [
        {"id": hid("join_ready_gap"), "left": {"identifier": f"{NS}.gold_wave_readiness", "alias": "gold_wave_readiness"},
         "right": {"identifier": f"{NS}.gold_baseline_gap", "alias": "gold_baseline_gap"},
         "sql": ["`gold_wave_readiness`.`card_segment` = `gold_baseline_gap`.`card_segment` AND `gold_wave_readiness`.`issuer_segment` = `gold_baseline_gap`.`issuer_segment`",
                 "--rt=FROM_RELATIONSHIP_TYPE_MANY_TO_MANY--"]},
        {"id": hid("join_daily_gap"), "left": {"identifier": f"{NS}.gold_auth_daily", "alias": "gold_auth_daily"},
         "right": {"identifier": f"{NS}.gold_baseline_gap", "alias": "gold_baseline_gap"},
         "sql": ["`gold_auth_daily`.`business_date` = `gold_baseline_gap`.`business_date` AND `gold_auth_daily`.`wave_cohort` = `gold_baseline_gap`.`wave_cohort`",
                 "--rt=FROM_RELATIONSHIP_TYPE_MANY_TO_MANY--"]},
    ]
    space = {
        "version": 2,
        "config": {"sample_questions": sorted([{"id": hid("sample" + q), "question": [q]} for q in SAMPLES], key=lambda x: x["id"])},
        "data_sources": {"tables": sorted(tables, key=lambda t: t["identifier"])},
        "instructions": {
            "text_instructions": [{"id": hid("text_v1"), "content": TEXT}],
            "example_question_sqls": sorted([{"id": hid("ex" + q), "question": [q], "sql": [s]} for q, s in EXAMPLES], key=lambda x: x["id"]),
            "join_specs": sorted(joins, key=lambda j: j["id"]),
        },
        "benchmarks": {"questions": sorted([{"id": hid("bench" + qid), "question": [q], "answer": [{"format": "SQL", "content": [s]}]}
                                            for qid, q, s in BENCHMARKS], key=lambda x: x["id"])},
    }
    return space


def cli(*args, payload=None):
    cmd = ["databricks", *args, *P, "-o", "json"]
    if payload is not None:
        cmd += ["--json", json.dumps(payload)]
    return json.loads(subprocess.check_output(cmd))


if __name__ == "__main__":
    space = build()
    ser = json.dumps(space)
    if os.path.exists(ID_FILE):
        sid = open(ID_FILE).read().strip()
        cli("genie", "update-space", sid, payload={"serialized_space": ser, "title": TITLE, "warehouse_id": WAREHOUSE})
        action = "updated"
    else:
        me = cli("current-user", "me")["userName"]
        parent = f"/Workspace/Users/{me}/febar_genie"
        subprocess.check_output(["databricks", "workspace", "mkdirs", parent, *P])
        out = cli("genie", "create-space", payload={"warehouse_id": WAREHOUSE, "title": TITLE, "parent_path": parent,
                  "description": "Governed gold tables for the card-migration acceptance and readiness story (synthetic data).",
                  "serialized_space": ser})
        sid = out["space_id"]
        open(ID_FILE, "w").write(sid + "\n")
        action = "created"
    got = cli("genie", "get-space", sid, "--include-serialized-space")
    exported = json.loads(got["serialized_space"])
    with open(os.path.join(ROOT, "src", "genie", "space.json"), "w") as fh:
        json.dump(exported, fh, indent=1, sort_keys=True)
    print(json.dumps({"space_id": sid, "action": action, "tables": [t["identifier"].split(".")[-1] for t in exported["data_sources"]["tables"]],
                      "examples": len(exported["instructions"].get("example_question_sqls", [])),
                      "benchmarks": len(exported.get("benchmarks", {}).get("questions", [])),
                      "sample_questions": len(exported.get("config", {}).get("sample_questions", []))}))
