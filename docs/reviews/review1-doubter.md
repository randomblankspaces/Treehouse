# Review 1 — DOUBTER: does the Treehouse idea (a23dec5) follow the pushed spec (373719c) and Clay's values?

Sources: `373719c:docs/*` (baseline), `a23dec5:docs/SCOPE.md` + FUTURE-WORK diff (idea), `clay-vision-doc.txt` lines 1–10, 47–48 (Clay values). Line numbers are within each file as shown by `git show | cat -n`. "VD" = vision doc.

## 1. Baseline items vs the idea

| Item | Verdict | Note |
|---|---|---|
| S1 model swap | FOLLOWS | D32 restates model hot-swap. Recording "the agent's thinking" depends on the model, so swapping models can change the trace schema (C12) |
| S2 tracer swap | FOLLOWS | D32 "swappable tracer" |
| S3 traces | FOLLOWS | D32 widens the trace to include prompt, context and thinking |
| S4 summary | FOLLOWS | D33(4) "plain summary" |
| S5 errors | FOLLOWS | D32 "every error" |
| S6 trust kept | UNADDRESSED | Nothing says the new trust estimate's calibration (which keyed runs, which version) is kept as provenance (C1) |
| S7 reproducible | FOLLOWS | Not touched. The Vantor license is unchecked (C14) |
| S8 UI | FOLLOWS | Not touched. D34 adds an MCP surface but doesn't replace the UI |
| S9 verifiable stats | CONFLICTS | The trust estimate on unkeyed runs can't be verified against truth by definition, and with the planned run counts it can't be fitted with credible uncertainty (C1, C2) |
| S10 compare | FOLLOWS | Not touched. OQ4 tool sets may now leak answers (C5) |
| S11 budget guard | FOLLOWS | Task prompt adds "$5"; see cost math (C9) |
| S12 output metric | CHANGES-IT | Output becomes "trust" = grade + process (S16), and the damage step has no output reference (C2, C6) |
| S13 Clay ideology | FOLLOWS (mostly) | Public Vantor data; license and provenance gaps (C1, C14) |
| S14–S19 (new) | UNADDRESSED in 01/02/04/05 | All "after review"; no F/SC/J/DoD and no cut line, about 34 h before the deadline (C3) |
| F1 harness + MCP + LGND tool | CONFLICTS (partly) | The task depends on an imagery-window/vision tool that isn't in F1. LGND embeddings end April 2026, before the August 2026 flood (C4, C8) |
| F2 trace capture | FOLLOWS + UNADDRESSED | "Data touched" (D39) is a new metric that F2 doesn't capture |
| F3 summary maps to events | FOLLOWS | — |
| F4 scoring vs task reference | CONFLICTS | The damage step has no reference (SCOPE:167). S18 takes latency and cost out of the scores, but F4 puts them in the workflow score (C7) |
| F5 report + provenance | UNADDRESSED | Trust-model version, task-understanding method and data-touched aren't in the report or manifest list |
| F6 hot-swap | FOLLOWS | — |
| F7 replay / re-score | UNADDRESSED | Replay needs a frozen, versioned trust estimator, and a non-LLM task-understanding scorer, or replay needs Bedrock (C10) |
| F8 UI | FOLLOWS | Unchanged |
| F9 comparison | FOLLOWS | — |
| F10 statistics | CONFLICTS (practical) | One headline task, mostly unkeyed; OQ4/OQ10 task count unclear (C11) |
| F11 budget guard | FOLLOWS | — |
| F12 spec + API | UNADDRESSED | S14 adds a second interface (MCP) that must expose the same parameters; nothing says how |
| SC1 | FOLLOWS | Public Vantor + synthetic prompt |
| SC2 | FOLLOWS | — |
| SC3 workflow + output | CONFLICTS | Output has no reference for the damage step; latency and cost move out of workflow (C2, C7) |
| SC4 report per run | FOLLOWS | — |
| SC5 swappable | FOLLOWS | Thinking-capture caveat (C12) |
| SC6 replay | UNADDRESSED | C10 |
| SC7 provenance | UNADDRESSED | Trust calibration not recorded (C1) |
| SC8 compare | FOLLOWS | — |
| SC9 good-vs-bad separation | CONFLICTS | Can't be shown on the unkeyed step without planted truth (C2) |
| SC10 budget | FOLLOWS | — |
| SC11 every parameter | UNADDRESSED | MCP server parity (S14) |
| SC12 reproducible | FOLLOWS | — |
| J1 live run | CONFLICTS | Step 4 "output metric is checked against the task's output reference": none exists for damage status |
| J2 replay | UNADDRESSED | Deterministic-match check needs a frozen trust model (C10) |
| J3 hot-swap | FOLLOWS (risk) | Step 2 "trace keeps the same schema" vs model-dependent thinking (C12) |
| J4 errors | FOLLOWS | Cloud-cover trap is a good error case; step 3 "wrong output lower" can't be shown for damage without a key |
| J5 compare | FOLLOWS | — |
| J6 stats | CONFLICTS | Step 2 known-good/bad separation is impossible on the unkeyed step unless outputs are planted (C2) |
| J7 budget | FOLLOWS | — |
| J8 fresh machine | FOLLOWS | Committed traces must not include image chips that break the Vantor license (C14) |
| J9 parameters | UNADDRESSED | Doesn't cover the MCP server or task-understanding/trust settings |
| DoD 1 end to end | FOLLOWS (at risk) | The vision tool doesn't exist yet (C8) |
| DoD 2 scoring vs reference | CONFLICTS | C2 |
| DoD 3 errors | FOLLOWS | — |
| DoD 4 hot-swap | FOLLOWS | — |
| DoD 5 replay + re-score | UNADDRESSED | C10 |
| DoD 6 compare | FOLLOWS | — |
| DoD 7 stats | CONFLICTS | C1, C2 |
| DoD 8 budget | FOLLOWS | — |
| DoD 9 params via API | UNADDRESSED | MCP parity |
| DoD 10 fresh machine | FOLLOWS | — |
| DoD 11 public Apache-2.0 + IaC | FOLLOWS | Vantor data license unchecked (C14) |
| DoD 12 committed trace | FOLLOWS | — |
| DoD 13 FUTURE-WORK current | FOLLOWS | Simulation logged. README stretch order not updated (C13) |
| DoD 14 README how-to | UNADDRESSED | Needs MCP server and trust estimate usage |
| D1, D2 | FOLLOWS | — |
| D3 / OQ15 tooling | FOLLOWS (risk) | Tool sets now include map servers that leak the key (C5) |
| D4 LGND tool | CHANGES-IT | D36 reframes Clay as a "vector-search layer"; resolution and date make that weak here (C4) |
| D5, D39 | FOLLOWS | D39 strengthens D5 |
| D6, D7, D8 | FOLLOWS | — |
| D9/D16 process main, output secondary | FOLLOWS in words, CONFLICTS in effect | D33 says output stays secondary, but S16/S17 make the trust headline mix process and output (C6) |
| D10 AWS | FOLLOWS | — |
| D11/D23 UI last | FOLLOWS | — |
| D12 all errors | FOLLOWS | — |
| D13 no ADB inputs | FOLLOWS | Synthetic prompt, but it's written in ADB's voice (C15) |
| D14–D22 | FOLLOWS | — |
| D24 solo, docs only spec | CONFLICTS (practical) | The spec is incomplete for S14–S19 (C3) |
| D25 OQ defaults are decisions; change only by logging | CONFLICTS | OQ10 (5 tasks) and OQ12 (never blended) are effectively revised without a logged decision (C6, C11) |
| D26–D30 | FOLLOWS | — |
| OQ1 expected-workflow spec | FOLLOWS (opportunity) | Its "forbidden tools" field is the natural guard against leaks (C5); damage step lacks an output reference |
| OQ2 stats | UNADDRESSED | No method for the trust estimate's uncertainty (C1) |
| OQ3 evaluator check | UNADDRESSED | No check for the trust estimator itself |
| OQ4 configs and cost | CONFLICTS (budget) | 100 runs × $5 = the whole $500 cap (C9) |
| OQ5, OQ6 | FOLLOWS / UNADDRESSED | Manifest lacks trust-model and imagery-window settings |
| OQ7, OQ8 | FOLLOWS | Cloud and no-imagery cases need a source tag (tool vs data limit) |
| OQ9 services | FOLLOWS | — |
| OQ10 five tasks | CHANGES-IT (unlogged) | One specialization plus solar "test example". Fate of the other 4 tasks unstated (C11) |
| OQ11 one spec schema | UNADDRESSED | MCP server must read the same schema |
| OQ12 deterministic, never blended | CONFLICTS | S16 blends; S15 likely needs an LLM judge (C6, C10) |
| OQ14 | FOLLOWS | D40 partly answers it |
| Out-of-scope list | FOLLOWS | Captions still stretch; simulation logged as stretch. The simulation drifts from "evaluate the agent" (C13) |
| 06 risks | UNADDRESSED | No new risks for the Nepal task: cloud, coverage, OSM completeness, vision cost, leaks, trust-model validity |
| EXTERNAL-DEPENDENCIES | UNADDRESSED | LGND embeddings still tagged "Stretch" (line 34) though the idea depends on them. Vantor license "See registry page" (line 33). No vision/COG tool listed |

## 2. Clay values vs the idea

| Value (VD line) | Verdict | Note |
|---|---|---|
| Exec summary: observe, summarize, score end to end on Clay's real tasks (VD 2–3) | FOLLOWS | ADB-style task, core loop first (D42) |
| Problem: "knowing whether to trust one" (VD 3) | FOLLOWS (strong intent) | D35 aims straight at this, which is the idea's best point. The method is unproven (C1) |
| User: Clay model & data team, no hand-checking every run (VD 6) | FOLLOWS | The trust estimate targets exactly this |
| User: Partners (ADB), "reusable harness that scores an agent against their tasks and rubric" (VD 6) | UNADDRESSED | There's no path for a partner to bring their own task or rubric. The trust estimate is fitted to one task family (C15) |
| User: Agent/harness developers, observable traces + clear scores (VD 6) | FOLLOWS | MCP server helps |
| User: Domain experts, "output scored against a rubric or reference examples" (VD 6) | CONFLICTS | The damage step has neither (C2) |
| Constraint: open and reproducible, Apache-2.0 (VD 7) | FOLLOWS (risk) | Vantor license (C14) |
| Constraint: trust and provenance first-class, keep "the rubric/reference it was judged against" (VD 7) | UNADDRESSED | The trust estimate is a new "reference" that isn't versioned (C1) |
| Constraint: public or synthetic data only (VD 7) | FOLLOWS | Vantor, LGND, OSM are all on Clay's list |
| Constraint: model + tracer behind abstractions (VD 7) | FOLLOWS | — |
| Principle: "Evaluating the agent is the product" (VD 10) | FOLLOWS for MVP; drifts in stretch | The simulation (D41) is a disaster-modeling product, not agent eval (C13) |
| Principle: "Known task + known input + a reference to score against. Every evaluated task needs all three" (VD 10) | CONFLICTS | "Nothing grades the damage step" (C2) |
| Principle: swappable model and tracer (VD 10) | FOLLOWS | — |
| Principle: recorded-trace fallback (VD 10) | FOLLOWS | Unchanged. Needs a frozen trust model (C10) |
| Approach: build an eval sandbox, not a model (VD 47) | FOLLOWS | The trust estimator is a small statistical model, not training. Keep it that size |
| Approach: pick tasks, ADB first (VD 48) | FOLLOWS | — |
| Approach: greenfield, migration-aware (VD 48) | FOLLOWS | — |
| Approach: public/synthetic data, mind NAIP Requester-Pays (VD 48) | FOLLOWS | Vantor is a public bucket. Cost risk moves to vision tokens (C9) |
| Approach: record traces for a flaky agent (VD 48) | FOLLOWS | — |

## 3. Attack

**C1. The trust estimate (S17/D35) has no fitting method, no validation, and not enough data to work within this build.**
- Severity: **critical**
- Evidence:
  - FACT, SCOPE@a23dec5:61: "learn from keyed runs how run context, input and trace relate to output accuracy, and apply it to unkeyed runs".
  - FACT, OQ-QUESTIONS@373719c:10: "with 5 tasks × 5 trials, about 100 runs".
  - FACT, SCOPE@a23dec5:167: "Nothing grades the damage step, which is exactly where the trust estimate (D35) is needed".
  - FACT, S9 (SCOPE:53) needs statistics shown "verifiably and truthfully".
  - INFERENCE: a relationship learned from about 100 runs, mostly on other tasks (solar, bridge inventory), then moved to a different step (damage) with no truth there is an extrapolation nobody can check. That is the exact "can we trust it?" claim S9 forbids making without evidence. The trust model also isn't recorded as provenance (S6/SC7).
- What would fix it: Narrow D35 to a claim the build can test. Validate the trust estimate on held-out keyed runs only (for example inventory step, or planted damage labels), state that its transfer to unkeyed steps is a hypothesis, and version the estimator as part of each run's provenance.

**C2. The headline task breaks Clay's "known task + known input + a reference" principle and the spec's scoring and journey checks.**
- Severity: **critical**
- Evidence:
  - FACT, VD:10: "Known task + known input + a reference to score against. Every evaluated task needs all three".
  - FACT, SCOPE@a23dec5:167: "Nothing grades the damage step".
  - FACT, 01:12 (F4): scores "both against the task's task reference".
  - FACT, 04:14 (J1.4): "The output metric is checked against the task's output reference".
  - FACT, 04:56 (J6.2): good vs bad must be separated "by more than the reported uncertainty".
  - INFERENCE: on the damage step, J1.4, J4.3, J6.2 and DoD 2/7 can't pass.
- What would fix it: Give the damage step a reference, even a small one. Options: hand-label a dozen bridges visible in clear post-flood windows, plant synthetic outputs with known status, or use the cloud trap as a deterministic key (bridges under cloud must be "cannot be assessed"). Keep "trust estimate" as an extra layer on top, not a replacement for the reference.

**C3. Six new requirements have no features, criteria, tests or DoD items, and there's no cut line, about 34 hours from a solo deadline.**
- Severity: **critical**
- Evidence:
  - FACT, SCOPE@a23dec5:58–63: S14–S19 all "after review".
  - FACT, SCOPE@a23dec5:140: "Pending from round 5: the solo scope cut line for the Thursday 10:00 deadline".
  - FACT, SCOPE@373719c:3: "If you find a requirement with no matching item … raise it".
  - FACT, D24: "Solo build".
  - INFERENCE: the baseline already had 11 Must features. The idea adds an MCP server, task-understanding scoring, trust blending, a trust model, a new vision tool and new data plumbing, without saying which are Must.
- What would fix it: Before building, set the cut line. Mark S14–S19 Must/Should/Stretch, give each Must an F/SC/J/DoD row, and send everything else to FUTURE-WORK now.

**C4. Clay embeddings as the "vector-search layer" for bridges doesn't fit this task's resolution or dates.**
- Severity: **major**
- Evidence:
  - FACT, SCOPE@a23dec5:132: "one 256-number vector per 1.28 km cell per month", covering "2017 to April 2026".
  - FACT, SCOPE@a23dec5:137: the floods are August 2026.
  - FACT, SCOPE@a23dec5:134 (D38): "Sentinel-2 is 10 m … not cars or footbridges".
  - FACT, SCOPE@a23dec5:165: "the agent narrows the search with Clay embeddings".
  - INFERENCE: a 1.28 km cell can at best flag "river valley with a road". It can't place a bridge, and it has no post-flood month, so it can't flag change. The task also bans map layers (line 152), so OSM can't stand in. Querying the embeddings needs a regional index from GeoParquet, which is unscoped work. EXTERNAL-DEPENDENCIES:34 still tags the embeddings "Stretch".
- What would fix it: Narrow Clay's role to what it can do here: rank 1.28 km cells along the river corridor as candidates, using pre-flood months. Score whether the agent used it efficiently (data touched, D39). Don't imply it detects bridges or damage. Mark the embeddings MVP in EXTERNAL-DEPENDENCIES.

**C5. Answer-key leakage is unresolved, and the planned tool sets may hand the agent the key.**
- Severity: **major**
- Evidence:
  - FACT, SCOPE@a23dec5:131: "OSM is both a normal map tool and an answer key".
  - FACT, EXTERNAL-DEPS@373719c:26 lists shortlist candidates `openstreetmap-mcp-server` and `Overture Maps MCP`.
  - FACT, OQ4 compares "RODA + 1–2 shortlist servers".
  - FACT, SCOPE@a23dec5:140: "whether answer-key sources are blocked" is pending.
  - INFERENCE: if a shortlist map server is in the tool set, inventory precision/recall measures lookup, not imagery reading. OSM's coverage of rural Nepali suspension footbridges is likely incomplete, so correct finds may be scored as false positives.
- What would fix it: Decide now. Answer-key sources are forbidden tools in the expected-workflow spec (OQ1 already supports this), calling one is logged as an agent error, and the inventory metric is limited to bridge types OSM maps reliably (or reported with that caveat).

**C6. "Output trust = grade + how it got there" (S16) blends process into output, which the accepted OQ12 forbids, and no decision is logged to revise it.**
- Severity: **major**
- Evidence:
  - FACT, OQ@373719c:18 (OQ12): output is "Reported as its own metric next to the workflow scores, never blended into them".
  - FACT, OQ header (line 3): "Change one only by logging a new decision in SCOPE.md".
  - FACT, SCOPE@a23dec5:60: "Output trust combines the output grade with how the agent reached its conclusion".
  - FACT, D33 (line 129) also says "Output stays a secondary metric".
  - INFERENCE: if trust becomes the number ADB reads, output-via-process becomes the headline, which contradicts "secondary".
- What would fix it: Keep the raw output grade as its own number, per OQ12. Present "trust" as a separate derived indicator with its inputs shown, and log a decision that says so explicitly.

**C7. S18 ("speed and cost not blended into other scores") contradicts F4/SC3/J1, which put latency and cost inside the workflow score.**
- Severity: **minor**
- Evidence:
  - FACT, SCOPE@a23dec5:62: "reported separately and not blended into other scores".
  - FACT, 01:12 (F4): workflow score covers "steps, latency, cost".
  - FACT, 02:10 (SC3) says the same, and 04:14 (J1.4) "Workflow scores cover … latency and cost".
- What would fix it: Choose one. Either the workflow score excludes latency, cost and data touched, which become their own panel, or S18 is reworded. Then update F4, SC3 and J1.

**C8. The task needs a tool that doesn't exist in the spec: reading COG windows and showing them to a vision-capable model.**
- Severity: **major**
- Evidence:
  - FACT, SCOPE@a23dec5:135: agents "read a small window around one bridge".
  - FACT, SCOPE@a23dec5:165: "Footbridges are visible only at 0.5 m".
  - FACT, F1 (01:9) lists only "RODA MCP, 1–2 servers from Clay's shortlist, and an LGND embeddings tool".
  - FACT, D40 confirms Bedrock access in general, not which multimodal models.
  - INFERENCE: without an image-chip MCP tool and a vision model, the damage step can't run at all. Model swaps (S1) would also be limited to multimodal models.
- What would fix it: Add an imagery-window tool to F1 as a Must, with its own error cases (no coverage, cloud, out of bounds), and confirm a multimodal Bedrock model ID in the Kiro check.

**C9. The cost math eats the whole sandbox.**
- Severity: **major**
- Evidence:
  - FACT, SCOPE@a23dec5:152: "Keep total cost under $5".
  - FACT, OQ4: "about 100 runs, likely under about $30".
  - FACT, SCOPE@a23dec5:39: "AWS sandbox capped at $500".
  - INFERENCE: 100 runs × up to $5 = $500, the entire cap. Image tokens for many 0.5 m chips make the $5 ceiling a realistic per-run cost, not a far-off one. The OQ4 "$30" estimate was made for text-only tasks.
- What would fix it: Re-estimate per-run cost from one real Nepal run first. Then set N, the task count and the budget-guard default so the full eval fits well under the cap (for example under $150).

**C10. Replay and deterministic scoring aren't designed for the new judgments (task understanding, trust).**
- Severity: **major**
- Evidence:
  - FACT, 01:15 (F7): "Replay with Bedrock access off still produces a report".
  - FACT, 04:25 (J2.3): "Scores from deterministic evaluators match exactly".
  - FACT, D25/OQ12: no LLM judge for output.
  - FACT, SCOPE@a23dec5:201 defines task understanding as "the right area, object, answer format, and the limits of the data".
  - INFERENCE: "limits of the data" is hard to check without an LLM judge. A trust model refitted on new runs changes old scores unless it's frozen.
- What would fix it: Define task understanding as deterministic checks: area inside the AOI, schema valid, all four statuses used correctly, cloud areas listed. Version and freeze the trust estimator per evaluator version.

**C11. The OQ10 task set and OQ4 statistics are quietly replaced by one specialization task.**
- Severity: **major**
- Evidence:
  - FACT, OQ@373719c:16 (OQ10): "5 ADB-style dataset-build tasks at three difficulty levels … and one deliberately ambiguous task".
  - FACT, SCOPE@a23dec5:133: "Solar farms in Virginia are a test example only", with the Nepal task as the specialization.
  - FACT, no decision revises OQ10.
  - INFERENCE: with one main task (two near-unassessable post scenes), F10 and J6 statistics rest on a handful of runs of one task. The deliberately ambiguous error task may be dropped.
- What would fix it: Log what the task set now is (for example the Nepal task split into keyed sub-tasks plus 2–3 cheap keyed tasks for calibration and stats) and keep the error-trigger task.

**C12. "Record the agent's thinking" conflicts with model hot-swap and the fixed trace schema.**
- Severity: **minor**
- Evidence:
  - FACT, SCOPE@a23dec5:128: tracer records "the agent's thinking".
  - FACT, 04:32 (J3.2): "The trace keeps the same schema".
  - INFERENCE: only some Bedrock models and harnesses return reasoning text.
- What would fix it: Make thinking an optional trace field that is recorded when available and marked absent otherwise. Never score it.

**C13. The simulation stretch drifts from "evaluating the agent is the product", and the docs disagree on stretch order.**
- Severity: **minor**
- Evidence:
  - FACT, VD:10: "Evaluating the agent is the product … not a one-off dataset".
  - FACT, FUTURE-WORK diff moves the simulation to #1.
  - FACT, README@373719c:50–54 still lists sensitivity analysis first and has no simulation.
  - INFERENCE: a bridge-failure simulation shown to ADB for reconstruction funding is a domain-modeling claim, with credibility risk if shown half-built.
- What would fix it: Keep it after Clay's own stretch goals (or frame it as "evaluate an agent that runs a simulation"), sync the README order, and leave it out of the demo.

**C14. The Vantor imagery license is unchecked, though the idea now builds on it and may commit derived chips or traces.**
- Severity: **minor**
- Evidence:
  - FACT, EXTERNAL-DEPS@373719c:33: license "See registry page".
  - FACT, DoD:18: committed sample traces.
  - INFERENCE, from memory and unverified: Maxar/Vantor open data has historically been CC BY-NC, which differs from Apache-2.0 code and needs attribution plus non-commercial terms on any committed imagery.
- What would fix it: Check the license, add attribution to the README and reports, and commit only image IDs and windows, not pixels, if the terms require it.

**C15. The partner reusability promise and the framing as ADB's voice are weak.**
- Severity: **minor**
- Evidence:
  - FACT, VD:6: partners need "a reusable harness that scores an agent against their tasks and rubric".
  - FACT, SCOPE@a23dec5:146 opens "ADB is preparing a quick-disbursement disaster response".
  - INFERENCE: nothing lets a partner bring a task or rubric (S14 exposes only scores and reports). An ADB-voiced prompt could be read as a real ADB brief.
- What would fix it: State that a task is just a task-reference file any partner can write, show a second one in the demo, and label the Nepal brief "synthetic, not from ADB" wherever it appears.

**C16. The Kathmandu option has no post-flood imagery, and the post scenes are mostly cloud.**
- Severity: **major**
- Evidence:
  - FACT, SCOPE@a23dec5:161–162: post-flood scenes cover lat 28.14–28.33 and 27.84–28.00 only, at 81% and 74% cloud.
  - FACT, line 159: only the pre-flood 2024 scene "includes Kathmandu".
  - INFERENCE: the Kathmandu valley (about 27.7° N) falls outside both post scenes, so the damage step there would be all "cannot be assessed". Trishuli (about 27.9–28.2° N, 85.1–85.4° E) overlaps both post scenes. With 74–81% cloud, even Trishuli may yield very few assessable bridges, which makes the demo thin and the stats thinner.
- What would fix it: Pick Trishuli now. Count assessable (cloud-free) bridges in the post scenes before committing to this task, and keep a keyed fallback task ready.

**C17. The new MCP server (S14) has no parameter-parity or audience decision, and the hosted-deployment question is still open.**
- Severity: **minor**
- Evidence:
  - FACT, SCOPE@a23dec5:130: "Who calls it … is open".
  - FACT, SC11 (02:19): "Every parameter is exposed through one run/eval spec and API".
  - FACT, SCOPE@a23dec5:121: hosted deployment still pending.
- What would fix it: Make the MCP server a thin read-only wrapper over the same API and schema (scores, reports, traces), or mark it Should/Stretch in the cut line.

## Where the idea is sound

- D35's goal (trust without an answer key) is exactly Clay's stated problem (VD:3). It's the strongest Quality-of-Idea and Impact story.
- The cloud-cover trap, data-touched/COG efficiency (D39), and D38's resolution honesty are good, measurable workflow signals.
- D42 (core loop first) and D41 (simulation as stretch, logged in FUTURE-WORK) follow the scope discipline.
- The baseline swaps, errors, budget, replay, reproducibility and Apache-2.0 are untouched and still hold.

I did not check: data facts in D36 and D39 (taken as stated); bridge coordinates (Kathmandu and Trishuli latitudes are from memory); the Vantor license (from memory, flagged).
