# Use Case: Acceptance Risk Control for Network Migration

> **Status: DRAFT, awaiting your approval.** The sections marked `[YOUR WORDS]` were drafted by AI from your discovery answers; rewrite them in your own words.
> `[ASSUMPTION]` = a number or fact I proposed, not from you. `[CHECK]` = verify before you use it.

**Customer:** a large U.S. bank and credit card issuer (FINS) that has acquired a payment network and is moving its card portfolios onto it in waves.
**Executive sponsor:** VP of Payment Network Integration · **Domain owner:** Director of Payment Network Operations

---

## 1. One-line outcome `[YOUR WORDS]`

Narrow the post-migration approval gap from **0.9 pp to within 0.3 pp** of a matched baseline. For a 400K-card wave, this recovers **$9M–$18.5M a year in lost purchase volume** (conservative to base case, §6). The VP also gets an evidence-backed go/no-go for wave 7, which launches in 90 days.

## 2. The problem in the customer's words `[YOUR WORDS]`

> "After a wave migrates, we find out about declines from dashboards, daily reports, complaints and acquirer emails, all in different systems. By the time we know which merchants or processors are behind a pattern, hours have passed. A complicated investigation takes our analysts four to six hours. And when the VP asks, 'If we move another 400,000 cardholders next month, how confident are we that their transactions will work?', answering means manual analysis across several departments."

**Quantified pain (wave 6):**

| | |
|---|---|
| Approval rate, migrated cards | 96.9% |
| Approval rate, matched baseline | 97.8% |
| Gap | −0.9 pp |
| Extra declines a day | 250,000 attempts × 0.9% = 2,250 |
| Affected spend a day | 2,250 × $75 = $168,750 |
| Spend not recovered (45%) | ≈ **$76K/day** (≈ $27.7M annualized) |

The $27.7M is purchase volume, not bank revenue. Finance estimates the interchange and retention impact separately.

## 3. Why now `[YOUR WORDS]`

1. **A fixed clock.** Wave 7 (400,000 cardholders) launches in about 90 days. Leadership has asked for proof that the network can take the volume without hurting approvals. The proposed gate: stay within 0.3 pp of baseline, with zero unresolved high-severity acceptance issues.
2. **The waves get harder.** Waves 1–6 moved the simpler segments. The four remaining waves concentrate international travel, e-commerce, recurring payments and digital wallets, where token, cross-border and card-on-file failures are most likely. `[ASSUMPTION]` These segments carry roughly 2× the decline rate of in-person domestic spend.
3. **Deal value and competitive risk.** The acquisition's financial case depends on moving volume onto the network. Every failed transaction invites the cardholder to reach for a competing card, and the incumbent global networks set the acceptance benchmark cardholders expect. Leadership reviews integration progress weekly and monthly, so any slip in approvals is visible at the top.
4. **Separation of sensitive data.** The bank also runs the network for third-party issuers. Any shared view must keep those institutions' commercially sensitive data separate from the bank's own portfolio, or the network risks those issuers' trust.

## 4. Personas `[YOUR WORDS]`

| | VP of Payment Network Integration (sponsor) | Director of Payment Network Operations (domain owner) |
|---|---|---|
| Reports to | Integration steering committee (weekly); executive leadership (monthly) | The VP; daily operational reporting |
| Must answer | How much volume has migrated, whether approvals are healthy, whether the network economics are landing, and whether the next wave is safe to launch | Why approvals dropped, where, who owns the fix, and whether the fix worked |
| How they work today | Gets readiness inputs from Strategy, Integration, Card Tech and Ops; the analysis is manual | 15 analysts; mornings spent on authorization reports, pulling data from 5 systems, matching decline codes, chasing acquirers, updating spreadsheets and tickets |
| KPIs owned | Migration readiness (go/no-go); approval rate vs baseline (≤ 0.3 pp); lost spend | Time to detect; time to likely root cause; open high-severity issues; decline rate on migrated cards |
| Wants | An evidence-backed readiness assessment for each wave | Detect in ≤ 5 min, root cause in ≤ 30 min, dollar exposure quantified, routed to the right team automatically |

## 5. Today versus tomorrow `[YOUR WORDS]`

| | Today | Tomorrow |
|---|---|---|
| **Detect** | Hours later, from dashboards, daily reports, complaints and acquirer emails | Anomalies flagged automatically for each acquirer, MCC, region, channel and wave against a matched baseline, minutes after the data lands |
| **Diagnose** | 4–6 h per complex case; analysts manually reconcile different response codes and merchant IDs | A standardized decline taxonomy splits acceptance failures from legitimate issuer declines; likely root cause and evidence are proposed in ≤ 30 min |
| **Act and track** | Spreadsheets and separate tickets; no link from anomaly to owner, fix and outcome | One case per anomaly, with owner team, fix, status, dollar exposure and recovered spend tracked to closure |
| **Decide the next wave** | A manual roll-up across departments for the go/no-go | A readiness score per wave and segment from open issues, at-risk volume and segment-level risk; the VP asks follow-up questions in plain English |

## 6. Value hypothesis

Basis: one 400K-card wave, about 250,000 daily authorization attempts, $75 average ticket, 45% of declined spend not recovered (your figures). Values are illustrative.

**The key uncertainty is how much of the 0.9 pp gap is fixable** (acceptance or configuration failures), as opposed to legitimate issuer declines that should stay declined. We show three scenarios rather than one number. The prototype's root-cause split (acceptance vs issuer decline) is the method the customer would use on their own data to find out which scenario they are in.

| Scenario | Fixable share of gap `[ASSUMPTION]` | Gap closed | Declines avoided/day | Lost spend recovered/day | Annualized, per wave cohort |
|---|---|---|---|---|---|
| Conservative | 1/3 | 0.9 → 0.6 pp | 750 | ≈ $25.3K | **≈ $9.2M** |
| **Base** | 2/3 | 0.9 → 0.3 pp (meets the gate) | 1,500 | ≈ $50.6K | **≈ $18.5M** |
| Stretch | ~0.78 | 0.9 → 0.2 pp | 1,750 | ≈ $59.1K | **≈ $21.6M** |

Formula: declines avoided × $75 × 45% unrecovered × 365. All three hold only if the effect persists for the cohort `[ASSUMPTION]`.

| Value driver | Current baseline | Expected change (base case) | Assumption | Illustrative value |
|---|---|---|---|---|
| **Approval rate** (migrated vs matched baseline) | 96.9% vs 97.8% (−0.9 pp) | Gap ≤ 0.3 pp | Base scenario above | +0.6 pp approval on the wave cohort (range +0.3 to +0.7) |
| **Decline rate** (migrated cohort) | ≈ 3.1% (vs 2.2% baseline) | ≈ 2.5% | Same | 1,500 fewer declines a day (range 750–1,750) |
| **Lost spend** | ≈ $76K/day unrecovered (≈ $27.7M/yr) | ≈ $25K/day | Same | **$9.2M–$18.5M/yr per wave cohort** (base $18.5M) |
| **At-risk transaction volume** (next wave) | Not measured continuously; offline estimates now and then | Measured daily, by segment, before launch | `[ASSUMPTION]` 30% of wave 7's ~250K daily attempts fall in complex segments (international, e-commerce, recurring, wallet) | ≈ 75K attempts/day ≈ $5.6M/day of spend in view before go-live |
| **Migration readiness** | Manual, multi-department; `[ASSUMPTION]` ~2 weeks to assemble | A standing readiness score; gate = ≤ 0.3 pp and zero open high-severity issues | `[ASSUMPTION]` Assembly time falls to < 1 day | Go/no-go decided on evidence, not opinion |
| **Analyst time** (supporting) | 4–6 h per complex investigation | ≤ 30 min to likely cause | `[ASSUMPTION]` 10 complex investigations a week; $150K loaded cost per analyst | ≈ 45 h/week ≈ 1.1 FTE ≈ $165K/yr redeployed to fixing |

Lost spend is not revenue. Converting it to interchange and retention value is Finance's job, and it stays out of scope (see §9).

## 7. The data

A customer like this has about nine relevant source systems. **The prototype deliberately builds five core sources in depth**, because a narrow, fully evidenced journey beats a broad, shallow one. Everything is **synthetic**, at a proposed scale of `[ASSUMPTION]` about 60 days × about 150K authorizations a day ≈ 9M rows. That scale is a decision for the build plan.

**Core: built end to end**

| Source system | Tables / feeds | Prod volume | Prototype rows | What's messy |
|---|---|---|---|---|
| Issuer authorization systems | `auth_attempts` (attempt, amount, decision, issuer reason) | 8M/day | ~9M | Retries and re-sends duplicate attempts; reversals arrive as separate events |
| Acquired-network feed | `network_auth_events` (routing, network response code, processing metadata) | 1.6M/day | ~2M | Its own response-code set and merchant ID format; seconds-to-minutes latency |
| Legacy-network reporting | `legacy_auth_daily` (historical and diagnostic) | 6.4M/day | ~7M | Some files arrive the next day; different field names for the same concepts |
| Merchant and acquirer reference | `merchants`, `acquirers` | 1.2M merchants, 80 acquirers | ~50K / 80 | Refreshed daily; one merchant has different IDs per network; stale MCCs |
| Card portfolio | `cards` (segment, product, wave, migration date, status) | 12M cards | ~200K | Migration dates change when waves slip; changes over time need tracking (SCD) |

**Supporting: small and static**

| Table | Rows | Purpose |
|---|---|---|
| `response_code_map` (legacy ↔ acquired ↔ issuer → standard category) | ~150 | Built and governed by us; doesn't exist today |
| `recovery_assumptions` (Finance: unrecovered-spend rate by segment) | ~10 | One versioned assumptions table instead of a Finance feed |

**Stretch: only if the core journey is finished and evidenced**

| Source system | Why it's deferred |
|---|---|
| Customer service complaints (free text, ~20K rows) | Would give GenAI extra evidence; the core GenAI works from the case's own metrics |
| Tokenization events | The token failure is shown as a channel/token flag on the authorization instead of a separate feed |

## 8. How the six stages serve the Director `[YOUR WORDS]`

1. **Lakeflow:** ingests the five core feeds into one bronze → silver → gold flow. It handles late legacy files and duplicate retries, and maps every decline to a standard category, so analysts stop reconciling systems by hand.
2. **Unity Catalog:** one governed copy of authorization data, with lineage from raw file to readiness score. Row filters keep third-party issuers' data apart from the bank's own portfolio, and masks hide card numbers, so analysts see only what their role allows.
3. **Lakebase:** the system of record for the team's work: the one stage where *people* write data, not pipelines. It replaces today's spreadsheets and separate tickets.
   - **What it holds:** a `cases` table (anomaly, owner team, assignee, severity, status, fix, dollar exposure, recovered spend). An append-only `case_events` table records every claim, reassignment, note and status change, with who made it and when; that is the audit trail.
   - **Why it needs operational Postgres:**
     - **Concurrent claims are safe.** 15 analysts work the same queue. A claim is a single-row transactional update (`UPDATE … WHERE status = 'open'`), so if two analysts click the same case, exactly one wins.
     - **Fast reads and writes per row.** Each App click reads or updates one case in milliseconds, and the queue shows the change immediately.
     - **State the lakehouse can't produce.** Status, owner and fix notes come from people, not from any source feed. Without Lakebase, that data would live in a spreadsheet.
   - **How it connects in both directions:**
     - **Into Lakebase:** new anomalies from the gold tables are synced in as open cases, idempotently, one case per anomaly key.
     - **Back to the lakehouse:** case status and recovered spend flow back into Unity Catalog. There they feed the wave readiness score (no open high-severity cases is part of the gate), the value tracking, and Genie, which can then answer "How many high-severity cases are still open for wave 7?"
   - **Evidence we commit:** a concurrent-claim test (two simultaneous claims → one succeeds, one is rejected); measured read and write latency from the App; and a query showing a case resolved in Lakebase changing the readiness score in the lakehouse.
4. **ML / GenAI:** ML flags decline anomalies against a matched baseline and classifies the likely root cause. Because the synthetic data contains incidents we planted on purpose, we measure how many the model catches and how many false alarms it raises, and commit the results (EVAL_PROTOCOL.md). GenAI writes the case summary and suggested next step, citing the case's metrics; the quality of that output is scored too.
5. **Genie:** answers the VP's and analysts' ad-hoc questions in plain English, such as "What spend in wave 7's e-commerce segment is at risk, and at which acquirers?", without a SQL request to the team.
6. **App:** the Director's command center: an anomaly feed, a case workbench (claim, assign, resolve) that writes back to Lakebase, and a wave readiness view for the go/no-go.

## 9. What we will NOT build

- Real-time authorization decisioning, or changes to issuer or processor stand-in rules. We observe and diagnose; we don't approve or decline.
- Sub-second streaming at production scale. "Detect in ≤ 5 minutes" is the customer's **target**. The prototype replays synthetic feeds in micro-batches, and we commit the detection latency we actually measure (data landing → anomaly flagged) as evidence. We never claim production latency.
- The four non-core sources (token service, complaints, Finance feed, legacy diagnostics beyond the daily file) are stretch only; see §7.
- Finance's interchange, network economics or retention models. We report lost purchase volume only.
- Fraud models, or any judgment on whether a legitimate issuer decline was right.
- Cardholder or merchant outreach, and integration with real ticketing systems. Cases live in Lakebase only.
- Real customer data, real merchant or acquirer names, or real network response-code tables. All synthetic.

---

## 10. Challenge: where this case is weak, and how to fix it

**Already applied in this draft:** (1) scope cut to five core sources; (2) value shown as three scenarios instead of one number; (3) ML judged on the planted incidents it catches vs false alarms; (4) unverified regulatory claims replaced with statements we can defend; (5) 5-minute detection framed as a target, with measured latency as evidence; (6) Lakebase justified as the system of record for analyst work, with two-way flow and committed evidence (§8.3).

| Risk | Why it hurts | Proposed fix |
|---|---|---|
| **"Unified platform" sounds generic** | Reads like a reworded "improve operations" | Center the demo on one planted incident: an acquiring processor misconfigured for e-commerce token transactions on the new network after wave 6, hitting about 200 merchants. Follow it from detection → root cause → case → fix → recovered spend → the wave 7 gate. |
| **Detection "within 5 minutes" can't be proven at prototype scale** | An evaluator will test the claim | State it as a target. Show micro-batch detection on replayed data and record the measured latency in `evidence/`. Never claim production latency. |
| **"Matched baseline" is easy to fake** | Comparing migrated cards with all non-migrated cards is biased by segment | Match on segment, channel, MCC group and region, and show the unmatched vs matched gap side by side. That makes the 0.9 pp credible and is strong ML/analytics evidence. |
| **Genie could look bolted on** | The App already answers questions | Give Genie a different user and job: the VP's ad-hoc readiness questions on gold tables. The App is the Director's workflow tool, not a Q&A tool. |
| **Lakebase could look bolted on** *(applied, §8.3)* | Cases could just be a Delta table | Lakebase is the only stage where people write data. Concurrent claims are transactional, App reads and writes are fast, and an audit trail records every change. Case status flows back into the readiness gate and Genie. Evidence: a concurrent-claim test, measured latency, and resolve → readiness-score change. |
| **GenAI could look decorative** | "Summarize this" adds little | Point GenAI at complaint free text to supply root-cause evidence, and at case notes that cite the specific metrics. Score its output in EVAL_PROTOCOL.md. |
| **Could read as internal** | — | This one is fine: it is a customer business outcome with external partners (acquirers). Keep Databricks-internal terms out of the story. |
| **Real brands and names** | No-names rule | Say "incumbent global networks", never brand names. Keep merchants and acquirers synthetic (`ACQ-017`, `MER-…`). Never name the bank or the network. |
| **Readiness score is a black box** | The VP needs to defend it to the steering committee | Make it explainable: an open high-severity count, at-risk volume, and segment risk with explicit weights, each traceable in UC lineage. |
