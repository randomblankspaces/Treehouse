# TREEHOUSE DEFENSE BOOK (AWS panel)

Basis: the verified answers supplied to me. I did not re-read the repo docs in this pass, so "repo claim" means taken from the answers and not re-checked. Hour figures marked (est) are estimates, not measurements. Today is Wed Nov 4 and the repo is due Thu Nov 5 10:00 EST, so everything below competes for the same solo hours.

Ratings:
- **EASY**: the answer holds as it stands.
- **PREP**: the answer holds if Suhas rehearses a specific wording.
- **HARD**: the alternative is better or the answer is weak. A switch is named.

## What actually ran (Kiro build, 2026-11-05 UTC). Claims elsewhere in this book are only valid if listed here.
| Claim | Status | Evidence |
|---|---|---|
| Strands agent on Bedrock (Sonnet 5.5; Nova Pro comparison) ran T1 Nagoya, T5 Gifu, T1 Chattogram | **RAN** (17 runs) | `fixtures/live/cassettes/`, `fixtures/live/experiments/` |
| Decision recorded before every action | **RAN**, after a fix (live run 1 showed decisions could not bind to Bedrock-assigned ids) | `fixtures/live/runs/*/t-0.investigation.json` |
| Separate panels: output (grade-lgnd-v1), RV1–RV10, calibration, predicted accuracy, cost | **RAN** on synthetic fixtures. Predicted accuracy has **insufficient validation** | `fixtures/live/experiments/metrics.json` |
| Reviewer model of a different family | **RAN** (Nova Pro, 1 run) | `fixtures/live/review/` |
| AgentCore Evaluations, built-in + code-based Lambda | **RAN** (1 run; 4 built-ins + 2 Lambda) | `fixtures/live/agentcore/` |
| Compliance Object Lock store + denied delete | **RAN** | `fixtures/live/receipts/denied-delete.json`, `infra/cdk-outputs.json` |
| Vision sub-agent on GSI chips | **Designed + tested offline**. No live agent called it | `tests/unit/test_vision_subagent.py` |
| Real AEF / LGND / PLATEAU data | **NOT USED**. Synthetic fixtures (access blocked) | `docs/KIRO-STATUS.md` |
| AgentCore Observability / Transaction Search | Enabled (destination CloudWatchLogs). No AgentCore Runtime hosted, so **roadmap** | `aws-foundation.json` |
| UI for the warehouse runs (task 10) | **NOT BUILT** (skipped) | — |
| Step Functions fan-out, Clay compute on GPU | **Roadmap** | — |

## 0. What actually ran (updated 2026-11-05 by Kiro; every line has a committed artifact)

| Claim | Status | Evidence |
|---|---|---|
| Strands agent on Bedrock (Sonnet 5.5; Nova Pro comparison) ran the warehouse T1 task live | **Ran** (17 runs) | `fixtures/live/cassettes/`, `fixtures/live/runs/`, `fixtures/live/experiments/runs/` |
| Decision recorded before every action, bound before dispatch | **Ran** (binds on exact tool and parameters, contract v2) | `t-0.investigation.json` in each run dir |
| Nagoya / Gifu / Bangladesh scenarios, N=3 each, plus a model comparison | **Ran** | `fixtures/live/experiments/metrics.json` |
| Output grader (report Table 7/11 protocol) | **Ran** on synthetic fixture references only | same metrics JSON |
| RV1–RV10 rules on live runs | **Ran** | `fixtures/live/rules/` |
| Reviewer model of a different family (Nova Pro) | **Ran** (1 run) | `fixtures/live/review/` |
| AgentCore Evaluations (4 built-ins + 2 Lambda code-based evaluators) | **Ran** (1 run) | `fixtures/live/agentcore/` |
| CDK deploy, Compliance Object Lock store, denied delete | **Ran** | `infra/cdk-outputs.json`, `fixtures/live/receipts/` |
| Offline replay of live runs | **Ran** | `tests/journeys/test_live_replay.py`, `scripts/replay_live.py` |
| Real AEF / LGND embeddings, real PLATEAU / OSM references | **Not run**: synthetic fixtures | `docs/KIRO-STATUS.md` (tasks 1–2) |
| Vision sub-agent on GSI chips used by a live agent | **Designed and tested offline**; no live agent called it | task 5 in KIRO-STATUS |
| Classifier comparison probe vs SVM | **Offline only** (fixture embeddings) | metrics JSON `comparisons.classifier` |
| Predicted accuracy from reasoning | **Ran, insufficient validation** (2 configs) | metrics JSON `predicted_accuracy` |
| Clay computed on 160 m chips, Step Functions fan-out, online AgentCore eval, UI for these runs | **Roadmap** | — |

## Three rules for every answer

1. **Claim only what ran.** Label everything else "designed" or "roadmap". AWS judges punish the gap between design and delivery more than a smaller scope.
2. **Concede first, then pivot.** The strongest lines are "that is a unit test, not validation" and "the passport refuses to give a number here".
3. **The lead claim must survive the H10 fallback.** The fallback ships sealed provenance, deterministic rules, and a human random-gold audit with an exact interval. The verifier and PPI are an upgrade, shown only if they narrow the interval.

---

## 1. Switch list (ordered by value/cost)

| # | Switch | Why it is better | Cost | Fits Thu 10:00? |
|---|---|---|---|---|
| 1 | **Claim rewrite, zero code.** Drop "any agent", replacing it with "emits OTel GenAI spans (observe) or calls tools via our gateway (enforce)". Replace "records everything" with "records every decision and hash-pins every input". Reframe "trust engine" as "audit-grade evidence pipeline: a sealed, replayable, Olofsson-compatible stratified audit with an optional narrowing verifier". Say "write-once, tamper-evident", not "sealed", wherever no anchor ran. Remove "independent" from the verifier copy. Call the format "OTel-shaped sealed record". Reword "validation" to "regression test" for planted violations. | Removes the six easiest attacks at no build risk. | 1 h | Yes |
| 2 | **Pre-registered PPI gate.** Headline is the gold-only exact interval unless kappa(verifier, gold) >= 0.6 with n_gold >= 20. In that case the headline is PPI with lambda=1, and the gold-only interval is printed beside it. Always print the width ratio and the "did not narrow" note. | Own simulation: PPI width vs gold-only was 0.75x for a strong verifier and 1.07x for a weak one, and the gate kept coverage at 0.93 to 0.998. Tuned PPI++ is worse at n=20 (arXiv 2411.12665). | 0.5 h (about 15 lines and 1 test) | Yes |
| 3 | **Object Lock to Compliance, 1-day retention, for the submission bucket.** Keep Governance on a separate dev stack. Read back GetObjectRetention into the manifest. Run the denied delete as the admin role on a specific versionId. CDK assertion retention_days <= 2. | Governance can be bypassed by an admin, and the console sends the bypass header by default. Compliance cannot be bypassed even by root. | 1 h | Yes. The lock is irreversible for one day, so test elsewhere first. |
| 4 | **Honest labels on screen.** Chip reads "HUMAN-AUDITED (n=20, 1 labeller)" until kappa exists. Show three plain states (human-checked sample, model-checked only, not trusted/abstained). Remove the embedding-distance percentile (show the raw number labelled "context, not used in interval"). Reconcile the pan_gsd range (0.43-0.71 vs 0.31-0.77 m) in SYSTEM-DESIGN lines 106 and 232. | Removes the "decoration" and "n=1 annotator" attacks. | about 1 h | Yes |
| 5 | **Second labeller on the same 20 items, Cohen's kappa.** Optionally label 5-10 keyed Virginia items blind. | Converts unmeasured reference error into a measured number. | 0.5 h of another person's time | Yes, if a person is available |
| 6 | **README front page.** One problem, one screenshot, one number, one AWS diagram. Add a claims-vs-evidence table linked to tests, a future-work file (LORO, Dawid-Skene, conformal, capture-recapture, hindcast), and a credential-free `make demo` (replay, verify the chain, print the passport). | Closes the "design vs delivery" gap. | 1-2 h (est) | Yes |
| 7 | **Re-order the AWS spine first.** Probe, then one real Bedrock run sealed to the Object-Lock bucket with a visible denied delete. Then one AgentCore evaluate call, with CloudTrail and console screenshots committed to the repo. Cut "Could" rows from the pitch until they run. | Three load-bearing services shown beat twelve conditional ones. | Scheduling only (the items are already planned) | Yes, but it must come first |
| 8 | **Promote AgentCore Evaluations from side column to pipeline stage.** Write its verdicts on the sampled items into the PPI input as a second proxy. Demo one table: rule check vs AgentCore judge vs human gold on the 20 gold items. | AgentCore means are not design-based estimates. We add the sampling frame and random gold, and it becomes load-bearing instead of a checkbox. | 1-2 h on top of T3 (est) | Yes, conditional on the probe |
| 9 | **Demo order: live then replay.** One live Strands-on-Bedrock trial on a tiny AOI, then export the cassette and replay it into a fresh store with equal heads. Add LIVE/REPLAY chips and a calls_live/calls_total footer from the manifest. Keep a pre-recorded fallback. | The AWS criterion needs a live call, and replay proves the record is sufficient. | about 4 h (the answer says half a day) | Yes, if a live Strands run exists at H10 |
| 10 | **No-tool baseline** on the Virginia task. Report "score above no-tool baseline" and flag memory exposure. | The only memorisation control that fits the budget, and it produces a number. | < 1 h (est) | Yes |
| 11 | **Validation slide: coverage and width over seeded resamples** on a keyed task. Compare gold-only floor, PPI, gated headline and B2. Label it SYNTHETIC or "Virginia, 1 regime". Grey the beat-baseline panel to a footnote. Reuse the M1 harness and explain its 0.86 coverage bar. | Replaces a rule that cannot run with a runnable claim. | 1-2 h | Yes |
| 12 | **Rule false-positive and real-catch rates** from existing traces, plus a short red-team pass-through number. | Answers "100% on self-planted is circular". | < 1 h (est) | Yes |
| 13 | **Templated plain-language summary** with a test that every number and chip in the text equals the JSON. Hosted static report as the first screen. Drop MCP from the pitch. | An LLM summary can round "not computable" into "looks good". | 1 h + 1-2 h | Yes |
| 14 | **Add Guardrails** on verifier input/output and **one AWS Budgets alarm**. | Cheap, visible, relevant to security and cost. | 30-60 min each (est) | Yes, if time remains |
| 15 | **Verifier default = one tool-free structured Converse call.** Keep the agent form only where it must fetch windows. Run a 30-image bake-off over 3-4 Bedrock vision models against the first gold labels. | Lower variance, cheaper, and replayable. The bake-off is itself an artifact. | about 2-3 h (est; no figure was given) | Yes, if gold labels exist by then |
| 16 | **CloudTrail data events with log-file validation** (turn it on early, because digests are hourly). Then **KMS Sign of the manifest hash** by a separate sealer role. Add an `anchor` field to the manifest. | A chain stored beside its data proves only internal consistency. | CloudTrail about 1 h (est), KMS Sign about half a day | Partly. Do CloudTrail first and mark KMS Sign roadmap. |
| 17 | **Swap custom retry for botocore adaptive retries** plus an event hook for per-attempt span events. | Less code, and keeps trace completeness. | about 1 h (est) | Only if the custom loop is not already merged and tested |
| 18 | **Task Card pass/fail gates plus a dominance table.** Demote the validity strip to descriptive, then run the process-vs-correctness scatter on Virginia. Replace the 3-bin plot with Brier plus a warning. | Answers "how do I pick A vs B" without a composite. | 1-2 h each (est) | Optional |
| 19 | **Live worker = native Strands Agent + BedrockModel + native OTel.** The gateway becomes tools/hooks and the plain loop becomes a test double only. | A heavily wrapped Strands is hard to defend as a Strands choice. | 2-3 h plus a hook-based cassette recorder (est) | **Risky.** Only if W2 is not merged. Otherwise use the honest label "Strands: offline-tested only". |
| 20 | **Before/after slide** with precision and coverage of the full table vs the certified subset. Cut the act layer to one sentence. | Measured impact needs no consumer. | "a few hours" (est) | If Nepal has real gold labels |
| 21 | **Move large-workload routing to a "roadmap" page.** Optionally run one fan-out path and publish numbers. | One measured crossover beats five unmeasured rules. | 0 h to move, about 1 h to measure | Move: yes. Measure: optional. |
| 22 | OTLP/JSON export plus a Strands-vs-converted fidelity test | Measures the converter's lossiness. | about 1 day | **No.** Roadmap. |
| 23 | Foreign-framework agent through the observe path | Earns the word "any". | 2-3 h (est) | **No.** Only after Must-0 and the AWS spine. |
| 24 | Second keyed regime, so LORO becomes computable | The single best generalisation fix. | Out of scope in 34 h | **No** |

**Priority if hours are scarce:** do 1-7 first (about 6 to 7 h in total, mostly copy and config). Do 8-12 next. Treat 19, 22, 23 and 24 as "do not start".

---

## 2. Top 15 questions AWS judges will ask

**1. Why not two labelers auditing 300 random rows with a Clopper-Pearson interval?**
*30-second answer:* A stratified random audit is the core of Treehouse, and the random gold subsample is an Olofsson-style design-based audit (cited from memory, unverified). If Clay has the labeller budget for 300 rows, take it: about ±0.045 at p=0.8, and Treehouse shows exactly that. We add what a bare audit lacks: a sampling frame frozen before anyone sees output, proof the key never leaked, 100% deterministic-rule coverage, attribution to one replayable run, and cheap re-audits. Also, Ground Truth and A2I closed to new customers on 2026-07-30.
*Why this beats a bare audit:* Treehouse contains that audit and adds sealed provenance, leak control and full-coverage rules. A one-off audit cannot say which agent configuration made the rows.

**2. What decision can Clay make from a ±0.2 interval?**
*30-second answer:* "Ship this subset, call it verified, or buy more labels." At n_gold=20 the passport says not to publish a precision claim yet, and it states the n needed for ±0.1 (about 60 at p=0.8) or ±0.05 (about 250). The name overpromises, so we lead with what is demonstrated and treat the passport as "measured, estimated, or refused".
*Why this beats a pure score:* Evaluators that always emit a score invite overconfidence. We refuse to give a number we cannot back.

**3. AgentCore Evaluations already exists. What does Treehouse add?**
*30-second answer:* AgentCore scores traces, tool calls and sessions, and batch mode returns per-evaluator means. A mean is not a design-based estimate, because there is no sampling frame, no inclusion probabilities and no random human subsample. AgentCore is what we score traces with. Its verdicts on the sampled items feed our estimator as a proxy, corrected by random human gold.
*Why this beats AgentCore alone:* A bad judge only widens our interval, because validity comes from the random gold.

**4. Pick one case where certification changed a decision.**
*30-second answer:* The act layer is a boundary, not impact evidence. The measured delta is precision of the full agent table vs the certified subset, against held-out human labels, at stated coverage. I will claim a changed decision only if the Nepal run really contains rule-failed claims the raw table would have shipped. Otherwise I say "no change on this run".
*Why this beats a consumer story:* A before/after precision and coverage number needs no consumer. A dollar figure for flood response would be invented.

**5. Which real third-party agent have you run? Is "any agent" defensible?**
*30-second answer:* None yet, so I dropped "any". The claim is agents that emit OTel GenAI spans (observe) or call tools through our gateway (enforce). Only the gateway can guarantee key isolation and metering, because you cannot retroactively stop an agent from reading a key.
*Why this beats OTel-only:* OTel-only can observe but not enforce.

**6. Is your Virginia score memorisation?**
*30-second answer:* Gateway masking stops tool leakage only. The control for parametric memory is a no-tool baseline: same prompts, no imagery tool. Any score above it is tool-grounded work, and a high no-tool score is reported as memory exposure.
*Why this beats claiming isolation:* A held-out post-cutoff key would be better but we have one event. The no-tool baseline is the only memory test that fits the budget.

**7. Can you show the key isolation in CloudTrail?**
*30-second answer:* The manifest states IAM-enforced vs local convention. We add a policy-simulator test and a CloudTrail data-event showing AccessDenied for the worker role (S3 data events must be enabled). In-account Deny is a policy, not a boundary against an admin. Cross-account is the production recommendation.
*Why this beats an unexercised claim:* A guarantee never exercised is the weakest AWS-security story. We show one real denial or say "local convention".

**8. Why a different-family LLM agent as verifier?**
*30-second answer:* The verifier is only a variance-reduction device. Under random gold, validity never depends on it. It is spent only if it narrows the interval on the 20 gold items, else we fall back to human-only (the H10 rule). I would make the default one tool-free structured Converse call. Different family is a correlation hedge, not independence, and whether Nova Pro reads 0.5 m imagery is untested (unverified), so models are picked by a bake-off.
*Why this beats an ensemble or a custom detector:* A custom change detector needs training data we do not have. Ensembles add cost for unmeasured gain at n=20.

**9. With 20 gold labels, does PPI help at all?**
*30-second answer:* It depends on the verifier, and at n=20 it can hurt. In my own simulation (60-claim frame, 20 random labels, 90% intervals, 400 runs, not re-run by the checker) a strong verifier gave 0.75x the gold-only width and a weak one 1.07x. So gold-only exact is always the floor, and PPI becomes the headline only if kappa against human labels is at least 0.6, fixed before we look.
*Why this beats tuned PPI++:* PPI++ estimates lambda from the same 20 labels, and arXiv 2411.12665 reports it can do worse than classical inference with scarce labels. A one-line pre-registered gate is simpler and easier to defend.

**10. The gold is one tired builder. Why call it GOLD-ANCHORED?**
*30-second answer:* It is our weakest point. Anchoring on the verifier is blocked mechanically: the seed is committed before any verifier output, the labeller never sees the verdict, and the tier downgrades if the order is violated. That does not stop one person's mistakes. So the chip reads "human-audited, n=20, 1 labeller" until a second labeller gives Cohen's kappa.
*Why this beats Ground Truth/A2I:* At 20 items the setup costs more than the labelling, and those services are closed to new customers.

**11. Why is "confirmable by a blind human" the target when it is not ground truth?**
*30-second answer:* The product says so: "an estimate against a human reference, not against truth". Nepal has no field-verified source by Thursday, and Clay's day-to-day question is what can be acted on without redoing the work. Unassessable items count as unconfirmed, giving a lower bound, with the upper bound printed. Confirmed / refuted / could-not-assess counts sit beside it.
*Why this beats reporting precision with a separate cannot-assess rate:* Dropping those units is non-random missingness, so a claim would look correct because nobody could check it.

**12. How do you know your trace is not edited, and why a custom chain?**
*30-second answer:* The adversary is after-the-fact editing once the key or labels are visible. The chain gives order, completeness across trial files, and offline verification of a downloaded bundle. A chain whose head is only in the same bucket proves nothing against someone with write access, so the seal step adds a KMS Sign by a separate sealer role and CloudTrail data events with log-file validation. Model calls are reconciled against Bedrock's invocation log. We say "tamper-evident", not "tamper-proof".
*Why this beats Object Lock + checksums + CloudTrail alone:* Each covers one gap. None proves ordering inside a file, that N files belong to one run, or that a copied bundle is intact. The chain reduces a run to one 32-byte head that is cheap to anchor. QLDB reached end of support on 31 Jul 2025.

**13. Object Lock Governance mode can be bypassed by an admin. Is your seal real?**
*30-second answer:* Correct, so the submission bucket uses Compliance mode with 1-day retention. No principal can delete or shorten it, root included. The denied-delete demo runs as the admin role against a specific versionId, because a simple DELETE only adds a delete marker.
*Why this beats Governance:* It removes the objection that whoever deployed the stack can undo the seal.

**14. Why a custom trace format when Strands already emits OTel?**
*30-second answer:* The canonical record already is OTel GenAI-shaped, with our fields under treehouse.*. We own the write path for three reasons. The record must be lossless and deterministic: batch exporters can drop spans, and random ids would break golden heads. It must work with no AWS. And the key events happen at our gateway and wrapper, not inside Strands. We rename it "OTel-shaped sealed record".
*Why this beats primary Strands OTel:* One path would be simpler, but the same wrapper feeds the cassette recorder, budget meter and chain writer. The verifier and scorers are not Strands. The fidelity test (diffing AgentCore results on both) is roadmap.

**15. Which Strands harness produced the spans a judge sees, and what is live on AWS?**
*30-second answer:* The Must-0 demo engine is a plain loop, with Strands wired in through TreehouseStrandsModel. That is the weakest AWS-facing choice. If the Strands path is not merged, the manifest and demo say "Strands: offline-tested only". The demo runs one live Bedrock trial, then replay, with an S3 console tab on the real bucket and cdk deploy output committed to the repo.
*Why this beats a fully live or fully replayed demo:* Fully live is risky on a new-account quota, and fully replayed proves nothing about AWS.

---

## 3. Per-area tables

### Area A: The idea, impact and AWS architecture

| Decision | Rating | Judge question | Answer | Alternative | Why ours is better (or switch to) |
|---|---|---|---|---|---|
| Separate trust layer vs plain human audit | PREP | What does the wrapper add over a random 300-row audit? | The audit is inside our design. We add frozen frame, key-leak proof, full-coverage rules, run attribution, cheap re-audits. | Ground Truth / A2I / staff audit | The alternative is a subset of ours. Switch #1: reframe the pitch. |
| Passport headline with ±0.15-0.2 intervals and "not computable" | PREP | What decision comes from ±0.2? Is the headline an overclaim? | Ship, call verified, or buy labels, with n needed shown. Wording rename needed. | A raw table with no number | Refusing a number we cannot back is the differentiator. Switch #1, #2. |
| AgentCore Evaluations as a side column | **HARD** | Why is it not a stage? | A mean score is not a design-based estimate. Concede under-weighting. | AgentCore alone | **Switch #8**: promote it as a PPI proxy (1-2 h). |
| Act layer as a Could stub | **HARD** | How does certification change an outcome? | It does not yet. Show before/after precision and coverage instead. | Consumer-side story | **Switch #20**: one sentence plus a slide. |
| "Any geospatial agent" | PREP | Which foreign agent ran? | None. Observe (OTel in) vs enforce (gateway). | OTel-only | Switch #1: drop "any". Foreign agent is **Switch #23** (not before Thu). |
| Three live tasks plus replay, synthetic flagged | PREP | Does it generalise? Is synthetic-on-synthetic circular? | No generalisation claim. Synthetic is a unit test and never a result slide. | A platform claim | Narrow real results. If Virginia is blocked, show Nepal only. |
| Six chips and a typed passport | PREP | Would an engineer prefer one line? Has anyone outside the team looked? | One line first, three visible states, templated summary. No outside review exists. | One bare line | Typed data underneath keeps labels from being stripped. **Switch #4, #13.** |
| Deterministic rules with planted violations | PREP | 100% on planted is circular. | A regression test, not validation. Rules catch malformed or forbidden claims, not plausible wrong ones. | Guardrails grounding, AgentCore judges | Rules first, judges second, humans as truth. **Switch #12.** |
| Key isolation, masking, canaries | PREP | Memory? CloudTrail denial? Cross-account? | No-tool baseline. State IAM vs convention. Cross-account is the production step. | Held-out post-cutoff key | **Switch #10.** |
| Blind different-family Strands verifier | PREP | Why an agent verifier, why a different family? | A variance-reduction device only. Prefer one tool-free Converse call. Bake-off picks the model. | Ensemble, custom detector, more labels | **Switch #15.** |
| Stratified sampling plus unreported-places frame | PREP | Is 0 in 10 omission usable? | The two-sided 95% upper bound is about 0.31, which is not decision-grade. Show "recall unknown, needs N draws". | Capture-recapture (Could) | Honest "unknown" beats a fake estimate. |
| No composite, K=3, Holm | PREP | How do I pick A vs B? What survives Holm? | Nothing is significant at K=3. Banner says so. Add gates and a dominance view. | A weighted composite | **Switch #18.** |
| Process panels and calibration plot | **HARD** (conceded) | Is predictive value tested? Is a 3-bin plot on under 50 items meaningful? | Descriptive only. Brier plus warning. Print the cluster count. | Fewer panels | **Switch #18.** |
| Strands via TreehouseStrandsModel, plain-loop demo engine | **HARD** (conceded) | Which harness made the spans? Why a wrapper? | The Strands story is weak if the plain loop made the traces. Reason was cassettes and fixed tool order. | Native Strands + BedrockModel + OTel | **Switch #19** (2-3 h, risky) or the honest label. |
| Custom retry, concurrency 2, smoke test | PREP | Why reimplement retry? | It makes every throttle a span event. botocore adaptive retries plus an event hook does the same with less code. | botocore modes | **Switch #17.** The model table is **Switch #15.** |
| AWS floor: Converse plus versioned S3, rest probe-gated | **HARD** | Is the floor enough? Why was the spine tested last? | Re-order so the spine comes first. | AgentCore Runtime + Observability + Evaluations | **Switch #7.** Object Lock is the AWS-native guarantee we cannot get locally. |
| CDK for the run store, Lambda evaluator and registration | EASY | Do the constructs exist? What about the evaluator lock? | The stable L2 Evaluator and OnlineEvaluationConfig exist in aws-cdk-lib/aws-bedrockagentcore (Python binding unconfirmed). Ship the online config DISABLED. Add a teardown note. | L1 Cfn | Use stable L2, L1 as fallback. |
| Large-workload routing | **HARD** (conceded) | Which path ran? Why DuckDB not Athena? | None ran, so it is "designed, not measured". Bedrock batch needs at least 100 records (mostly verified) and has no tool calling. | One measured path | **Switch #21.** DuckDB stays (same SQL runs on Athena later, and quota is the bottleneck). |
| Cuts: Guardrails, Budgets, A2I | PREP | Why cut them? | A2I and Ground Truth are closed to new customers, so the custom labelling tool stays. Guardrails and Budgets are cheap to restore. | Managed services | **Switch #14.** |
| Solo scope (13 appendices, 30 decisions) | PREP | Too much design? What exists at H10? | The H10 fallback is the project. Unbuilt methods go to future work. | A smaller design | **Switch #6.** |
| Demo script mapped to criteria | EASY | Which minutes are live? What if Bedrock throttles? | One live call, a recorded run, console tab, and a replay that needs no credentials. | Fully live or fully replayed | **Switch #9** improves it. |

### Area B: Trust estimation for unkeyed data

| Decision | Rating | Judge question | Answer | Alternative | Why ours is better (or switch to) |
|---|---|---|---|---|---|
| One PPI family, lambda=1 at n_gold<50 | **HARD** | At n=20 is PPI narrower than gold-only? Why not PPI++? | Depends on the verifier and can hurt. Gate on kappa >= 0.6. | Tuned PPI++ / gold-only / active sampling | **Switch #2.** Gold-only loses 16-25% width when the verifier is good. PPI++ is unstable at scarce n. Active sampling conflicts with the commit-the-seed-first rule. |
| Verifier on top of random gold | PREP | Why a verifier at all? Break-even? | Value is per-claim trust states, controls and triage. The width benefit exists only when the gate passes. At N=60 it saves about nothing unless kappa is above roughly 0.6. | More human labels, non-LLM second source | Do not claim the verifier already drives stratification (strata are class, confidence tercile, cloud class). Add a break-even line to the passport. |
| verified_precision lower bound with an upper-bound variant | PREP | Does it measure the builder's eyes? | Yes, and the chip says so. Counts of confirmed, refuted and could-not-assess go beside it. | Separate cannot_assess rate | Dropping cannot-assess rows is non-random missingness. Optional 5-10 bridge independent check (30-45 min). |
| Builder-only random gold, retest n=5 | **HARD** | Anchoring? Inter-annotator agreement? | Seed committed before verifier output, blind labelling, tier downgrade on violation. Fix with a second labeller. | Ground Truth / A2I private workforce | **Switch #4, #5.** |
| Baselines B0/B1/B2, "not computable" rule | **HARD** (conceded) | Which single number shows the engine beats a naive estimate? | Replace with coverage and width over 400 seeded resamples. Gold-only coverage comes from random sampling, not an error model. | Beat-the-baseline needing 3+ regimes | **Switch #11.** M1's 0.86 coverage bar needs an explanation. |
| Six tier chips | PREP | Too much vocabulary? | The tier gates what the system may say. Plain labels already exist in chip(). Show three states on screen. | Three states only | Typed data plus a three-word surface. **Switch #4.** |
| Shift in two spaces (Clay embedding, acquisition) | **HARD** (conceded) | What does a percentile of one region mean? | Undefined, so remove it. Keep acquisition covariates. Embedding is "context only". | Drop it entirely | Keeps the explicit Clay link without a fake percentile. **Switch #4.** |

### Area C: Tracing, provenance and replay

| Decision | Rating | Judge question | Answer | Alternative | Why ours is better (or switch to) |
|---|---|---|---|---|---|
| Hash-chained JSONL plus manifest, anchors Could/Should | PREP | Who is the adversary? Why not Object Lock + CloudTrail? | After-the-fact editing. The chain adds order, completeness and offline verification. Anchors move into the seal step. | Object Lock + S3 checksums + CloudTrail + KMS head | Each managed piece covers one gap. The chain is what makes all of them cheap to anchor. **Switch #16.** |
| Object Lock Governance with a denied-delete demo | **HARD** (conceded) | Does the demo show the lock or only an IAM Deny? Why not Compliance? | Use Compliance, 1-day retention, run as admin, specific versionId. | Governance with Deny | **Switch #3.** Governance is for dev. |
| Own sealed OTel-shaped record plus converter | PREP | Why not make Strands OTel the primary record? | Lossless, deterministic, works with no AWS, and the key events are at our gateway. It is OTel-shaped. | ADOT/Strands OTel primary | The fidelity test is roadmap (**Switch #22**). Rename in **Switch #1.** |
| Cassette replay, demo re-runs real loop and gateway | PREP | Is replay "canned"? How much touches real Bedrock? | Replay is for re-scoring and provenance, not reproducibility. Start with one live trial. | VCR test or demo video | Replay re-executes our real code and catches tool divergence. **Switch #9.** |
| Pixels by decoded-array hash, no bytes stored | PREP | Is "records everything the agent saw" true? Where is data governance? | No. Narrow to "every decision, every input hash-pinned". Immutable licensed pixels would block a takedown. | Store pixels | Re-fetch under your own licence and compare the hash. Public-domain NAIP crops may be stored. Add the governance table (about 2 h, est). |

---

## 4. How Treehouse beats the alternatives

Comparisons of the alternatives are general knowledge unless marked. The answers I was given do not verify LangSmith, Phoenix, Braintrust, Inspect or Bedrock model-evaluation features in detail, so I flag those cells.

| Alternative | What it does well (stated plainly) | Where Treehouse is better | Where the alternative is better |
|---|---|---|---|
| **LangSmith / Phoenix / Braintrust / Inspect** (general knowledge, not verified in this review) | Mature trace UIs, datasets and experiment tracking. Langfuse and Phoenix ingest OTel GenAI spans (verified for Phoenix and Langfuse in the answers). | A sealed, write-once, chain-verified record with the key withheld. A random human subsample with an interval and tier, and an abstain rule. Geospatial specifics: imagery pixel hashes, bbox containment, AOI checks. Offline verification with no AWS. | Far more polished UI, richer integrations and a broader community. Our trace is OTel-shaped, so we can export to them. Inspect is stronger for general eval-suite structure (unverified here). |
| **Bedrock model evaluations** (not covered in the verified answers; treat as unchecked) | AWS-native and managed. Compares models on datasets and metrics. | We evaluate an agent's dataset output on unkeyed tasks. We provide a design-based interval and a provenance record. | Managed service with no code to maintain. Better if the question is "which foundation model", not "can we trust this dataset". |
| **AgentCore Evaluations alone** (verified) | Scores traces, tool calls and sessions. Batch mode returns per-evaluator averages. Supports ground-truth evaluation (on-demand and batch only, not online). Accepts OTel spans from Strands and LangGraph. | Dataset-level estimate: a sampling frame, inclusion probabilities, a random human subsample, an interval and a tier. A sealed record the harness cannot flatter. Key isolation. We use AgentCore as a proxy inside the estimator. | Managed, supported and in nine regions including us-east-1. Better for per-session scoring of live production agents. A Lambda evaluator is limited to 6 MB per session and a 300 s timeout, so heavy scoring is easier on our side. Where a key exists, its ground-truth evaluation is a legitimate comparison. |
| **Classical remote-sensing accuracy assessment (Olofsson-style)** | The gold standard for design-based sampling. Established, accepted and well understood. | We contain it: the random gold subsample is that audit. We add a sealed, replayable agent run, leak control, full-coverage deterministic rules and an optional verifier that narrows the interval. | If you have field-verified reference data and labeller budget, the classical audit is the more rigorous measure of truth. Our reference is a blind human reading the same pixels, so it is not ground truth. At n=20 our interval is wide (±0.15-0.2), and 300 labels would give about ±0.045. |

**One sentence for the panel:** Treehouse is not a replacement for any of these. It is the layer that turns an agent's output and a few random human labels into a dataset-level number that comes with its evidence and its refusal rule.

---

*Not checked: I did not re-read SYSTEM-DESIGN.md, IMPLEMENTATION-DESIGN.md or T3.brief.md in this pass, and the hour estimates marked (est) are mine. The PPI simulation figures are the builder's own, not re-run. Treat the Strands rework (#19) and the OTLP fidelity test (#22) as the two switches most likely to cost more than shown.*