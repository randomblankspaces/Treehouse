# Team Scope — Clay agent-eval sandbox ("Treehouse")

> **LGND/ADB context — minimal agent-evaluation scope confirmed:** read [the report brief](LGND-REPORT-CONTEXT.md).
> The report is benchmark context; the confirmed minimal pipeline is recorded in OUTLINE.md, rather than silently renumbering historical S/D requirements.
> Suhas confirmed an agent-evaluation sandbox; Strands is part of the workflow being assessed.
> See the report brief and Kiro prompts for that scope; broader benchmark studies remain future work.

> Current context, November 4: Suhas clarified that Treehouse evaluates an agent's complete
> investigation and the accuracy of its resulting geographic database, across configurable tasks
> and zones. Agent explanations/confidence are self-reports; held-out evaluation and separate-context
> process review have distinct evidence labels. Independent test authorship precedes implementation.
> The current delivery sequence and superseding scope are in [OUTLINE.md](OUTLINE.md)
> and [PLAN.md](PLAN.md). Earlier Nepal-only, UI-deferred and old overnight ordering below
> are historical where they conflict; preserved decisions are not new execution authority.


> **For agents — what this file is:** The team's own scope: the problem, constraints, and solution requirements in the team's words, plus a decisions log from the scope interview, the design talk and the overnight design councils (D1–D75). It is the **source of team intent**. Files 01–06 turn it into features, criteria, tests and risks, merged with Clay's vision doc. Every S-requirement below maps to items in 01/02/04/05. S14–S19 (round 5) were mapped and S20–S29 added in round 6, from the two adopted designs in [design/](design/). If you find a requirement with no matching item, or this file disagrees with a numbered file, raise it with the team and don't silently pick one. The build-time design questions in [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) are **decided** (D25), and several are superseded by round 6 (marked there). Text marked *(interpretation)* is the assistant's reading and hasn't been confirmed by the team. Terms are defined in the [Glossary](#glossary) at the end.

## Problem

AI agents in Clay's dataset workflows are a **black box**. When an agent plans and runs a geospatial dataset build by calling tools, it's hard to observe what it did, and there's **no scoring**, so nobody can say whether to trust the run.

**Requirement:** make the agent's work visible and scored, following **Clay's ideology**. *(Interpretation, from Clay's vision doc:* open, reproducible, public/synthetic data only, and trust and provenance treated as first-class.*)*

## Usage

The product is an **agent evaluation** tool, presented as **Treehouse** (D31). Someone runs an agent on a known task, and the product shows what the agent did and how well it did it.

**Flow (D32):** a partner sends a task (e.g. "assess the bridges in this flood area") to the harness → the model works it through Clay and AWS tools → a swappable tracer records the prompt, the context, the agent's thinking, every tool call and every error → the output is graded for what it missed or overshot → Treehouse returns scores, a report and a plain summary, through the API and an MCP server.

**What Treehouse judges (D33):**
1. **How the agent worked** (the main judgment).
2. **Whether its output can be trusted:** the output grade plus how it reached that conclusion.
3. **Whether it understood the task.**
4. A **plain summary** of what it actually did, for the user.

**Cost and speed** are reported next to these as key, separate numbers (D39).

**The core idea (D35):** on tasks with an answer key, Treehouse learns how a run's context, input and trace relate to the accuracy of its output. Where there is no answer key (ADB's real situation), it uses that relationship to say how far the output can be trusted.

## Constraints (as listed by the team)

| Constraint | Meaning | Basis |
|---|---|---|
| Money | The **agent run's cost**, measured per run and per step. First-class, because the agent wades through very large data | Team, D5, D39 |
| Speed | The **agent run's latency**, measured per run and per step. First-class, for the same reason | Team, D5, D39 |
| Compute | Modest instances only, no HyperPod or large Trainium | *(Interpretation, from Clay's service disallow list. Unconfirmed)* |
| Amazon Bedrock | The agent's model runs on Bedrock. Access is confirmed in the Workshop Studio account: everything in the AWS event guide is included (D40). The exact model ids are UNVERIFIED until the K1 probe (D61) | Team |
| Python | Harness, MCP wiring, trace capture, scoring (Python 3.12+ per Clay's doc) | Team |
| Clay embedding model | Pre-computed LGND embeddings exposed to the agent as a tool. We don't run the model ourselves. Clay acts as the **vector-search layer** that narrows the search; the agent then checks imagery more closely (D36) | Team, D4, D36 |
| Agent comparison | Listed as a constraint, but it's also a requirement to build: see **S10** | Team, D3 |

**Project limits (from the event and source docs, not the team's list):** AWS sandbox capped at **$500**. The public repo must be up before judging (Thu Nov 5, prelims at 10:00 am). Official build hours don't bind us (D18).

## Solution requirements

| # | Requirement (team's words, cleaned up) | Feature (01) | Criterion (02) | Test (04) |
|---|---|---|---|---|
| S1 | AI models swap **without code changes** | F6 | SC5 | J3 |
| S2 | Tracing tooling is **swappable** | F6 | SC5 | J3 |
| S3 | Agent activity is **captured as traces** | F2 | SC2 | J1 |
| S4 | A **human-readable summary** | F3 | SC2 | J1 |
| S5 | **Include errors the model may run into.** All agent errors are logged (D12) | F2 | SC2 | J4 |
| S6 | **Trust kept after the run:** keep the traces, the input, and the rubric/reference | F5 | SC7 | J1 |
| S7 | **Open and reproducible** on other machines, beyond the engineer who made it | F12 | SC12 | J8 |
| S8 | **TypeScript or JavaScript UI.** Deferred until the backend is done (D11), but every parameter must already be available to it | F8, F12 | SC11 | J9 |
| S9 | **Verifiable statistics:** the sandbox shows, verifiably and truthfully, that it can evaluate agents (models and harnesses) statistically. The goal is not identical numbers (D1) | F10 | SC9 | J6 |
| S10 | **Compare harnesses, agents, and tooling** (D3) | F9 | SC8 | J5 |
| S11 | **Optional budget guard**, set per run or per eval (D6) | F11 | SC10 | J7 |
| S12 | **Output included as an evaluation metric** (D16) | F4 | SC3 | J1 |
| S13 | Must follow **Clay's ideology** (open, public/synthetic data, provenance) | F5, F12 | SC7, SC12 | J8 |
| S14 | **Scores and reports are also served as an MCP server**, not only the API (D34). Read-only wrapper over the report bundle (D64) | F20 | SC13 | J10 |
| S15 | A **task-understanding score**: did the agent understand what was asked (D33). Deterministic checks only (D62) | F4 | SC14 | J11 |
| S16 | **Output trust** combines the output grade with **how the agent reached its conclusion** (D33). Trust is a separate, derived number shown with its process inputs (D45) | F4, F17 | SC15 | J12 |
| S17 | **Trust without an answer key:** learn from keyed runs how run context, input and trace relate to output accuracy, and apply it to unkeyed runs (D35). MVP method: PPI over a blind verifier plus random human gold (D48) | F16, F17 | SC16 | J13 |
| S18 | **Speed and cost are first-class metrics**, reported separately and not blended into other scores (D33, D39). Their own panel, with data touched (D63) | F5 | SC17 | J14 |
| S19 | The **specialization task** is the synthetic ADB Nepal-flood bridge task. Solar farms are a test example only (D37). AOI: Bhote Koshi corridor (D55) | F14, F24 | SC18 | J15 |
| S20 | **Trust passport with evidence tiers:** every accuracy or trust number states its tier, sample size, interval and estimator version, and abstains when it can't be supported (D46, D48) | F17, F26 | SC16 | J13 |
| S21 | **Blind sampled verifier:** a second agent checks a probability sample of claims and unreported places without seeing the worker's answer, on a different model family by default (D43, D44). The unreported-places half is W10, a declared deviation from DD1 (D74) | F16, F26 | SC19, SC27 | J12, J13 |
| S22 | **Typed numbers:** every number says whether it is **evaluated** (against a key), **estimated**, or **measured** from the trace, and the label survives the report, API, MCP and CSV (D46, D47) | F18 | SC20 | J16 |
| S23 | **Forbidden answer-key sources:** a task's answer-key sources are blocked for the worker and the verifier, and any attempt is logged (D51) | F15 | SC21 | J4 |
| S24 | **Synthetic labelling:** anything synthetic is labelled SYNTHETIC wherever it appears and never counts as real keyed evidence (D53) | F22, F18 | SC22 | J16 |
| S25 | **Imagery the agent can actually inspect:** scene discovery from the catalog plus small byte-range image windows, with honest coverage errors (D57, D58) | F13, F14 | SC23 | J1, J15 |
| S26 | **Total spend stays under the $500 sandbox cap**, across all runs and sessions (D65) | F21 | SC24 | J17 |
| S27 | **Tasks are region-agnostic files:** the same card format runs Nepal, Virginia or India, with nothing region-specific in the code (D52) | F24 | SC18 | J15 |
| S28 | **Sealed, verifiable records:** each run is sealed before any check sees it, and anyone can verify the hash chain offline (D72) | F25 | SC25 | J2 |
| S29 | **AWS-native, not AWS-locked:** every AWS piece has a local stand-in, a probe decides which runs, and the manifest says which ran (D10, D67) | F23, F25 | SC26 | J18 |

## Decisions log (scope interview 2026-11-03; design councils 2026-11-04)

The team's answers are recorded close to their own words. Anything the assistant added is marked *(recommended)* and points to OPEN-QUESTIONS.md.

### Round 1

| # | Decision |
|---|---|
| D1 | "Verifiable code/statistic" means the sandbox can show statistics that are verifiable and true: it can **evaluate the agent in a statistical way**, for both models and harnesses. It's not about getting the exact same numbers. *Method: (recommended) OQ2* |
| D2 | The **models, the harnesses, and the trace evaluator** are hot-swappable (the tracer too, per S2) |
| D3 | **Comparing harnesses, agents, and tooling is necessary for the event.** *What "tooling" covers is open: OQ15* |
| D4 | Clay embeddings: **pre-computed LGND embeddings**, exposed to the agent as a tool. We don't run the model |
| D5 | "Speed" and "Money" both refer to the **agent's run time** (its latency and cost) |
| D6 | The **budget guard is an option that can be switched on or off**: on any run or eval you can set a budget guard. *Limits: (recommended) OQ7* |
| D7 | Agent framework: Strands Agents behind our own interface. The team's answer was "yes, AWS integration is a judging score" *(read as a yes to Strands)* *Refined by D60: plain loop first, Strands through our provider on Wednesday.* |
| D8 | Tracer: OpenTelemetry → local JSONL by default, with AWS CloudWatch/X-Ray as the second backend |
| D9 | *(Original answer to the LLM-judge question)* "The output quality doesn't matter. The actual judgement is the agent evaluation": tracking **the input, the context the agent was given, and the trace the agent took**. **Partly superseded by D16** |
| D10 | It should **run in different places**, with **some AWS integrations**. *Which services: (recommended) OQ9* |
| D11 | **Leave the UI for now.** Make sure **all available parameters** are exposed for the UI |
| D12 | **All agent errors are logged** |
| D13 | **We won't get ADB inputs.** We use **synthetic prompts**. *(Whether Clay sends an ADB rubric is unconfirmed: see 06)* |
| D14 | Team roles: ignored for now |

### Round 2

| # | Decision |
|---|---|
| D15 | The **PDFs stay out of the repo**, and **all md files are pushed**. *(The assistant also excluded the PDFs' text copies)* |
| D16 | **Include output as an evaluation metric.** This supersedes D9 to the extent that output *is* measured. Process (input, context, trace) is still the main judgment. *How output is scored (deterministic vs. LLM judge) is open: OQ12* |
| D17 | Detailed design questions are **parked until right before building**, in [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) |

### Round 3

| # | Decision |
|---|---|
| D18 | The team **can build outside the official build hours** |
| D19 | **We generate the synthetic tasks** ourselves. *What each task contains: (recommended) OQ1* |
| D20 | Team repo: [github.com/VishalPatil18/team-43-renaissance-philanthropy-clay](https://github.com/VishalPatil18/team-43-renaissance-philanthropy-clay) (public). These md files live in `docs/`. *(Work now happens on a fork: D27)* |
| D21 | Post-build features we couldn't implement go in [FUTURE-WORK.md](FUTURE-WORK.md), kept current and shipped in the repo |
| D22 | Text from the AWS event guide may be kept in the md files (the PDFs themselves stay out) |

**Open from round 3:** the team said "we have it working". What exactly works is still to be confirmed (OQ14). *Superseded:* what runs in the AWS account is now recorded by the K1 capability probe (D67), and build state by HANDOFF.md and TODO.md.

### Round 4

| # | Decision |
|---|---|
| D23 | **Partners (e.g. ADB) use the product through a UI.** The UI is essential, and it's built **last**, after the backend works |
| D24 | **Solo build.** Suhas builds alone. `docs/` (this file plus the MVP files) is the only spec. The SRS, the per-member plans, and all of `dev-docs/` were removed from the fork (see D29) |
| D25 | **All defaults in [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) are accepted as decisions.** For OQ12, output is scored by deterministic checks against an answer key, with no LLM judge. OQ13 (team roles) doesn't apply to a solo build. OQ14 is still open *(OQ14 was later superseded by D67.)* *Revised by D43: the blind verifier is admitted as a separately reported signal (DD1).* |
| D26 | **Workflow:** code is written and tested locally, then pushed to a branch on the fork. Kiro (a web IDE inside the AWS Workshop Studio account) pulls the branch, runs only the steps that need AWS (Bedrock calls, deploys, live runs), and reports back |
| D27 | **Work happens on the fork** [randomblankspaces/team-43-renaissance-philanthropy-clay](https://github.com/randomblankspaces/team-43-renaissance-philanthropy-clay). Each milestone goes on its own branch with a PR into the fork's `main`. The team repo (`VishalPatil18/…`) is `upstream`. **Nothing is pushed or PR'd to upstream**, and everything is built and tested in the fork |
| D28 | **License switched to Apache-2.0** in the fork, as Clay requires |
| D29 | `dev-docs/` (design decisions, architecture, UI style guide) was **scrapped**. Its conflicts with this spec far exceeded the team's limit of 15 (references to the deleted SRS, five-person workstreams, MIT, team release dates). The UI style guide was copied from a banking site and used proprietary fonts. The architecture will be redone from scratch. The teammates' agent skills (`.agents/`, `skills-lock.json`) were also removed |
| D30 | **AWS is reached only through the browser** (Workshop Studio + Kiro web IDE). There are no AWS credentials on the dev Mac. Every AWS step is a prompt for Kiro, which reports back (extends D26) |

**Pending from round 4:** whether the API and UI get a hosted AWS deployment with login for partners. *Proposed by D67 (Suhas to confirm):* hosted login (Fargate + Cognito) is Stretch; the report is a self-contained HTML file, served locally or by presigned URL.

### Round 5 (design talk, 2026-11-03 evening)

| # | Decision |
|---|---|
| D31 | **Name:** the repo and docs stay "Clay agent-eval sandbox". When we present, the product is called **Treehouse** |
| D32 | **Product flow:** a partner sends a task to the harness. The model uses Clay and AWS tools. A swappable tracer records the prompt, the context, the agent's thinking, every tool call and every error. The output is graded for what it missed or overshot. Treehouse returns scores and a report. Model and tracer stay hot-swappable (D2) |
| D33 | **What gets judged:** (1) how the agent worked, which is the main judgment; (2) whether its output can be trusted, from the output grade *and* how it reached its conclusion; (3) whether it understood the task; (4) a plain summary of what the agent did, for the user. Output stays a secondary metric (D16). Cost and speed are "key, easy parts of agent evals", kept as separate numbers *Refined by D45 (three separate numbers; whether trust is the headline is still Suhas's call), D62, D63.* |
| D34 | **Scores and reports are both exposed as an MCP server**, alongside the API. *Who calls it (Clay's agents, Claude Desktop, Kiro) is open: decide in the design interview* *Status set by D64.* |
| D35 | **What the answer keys are for:** they exist for testing. In real ADB use nobody knows where the bridges are, but when the AI builds a dataset from satellite data, ADB needs to know whether to trust it. So on keyed tasks we look for the relationship between the run's context, input and trace and the accuracy of its output, and use it to draw conclusions where there is no answer key. *(Assistant's reading: the agent must not be able to reach the answer key during a test run. Confirm in the design interview, since OSM is both a normal map tool and an answer key)* *Method: D48. The agent can't reach the answer key: D51.* |
| D36 | **What Clay is.** *Fact-checked 2026-11-03:* the Clay model is an open foundation model that turns an image tile into a vector. LGND embeddings are Clay v1.5 run over the whole globe's Sentinel-2 archive (2017 to April 2026, about 15.2 billion vectors from about 2.2 PB of imagery), with **one 256-number vector per 1.28 km cell per month**. They are GeoParquet on source.coop, public, CC BY 4.0. LGND Geo MCP is LGND's commercial agent tool built on Clay; Clay's doc says teams get whitelisted, but our access and what it can find are unconfirmed (ask Clay). *Suhas:* Clay works as a **vector database** that narrows the search, after which the agent checks the images more closely. The vector database isn't the whole picture |
| D37 | **Solar farms in Virginia are a test example only.** The **specialization** is an ADB-style task: the August 2026 Nepal floods, building a bridge inventory and each bridge's post-flood status (see [Synthetic ADB task](#synthetic-adb-task-specialization)). The region is the **Kathmandu valley or the Trishuli river corridor**, to be decided later. The target is bridges in rural ADB areas *Region set by D55: the Bhote Koshi corridor.* |
| D38 | **The resolution limit is real.** Sentinel-2 is 10 m, so it shows solar farms and large bridges but not cars or footbridges. Outside the US, the only high-res imagery in Clay's data list is Vantor's disaster-event imagery (0.4–0.6 m in the Nepal scenes). *(Recommended: an agent that says what the data can't show earns task-understanding credit; confirm in the design interview)* *The recommendation is adopted in D62.* *(Fixture 2026-11-04: `pan_gsd` 0.31–0.77 m over the 33 items; 0.31–0.69 m over the 23 that intersect the AOI.)* |
| D39 | **Speed and cost are first-class**, because the agent goes through huge amounts of data. *Fact-checked:* the Vantor GeoTIFFs are Cloud-Optimized GeoTIFFs (they accept byte-range reads), so an agent can read a small window around one bridge instead of a 1–1.6 GB file. How much data an agent touches is part of how it worked |
| D40 | **Bedrock access is confirmed:** the Workshop Studio account includes everything in the AWS event guide (Suhas, 23:11). *This likely answers OQ14 for the account; the Kiro environment check still records the exact model IDs* |
| D41 | **Flood and bridge-failure simulation is a Treehouse feature, but STRETCH / FUTURE only, not MVP.** When built: (a) the simulation is **visible** to the user, and every input number is shown so the user can recreate and test it; (b) it uses flood records, soil data, pre- and post-flood imagery, and bridge type, size and condition; (c) it starts **only when the user selects a location in the dataset and clicks the action** to simulate; (d) it is **realistic, including bridge failure, but not overly so**; (e) it combines AWS, Clay and AI, pulling from as many valid databases as possible to reach a reasonably certain conclusion for ADB; (f) **a person verifies** each simulation, because it can contain errors and is token-heavy; (g) after the bare-bones version, it is checked against the August 2026 flood. Logged in [FUTURE-WORK.md](FUTURE-WORK.md) |
| D42 | **Build the current scope first:** the core loop on the specialization task. The simulation waits until that works |

**Pending from round 5** (proposed answers in round 6, most still Suhas to confirm): the solo cut line (D66); who calls the MCP server (D64, audience still open); whether answer-key sources are blocked (D51); Kathmandu vs. Trishuli (D55, Bhote Koshi corridor). Still open: LGND Geo MCP access and capability (ask Clay).

### Round 6 (overnight councils, 2026-11-04)

Suhas was asleep and hands-off. DD1 is his own decision ([design-decisions.md](design/design-decisions.md)). Everything else was decided by the two design councils: [SYSTEM-DESIGN.md](design/SYSTEM-DESIGN.md) (**SD**, council 1) and [IMPLEMENTATION-DESIGN.md](design/IMPLEMENTATION-DESIGN.md) (**ID**, council 2, unanimous at round 3), answering the review-1 judge ([review1-judge.md](reviews/review1-judge.md), **RJ**). Status column:
- **Suhas** = his decision.
- **Council (Suhas to confirm)** = the designs or the judge flag it for him (SD A12, ID §10, RJ §5).
- **Council** = adopted by the councils and not flagged. Suhas can still override any row by logging a new decision.
- **DEVIATION** = council or agent text changed or deferred one of Suhas's own decisions (D1–D42, DD1). Always Suhas to confirm. All of them are listed in [Decisions Suhas must confirm](#decisions-suhas-must-confirm).

| # | Decision | Status | Source |
|---|---|---|---|
| D43 | **DD1 verbatim:** truth sources in the MVP = answer keys + a verifier agent (sampled: claimed items + unreported places, blind to the claim, own accuracy measured on keyed tasks). Hindcasting = first stretch. Revises D25/OQ12 "no LLM judge for output": the verifier is a separately reported signal. *Added by the councils (not Suhas): the verifier is calibrated, never the output grade, and its verdicts are recorded so replay reproduces them without Bedrock (RJ C10). The unreported-places half is deferred to W10, a deviation (D74)* | **Suhas** (DD1, 23:38) for the DD1 text; Council for the added sentence | design-decisions.md; SD A5 item 3; RJ C10 |
| D44 | **The verifier is blind and uses a different model family from the worker by default.** It gets only location, object definition and scene ids, fetches its own windows, has only `imagery_window` and `stac_search`, and may answer `cannot_assess`. Config validation enforces the family rule; `allow_same_family: true` stamps the manifest "self-verified" and removes independence credit | Council (Suhas to confirm) | SD A5 "DECISION"; ID §2 `RunConfig`; RJ §5 decision 2 |
| D45 | **Three separate numbers, never blended:** how the agent worked (process), the raw output grade, and trust (derived). The scorecard has five panels (process, task understanding, output, trust, cost/speed/data touched) and **no default composite**. Trust is shown with its inputs (`process_facts` beside the interval). *Decided:* the trust passport and plain summary sit in the report's first viewport, and trust is a headline only if it beats its baseline (SD commitment 4). *Not decided:* whether trust formally replaces D33's "how the agent worked is the main judgment". That is RJ decision 1, still Suhas's call | Council; headline question for Suhas | SD A6, A9; ID §3 Report; RJ C6, §5 decision 1 |
| D46 | **Typed numbers and evidence tiers.** Every number is a `TypedNumber` carrying type, tier, n, interval, estimator version, manifest ref and a required `synthetic` flag. Accuracy and trust tiers: **KEYED** (*evaluated*), **GOLD-ANCHORED**, **CALIBRATED-TRANSFER**, **MODEL-ESTIMATED** (all *estimated*), **ABSTAINED** (no number, with a reason). An unkeyed output is never called "scored" or "evaluated". Plain-English chips: "Checked", "Estimated from a random check", "Estimated from track record", "Rough model guess", "Not issued" | Council | SD Conventions, A6, A13 §3; ID §2; RJ C2 |
| D47 | **MEASURED is a sixth tier** for exact trace-derived numbers (process, understanding, cost panels and the controls kappa), chip "Measured from trace". Never used for output or trust | Council (Suhas to confirm) [DEV] | ID §0 row 8, §10 item 1 |
| D48 | **Trust method:** design-based prediction-powered inference (PPI) over the blind verifier's verdicts plus a random human gold subsample (about 20–25), λ fixed at 1 while n_gold < 50, stratified-bootstrap or exact intervals. The gold-only interval and the width ratio are printed beside it. Baselines B0/B1/B2, an abstain rule, a disagreement rule and a gate (Rely / Spot-check / Do not rely). The estimator is versioned and frozen (`estimators.lock`, W13, before the first live GOLD-ANCHORED run). Validation in the MVP is planted-error, placebo, shuffled-label and seeded coverage tests (method tests M1–M17). Leave-one-regime-out is **"not computable: 1 keyed regime"** until a second real keyed regime exists | Council | SD A7, A13; ID §3 PPI, §6; RJ C1 |
| D49 | **A human `cannot_assess` gold label counts as "not verified".** The headline is then named `verified_precision` (a lower bound), with `n_gold_cannot_assess` and a y=1 upper bound beside it | Council (Suhas to confirm) | ID §0 row 26, §10 item 4 |
| D50 | **The shuffled-label test is referenced to the gold-only interval, not B2.** A correct estimator fails the B2 version (measured width 0.34 vs 0.51) | Council (Suhas to confirm) [DEV] | ID §0 row 10, §10 item 3 |
| D51 | **Forbidden answer-key sources.** Every keyed step declares its key sources as `forbidden_sources`, for the worker and the verifier. Four layers: gateway deny-list; key isolation (a separate key directory or IAM-denied bucket, with the manifest saying which ran); a leak detector with canary decoys in key copies we host; and an honest limit printed on every report (model memory of OSM/USPVDB can't be blocked). A blocked call is a logged `key_access_attempt` agent error and the touched item is excluded from keyed grading. Where OSM is the key it is **not in the tool set and is also denied** at the gateway (answers RJ decision 9). Masked-block OSM keying is a Could | Council (Suhas to confirm the RJ decision 9 answer) | SD A2, A3; ID §3 gateway; RJ C5 |
| D52 | **Task cards are region-agnostic, self-contained files** (YAML plus JSON Schema, content-hashed): AOI, time window, `as_of`, data allowlist with licences, steps with keying, forbidden sources, `must_notice`, sampling and gold plans, budget. No region constants in code (a test scans `src/` for lat/lon literals and place names). The goal text carries "synthetic task, not from the partner". Four cards: `synth-crossings-v1`, `nepal-bhote-koshi-bridges`, `virginia-solar-18sth` (`pending_fetch`), `india-brahmaputra-bridges` (validate-only stub, a different family that the passport abstains on) as the "works anywhere" proof (answers RJ decision 7) | Council (Suhas to confirm the second region) | SD A2, A7; ID §0 row 23, §2, §6 J15; wip/council2/a-rs.md §5.4; RJ C15 |
| D53 | **A SYNTHETIC keyed task is added, never a keyed regime.** `synth-crossings-v1` (a generated river world with a planted key) drives offline replay and the method tests. Every number from it carries the SYNTHETIC chip. It never counts toward leave-one-regime-out, "k regimes", B0 pooling or trust transfer, and it never backs a KEYED number, a verifier sensitivity/specificity claim or the Clay ablation in the demo. It would not have satisfied SD's H10 checkpoint, now superseded by C1–C3 (D66) | Council (Suhas to confirm) | SD Conventions, A12 demo task 1; ID §5.1; council-1-log.md doubt 14 |
| D54 | **Virginia solar stays demo task 1 (keyed, USPVDB), run live via Kiro** or exported credentials. It ships as `pending_fetch`: USPVDB is blocked from the build container, so `fetch_uspvdb.py` runs on Suhas's Mac (K6). NAIP is Requester Pays and needs AWS credentials; the key/imagery date gap (USPVDB V4.0 April 2026, NAIP on AWS about 2010–2023) must be checked | Council (Suhas to confirm) | SD A12 demo task 1, decisions table last row; ID §10 item 9 |
| D55 | **Nepal AOI = the Bhote Koshi corridor, Syabrubesi to Timure/Rasuwagadhi** (Rasuwa district, where the flood actually hit), a parallelogram (85.330, 28.150), (85.375, 28.150), (85.400, 28.290), (85.345, 28.290); `smoke_aoi` [85.33, 28.14, 85.37, 28.18]; `as_of` 2026-09-18. **The corners are UNVERIFIED** (placed from memory): Suhas checks them visually at K2b. A lower-Trishuli alternate card is kept only if time allows. Resolves D37's "Kathmandu or Trishuli" | Council (Suhas to confirm) | ID §5.2, §10 item 8; wip/council2/a-rs.md §5.2; RJ C16, §5 decision 6 |
| D56 | **Nepal reference path:** the inventory step is partly keyed against an OSM bridge snapshot (`pending_fetch`); the damage step is unkeyed and becomes GOLD-ANCHORED from about 24 blind human labels by the builder ("builder-checked human reference", not truth). Controls are post/post test-retest on the same-pass pair E5610/E5810; pre/pre placebo is "unavailable" (2 pre scenes, about 51 % overlap per RS, about 63 % of the AOI covered by both by fixture footprints, 3–5-year gap). The rubric grades **post-event state**, because the July 2025 flood breaks the pre-event baseline. Until Suhas labels, the demo uses synthetic points on the real corridor with synthetic gold, labelled "illustrative, not surveyed bridges" and "SYNTHETIC GOLD, not human labels" (answers RJ decision 4) | Council (Suhas to confirm) | SD A5 controls, A7 flagship; ID §0 row 24, §5.2, §10 item 5 |
| D57 | **Scene discovery is a system step.** The agent and the checks find scenes through `stac_search` over a pinned STAC fixture (item ids and ETags), not a hand list. The SCOPE data table is corrected to the 33-scene catalog (below) | Council | ID §3 stac server, §5.2; RJ C16 |
| D58 | **A generic `imagery_window` tool is Must:** a byte-range window read from any STAC/COG source, returning scene id, bbox, date, GSD (nominal and effective), scene cloud %, **bytes read**, a pixel hash and an obscuration heuristic, with explicit `no_coverage` and `out_of_bounds` errors. Tonight it uses a synthetic source with a declared block model ("modelled bytes"); the real COG reader is W1. Tasks with `needs_vision` accept only vision-capable models | Council | SD A3 tools; ID §0 row 6, §3 imagery; RJ C8 |
| D59 | **Clay embeddings narrow, imagery decides.** `clay_search` returns ranked cells plus a coverage report (Sentinel-2, 1.28 km cells, Jan 2017 to Apr 2026, can't see a footbridge, predates the Aug 2026 flood). Clay's value is tested by a with/without ablation, not asserted. LGND embeddings are tagged MVP (narrowing only) | Council | SD A3; RJ C4 |
| D60 | **The plain Converse tool loop is the Must-0 demo and replay engine. Strands arrives Wednesday (W2)** through our own `ModelProvider` with a sequential tool executor, so there is one Bedrock code path. If W2 slips, the live Nepal run uses the plain loop and every output says "Strands adapter: offline-tested only". Revises SD A3's "Strands default, plain loop Should". AgentVerifier ships in W2 too: if W2 slips, either AgentVerifier is split out to run on the plain loop, or K4 runs with recorded verdicts only and the passport says "verifier: recorded, not live" (ID §7 W2, §8 K4) | Council (Suhas to confirm) [DEV] | ID §0 rows 2 and 14, §10 item 2, §8 K4 |
| D61 | **Default models: Claude Sonnet 5.5 as worker, Amazon Nova Pro as verifier.** Both ids are **UNVERIFIED until the K1 probe**; the vision smoke test (K2b) decides the final pair | Council (Suhas to confirm) | ID §3 Bedrock adapter, §10 item 7, fact-check U1/U2 |
| D62 | **Task understanding is scored deterministically:** the agent's first step is a structured Understanding Statement, checked against the card's `must_notice` items and against its later actions (MEASURED). Declaring a data limit (resolution, cloud, embedding dates) earns credit, adopting D38's recommendation. Reasoning text is stored when the provider returns it, marked `absent` when not, and **never scored** | Council (Suhas to confirm the D38 recommendation) | SD A3, A6 panel 2; ID §3 scorers; RJ C10, C12 |
| D63 | **Speed, cost and data touched are their own panel (Panel 5), never blended into the others.** It holds dollars per role and step, tokens, calls, windows, bytes read, latency p50/p95, cost per correct item (only when keyed), and the verifier's cost as "the price of trust". This resolves S18 vs the old F4/SC3/J1.4 | Council | SD A6; ID §3; RJ C7 |
| D64 | **MCP server status:** a thin, read-only wrapper over the report bundle with exactly 8 tools (`list_runs`, `get_scorecard`, `get_trust_passport`, `explain_trust`, `get_plain_summary`, `get_claim`, `compare_configs`, `get_trace_span`) and one resource. Every number comes back typed. Write tools are off. SD puts it in Must-1 (A9 calls it the first Must-1 item, A12 lists it fifth) and cuts it first on slip; the build queue has it at W7. *(Interpretation:* the spec sheet first treated it as Should, matching RJ C17. It now follows the designs: **Must-1, cut first on slip**, built in W7. Should or Stretch is still Suhas's call, RJ decision 10*)*. If it is cut, that **deviates from D34** (scores and reports exposed as an MCP server). Callers are any MCP client over stdio; D34's "who calls it" stays open | Council (Suhas to confirm) | SD A9, A12 Must-1 item 5; ID §3 MCP server, §7 W7; RJ C17 |
| D65 | **Spend thresholds:** a cross-run spend ledger with worst-case reservation, **$250 planned, $350 alarm, $450 hard stop** under the $500 cap. Live calls are refused while a model's price is null. The K1 probe is capped at $3. On Kiro the ledger lives in the repo and is pushed after every step. Measure one real vision run (K3) first, then size N from p90 cost (answers RJ decision 8) | Council (Suhas to confirm) | SD A8 budget; ID §3 SpendLedger, §10 item 11; RJ C9 |
| D66 | **Cut line:** SD A12's Must-0 walking skeleton, Must-1, Should, Could and Stretch lists, as implemented by ID §7's overnight packages P0b–P8 (P9 becomes W0) and the Wednesday queue W0–W15, with checkpoints C1 (P5 merged by H4.5), C2 (07:15: pre-empt if P6 is not merged; P6 by 08:00) and C3 (08:00: push everything; TODO.md says which of P7–P8 merged), and a non-negotiable freeze at T-6h. The demo is recorded from replayed traces regardless. Per-feature priorities are in [01](01-features-in-scope.md) (answers RJ decision 5). Notes: (a) SD A12's H10 checkpoint (a live keyed Virginia run by H10) and its fallback are **superseded** by ID's C1–C3, because Virginia is `pending_fetch` and there are no AWS credentials overnight. The first live keyed run is K3 (synthetic, which by D53 does not count), then Virginia after K6. (b) The versioned S3 store is Must-0 by SD (A4, A10) but is built in W5/K8, so tonight's demo shows the local store and the manifest says so. (c) Multi-provider (HANDOFF hard rule; RJ must-fix 1) is Could: the `ModelProvider` interface allows it, but only Bedrock and the Fake/Replay providers ship. (d) RODA MCP and the shortlist servers are optional (F1), departing from Clay's Day-1 guidance. (e) The tiers that deviate from Suhas's own decisions (DD1 unreported places, D3, D8, D23) are listed in [Decisions Suhas must confirm](#decisions-suhas-must-confirm) | Council (Suhas to confirm) | SD A12; ID §7; RJ C3 |
| D67 | **AWS: native, not locked.** Every seam has a local stand-in, and the manifest records which backend actually ran (from read-backs, never from config). The hour-0 capability probe (K1, `aws-capabilities.json`) decides. Guaranteed floor in the demo: Bedrock Converse plus a versioned S3 run store; Object Lock, the key-bucket IAM Deny and CDK for what we deploy are Must-1 (CDK is W6, none tonight); the CloudWatch tracer (a **DEVIATION** from D8, which named CloudWatch/X-Ray as the second backend), Lambda window reads and invocation logging are Should. Hosted login (Fargate + Cognito) is Stretch (SD A10; SD A9 says "cut"). Every AWS step is a Kiro prompt (K0–K9; TODO.md adds K0, the execution locus). Supersedes OQ9 and proposes an answer to round 4's pending "hosted deployment with login" | Council (Suhas to confirm the hosted-login Stretch tier, which closes his round-4 pending item, and the D8 deviation) | SD A9, A10; ID §7–§8 |
| D68 | **Statistics and comparisons:** every MVP comparison is labelled exploratory. Paired comparisons, one factor at a time (model cross-family; harness only if both harnesses exist; tooling = with/without `clay_search`; verifier same vs cross-family), with cluster or paired bootstrap CIs, Wilson only for simple proportions, a fixed two-stage trial plan (K=3, then a pre-declared allocation), Holm over a committed primary list, and at least 5 per arm. `compare` is W8. Supersedes OQ2 and OQ4. **DEVIATION from D3:** SD A12 lists the paired comparison as Should 7 and ID builds it in W8, while D3 (Suhas) calls comparison necessary for the event. 01 follows the designs (F9 Should); Suhas to confirm or raise it to Must | Council for the method; **Suhas to confirm** the F9 tier (DEVIATION from D3) | SD A8; ID §6, §7 W8 |
| D69 | **OQ10's five text tasks are superseded by the four task cards (D52).** Keyed cards are the calibration and statistics set (synthetic only for method tests, D53). The planted policies (fabricator, skimmer, looper, key-peeker, overconfident, budget-stop) take over the error-triggering role of OQ10's ambiguous task. *(This departs from RJ C11, which kept the ambiguous task. RJ is the review-1 judge, not Suhas.)* | Council (Suhas to confirm) | ID §5.1; RJ C11 |
| D70 | **Licences and pixels in provenance:** SPDX per source and blob, a licence floor and a non-commercial notice on every Vantor-derived report. Commit scene ids, bboxes, byte ranges and pixel hashes, **never imagery pixels** (a licence scan rejects image bytes in `fixtures/`, `tasks/` and `docs/`). Vantor is CC-BY-NC-4.0 | Council; the no-pixels rule is from Suhas's job instructions (HANDOFF.md "Hard rules"), not a D1–D42 decision | SD A4; ID §6; HANDOFF.md; RJ C14 |
| D71 | **The simulation and the act layer stay downstream** of the eval product. The act layer is a Could stub (an inspection-priority list that consumes only the Certified Dataset). The simulation ships as a Simulation Card spec only (Stretch/Future, D41 unchanged). README stretch order: the hindcast first, then Clay's stretch goals; the simulation stays last among builds (RJ C13). *(Default follows DD1 literally: hindcast first, then Clay's stretch goals. If DD1 meant first among truth sources only, it moves after Clay's goals, which was the earlier reading. Suhas to confirm.)* | Council (Suhas to confirm the order) | SD A1, A11; RJ C13 |
| D72 | **Seal before any check.** Trace, cassette, claim table and manifest are written once and hash-chained, one chain per trial, before any key, verifier or human sees the output. Scorers are pure functions of sealed records, replay never calls a live model, and `treehouse verify` checks the chain anywhere with no AWS | Council | SD commitments 1, A1, A4; ID §3 Store, §4 |
| D73 | **Images reach the model through an in-process side channel** (`PixelCache`), not MCP ImageContent, so pixels stay out of MCP payloads and cassettes | Council (Suhas to confirm) | ID §0 row 21, §10 item 10 |
| D74 | **DEVIATION from DD1: the unreported-places frame is deferred.** DD1 samples "claimed items + unreported places", and SD A5 keeps both parts. ID defers the unreported-places frame and miss rate to W10 (Should) with no [DEV] mark and no §10 entry, and the first spec sheet copied that silently. Until W10 the MVP verifier samples claimed items and controls only, and every passport says "unreported places not sampled (W10)". When W10 lands, SC27 and J13 step 8 test it | **Council: DEVIATION, Suhas to confirm** | design-decisions.md; SD A5 item 3; ID §2 `unreported_frame # W10`, §7 W10 |
| D75 | **Morning order and spec timing:** K1 → K2a prices → K3 (live synthetic, about $15) → W1 → K2b vision smoke (about 09:45). TODO.md puts K0 (execution locus) before K1. ID scheduled the spec-sheet update after P6; it was done before P6 merged | Council (Suhas to confirm) | ID §0 row 30, §10 items 6, 12; TODO.md |

**Pending from round 6:**
- Suhas to confirm or override every item in [Decisions Suhas must confirm](#decisions-suhas-must-confirm) below.
- The Nepal AOI corners (K2b), real per-run vision cost (K3), and Bedrock model ids (K1).
- LGND Geo MCP access (still to ask Clay).
- OSM footbridge completeness in Rasuwa.
- The Virginia key/imagery date gap.

### Decisions Suhas must confirm

One line each. **DEVIATION** rows change or defer one of his own decisions (D1–D42, DD1); the rest are council choices flagged for him.

**Deviations from Suhas's own decisions**
1. **D74 (DD1):** the verifier's unreported-places frame and miss rate are W10 (Should); the MVP samples claimed items and controls only.
2. **D68 / F9 (D3):** the paired comparison eval is Should (SD A12 Should 7, W8), though D3 calls comparison necessary.
3. **F8 (D23):** the UI is Should (SD A12 Should 2), though D23 calls it essential; the HTML report stands in.
4. **D67 / F6 (D8):** the CloudWatch second tracer is Should (W9); until then only the JSONL tracer exists.
5. **F12, F20 (D32, D34):** the API is Should (W12; SD A12 even lists it as Could) and the MCP server is Must-1, cut first on slip; cutting either deviates from D32/D34.
6. **DD1 "own accuracy measured on keyed tasks":** only Virginia (`pending_fetch`, K6) can supply it; until then the passport says "synthetic controls only, not evidence" (SC19).
7. **D71 (DD1):** stretch order now follows DD1 literally (hindcast first); confirm, or say DD1 meant first among truth sources only.

**Council choices flagged for Suhas**
8. **D45:** whether trust formally replaces "how the agent worked" as the main judgment (RJ decision 1).
9. **D44:** verifier blind and cross-family by default; `allow_same_family` stamps "self-verified".
10. **D47 [DEV of SD]:** MEASURED as a sixth tier.
11. **D49:** human `cannot_assess` counts as "not verified" (`verified_precision`).
12. **D50 [DEV of SD]:** shuffled-label test referenced to the gold-only interval.
13. **D51:** OSM not in the tool set and denied where it is the key (RJ decision 9).
14. **D52:** India as the second-region proof (RJ decision 7).
15. **D53:** the SYNTHETIC keyed task and its limits.
16. **D54:** Virginia stays demo task 1, run live via Kiro, shipped `pending_fetch`.
17. **D55:** Nepal AOI corners (visual check at K2b).
18. **D56:** Nepal reference path and synthetic gold until he labels (RJ decision 4).
19. **D60 [DEV of SD]:** plain loop is the Must-0 engine; Strands and AgentVerifier in W2, with the stated fallback.
20. **D61:** default models Sonnet 5.5 / Nova Pro (UNVERIFIED until K1, K2b).
21. **D62:** adopting D38's recommendation (credit for declaring data limits).
22. **D64:** MCP server tier, Should or Stretch (RJ decision 10).
23. **D65:** spend thresholds $250 / $350 / $450 (RJ decision 8).
24. **D66:** the cut line, including the superseded H10 checkpoint, multi-provider as Could, and RODA optional.
25. **D67:** hosted login (Fargate + Cognito) as Stretch, closing his round-4 pending item.
26. **D69:** planted policies replace OQ10's ambiguous task (departs from RJ C11).
27. **D73:** images through the in-process side channel.
28. **D75:** morning order K0 → K1 → K2a → K3 → W1 → K2b.

## Synthetic ADB task (specialization)

Written by the assistant as a synthetic ADB prompt (D13, D19, D37). It ships as the task card `nepal-bhote-koshi-bridges` (D52, D55). The synthetic notice is part of the prompt itself (RJ C15). The data facts below were re-checked against the Vantor STAC catalog on 2026-11-04 (D57).

> *Synthetic task written by the Treehouse team. It is not from ADB.*
>
> **Task: rapid bridge damage assessment, Nepal floods (August 2026).** ADB is preparing a quick-disbursement disaster response for Nepal after the August 2026 floods. Before committing reconstruction funds, we need a dataset of river-crossing bridges in the flood-affected area and their condition after the event. Using only public satellite data and Clay's tools:
> 1. Build an inventory of every bridge crossing the main river and its tributaries in the area, road bridges and suspension footbridges.
> 2. For each bridge, assess its post-flood status: **intact, damaged, destroyed, or cannot be assessed**.
> 3. Return a GeoJSON file of points with: bridge ID, coordinates, bridge type, river crossed, status, confidence (0–1), the image ID and date used as evidence for both before and after, and a one-line reason.
> 4. List any areas you could not assess and why (for example cloud cover, no post-event imagery, or resolution too coarse).
>
> Do not use existing bridge databases or map layers as your source: we need to know what the imagery shows. Keep total cost under $20 per run.

The card's `budget` block (`usd: 20`, plus tool-call, byte, time and token limits) is normative; the prompt only repeats it.

**The event** (STAC `event.json`): a glacier-collapse flash flood on **2026-08-26** (about 03:30 UTC) entered the **Bhote Koshi** from the Tibet side in **Rasuwa district**. It hit Timure and Rasuwagadhi first, then moved down to Syabrubesi and the Trishuli corridor. There is **no cloud mask** (`mask: false`); cloud is a single scene-level `eo:cloud_cover` number.

**Data behind it** (`s3://vantor-opendata/events/Nepal-Flooding-Aug-2026/`, public, us-east-1, CC-BY-NC-4.0). The catalog holds **33 scenes: 4 pre-event and 29 post-event**, by the STAC `phase` field. Items carry `eo:cloud_cover`, `pan_gsd` (0.31–0.77 m across the 33 items and 0.31–0.69 m over the 23 that intersect the AOI; SD A3 said 0.43–0.71 m, corrected post-adoption), `view:off_nadir` and `view:sun_*`. The full list is in `wip/fixtures/nepal-flooding-aug-2026.stac.json` (metadata only). **23 scenes intersect the AOI** (2 pre, 21 post), the 23 ids the Nepal card pins. The scenes the designs use (AOI coverage measured on fixture footprints, 2026-11-04):

| Scene | Date | Phase | Cloud | pan_gsd | Role in the designs |
|---|---|---|---|---|---|
| B1300011011E5610 | 2026-09-07 01:43Z | post | 18 % | 0.35 m | **Clearest post scene over the corridor**; covers the whole AOI; `nepal-good` uses it |
| B1300011011E5810 | 2026-09-07 01:44Z | post | 19 % | 0.37 m | **Test-retest twin of E5610** (same pass, 30 s later): the Nepal verifier control |
| B1300011011F4F10 | 2026-09-08 | post | 44 % | 0.37 m | Partial-cloud post scene (about 99 % AOI coverage by footprint; a-rs.md says 91 %) |
| B160001101ECBC10, B160001101ECBD10 | 2026-09-18 | post | 7 %, 6 % | 0.36 m | Clearest post scenes overall, but **outside the upper corridor** (lon 85.46–85.58) |
| 16 scenes, 2026-08-27 to 09-09 (for example B040001100881410, B030001100CF1310, B130001101153A10, B120001101226410) | | post | 71–94 % | 0.31–0.69 m | **The cloud trap**: they intersect the AOI (15 cover at least 60 % of it) but are mostly cloud. ID §5.2 and a-rs.md said 13; the fixture gives 16 |
| B030001100EF5910, B1200011012B2A10 | 2026-09-08, 09-12 | post | 48 %, 59 % | 0.51, 0.38 m | Partial cloud; each covers about half the AOI |
| B030001100EF5510 | 2026-09-08 | post | 24 % | 0.48 m | Lower-Trishuli alternate (with the 2026-02-05 pre scene) |
| 10300100C86CED00 | 2021-10-16 | pre | 22 % | 0.57 m | Pre scene covering about 83 % of the AOI |
| 10500100364E8400 | 2023-09-17 | pre | 46 % | 0.43 m | Pre scene covering about 72 % of the AOI (stops at 28.26 N, so not Rasuwagadhi) |
| 10300100FCB83600 | 2024-05-29 | pre | 15 % | 0.58 m | Pre scene; **doesn't cover the upper corridor** (includes Kathmandu) |
| B160001100CDB210 | 2026-02-05 | pre | 0 % | 0.35 m | Only post-July-2025 pre scene; **doesn't cover the upper corridor** (lower Trishuli only) |

Sources: STAC fixture; ID §5.2; SD A5 controls and A12 demo task 2; wip/council2/a-rs.md §5.2 (AOI coverage; its 13-scene count, measured by bbox, is superseded by the fixture's 16). The earlier version of this table listed only 5 scenes and two 74–81 % cloud post scenes, which made the cloud picture look worse than it is (RJ C16).

**Caveat: the July 2025 flood.** A Bhote Koshi flood on 2025-07-08 destroyed the Miteri (Nepal–China friendship) bridge at Rasuwagadhi, and a 2025-07-30 flood cut the Syabrubesi–Rasuwagadhi road (Kathmandu Post and ekantipur, 2025-07-08). The pre-event scenes from 2021 and 2023 are therefore **not a "no change" baseline** for the upper corridor. Damage is graded as **post-event state**. Change is attributed to the August 2026 event only where a pre scene dated after July 2025 covers the bridge, and none does in the upper corridor (SD A5).

**Scene discovery is a system step** (D57). The list above is for people. Runs find scenes through `stac_search` over the pinned fixture (item ids plus ETags), and the hour-1 probe checks per bridge which pre and post scenes cover it.

**Why it tests an agent well:**
- **Coarse to fine:** the agent narrows the search with Clay embeddings, then reads small windows of the 0.31–0.69 m imagery. Footbridges are visible only at about 0.5 m effective resolution (D58, D59).
- **A trap:** 16 post scenes over the AOI are 71–94 % cloud, while E5610 and E5810 are 18–19 %. A good agent picks the clear pair and marks obscured bridges "cannot be assessed"; a bad one averages over cloudy scenes or guesses.
- **Half keyed:** OSM bridges can grade the inventory step (as a forbidden source, D51). No key grades the damage step, so its trust number is GOLD-ANCHORED from blind human labels, or MODEL-ESTIMATED and wide without them (D56).

## Works under

Scope: **ADB agentic eval only**, specialized on the Nepal flood bridge task (D37, D55). The simulation is a stretch (D41, D71). How it is built: [design/SYSTEM-DESIGN.md](design/SYSTEM-DESIGN.md) and [design/IMPLEMENTATION-DESIGN.md](design/IMPLEMENTATION-DESIGN.md). Captions are a stretch, attempted after the ADB stretch goals. All MVP files apply: [01](01-features-in-scope.md) · [02](02-success-criteria.md) · [03](03-out-of-scope.md) · [04](04-user-journeys-tests.md) · [05](05-definition-of-done.md) · [06](06-risks-and-dependencies.md) · [EXTERNAL-DEPENDENCIES](EXTERNAL-DEPENDENCIES.md).

## Glossary

| Term | Meaning |
|---|---|
| **Clay** | The beneficiary: an open Earth foundation model project, building the "Earth Dataset Foundry" |
| **ADB** | Asian Development Bank, a Clay partner. The "ADB agentic eval" is the task of evaluating an agent on an ADB-style "how to use AI / build datasets" job |
| **Agent** | An LLM (on Bedrock) that plans and calls tools to do a task |
| **Harness** | The code that runs the agent loop: prompt → model → tool calls → result. Examples: Strands Agents, or a plain Bedrock Converse loop |
| **MCP** | Model Context Protocol, the standard way the agent reaches tools ("MCP servers") |
| **Tooling / tool set** | The set of MCP servers the agent can use in a run (see OQ15 for other meanings) |
| **RODA** | AWS Registry of Open Data. The RODA MCP server lets the agent search and sample it |
| **LGND embeddings** | Pre-computed Clay model embeddings of imagery, published on Source Cooperative |
| **NAIP / Requester-Pays** | US aerial imagery on S3. Requester-Pays means our account pays for each read |
| **USPVDB / USWTDB / GRW / OSM** | Public reference datasets of solar sites, wind turbines, renewables and map features, used as answer keys |
| **Trace** | The recorded log of one agent run: every step, tool call, argument, result, error, latency and cost |
| **Tracer** | The component that records traces (e.g. OpenTelemetry → JSONL). Swappable |
| **Trace evaluator** | The component that scores a trace (and the output) against a task reference. Swappable, and can re-score stored traces |
| **Task reference** (formerly "rubric version") | What a synthetic task is scored against: its expected-workflow spec plus its output reference, with a version number |
| **Configuration** | One combination of model + harness + tool set + evaluator under test |
| **Trial** | One run of one configuration on one task. Statistics come from repeated trials |
| **Budget guard** | Optional per-run limits (e.g. steps, tokens, $, time) that stop a run when it hits one |
| **Replay** | Feeding a stored trace back through summarize → score → report with no live model |
| **Treehouse** | The name the product is presented under (D31) |
| **Sentinel-2** | ESA's free global satellite imagery at 10 m. The LGND embeddings are built from it |
| **Vantor open data** | Free high-resolution imagery of disaster events, in `s3://vantor-opendata` (Nepal: `pan_gsd` 0.31–0.77 m over the 33 items, 0.31–0.69 m over the 23 that intersect the AOI) |
| **COG** | Cloud-Optimized GeoTIFF: an image file that can be read a window at a time over HTTP |
| **Answer key / keyed task** | A task whose correct output is known from a reference dataset (USPVDB, GRW, OSM). An *unkeyed* task has none |
| **Trust estimate** | How far an unkeyed run's output can be trusted, inferred from what keyed runs showed (D35). In the MVP it is the headline interval inside the trust passport (D48); whether trust is the report's headline number is still Suhas's call (D45) |
| **Task understanding** | Whether the agent grasped what was asked: the right area, object, answer format, and the limits of the data (D33) |
| **Task card** | The self-contained file that defines a task: AOI, dates, data sources and licences, steps and keying, forbidden sources, `must_notice`, sampling and gold plans, budget (D52) |
| **Tool gateway** | The layer every tool call passes through: allow-list, forbidden-source block, `as_of` date limit, metering of bytes, dollars and time, and span recording (D51) |
| **Verifier** | The second, blind agent that checks a probability sample of claims and (from W10) unreported places, on a different model family by default (D43, D44, D74) |
| **Gold label** | A blind human label on a randomly drawn sampled unit, drawn and committed before any verifier verdict is seen. Here the labeller is the builder, so gold is a "builder-checked human reference", not truth (D56) |
| **PPI** | Prediction-powered inference: the verifier's verdicts corrected by the human-minus-verifier difference on the gold sample, giving an interval that stays valid even if the verifier is wrong (D48) |
| **Trust passport** | The per-run trust record: estimand, headline interval with tier, alternatives (gold-only, B0/B1/B2), controls, gate, estimator version (D48) |
| **Evidence tier** | KEYED (evaluated against a key), GOLD-ANCHORED, CALIBRATED-TRANSFER, MODEL-ESTIMATED (estimated), ABSTAINED (no number). Exact trace numbers are **MEASURED** (D46, D47) |
| **Evaluated / estimated / measured** | Evaluated = scored against an answer key. Estimated = any other accuracy or trust number, always with n and an interval. Measured = read exactly from the sealed trace (cost, time, bytes, process sub-scores) (D46, D47) |
| **SYNTHETIC** | Anything we generated (the synthetic world, synthetic gold, demo points). Labelled everywhere, and never counts as real keyed evidence (D53) |
| **Seal** | Writing a run's trace, cassette, claims and manifest once, hash-chained, before any check sees them (D72) |
| **Cassette** | The recorded model and tool responses of a run, replayed with no live model. Pixel-free |
| **Kiro prompt (K0–K9)** | A ready-to-paste instruction for the Kiro web IDE, which runs the AWS-only steps (D26, D30, D67) |
| **Simulation** | The stretch flood and bridge-failure simulation (D41). Not MVP |
