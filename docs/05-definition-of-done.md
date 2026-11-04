# MVP Definition of Done

> **For agents — what this file is:** The MVP is done when every box here is ticked. Each item links to the journey test in [04](04-user-journeys-tests.md) that proves it. Use it as the final gate before demo and submission. Items marked *(Must-1)* or *(Should)* may be cut by the cut line (SCOPE D66), from the bottom; if cut, they move to [FUTURE-WORK.md](FUTURE-WORK.md) instead of being ticked. A tier that deviates from one of Suhas's own decisions is listed in [SCOPE: Decisions Suhas must confirm](SCOPE.md#decisions-suhas-must-confirm).

> Scope: **ADB agentic eval only**. Captions are a stretch after the ADB stretch goals. Index: [README.md](README.md)

**Core loop**
- [ ] One task card runs end to end: harness → gateway and MCP tools → trace capture → seal → check → score → trust → report (**J1**).
- [ ] Scoring keeps separate panels: how the agent worked, task understanding, and output (KEYED, or a stated reason when unkeyed), with no default composite (**J1**, **J11**, **J12**).
- [ ] Cost, speed and data touched are their own MEASURED panel and never appear in the other panels (**J14**).
- [ ] Every error (agent, tool, policy, budget, infra) is logged and shown in the summary (**J4**).
- [ ] Model and trace evaluator are hot-swappable through config (**J3** steps 1, 4).
- [ ] *(Should)* The harness (plain loop ↔ Strands, W2) and the tracer (JSONL ↔ CloudWatch/OTLP mirror, W9) swap the same way (**J3** steps 2, 3). The tracer tier deviates from D8.
- [ ] The agent finds scenes with `stac_search` on the pinned fixture and reads windows with `imagery_window`; every error code is typed and bytes read are recorded (**J1**, **J15**).
- [ ] *(Must-1)* The plain summary passes the numbers lint: a planted number or a missing span id is rejected (**J1** step 3).
- [ ] Recorded-trace replay verified, including re-scoring with a swapped evaluator (**J2**, **J3**).
- [ ] Sealed runs verify offline, and tampering is pinpointed (**J2**).

**Trust and checks**
- [ ] The gateway blocks every forbidden answer-key source for worker and verifier, and the planted key-peeker is caught (**J4**).
- [ ] The blind sampled verifier passes the blindness test, and the worker and verifier are different families (or the manifest says "self-verified") (**J12**, **J13**).
- [ ] Every unkeyed run has a trust passport with tier, n, interval, gold-only interval, baselines, controls and gate. Method tests M1–M17 pass, and "not computable: 1 keyed regime" is shown (**J13**).
- [ ] The estimator is frozen in `estimators.lock` before the first live GOLD-ANCHORED run (**J13**).
- [ ] A rule-failed claim is never trusted, whatever the verifier says (**J12**).
- [ ] The verifier's accuracy is measured on a real keyed task, or the passport says it isn't (DD1) (**J13** step 6).
- [ ] *(Must-1)* Blind labelling: exported gold items carry no worker or verifier fields, and labels are sealed before reveal (**J13** step 7).
- [ ] Until W10, every passport says "unreported places not sampled (W10)". *(Should, W10)* Then the verifier samples unreported places and the passport reports a miss rate (**J13** step 8; DEVIATION from DD1, SCOPE D74).

**Labels and honesty**
- [ ] Every number is typed and chipped: evaluated, estimated or measured. No bare floats; every digit in the report sits inside a chip (**J16**).
- [ ] Every synthetic number, row and report is labelled SYNTHETIC, and no synthetic task counts as a keyed regime (**J16**).
- [ ] The Nepal, synthetic, Virginia (`pending_fetch`) and India stub cards validate from the same schema; the cloud trap rewards `cannot_assess`; no region constants in `src/` (**J15**).
- [ ] No Vantor (or any) imagery pixels in the repo, committed traces, reports or demo recording; the licence scan passes; every Vantor-derived report carries the licence floor and the CC-BY-NC notice (licence scan, ID §6).

**Statistics, comparison and budget**
- [ ] *(Should, W8)* Harnesses, agents and tooling are compared on the same tasks, labelled exploratory (**J5**). This tier deviates from D3; Suhas to confirm.
- [ ] Evaluation is statistically verifiable: repeated trials, uncertainty, good-vs-bad separation, and the shuffled-label check against the gold-only interval (**J6**; the A-vs-B test in step 3 is W8, with the comparison).
- [ ] Optional budget guard works when on and is absent when off (**J7**).
- [ ] Total spend stays under $450 by the spend ledger; the ledger file is committed after each Kiro step (**J17**).

**Interfaces and AWS**
- [ ] Every parameter is exposed through the run/eval spec (`treehouse schema`) and the CLI (**J9** step 1).
- [ ] *(Should, W12)* The FastAPI service exposes the same spec (**J9** step 2).
- [ ] *(Must-1, cut first on slip)* The read-only MCP server serves exactly 8 tools with typed numbers (**J10**).
- [ ] The capability probe has run via Kiro (K1), `aws-capabilities.json` is committed, and each manifest states which backend actually ran (**J18**).
- [ ] Versioned S3 run store (SD's Must-0 AWS floor, built W5/K8) and, as *(Must-1)*, Object Lock with default retention, the key-bucket IAM Deny and CDK for what is deployed; or the manifest says which stand-in ran (**J18**).
- [ ] At least one live Bedrock run (K3) is recorded, and its pixel-free cassette replays (K5) (**J1**, **J2**).
- [ ] Every remaining AWS step is a ready-to-paste Kiro prompt in `TODO.md`.

**Repo and submission**
- [ ] A teammate reproduces it on a fresh machine from the README: `uv sync --frozen && uv run treehouse demo` offline (**J8**).
- [ ] Code in a **public, open-source GitHub repo** that Clay can access after the event, with infrastructure as code where it applies. Licensed **Apache-2.0**, as Clay requires (SCOPE D28).
- [ ] At least one recorded trace and its report committed to the repo, so the demo works even after the sandbox is wiped.
- [ ] The demo is recorded from replayed traces before the T-6h freeze (SCOPE D66).
- [ ] [FUTURE-WORK.md](FUTURE-WORK.md) lists every feature cut or deferred during the build.
- [ ] README explains how to run live, replay, swap components, run a comparison, set a budget, read the chips, and write a task card.

Journeys: [04-user-journeys-tests.md](04-user-journeys-tests.md).
