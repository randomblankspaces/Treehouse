# Team Scope — Clay agent-eval sandbox ("Treehouse")

> **For agents — what this file is:** The team's own scope: the problem, constraints, and solution requirements in the team's words, plus a decisions log from the scope interview and design talk (D1–D42). It is the **source of team intent**. Files 01–06 turn it into features, criteria, tests and risks, merged with Clay's vision doc. Every S-requirement below maps to items in 01/02/04/05, except S14–S19 (added in round 5), which get their 01/02/04 items after the scope review. If you find a requirement with no matching item, or this file disagrees with a numbered file, raise it with the team and don't silently pick one. The build-time design questions in [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) are now **decided** (D25). Text marked *(interpretation)* is the assistant's reading and hasn't been confirmed by the team. Terms are defined in the [Glossary](#glossary) at the end.

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
| Amazon Bedrock | The agent's model runs on Bedrock. Access is confirmed in the Workshop Studio account: everything in the AWS event guide is included (D40) | Team |
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
| S14 | **Scores and reports are also served as an MCP server**, not only the API (D34) | after review | after review | after review |
| S15 | A **task-understanding score**: did the agent understand what was asked (D33) | after review | after review | after review |
| S16 | **Output trust** combines the output grade with **how the agent reached its conclusion** (D33) | after review | after review | after review |
| S17 | **Trust without an answer key:** learn from keyed runs how run context, input and trace relate to output accuracy, and apply it to unkeyed runs (D35) | after review | after review | after review |
| S18 | **Speed and cost are first-class metrics**, reported separately and not blended into other scores (D33, D39) | after review | after review | after review |
| S19 | The **specialization task** is the synthetic ADB Nepal-flood bridge task. Solar farms are a test example only (D37) | after review | after review | after review |

## Decisions log (scope interview, 2026-11-03)

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
| D7 | Agent framework: Strands Agents behind our own interface. The team's answer was "yes, AWS integration is a judging score" *(read as a yes to Strands)* |
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

**Open from round 3:** the team said "we have it working". What exactly works is still to be confirmed (OQ14).

### Round 4

| # | Decision |
|---|---|
| D23 | **Partners (e.g. ADB) use the product through a UI.** The UI is essential, and it's built **last**, after the backend works |
| D24 | **Solo build.** Suhas builds alone. `docs/` (this file plus the MVP files) is the only spec. The SRS, the per-member plans, and all of `dev-docs/` were removed from the fork (see D29) |
| D25 | **All defaults in [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) are accepted as decisions.** For OQ12, output is scored by deterministic checks against an answer key, with no LLM judge. OQ13 (team roles) doesn't apply to a solo build. OQ14 is still open |
| D26 | **Workflow:** code is written and tested locally, then pushed to a branch on the fork. Kiro (a web IDE inside the AWS Workshop Studio account) pulls the branch, runs only the steps that need AWS (Bedrock calls, deploys, live runs), and reports back |
| D27 | **Work happens on the fork** [randomblankspaces/team-43-renaissance-philanthropy-clay](https://github.com/randomblankspaces/team-43-renaissance-philanthropy-clay). Each milestone goes on its own branch with a PR into the fork's `main`. The team repo (`VishalPatil18/…`) is `upstream`. **Nothing is pushed or PR'd to upstream**, and everything is built and tested in the fork |
| D28 | **License switched to Apache-2.0** in the fork, as Clay requires |
| D29 | `dev-docs/` (design decisions, architecture, UI style guide) was **scrapped**. Its conflicts with this spec far exceeded the team's limit of 15 (references to the deleted SRS, five-person workstreams, MIT, team release dates). The UI style guide was copied from a banking site and used proprietary fonts. The architecture will be redone from scratch. The teammates' agent skills (`.agents/`, `skills-lock.json`) were also removed |
| D30 | **AWS is reached only through the browser** (Workshop Studio + Kiro web IDE). There are no AWS credentials on the dev Mac. Every AWS step is a prompt for Kiro, which reports back (extends D26) |

**Pending from round 4:** whether the API and UI get a hosted AWS deployment with login for partners (to discuss next).

### Round 5 (design talk, 2026-11-03 evening)

| # | Decision |
|---|---|
| D31 | **Name:** the repo and docs stay "Clay agent-eval sandbox". When we present, the product is called **Treehouse** |
| D32 | **Product flow:** a partner sends a task to the harness. The model uses Clay and AWS tools. A swappable tracer records the prompt, the context, the agent's thinking, every tool call and every error. The output is graded for what it missed or overshot. Treehouse returns scores and a report. Model and tracer stay hot-swappable (D2) |
| D33 | **What gets judged:** (1) how the agent worked, which is the main judgment; (2) whether its output can be trusted, from the output grade *and* how it reached its conclusion; (3) whether it understood the task; (4) a plain summary of what the agent did, for the user. Output stays a secondary metric (D16). Cost and speed are "key, easy parts of agent evals", kept as separate numbers |
| D34 | **Scores and reports are both exposed as an MCP server**, alongside the API. *Who calls it (Clay's agents, Claude Desktop, Kiro) is open: decide in the design interview* |
| D35 | **What the answer keys are for:** they exist for testing. In real ADB use nobody knows where the bridges are, but when the AI builds a dataset from satellite data, ADB needs to know whether to trust it. So on keyed tasks we look for the relationship between the run's context, input and trace and the accuracy of its output, and use it to draw conclusions where there is no answer key. *(Assistant's reading: the agent must not be able to reach the answer key during a test run. Confirm in the design interview, since OSM is both a normal map tool and an answer key)* |
| D36 | **What Clay is.** *Fact-checked 2026-11-03:* the Clay model is an open foundation model that turns an image tile into a vector. LGND embeddings are Clay v1.5 run over the whole globe's Sentinel-2 archive (2017 to April 2026, about 15.2 billion vectors from about 2.2 PB of imagery), with **one 256-number vector per 1.28 km cell per month**. They are GeoParquet on source.coop, public, CC BY 4.0. LGND Geo MCP is LGND's commercial agent tool built on Clay; Clay's doc says teams get whitelisted, but our access and what it can find are unconfirmed (ask Clay). *Suhas:* Clay works as a **vector database** that narrows the search, after which the agent checks the images more closely. The vector database isn't the whole picture |
| D37 | **Solar farms in Virginia are a test example only.** The **specialization** is an ADB-style task: the August 2026 Nepal floods, building a bridge inventory and each bridge's post-flood status (see [Synthetic ADB task](#synthetic-adb-task-specialization)). The region is the **Kathmandu valley or the Trishuli river corridor**, to be decided later. The target is bridges in rural ADB areas |
| D38 | **The resolution limit is real.** Sentinel-2 is 10 m, so it shows solar farms and large bridges but not cars or footbridges. Outside the US, the only high-res imagery in Clay's data list is Vantor's disaster-event imagery (0.4–0.6 m in the Nepal scenes). *(Recommended: an agent that says what the data can't show earns task-understanding credit; confirm in the design interview)* |
| D39 | **Speed and cost are first-class**, because the agent goes through huge amounts of data. *Fact-checked:* the Vantor GeoTIFFs are Cloud-Optimized GeoTIFFs (they accept byte-range reads), so an agent can read a small window around one bridge instead of a 1–1.6 GB file. How much data an agent touches is part of how it worked |
| D40 | **Bedrock access is confirmed:** the Workshop Studio account includes everything in the AWS event guide (Suhas, 23:11). *This likely answers OQ14 for the account; the Kiro environment check still records the exact model IDs* |
| D41 | **Flood and bridge-failure simulation is a Treehouse feature, but STRETCH / FUTURE only, not MVP.** When built: (a) the simulation is **visible** to the user, and every input number is shown so the user can recreate and test it; (b) it uses flood records, soil data, pre- and post-flood imagery, and bridge type, size and condition; (c) it starts **only when the user selects a location in the dataset and clicks the action** to simulate; (d) it is **realistic, including bridge failure, but not overly so**; (e) it combines AWS, Clay and AI, pulling from as many valid databases as possible to reach a reasonably certain conclusion for ADB; (f) **a person verifies** each simulation, because it can contain errors and is token-heavy; (g) after the bare-bones version, it is checked against the August 2026 flood. Logged in [FUTURE-WORK.md](FUTURE-WORK.md) |
| D42 | **Build the current scope first:** the core loop on the specialization task. The simulation waits until that works |

**Pending from round 5:** the solo scope cut line for the Thursday 10:00 deadline; LGND Geo MCP access and capability (ask Clay); who calls the MCP server; whether answer-key sources are blocked from the agent; Kathmandu vs. Trishuli.

## Synthetic ADB task (specialization)

Written by the assistant as a synthetic ADB prompt (D13, D19, D37). The data facts were checked on 2026-11-03.

> **Task: rapid bridge damage assessment, Nepal floods (August 2026).** ADB is preparing a quick-disbursement disaster response for Nepal after the August 2026 floods. Before committing reconstruction funds, we need a dataset of river-crossing bridges in the flood-affected area and their condition after the event. Using only public satellite data and Clay's tools:
> 1. Build an inventory of every bridge crossing the main river and its tributaries in the area, road bridges and suspension footbridges.
> 2. For each bridge, assess its post-flood status: **intact, damaged, destroyed, or cannot be assessed**.
> 3. Return a GeoJSON file of points with: bridge ID, coordinates, bridge type, river crossed, status, confidence (0–1), the image ID and date used as evidence for both before and after, and a one-line reason.
> 4. List any areas you could not assess and why (for example cloud cover, no post-event imagery, or resolution too coarse).
>
> Do not use existing bridge databases or map layers as your source: we need to know what the imagery shows. Keep total cost under $5.

**Data behind it** (`s3://vantor-opendata/events/Nepal-Flooding-Aug-2026/`, public):

| Scene | Date | Ground resolution | Cloud | Area (lon / lat) |
|---|---|---|---|---|
| 10300100C86CED00 | 2021-10-16 (pre) | 0.57 m | 22 % | 85.13–85.39 / 27.93–29.04 |
| 10300100FCB83600 | 2024-05-29 (pre) | 0.58 m | 15 % | 85.14–85.35 / 26.92–28.06 (includes Kathmandu) |
| 10500100364E8400 | 2023-09-17 (pre) | 0.43 m | 46 % | 84.36–85.82 / 28.11–28.26 |
| B030001100CF1110 | 2026-08-28 (post) | 0.55 m | 81 % | 85.28–85.47 / 28.14–28.33 |
| B030001100CF1210 | 2026-08-28 (post) | 0.49 m | 74 % | 85.05–85.23 / 27.84–28.00 |

**Why it tests an agent well:**
- **Coarse to fine:** the agent narrows the search with Clay embeddings, then reads small windows of the 0.5 m imagery. Footbridges are visible only at 0.5 m.
- **A trap:** the post-flood scenes are 74–81 % cloud. A good agent marks those bridges "cannot be assessed"; a bad one guesses.
- **Half keyed:** OSM bridges can grade the inventory step. Nothing grades the damage step, which is exactly where the trust estimate (D35) is needed.

## Works under

Scope: **ADB agentic eval only**, specialized on the Nepal flood bridge task (D37). The simulation is a stretch (D41). Captions are a stretch, attempted after the ADB stretch goals. All MVP files apply: [01](01-features-in-scope.md) · [02](02-success-criteria.md) · [03](03-out-of-scope.md) · [04](04-user-journeys-tests.md) · [05](05-definition-of-done.md) · [06](06-risks-and-dependencies.md) · [EXTERNAL-DEPENDENCIES](EXTERNAL-DEPENDENCIES.md).

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
| **Vantor open data** | Free high-resolution (about 0.3–0.6 m) imagery of disaster events, in `s3://vantor-opendata` |
| **COG** | Cloud-Optimized GeoTIFF: an image file that can be read a window at a time over HTTP |
| **Answer key / keyed task** | A task whose correct output is known from a reference dataset (USPVDB, GRW, OSM). An *unkeyed* task has none |
| **Trust estimate** | How far an unkeyed run's output can be trusted, inferred from what keyed runs showed (D35) |
| **Task understanding** | Whether the agent grasped what was asked: the right area, object, answer format, and the limits of the data (D33) |
| **Simulation** | The stretch flood and bridge-failure simulation (D41). Not MVP |
