# MVP Success Criteria

> **For agents — what this file is:** MVP success criteria (SC1–SC27). These are the outcomes the build must show. SC1–SC7 come from Clay's vision doc (adjusted for team decisions), SC8–SC12 from the team's scope ([SCOPE.md](SCOPE.md)), and SC13–SC27 from S14–S29 as set by the two designs ([design/](design/)). Each one is proven by a journey test in [04](04-user-journeys-tests.md). Terms are in the [SCOPE glossary](SCOPE.md#glossary).

> Scope: **ADB agentic eval only**. Captions are a stretch after the ADB stretch goals. Index: [README.md](README.md)

- [ ] **SC1.** An LLM harness performs a synthetic ADB-style task by calling geospatial tools over MCP, using public or synthetic data. *(J1)*
- [ ] **SC2.** The agent's activity, **including every error**, is captured as traces and summarized into a human-readable view. *(J1, J4)*
- [ ] **SC3.** Each run is scored on separate panels, never blended (SCOPE D45): *(J1)*
  - **How the agent worked** (Panel 1), from the trace: grounding, evidence sufficiency, tool validity and order, error recovery, loops, abstention, forbidden attempts, budget adherence. MEASURED.
  - **Task understanding** (Panel 2). See SC14.
  - **Output** (Panel 3), against the task's key where one exists (KEYED), with a stated reason and no grade where none exists. We get no ADB inputs (D13); whether Clay sends an ADB rubric is unconfirmed.
  - Latency and cost are **not** part of these panels. They are Panel 5 (SC17).
- [ ] **SC4.** The sandbox produces an evaluation report for every run. *(J1)*
- [ ] **SC5.** The **model, harness, tracer, and trace evaluator** are each swappable behind an abstraction, with no code changes. *(J3)*
- [ ] **SC6.** If the live agent fails, recorded traces replay through scoring and still produce a report. *(J2)*
- [ ] **SC7.** Trust and provenance: every scored run keeps its trace, its inputs, the full context the agent was given (prompt, system prompt, tools and schemas, model, harness, budget settings), the task-card hash it was judged against, and each data source's licence. *(J1)*
- [ ] **SC8.** The sandbox **compares harnesses, agents (models), and tooling** on the same tasks, one factor at a time, labelled exploratory. *(J5)*
- [ ] **SC9.** The evaluation is **statistically verifiable**: repeated trials give statistics with uncertainty, and the evaluator separates good from bad runs by a margin larger than that uncertainty. *(J6)*
- [ ] **SC10.** An **optional budget guard** can be set per run or per eval, and it stops runs that exceed it. *(J7)*
- [ ] **SC11.** **Every parameter** is exposed through one run/eval spec and the CLI, so a UI can be built later without backend changes. The FastAPI service exposing the same spec is Should (W12). *(J9)*
- [ ] **SC12.** **Reproducible beyond its builders:** a teammate on a different machine can set it up and run it from the README. *(J8)*
- [ ] **SC13.** *(S14)* Scores and reports are served by a **read-only MCP server** with exactly 8 tools and one report resource. Every number it returns is a TypedNumber with its tier, and it matches the JSON bundle. *(J10)*
- [ ] **SC14.** *(S15)* **Task understanding** is scored deterministically: the agent's Understanding Statement against the card's `must_notice` items, and its plan against its actions. A good agent scores above a looping one. *(J11)*
- [ ] **SC15.** *(S16)* **Output trust** is a separate, derived number shown beside the process facts it depends on. A claim that fails a hard rule (fabricated or ungrounded evidence, forbidden source) is never trusted, whatever the verifier says. *(J12)*
- [ ] **SC16.** *(S17, S20)* Every unkeyed output gets a **trust passport**: an estimand, a tiered headline interval with n and estimator version, the gold-only interval, the baselines, the controls and a gate. The method tests (M1–M17) pass, and the passport says "not computable: 1 keyed regime" instead of implying cross-regime validation. *(J13)*
- [ ] **SC17.** *(S18)* **Cost, speed and data touched** form their own MEASURED panel (Panel 5) and never appear inside Panels 1–4. *(J14)*
- [ ] **SC18.** *(S19, S27)* The **Nepal flagship** runs from a region-agnostic task card. The cloud trap rewards a correct `cannot_assess`, the India card validates unchanged, and `src/` holds no region constants. *(J15)*
- [ ] **SC19.** *(S21)* The **verifier is blind and sampled**: its input holds no worker label, confidence or reasoning, claims and controls look the same, inclusion probabilities are stored, gold is drawn before any verdict, and the worker and verifier are different model families unless the manifest says "self-verified". The verifier's sensitivity and specificity are measured on keyed controls from a real keyed task (Virginia, K3/K4 after K6) and shown in the passport; until then the passport says "verifier accuracy: synthetic controls only, not evidence" (DD1). *(J12, J13)*
- [ ] **SC20.** *(S22)* **Every number is typed and chipped:** evaluated (KEYED), estimated (the other tiers, with n and interval) or MEASURED. There are no bare floats in the scorecard, passport or bundle, and every digit in the HTML report sits inside a chip. *(J16)*
- [ ] **SC21.** *(S23)* **Forbidden answer-key sources** are blocked for worker and verifier. Each attempt is logged as a `key_access_attempt`, the touched items are excluded from keyed grading, and a canary in the claims marks the run invalid for accuracy. *(J4)*
- [ ] **SC22.** *(S24)* Every number, row and report from synthetic data carries the **SYNTHETIC** label, and synthetic tasks never count as a keyed regime. *(J16)*
- [ ] **SC23.** *(S25)* The agent **discovers scenes from the STAC catalog** and reads **byte-range image windows**, with typed `no_coverage` and `out_of_bounds` errors and the bytes read recorded. *(J1, J15)*
- [ ] **SC24.** *(S26)* **Total spend stays under the $500 cap:** the spend ledger reserves before every model call and refuses above $450, and replay costs $0. *(J17)*
- [ ] **SC25.** *(S28)* **Sealed records are verifiable offline:** `treehouse verify` passes on an untouched store and pinpoints any tampering. *(J2)*
- [ ] **SC26.** *(S29)* **AWS-native, not AWS-locked:** the capability probe classifies every service without aborting, every AWS seam has a local stand-in, and the manifest states which backend actually ran. *(J18)*
- [ ] **SC27.** *(S21; Should, W10; SCOPE D74)* When W10 lands, the verifier also samples **unreported places** from a defined corridor frame, and the passport reports a miss rate with n and an interval. Until then every passport says "unreported places not sampled (W10)". *(J13)*
