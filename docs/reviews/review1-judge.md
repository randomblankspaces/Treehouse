# Review 1: JUDGE ruling on Treehouse (a23dec5) against the pushed spec (373719c) and Clay's values

Basis: doubter, defender and verifier reports. Where the verifier marked a statement WRONG or MISLEADING, I did not rely on it. Suhas's clarifications are treated as authoritative about intent. Because of them, a finding about the Nepal example becomes a requirement on the system wherever the example only exposes a general gap.

Verifier corrections that decide several rulings:
- (a) The SCOPE scene table is incomplete. The event folder holds 33 scenes, 28 of them post-event, and some are 6–24 % cloud.
- (b) There is no cloud mask, only a per-scene `eo:cloud_cover` number. So "bridge under cloud" is **not** a deterministic key.
- (c) The flood is a Rasuwa / Bhote Koshi (upper Trishuli) glacier-collapse event.
- (d) The Vantor license is CC-BY-NC-4.0.
- (e) The defender's "100 runs is a text-task plan" is misleading. OQ4 still governs.

## 1. Rulings

| Claim | Ruling | Final severity | Decisive evidence | Required fix (system level) |
|---|---|---|---|---|
| C1 Trust estimate has no method, validation or provenance | UPHELD | **critical** | SCOPE:61 states only the goal. There is no estimator version anywhere (verifier). The defender's run-count rebuttal is misleading (correction e). The clarifications make the trust estimate the *core* of the system, which raises the stakes | Define how trust is estimated: inputs are process signals and run context, the target is output accuracy on keyed runs. Validate it on held-out keyed runs and report that error. Label every unkeyed use "estimate". Version and freeze the estimator in each run's provenance |
| C2 Headline step lacks "known task + input + reference" | UPHELD | **critical** | VD:10 says "Every evaluated task needs all three", and SCOPE:167 says "Nothing grades the damage step". The defender's downgrade rested on the cloud key, which the verifier ruled WRONG (correction b). Only footprint coverage is deterministic, and only for a fixed scene set | Separate **evaluated** (keyed) runs from **estimated** (unkeyed) runs everywhere in the system, so it never calls an unkeyed output "scored". Every demo path through the flagship example needs at least one real reference: hand-labeled items, planted traces (J6.2), or hindcast labels |
| C3 S14–S19 have no F/SC/J/DoD and there is no cut line, about 34 h out, solo | UPHELD | **critical** | SCOPE:58–63 and :140 show the cut line pending. SCOPE:3 declares the deferral, so it isn't hidden, but it is still undone, and SCOPE:3 omits 05/DoD. Baseline: 11 Must features | Set Must/Should/Stretch for S14–S19 and for every clarification-era addition (verifier agent, hindcasting, multi-provider). Give each Must an F/SC/J/DoD row before design |
| C4 Clay embeddings don't fit 0.5 m bridges or Aug-2026 dates | PARTLY UPHELD | minor | The idea already limits embeddings to narrowing (:165, :132, :134). The "Stretch" tag is a stale baseline row (F1 already makes it Must). Data ends April 2026 (LGND README, verified) | The embeddings tool is coarse candidate ranking only, and it must report its date and resolution coverage so the agent (and the eval) can see when it doesn't apply to a region or time. Mark it MVP in EXTERNAL-DEPENDENCIES |
| C5 Answer-key leakage unresolved | UPHELD | major | SCOPE:131 says OSM is a tool *and* a key. OSM/Overture servers are on the shortlist (EXT-DEPS:26). The decision is pending (:140). The mechanism exists (OQ1 "forbidden tools") but isn't applied | Every task reference declares its answer-key sources as forbidden tools, for the worker agent **and** the verifier agent. A call to one is a logged agent error. Key incompleteness (e.g. rural footbridges in OSM) is reported as a caveat on precision |
| C6 "Output trust" blends process into output against OQ12 | PARTLY UPHELD | major | OQ12's letter forbids blending output *into workflow scores* only (defender, verified). But D33 says "Output stays a secondary metric" (:129), and the clarifications make trust the headline. That change needs a logged decision under the OQ header rule | Log a decision: the raw output grade, the workflow scores and the derived trust estimate are three separate numbers, and trust is shown with its inputs. State plainly whether trust is now the headline (this revises D33/D9) |
| C7 S18 vs F4/SC3/J1.4 on latency and cost | UPHELD | minor | SCOPE:62 vs 01:12, 02:10, 04:14. Both sides agree | Pick one: speed, cost and data touched form their own panel. Update F4, SC3 and J1.4 |
| C8 No imagery-window or vision tool in the spec | UPHELD | major | F1 (01:9) lacks it, and the damage step needs 0.5 m windows (:135, :165). Whether stac-mcp or gis-mcp can do it is UNVERIFIED | Make a generic imagery-window tool (any STAC/COG source, with no-coverage and out-of-bounds errors) a Must. Under the multi-provider requirement, the spec must say model swaps for this task class are limited to multimodal models, and confirm a multimodal Bedrock default |
| C9 Cost eats the $500 sandbox | PARTLY UPHELD | major | The arithmetic is right, but the premise (every run at $5) is an inference (correction f). Existing controls exist (OQ:10, 06:17, budget guard Must). Vision tokens make the $30 estimate stale. Unestablished: real per-run cost. A second verifier agent and hindcast runs would add cost (inference) | Measure one real vision run before sizing anything. Set N, the task count, the verifier-agent sampling and the budget-guard default so the full eval stays under a stated cap |
| C10 Replay and deterministic scoring for task understanding and trust | UPHELD | major | F7, J2.3, D25 and :201 are verified. The defender's deterministic "cannot be assessed for cloud" check is unsupported (no mask). **Raised by the clarifications:** the proposed verifier agent is an LLM judging *output*, which D25 and OQ12 forbid unless a decision is logged | Define task understanding as deterministic checks only (AOI, schema, format, footprint coverage). Freeze and version the trust estimator. Log a decision admitting the verifier agent as a *separately reported, calibrated* signal (never the grade), with its outputs recorded so replay reproduces it without Bedrock |
| C11 OQ10 task set quietly replaced | PARTLY UPHELD | minor | Nothing deletes OQ10, so the defender is right, but no decision logs the tasks' new role (D25 rule). The "build a system, not a demo" clarification makes several tasks *necessary* for calibration and generality | Log that the OQ10 keyed tasks are the calibration and statistics set, Nepal-style tasks are examples running through it, and the ambiguous error task stays |
| C12 "Record thinking" vs hot-swap and schema | PARTLY UPHELD | minor | J3.2 is the tracer swap, not the model swap (verified). The multi-provider requirement makes uneven reasoning output certain across providers | Thinking is an optional trace field, marked absent when the provider doesn't return it, and never scored or used as a trust input unless present for all compared runs |
| C13 Simulation drifts from "evaluating the agent is the product" | PARTLY UPHELD | minor | D41 fences it as stretch (verified). But Suhas's clarification folds "changes we can make on the world" into "the actual system", which pulls against VD:10. README order is out of sync | Keep the simulation as a downstream consumer of the agent-built database, outside the eval product and the demo. Put Clay's stretch goals first. Sync the README |
| C14 Vantor license unchecked | UPHELD | major | Verified CC-BY-NC-4.0. The vision tool sends pixels, so traces may carry pixels (verifier rejects the defender's "IDs, not pixels"). DoD 12 commits sample traces. The repo is Apache-2.0 and must be reproducible elsewhere | Record each data source's license in provenance. Committed traces and reports carry scene IDs and windows, not pixels. Attribution plus non-commercial notice wherever Vantor-derived content appears |
| C15 Partner reusability; prompt in ADB's voice | UPHELD | major (raised from minor) | VD:6 says partners need to score "their tasks and rubric". The clarification ("same flow for India or anywhere") makes generality the core claim, but nothing yet *demonstrates* it. The "synthetic" label (:144) is outside the prompt text | A task is a self-contained file (region, imagery source, prompt, optional reference, forbidden tools), and nothing is hard-coded to Nepal. Prove it by running a second region or task. Put "synthetic, not from ADB" inside the prompt and on reports |
| C16 Kathmandu has no post imagery; post scenes mostly cloud | PARTLY UPHELD (premise corrected) | major (as a data-integrity finding) | 33 scenes, not 5. Clearer post scenes exist (6–24 %). Kathmandu has thin edge coverage. The flood is in Rasuwa / Bhote Koshi (corrections a, c). Both sides' "designed trap" premise came from an incomplete table | Correct the SCOPE data table. The system discovers scenes from the STAC catalog for the task's AOI and dates instead of trusting a hand list. The example AOI should sit in the actual flood zone. Count clear coverage at candidate items before relying on the example |
| C17 MCP server: no parity or audience decision | UPHELD | minor | "Who calls it … is open" (:130), against SC11 (02:19) | Thin read-only wrapper over the same API and schema. Should, not Must, in the cut line |

## 2. Overall verdict

**Is the idea good? Yes.**
- It aims at Clay's stated bottleneck, "knowing whether to trust one" (VD:3), and both sides agree that is its strongest point.
- The clarified framing helps: a general system that evaluates any agent run, with keys used only to learn which process signals predict accuracy. That is more defensible and more reusable (VD:6 partners) than a Nepal demo.
- The data-touched and COG-efficiency signal (D39), D38's resolution honesty, and the core-loop-first discipline (D42) are genuine strengths.
- The baseline guarantees (swaps, replay, budget, Apache-2.0, public data) are untouched.

**Is it properly set up? No, not yet.**
- The central mechanism, the trust estimate, has no method, validation or provenance (C1).
- The flagship step has no reference, and the defender's proposed key (cloud from metadata) doesn't exist (C2).
- Nothing is mapped to F/SC/J/DoD and there is no cut line, about 34 h before a solo deadline (C3).
- The doc's own data table is materially wrong: 5 of 33 scenes, a wrong cloud picture, and the event location not used (C16).
- The new verifier-agent idea collides with D25 and OQ12 unless a decision is logged (C10).

These are setup gaps, not flaws in the core idea, but each blocks system design.

## 3. Must-fix list before system design

1. Write the cut line: S14–S19 plus the verifier agent, hindcasting and multi-provider marked Must/Should/Stretch. Every Must gets an F/SC/J/DoD row.
2. Define the trust estimate: inputs, target, held-out validation on keyed runs, the "estimate" label on unkeyed runs, and a frozen, versioned estimator in provenance.
3. Split "evaluated" (keyed) from "estimated" (unkeyed) in every score and report, and give the flagship example at least one real reference path.
4. Log the decisions owed under the OQ header rule: trust as a third number (OQ12/D33), the verifier agent's status vs the D25 LLM-judge ban, the OQ10 tasks as the calibration set, and S18 vs F4.
5. Correct the SCOPE Nepal data table from the STAC catalog (33 scenes, actual cloud values, Rasuwa / Bhote Koshi location), and make scene discovery a system step, not a hand list.
6. Add a generic imagery-window tool as Must, and state the multimodal-model constraint on swaps for vision tasks.
7. Declare answer-key sources as forbidden tools per task, for both the worker and the verifier agent.
8. Measure one real vision run's cost, then size N, verifier sampling and the budget-guard default under a stated cap.
9. Record data licenses in provenance, and commit IDs and windows only, with Vantor CC-BY-NC attribution.
10. Make tasks region-agnostic files, and plan a second region or task to prove it. Put the "synthetic" label inside the prompt.
11. Minor syncs: thinking is an optional field, the MCP server is a thin read-only Should, the README stretch order is corrected, and the LGND tag is MVP.

## 4. On the assistant's proposed synthesis

The synthesis is the right shape. "Agent makes claims, claims are checked against whatever truth exists, and the record of process signals vs check results becomes the trust estimate" gives C1 a concrete target and turns C2 from a gap into a design category (evaluated vs estimated). It falls short in four places:

1. The verifier agent is an LLM judging output, which D25 and OQ12 forbid. The synthesis is only legitimate with a logged decision, and only if the verifier's own accuracy is measured on keyed tasks. If it uses the same model or provider as the worker, its errors may correlate with the worker's, and that agreement would overstate trust (inference).
2. Hindcasting is not a third source of truth by itself. Post-event imagery is still unlabeled pixels, so grading against it needs either human labels or the verifier agent. It therefore collapses into sources 1 or 2 unless someone labels it. Also, no cloud mask exists (correction b), so even "assessable or not" isn't automatic.
3. It says nothing about how many keyed runs are needed or how the estimator is validated and frozen. That is the actual content of C1.
4. It doesn't touch C3 (cut line), C9 (cost, which a second agent increases) or C14 (license).

Verdict: adopt it as the conceptual frame, but it resolves the critical findings only once its truth sources are each validated and its LLM-judge status is logged.

## 5. Decisions Suhas must make

1. Is the trust estimate now the headline number, replacing D33's "output stays secondary"?
2. Is the verifier agent allowed as a separately reported signal, revising D25's no-LLM-judge-for-output rule, and must it run on a different model or provider from the worker?
3. Which truth sources are in the MVP: keys only, keys plus verifier agent, or also hindcasting?
4. What reference does the flagship example get: hand-labeled items (how many), planted traces, or none (estimate-only, labeled as such)?
5. What is the cut line: which of S14–S19 and the new additions are Must by the Thursday 10:00 deadline?
6. Which AOI is the flagship example: Rasuwa / Bhote Koshi corridor, Trishuli, or another, after checking clear coverage?
7. What is the second region or task that proves "works anywhere" in the demo?
8. What total-eval cost cap ($) should N and the budget guard be sized against?
9. Are answer-key servers (OSM/Overture) excluded from the tool sets entirely, or present but forbidden per task?
10. Is the MCP server Should or Stretch?

Not checked by me: any source line or data fact beyond the three reports. I relied on the verifier's checks. Unestablished: real per-run vision cost, OSM footbridge completeness in Rasuwa, whether stac-mcp or gis-mcp read COG windows, and clear coverage at actual bridge locations.
