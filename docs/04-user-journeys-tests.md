# MVP User Journeys as Tests

> **For agents — what this file is:** Acceptance tests written as user journeys (J1–J18). Each step has a check, and a journey passes only if every check passes. Each journey proves the success criteria in [02](02-success-criteria.md) noted beside it, and names the build package that makes it testable (ID §6 "Journeys" table, [design/IMPLEMENTATION-DESIGN.md](design/IMPLEMENTATION-DESIGN.md)). Journeys live in `tests/journeys/`. Most run offline on the synthetic demo world; "live" steps run on AWS through Kiro. J16–J18 are spec-sheet additions; their packages are inferred from ID §7, not from the §6 table. Terms are in the [SCOPE glossary](SCOPE.md#glossary).

> Scope: **ADB agentic eval only**. Captions are a stretch after the ADB stretch goals. Index: [README.md](README.md)

### J1. Evaluate one live run (SC1–SC4, SC7, SC23) — offline twin: P5, P7; live: K3

| Step | Action | Verify (test) |
|---|---|---|
| 1 | Developer picks a task card and a configuration (model, harness, tool set, evaluator, optional budget) | The run manifest records the task id and card hash, prompt, system prompt, tool list with schemas, model id as returned and its settings, harness, tracer, evaluator, budget settings, the backends that actually ran, and the licence floor |
| 2 | Harness runs on Bedrock and calls MCP tools through the gateway | Trace has ≥1 MCP tool call, including `stac_search` and `imagery_window`. Every call has a name, arguments, result or error, latency, cost and bytes read. Claims come only from `record_claim`, and each cites a tool result from this run. The run ends with a final output |
| 3 | Sandbox summarizes the trace | Summary lists the steps in order and points out the failures, retries or dead ends in the trace. Every claim maps to a trace event. A planted number or missing span id in the summary is rejected by the lint (ID I7; W0) |
| 4 | Evaluator scores the run | Panel 1 (how it worked) and Panel 2 (understanding) are MEASURED from the trace. Panel 3 (output) is KEYED against the task's key, or shows a `no_grade_reason`. Each number has its evidence. **Latency and cost are not in these panels**: they are Panel 5 (J14, SCOPE D63) |
| 5 | Sandbox emits a report | Report opens with a verdict line, the plain summary and the trust passport, then the five chipped panels, the claim table, per-run and per-step latency and cost in Panel 5, the full context from step 1, the licence floor, and a path to the raw trace. No image bytes |

### J2. Replay a recorded trace (SC6, SC25) — P2, P5

> Not the same as the source's "Journey 2" (sensitivity analysis), which is a stretch goal listed in [FUTURE-WORK.md](FUTURE-WORK.md).

| Step | Action | Verify (test) |
|---|---|---|
| 1 | Turn off live model access (sockets blocked by the offline guard) | No Bedrock call is made, confirmed by the guard |
| 2 | Point the sandbox at a stored run from J1 (or a demo cassette) | The cassette re-runs through the loop, gateway and in-process MCP servers, seals into a fresh store, and a report is produced |
| 3 | Compare with the live report | Scores from deterministic evaluators match exactly. The verifier's recorded verdicts reproduce the passport byte for byte |
| 4 | Run `treehouse verify` on the store, then tamper with one trace line (flip, delete, reorder or truncate) | Untouched store: exit 0. Tampered store: exit 1, naming the file and sequence number |

### J3. Hot-swap every component (SC5) — model and evaluator: P7; tracer: W9; harness: W2

| Step | Action | Verify (test) |
|---|---|---|
| 1 | Change the **model** id in config | J1 passes with no code change. The report records the new model. A non-vision model is rejected for a vision task |
| 2 | *(Should, W9)* Change the **tracer** backend (local JSONL → CloudWatch/OTLP mirror) | J1 passes with no code change. The trace keeps the same schema, and span counts and token totals reconcile |
| 3 | *(Should, W2)* Change the **harness** (plain Converse loop ↔ Strands) | J1 passes with no code change. The report records the new harness. The same script gives identical request hashes and claim tables under both |
| 4 | Change the **trace evaluator** and re-score stored traces | New scores appear for old runs without re-running the agent, appended as a new versioned record. The report records the evaluator version |

### J4. Errors are caught and logged (SC2, SC21) — P4, P7

| Step | Action | Verify (test) |
|---|---|---|
| 1 | Make a tool call fail (bad args, no coverage, out of bounds) | The trace records a tool-side error. The summary mentions it. Panel 1 is lower than in a clean run |
| 2 | Trigger model-side errors (the `looper` policy: repeated calls, bad args, a nonexistent tool, giving up) | Each one is logged as an error in the trace and shows up in the summary |
| 3 | Feed deliberately wrong output into scoring (the corruption series: 0, 10, 20, 40 % of correct claims flipped) | The KEYED output metric falls by exactly the flipped fraction |
| 4 | Run the `key-peeker` policy (calls `key_lookup` and a `keys/` path, then claims crossings plus a canary) | Both calls are blocked with `key_access_attempt` spans and never raise. Items without imagery evidence are `probable_leak`. The canary marks the run `INVALID_FOR_ACCURACY` |
| 5 | Run the `fabricator` policy (cites unfetched results and windows that only overlap the point) | Rule R4 flags 10 fabrications and 10 ungrounded claims |

### J5. Compare configurations (SC8) — W8 *(Should; deviation from D3, SCOPE D68)*

| Step | Action | Verify (test) |
|---|---|---|
| 1 | Define a baseline plus at least one variant that differs in one factor: model, harness, tool set (with/without `clay_search`) or verifier family | Both configurations run on the same tasks, seeds and pinned data |
| 2 | Run the comparison eval | A comparison report shows paired differences side by side for each metric, with CIs, labelled exploratory, saying which configuration is better and by how much, or "inconclusive at N=k" |

### J6. Statistical verification (SC9) — P7 (step 2), P8 (step 4), W8 (steps 1, 3)

| Step | Action | Verify (test) |
|---|---|---|
| 1 | Run N trials per configuration (fixed two-stage plan set in the spec) | The report shows aggregate statistics with uncertainty for each configuration, plus the minimum detectable difference at actual N |
| 2 | Evaluate a known-good and a known-bad agent (the `good` and `fabricator` policies) | Their KEYED CIs separate, so the eval can tell them apart |
| 3 | A-vs-B comparison | Permutation test with Holm correction and a paired bootstrap CI. The report says whether the difference is statistically meaningful, or "inconclusive at N=k" |
| 4 | Shuffle the verifier's verdicts (method test M4) | Coverage stays ≥ 0.86 and the mean width is ≥ 0.95 × the **gold-only classical interval**. The reference is the gold-only interval, not B2 (SCOPE D50) |

### J7. Budget guard (SC10) — P3, P4, P5

| Step | Action | Verify (test) |
|---|---|---|
| 1 | Run with the guard on and a tight limit (the `budget-stop` policy, 12 tool calls) | The run stops with `stop="budget"`. The trace logs a budget-stop error naming the limit hit |
| 2 | Run the same task with the guard off | No limit is applied, and the run completes normally |

### J8. Reproducible on another machine (SC12) — P5

| Step | Action | Verify (test) |
|---|---|---|
| 1 | A teammate who didn't build it clones the repo on a fresh machine and follows the README | `uv sync --frozen` works from the lock file with no one else's help |
| 2 | They run `uv run treehouse demo` with no AWS credentials and no network | Reports are produced in under 60 s, and the store verifies (CI runs this on a clean clone) |

### J9. Every parameter exposed (SC11) — P1 (schema); W12 (API)

| Step | Action | Verify (test) |
|---|---|---|
| 1 | Read the run/eval spec schema (`treehouse schema`, later the API) | Every option used in J1–J7 (model, harness, tracer, evaluator, tool set, task, trials, budget limits) appears in the schema |
| 2 | *(Should, W12)* Launch a run using only the API | The run completes. No option needs a code edit |

### J10. Results over MCP (SC13) — W7 *(Must-1, cut first on slip)*

| Step | Action | Verify (test) |
|---|---|---|
| 1 | Connect an MCP client to the Treehouse MCP server (stdio, or in-process `Client`) and list its tools | Exactly 8 tools: `list_runs`, `get_scorecard`, `get_trust_passport`, `explain_trust`, `get_plain_summary`, `get_claim`, `compare_configs`, `get_trace_span`, plus the resource `treehouse://runs/{id}/report`. No write tools |
| 2 | Call `get_scorecard` and `get_trust_passport` for a demo run | Every number is a TypedNumber with its tier and chip, and the values equal the run's JSON bundle |

### J11. Task understanding (SC14) — P7

| Step | Action | Verify (test) |
|---|---|---|
| 1 | Run the `good` and `looper` policies on `synth-crossings-v1` | Each trial's first step is a recorded Understanding Statement |
| 2 | Score Panel 2 | `must_notice` coverage and plan–action consistency are MEASURED and deterministic. `good` (which names the cloud and resolution limits) scores above `looper` |

### J12. Output trust combines grade and process (SC15, SC19) — P8

| Step | Action | Verify (test) |
|---|---|---|
| 1 | Take a claim that fails a hard rule (for example R4, fabricated evidence) while the verifier answered "yes" | The check ledger resolves it by the rule (rule fail beats human, key and verifier), and the gate is Do not rely |
| 2 | Open the trust passport | The process facts (grounding rate and others) appear beside the interval as their own typed numbers. The scorecard has no composite field |

### J13. Trust without an answer key (SC16, SC19, SC27) — P8; W3 (step 7); W10 (step 8)

| Step | Action | Verify (test) |
|---|---|---|
| 1 | Run the method tests (M1–M17) | All pass: PPI coverage ≥ 0.86 in every scenario, mutations caught, planted errors monotone, blindness holds, gold drawn from all sampled units including verifier abstentions |
| 2 | Build the Nepal passport without gold, then with gold | Without gold: MODEL-ESTIMATED with the wide B2 interval. With gold: GOLD-ANCHORED, with the gold-only interval and width ratio beside it, and "the verifier did not narrow the interval at n_gold=k" when it didn't |
| 3 | Read the beat-baseline field | It says "not computable: 1 keyed regime" |
| 4 | Load gold labels committed after the verifier's verdicts | The tier drops, with the reason `gold-not-precommitted` |
| 5 | Run `synth/good` as if unkeyed | The passport is followed by a KEYED truth reveal, chipped SYNTHETIC |
| 6 | Read the controls block on a synthetic run, then on a live keyed run | Synthetic: "verifier accuracy: synthetic controls only, not evidence". Live keyed (Virginia, after K6): sensitivity and specificity with n and an interval (DD1) |
| 7 | Export the gold sample, then import labels (F26) | No worker label, confidence or verifier verdict in the export; imported labels are sealed with the blind-protocol hash before any verdict is revealed |
| 8 | *(Should, W10)* Build a passport with the unreported-places frame | Before W10: the passport says "unreported places not sampled (W10)". After W10: a miss-rate estimand over the corridor frame with n and an interval (SC27, SCOPE D74) |

### J14. Speed and cost are first-class (SC17) — P7

| Step | Action | Verify (test) |
|---|---|---|
| 1 | Open Panel 5 for any run | Dollars per role, tokens (cache and image), calls, windows, bytes read and recorded model latency p50/p95 are MEASURED. Replayed values say "recorded". The verifier's cost is shown as "the price of trust". An unpriced model shows "unpriced", not a number |
| 2 | Run the blend test | No Panel 5 value appears in Panels 1–4. Cost per correct item appears only when Panel 3 is KEYED |

### J15. The specialization task, anywhere (SC18, SC23) — P4, P5, P7

| Step | Action | Verify (test) |
|---|---|---|
| 1 | `stac_search` the Nepal AOI on the pinned fixture | Returns the golden list of the 23 AOI scenes (2 pre, 21 post) from the 33-scene catalog, with phase, cloud and `pan_gsd` |
| 2 | Score the cloud trap | `synth/good` gets `cannot_assess` correct on 4/4 hidden crossings; `nepal-good` (picks E5610, abstains on obscured windows) scores above `nepal-guesser` |
| 3 | `treehouse task validate` all four cards | All pass; the India card validates unchanged |
| 4 | Scan `src/` | No lat/lon literals or place names |

### J16. Every number is labelled, and synthetic is synthetic (SC20, SC22) — P1, P5

| Step | Action | Verify (test) |
|---|---|---|
| 1 | Walk every field of the scorecard, passport and bundle | No bare float anywhere. KEYED numbers carry a key version and n; GOLD-ANCHORED carry n_gold, abstention rate and interval; MEASURED sit only in the process, understanding, cost and controls panels |
| 2 | Render the demo reports | Every digit-bearing text node (ids and dates aside) sits inside an element with `data-tier` |
| 3 | Check synthetic labels | Every TypedNumber in the demo has `synthetic=True`. Every Nepal claim and evidence row shows SYNTHETIC. The banner reads "SYNTHETIC DEMO DATA"; gold reads "SYNTHETIC GOLD, not human labels"; Nepal rows read "illustrative, not surveyed bridges" |

### J17. Spend stays under the cap (SC24) — P6

| Step | Action | Verify (test) |
|---|---|---|
| 1 | Property-test the spend ledger | Spend plus reservations never pass $450; above $350 needs a flag and a logged reason; above $250 warns; replay costs $0 |
| 2 | Call a model whose price is null | The call is refused, unless it is a probe call under the $0.25 per-call cap |
| 3 | Run the probe under Stubber | No Converse call happens without a reservation, and the probe stops at its $3 cap with the rest reported as `skipped_budget` |

### J18. AWS-native, not AWS-locked (SC26) — P6; live: K1, K8

| Step | Action | Verify (test) |
|---|---|---|
| 1 | Run the capability probe under Stubber, then live via Kiro (K1) | Every service is classified ok, denied, unavailable or error, and the probe never aborts. Output matches the `aws-capabilities/v1` schema |
| 2 | Run the demo with `backends: local`, then (K8) push to the versioned S3 store | Both produce reports. The manifest's `backends_resolved` states which backend ran, from read-backs, never from config. Key isolation reads "local convention" unless the IAM canary denial was observed |
