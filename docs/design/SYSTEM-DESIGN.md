# Treehouse: consensus system design (revision 2)

Status: merged from five revised proposals (statistician, remote-sensing, agent-eval, aws-architect, beneficiary-judge), then revised to resolve round-1 blocking objections. Every choice was picked on the strength of its reasoning and evidence. Vote counts were not used.

Conventions:
- **UNVERIFIED** marks things the builder must probe in hour 0.
- Dollar and hour figures are planning arithmetic, not measurements.
- Tier names, used consistently:
  - **KEYED**: scored against an answer key.
  - **GOLD-ANCHORED**: prediction-powered inference (PPI) against a random human subsample.
  - **CALIBRATED-TRANSFER**: verifier error rates measured elsewhere and transferred.
  - **MODEL-ESTIMATED**: a trace and covariate model only.
  - **ABSTAINED**: no number is issued.

## Five commitments

1. **Everything downstream is a pure function of sealed records.** Replay never calls a live model.
2. **Typed numbers.** Every number carries `type`, `tier`, `n`, interval, `estimator_version` and `manifest_ref` as data fields. The label survives the API, MCP and CSV.
3. **One estimator family with evidence tiers.** Data availability changes the amount and kind of gold. It never changes the method.
4. **The trust engine must beat a baseline or it is not the headline.** "No better than baseline (n regimes)" and "not computable: k regimes" are accepted, displayed outcomes.
5. **AWS-native, not AWS-locked.** Every seam has a local stand-in. An hour-0 probe decides which one runs.

## What the MVP claims about trust (stated up front)

The shipped trust claim is **the PPI estimate with its tier chip, plus the abstain rule**, validated by planted-error and placebo tests. With one keyed regime (Virginia solar) and one unkeyed regime (Nepal), leave-one-regime-out validation is **not computable** in the MVP. The UI shows "not computable: 1 keyed regime; passport defaults to the wide B2 interval for MODEL-ESTIMATED numbers". The demo never implies the engine has been validated across regimes. The honest answer to "how do you know the trust number is right?" is: for GOLD-ANCHORED numbers, validity comes from the random human subsample and does not depend on the verifier; for everything else, the number is labelled a model estimate and is wide.

---

## A1. System boundary and end-to-end flow

**Two layers, one file-shaped contract.**

- **Eval core (the product).**
  - Input: a Task Card. Output: a sealed run record, separate score panels, a Trust Passport, a plain summary and a report.
  - It never mutates the world.
  - Scorers are pure functions of (task hash, trace hash, key version, verifier outputs, sampling seed, estimator version).
  - LLM calls happen only in the worker, the verifier and the summarizer. All are recorded.
- **Act layer (consumer, Could).**
  - Separate package, one-way dependency on the core. Reads only the **Certified Dataset**: claims plus per-claim `trust_state`, `tier`, `p_correct` with interval, `run_id`, a dataset-level Trust Passport and manifest hashes.
  - It cannot start a run or change a score. Items below the card's gate go to "verify first", never "act". ADB can replace it.

**Flow.**

1. Partner submits a Task Card. `treehouse validate` lints it: schema, AOI, licenses, non-empty forbidden list for keyed steps; rejects a card that declares nothing about key sources.
2. Preflight: pin versions (harness, tools, price table, scorer, estimator, snapshot ids and ETags); compute the shift descriptor (A7); estimate cost; check the vision-capability flag; apply the budget guard.
3. The planner expands task x config x K trials.
4. The worker emits a structured Understanding Statement, then runs. All tools pass through the **Tool Gateway**: allow-list, forbidden-source block, metering of bytes, dollars and time, span emission, backoff and a concurrency cap. Claims are emitted only through `record_claim`.
5. Spans stream to hash-chained JSONL, **one file per trial** (A4). An optional OTLP exporter copies them.
6. **Seal and freeze, before any key, verifier or human sees the output.** Trace, cassette, claim table and manifest are written once to immutable storage.
7. Checks run cheap to expensive (A5). Each writes a new, versioned evaluation record.
8. Scorers emit separate panels (A6). The trust engine emits the passport (A7).
9. Report and plain summary are served through CLI, MCP and a static report.
10. Optional: the act layer consumes the Certified Dataset.

**Why this shape.** It matches Clay's "provenance and trust first-class" value; re-scoring with a better verifier is free; freeze-before-check is one PutObject and makes delayed keys and hindcasting honest; it mirrors Inspect's log/score separation and tau-bench's end-state grading; it maps onto Suhas's "the system evals the agent, then changes we can make on the world".

---

## A2. Task format

**Task Card.** YAML plus JSON Schema, semver, content-hashed. Runs reference `id@hash`. A region enters only through the AOI, data URIs and keys. No region constants live in code. The README ships one fixed card template with a worked example so a partner can write a card in minutes.

Fields:
- `id`, `version`, `hash`.
- `family`: the unit across which trust may transfer. Engine abstains across families.
- `goal`: verbatim, including the "synthetic task, not from the partner" notice.
- `aoi` (GeoJSON), `time_window`, `as_of` (tools refuse newer data; cheapest leak control and hindcast hook).
- `data_allowlist`: SPDX license per source, pinned snapshot ids (STAC item ids, object ETags, OSM snapshot date).
- `tools_allowed`, `needs_vision`.
- `output_schema`: claim row with id, geometry, class, `status` in {present, absent, damaged, intact, cannot_assess}, confidence, `evidence_refs`, reason. `cannot_assess` is first-class and gradable; for keyed precision it is excluded from the denominator and reported as coverage loss.
- `known_limits` / `must_notice`: machine-checkable understanding items (10 m imagery cannot show footbridges; cloud limits; Clay embeddings end Apr 2026).
- `keying`, **per step**: `{step, key_source, version_hash, license, reference_quality, completeness_caveat, key_coverage_mask, match_rule}`. `match_rule` holds tolerance radius per class and one-to-one assignment.
- `forbidden_sources`: hosts, dataset ids, tag queries, key bucket. Applies to worker and verifier.
- `sampling_plan`: strata, frame definition for unreported places, seed.
- `gold_plan` (optional): number, rubric, labeller, date, **blind-labelling protocol** (A5).
- `thresholds` (act gate), `budget`.

**Keyed, partly keyed, unkeyed.**
- **Keyed.** Complete key for the step. Precision and recall are KEYED with `reference_quality`.
- **Partly keyed.** Scored only inside `key_coverage`. Unmatched claims against an incomplete key are "to adjudicate", not "agent wrong" (Foody). **Masked-source keying** (Could): OSM is a normal tool and part of the bridges is withheld; mask by **spatial block**, pin the snapshot; recall is stated as recall against OSM only.
- **Unkeyed.** No output grade is issued; outputs are GOLD-ANCHORED, CALIBRATED-TRANSFER, MODEL-ESTIMATED or ABSTAINED.

**Forbidden answer-key sources: four layers.**
1. **Gateway deny-list** (host, dataset id, tool name) for worker and verifier. A blocked call is a `key_access_attempt` span, counted in the process score; the touched item is excluded from keyed grading as contaminated.
2. **Key isolation.** Keys live in a separate KMS-encrypted bucket with an explicit Deny for the worker role. Local stand-in: key directory outside the worker's mounted volume. **The manifest states which ran**: "key isolation: IAM-enforced" or "key isolation: local convention, not IAM-enforced". The stronger claim is never made when only the weaker ran. A CDK policy-simulator test is a Should; the Deny itself is documented with a manual check.
3. **Post-hoc leak detector.** A claim matching a key item within tolerance with no imagery-evidence span is a probable leak. **Canary decoys** are planted only in key copies we host, at verifiably empty coordinates; a decoy in claims marks the run `INVALID_FOR_ACCURACY` (kept in cost and process statistics, excluded from trust training). Public OSM cannot carry canaries.
4. **Honest limit, printed in every report.** Model memory of OSM or USPVDB cannot be excluded by blocking tools. Prefer post-cutoff events (Aug 2026 flood; per-model cutoffs UNVERIFIED). Partial mitigation only.

**How a partner brings a task.** Three on-ramps, same schema: (a) `treehouse task init` generates a card from prompt, AOI and schema (at least unkeyed); (b) add a gold plan of about 20 items to enable PPI; (c) point to a keyed sibling region of the same family as a calibration twin. The same file runs unchanged on Nepal, Virginia or India. A tiny India card that passes `validate` is the generality proof.

---

## A3. Agent harness, models, providers and tools

**Harness interface:** `run(task, config, tracer, budget) -> claims + trace_ref`.
- **Strands Agents** is the default (OpenTelemetry-native, supported by AgentCore Observability).
- A **~100-line plain Bedrock Converse tool loop** is the second implementation. It is a **Should**: in the MVP only the interface exists. If the loop is not built, the harness comparison axis is dropped from the demo and from A8.
- **Worker and verifier both run as Strands agents** through the same interface, with different model families and different tool sets. The verifier is a second Strands agent that checks each item, as Suhas specified.

**Models and providers.**
- Model registry: id, provider, family, vision flag, tool-use flag, reasoning-trace flag, dated price per 1k tokens, region.
- **Bedrock Converse is the default.** An OpenAI-compatible adapter (Ollama, vLLM, OpenRouter) is the "other providers" path (Could).
- Worker and verifier configured independently. Config validation rejects non-vision models on imagery tasks.
- **Model choice by smoke test** on real Vantor 0.5 m windows ("bridge visible or not"), run before anything else. If no available model can see a footbridge at that resolution, the Nepal flagship reports that as a finding (`cannot_assess` dominates) rather than burning budget.
- Record model id as returned, parameters, prompt hash. Never promise identical re-runs.
- **Quotas.** New-sandbox Bedrock quotas (vision TPM, image throttling) can silently cap trials. The gateway and model adapter use exponential backoff and a concurrency cap; N is sized from observed throughput as well as dollars.
- Verify the Strands provider matrix in live docs; sources disagreed.

**Trace normalization.** Adapters normalize reasoning-text exposure, token accounting, stop reasons and tool-call format into one event shape. Reasoning text is stored when present and **never scored**. Every process feature is computed from actions.

**Tools** (all through the gateway as small MCP servers).
- `clay_search`: cosine search over the AOI subset of LGND GeoParquet (DuckDB or numpy). Source facts: Sentinel-2, 256-d, 1.28 km cells, Jan 2017 to Apr 2026, CC BY 4.0. Returns ranked cells, similarity and a **coverage report** (cannot see a single footbridge; predates the Aug 2026 flood). "Clay narrows, imagery decides." No text-prototype search is promised (no text encoder documented, UNVERIFIED).
- `stac_search` / `scene_info`: footprint, date, GSD, **scene-level cloud % only**.
- `imagery_window` (byte-range COG window read): downsampled image plus scene id, bbox, date, GSD, scene cloud %, **bytes actually read**, pixel hash; explicit no-coverage and out-of-bounds errors; a deterministic **obscuration heuristic** (near-white, low-variance fraction) labelled a heuristic, validated against human gold before any rule uses it. Implemented first as local HTTP range reads (rasterio or a small pure-Python TIFF reader); Lambda port only if time remains (GDAL packaging is a time sink).
- `catalog_lookup` / `roda_search`.
- `record_claim`: only way to emit a claim; `evidence_refs` must resolve to earlier tool-result ids in this run, otherwise marked **ungrounded**.
- `note_limitation`.
- OSM is not in the toolset where it is the key.

**Understanding Statement.** First step, a structured object (restated goal, scope, planned data, known limits).

**Clay is tested, not asserted.** Standing with/without-`clay_search` ablation reporting accuracy, cost and bytes touched. Expect a real effect on Virginia solar (farms are large relative to a 1.28 km cell) and corridor narrowing only on Nepal. Report both.

---

## A4. Tracing and provenance

**Recorded per trial.** Task id, version, hash; config hash (model id as returned, region, params, harness version, tool versions, system-prompt hash, seed); every model call (messages, tokens in/out/cache, latency, stop reason, cost from a dated price table); every tool call (args, result digest or blob ref, bytes, pixels, latency, error type); errors, retries, budget events; claims with evidence refs; Understanding Statement; final output; software provenance (git SHA, lock hash, container digest); data pointers (STAC item id, asset href, ETag/version, bbox, date, license); scorer, estimator and key versions at score time.

**Schema.**
- OpenTelemetry GenAI-style spans (`invoke_agent` root, `chat` and `execute_tool` children). Semconv is "Development" status (unverified in this pass): **pin the version in every manifest** and add a CI test that scores a frozen sample trace after any semconv bump. All Treehouse fields live under `treehouse.*`.
- Canonical record: append-only JSONL, each line with `prev_hash`; Parquet copy for SQL.
- **Every concurrent trial writes its own chained JSONL file.** The run manifest chains the file heads, so parallel trials cannot fork a single chain.
- Exporters: JSONL always on; OTLP to CloudWatch second; a mismatch in span count or token totals is a provenance warning.

**Cassette, with its correction.** Tool payloads are content-addressed. A cassette keyed on (tool, normalized args) replays only the **same trajectory**. Cross-model comparison relies on **pinned snapshot ids and ETags**. Cassette uses: exact re-scoring, the zero-live-call demo fallback, scorer regression tests, isolating model nondeterminism from tool drift. Miss policy is explicit: fail, or fall through to live with a counted `cassette_miss`. The miss-policy machinery is a Should; the Must needs only same-trajectory replay.

**Replay levels.** (1) Re-score: exact. (2) Re-verify: exact given stored claims and crops. (3) Re-run: statistical only; Bedrock is not deterministic even at temperature 0.

**Immutability and versioning.**
- Runs are write-once. Manifest written last, chained to the previous manifest hash. `treehouse verify` checks the chain anywhere with no AWS.
- Evaluations, verifier outputs, human labels and trust estimates are **separate append-only records** keyed by (run hash, scorer version, key version, verifier config, estimator version, seed). Re-scoring appends.
- **Guaranteed AWS floor (Must-0):** Bedrock Converse for both roles plus an S3 **versioned** bucket holding sealed runs, with version history shown in the demo. **Object Lock (governance mode, short retention)** is the next step (Must-1): it can be enabled on an existing versioned bucket (since Nov 2023), cannot be disabled once on, and Object Lock buckets cannot be server-access-log destinations (unverified in this pass). If Object Lock is denied, use versioning plus the local hash chain and say so in the manifest. The denied-delete demo happens only if Object Lock is live.
- Provider-side witness: **Bedrock model-invocation logging** to a normal (non-Object-Lock) bucket, configured for **text and metadata only, image delivery disabled**, so large payloads and CC-BY-NC pixels are not copied. Token and call counts reconcile against the trace. Should, if allowed; the bucket policy is tested in the probe.

**Licenses and pixels.** SPDX per blob and key row; a **license floor** (most restrictive source) is printed on every report (a static per-source string if automation costs time). Vantor is CC-BY-NC-4.0: derived datasets carry a non-commercial flag; **no Vantor pixels in the repo, committed traces or demo recording**; commit scene ids, bboxes, byte ranges and pixel hashes only; crops live in a private cache; NC notice on any Vantor-derived view. LGND is CC BY 4.0. OSM is ODbL; keep OSM-derived keys in a separate directory. USPVDB and NAIP redistribution terms UNVERIFIED. Code is Apache-2.0.

---

## A5. Claim-checking layers

Each claim ends with a **check ledger**, one result per layer, never overwritten. **Resolution rule:** hard-rule fail > human > key > verifier > unchecked. A claim never becomes "correct" because nobody checked it.

1. **Deterministic rules** (free, every claim).
   - Schema valid; geometry inside the AOI and the cited scene footprint; cited scene and date exist and cover the point.
   - **Evidence-in-trace:** the cited window was fetched in this trace **and its bbox contains the claim geometry** (not merely overlaps). Otherwise a fabrication flag. Known weakness, recorded: an agent can fetch any window and cite it; this rule detects fabrication, not insight.
   - Forbidden calls and budget.
   - A damaged/intact claim needs a post-event footprint covering the point, from footprints not the agent.
   - The obscuration heuristic may raise a flag; it cannot decide.
2. **Answer key** within `key_coverage`: one-to-one spatial match under stored tolerance; precision, recall, F1, status accuracy with cluster-bootstrap CIs and `reference_quality`. Unmatched claims go to adjudication. **A gold label that disagrees with a keyed label on a keyed item is logged as reference error, never silently resolved.**
3. **Blind sampled verifier** (a Strands agent, different family by default).
   - **Blind:** receives location, object definition and scene ids; fetches its **own** windows with a different crop, offset, zoom ladder and, where possible, date pair; never sees the worker's label, confidence, reasoning, windows or other claims; cannot tell claimed items from controls.
   - **Tools:** `imagery_window` and `stac_search` only.
   - **Abstain** ("cannot assess") is legal and is an explicit third verdict category, never a vote.
   - **Sampling frame (design-based, after Olofsson):** a probability sample with inclusion probabilities and seed stored, stratified by claimed class, confidence tercile and scene cloud class. Two parts: claimed items, and **unreported places** (random draws over a defined corridor frame of waterways, roads, settlement proximity; Clay-narrowed candidates the worker skipped form an additional stratum). Key-derived candidates may be an extra stratum for keyed steps only. With about 40-60 claims, sample most of them and apply the finite-population correction.
   - **Controls (about 10-25% of the batch):** keyed positives/negatives from the same imagery regime where a key exists (existence sensitivity/specificity only; they do not calibrate damage state). For the unkeyed damage step: **pre/pre placebo pairs** (false-alarm rate) and **post/post test-retest pairs** (self-consistency). Pre-event scene count is probed in hour 1: if fewer than about 10 bridges have a pre/pre pair, use post/post test-retest only and print that in the passport.
4. **Two-source overlap (Chapman-corrected Lincoln-Petersen)**: recall upper bound only (Could).
5. **Human review, two separate queues.**
   - **Random-gold queue.** Drawn at random from **ALL sampled units, including verifier abstentions**, by seed fixed and committed (git timestamp) **before any verifier output is seen**, with inclusion probabilities stored. For PPI, the predictor f(x) for an abstained unit is an explicit third category (stratum-specific mean), so the rectifier (human minus f) is estimated over the full sample and the estimand is the whole claim table, not only the non-abstained part. **The abstention rate is reported beside every interval.**
   - **Blind-labelling protocol (recorded in the manifest).** The labeller sees only imagery windows, with worker label, worker confidence, verifier verdict and verifier reasoning hidden. Order is shuffled; labels are written and sealed before any verdict is revealed. The re-labels are also blind and shuffled. A small CSV or static labelling page shows crops by id; this tool is built before labelling.
   - **Adjudication queue.** Verifier-worker disagreements, unmatched claims, abstentions. Used to explain and fix; **never PPI gold** unless inclusion-probability weighted.
   - Reviewer id and timestamp recorded; written damage rubric. The labeller is the builder, so labels are "builder-checked human reference", not truth, and bounded by the pixels.
   - **Test-retest:** about 5 blind re-labels after a gap; report percent agreement and kappa with n=5 flagged as anecdotal.
   - **Scheduling:** labelling is a fixed 60-90 minute block before sleep (A12), because it gates the flagship GOLD-ANCHORED claim.

**DECISION: the verifier uses a different model family by default.** Enforced at config validation; `allow_same_family: true` stamps the manifest "self-verified" and removes independence credit. Statistical reasoning: self-preference and correlated errors are documented (nine judges from seven families behave like about 2.2 independent votes (unverified)) but magnitude is disputed. Under PPI with a random gold subsample, validity does not depend on verifier independence, only interval width does. So the family rule is an efficiency and bias-reduction device, and a hard tier cap only where **no gold subsample exists** (then capped at CALIBRATED-TRANSFER, "self-checked"). Measure, do not assume: on keyed items report phi on error indicators and effective independent votes per family pair.

---

## A6. Scoring breakdown

**No default composite.** Panels are separate. Blending exists only inside a panel with visible weights. A user-built composite is labelled "user-weighted composite" with the formula.

| Panel | Contents | Notes |
|---|---|---|
| 1. How the agent worked | Deterministic sub-scores that are **pure functions of the sealed trace**: grounding rate; evidence sufficiency for the claim type (status claims need a high-resolution window, not only an embedding score); tool-call validity and error recovery; coarse-to-fine use; redundancy and loops; abstention appropriateness; forbidden-source attempts and budget adherence. | **Zero LLM-judged and zero verifier-dependent components.** An optional trajectory judge (Strands TrajectoryEvaluator or AgentCore Evaluations) appears only as a labelled column outside this number. |
| 1b. Predictive validity of process (Should) | For each Panel 1 sub-score, cluster-bootstrap correlation with keyed accuracy, partial on model. | Sub-score that predicts nothing renders "style, not signal" and gets no trust weight. Defined a priori in `scoring-v1.md`. Never fed back to the agent. |
| 2. Task understanding | Understanding Statement vs `must_notice`; plan-versus-action consistency. | Deterministic. |
| 3. Output grade | Keyed slice: precision, recall, F1, status accuracy, CIs, tier KEYED. **Confidence calibration on verified/keyed claims lives here** (it depends on verdicts, so it is not a process score and is excluded from the 1b strip). Unkeyed: no grade; passport supplies an interval. | Counts always shown. |
| 4. Trust (derived) | P(correct) interval, tier, rung, shift numbers, estimator version, gate verdict (Rely / Spot-check / Do not rely). | Distinct from 1-3. |
| 5. Cost, speed, data touched | $ per run and step; wall time; p50/p95 step latency; tokens; tool calls; windows; **bytes read**; cost per correct item with CI where keyed. Verifier cost shown as "the price of trust". | Cost Explorer is reconciliation only. |

**Typed chips** on every number: KEYED (solid, key icon, "vs key v3, n=38, key quality: incomplete"); GOLD-ANCHORED (striped, `n_gold`, `n_verified`, abstention rate); CALIBRATED-TRANSFER (outlined, regimes used); MODEL-ESTIMATED (hatched, wide); ABSTAINED (grey, reason).

**Plain summary.** Deterministic fact table first; a model phrases prose around numeric placeholders slot-filled from the scorecard; each sentence cites valid span ids. A simple regex lint rejects any number not in the scorecard and any sentence without a valid span id. Labelled "narrative, not scored".

---

## A7. Trust estimation for unkeyed areas

**Honest framing.** No method validates itself on a region with no key. The engine: (1) calibrates and validates where keys exist, (2) buys local outcome evidence with a small random sample, (3) prices shift into the interval, (4) states the evidence tier, (5) abstains outside what was validated. Trust transfers within a `family`, never across.

**Baselines.** B0 (Suhas's simple model, must be beaten): pooled beta-binomial of keyed precision for the same (family, model, harness, tool set). B1: the agent's own stated confidence. B2: intercept-only beta-binomial per model and harness.

**Core: design-based PPI, one estimator family.**
- Estimand: a finite-population value over the run's **whole claim table** (claim precision, a count such as "N bridges damaged", or a miss rate in unreported places).
- Estimate = Horvitz-Thompson mean of verifier verdicts (abstention is its own category) + weighted mean of (human - verifier) on the random gold subsample G, drawn from all sampled units (A5).
- **Tuning with n_gold about 20:** the PPI++ power-tuning lambda would be estimated from the same tiny sample, so **lambda is fixed at 1 (standard PPI) when n_gold < 50, pre-registered**; cross-fitted lambda only above that. Intervals use a **stratified bootstrap or exact/hypergeometric method, not the CLT**, with finite-population correction. The interval method is printed in the passport.
- Small n, plainly: with about 20 gold labels the human-only 90% interval for a proportion near 0.8 is about +/-0.15 to 0.20; +/-0.10 needs about 43. Any PPI narrowing must be demonstrated on keyed tasks, not asserted.

**Tier ladder** (same framework, graded evidence).
- **KEYED:** direct against the key.
- **GOLD-ANCHORED:** core estimator with a random in-area gold subsample. Rungs L2 (verifier sample with controls), L3 (human-anchored), L4 (hindcast-validated, stretch).
- **CALIBRATED-TRANSFER:** no in-area gold. Verifier error rates from keyed regimes and same-batch controls via Rogan-Gladen; existence only, never damage state; interval bootstrapped over new sample and calibration data, **inflated by the observed between-regime spread**. Capped, not VERIFIED. Breaks as sensitivity + specificity approaches 1; that triggers ABSTAINED.
- **MODEL-ESTIMATED:** no verifier budget; pooled Bayesian logistic or beta-binomial prior, always wide.
- **ABSTAINED:** target outside validated range or no calibration for this family.

**No discontinuous switching.** The headline is the highest-tier estimate available; a very small `n_gold` gives a wide interval and a visible `n_gold`, never a silent method change.

**Model prior (small, pre-registered).** At most 4 label-free features (grounding rate, evidence breadth, cross-trial vote fraction, scene cloud %/GSD) plus verifier verdict where present. Pooled Bayesian logistic with weakly informative priors; region variance fixed by a prior that inflates predictive intervals for a new region. No random effects under 6 regimes. Unit of inference is the region or scene cluster.

**Distribution shift, two axes.** (1) Landscape: Clay-embedding distance of the target AOI to each keyed region (classifier two-sample AUC or energy distance) as a **number and percentile of keyed-to-keyed distances** plus nearest keyed region by name; a textual INSIDE/EDGE/OUTSIDE label only beside the number with the ruler stated. Necessary, not sufficient. (2) Acquisition regime: GSD, scene cloud %, sensor, off-nadir and sun angle (UNVERIFIED for Vantor), pre/post date gap, object size; these enter the model directly and are tested by feature ablation, not assumed. Build effort beyond the number and percentile is Should.

**Combination.** No fusion. The passport lists each estimate with its chip. **Non-overlapping intervals trigger "estimators disagree: treat as unverified"**, capping confidence at LOW. Outside applicability with no verifier budget: ABSTAIN.

**Diagnostics, never headline** (each with a kill criterion). Agreement-on-the-line: only with at least about 8 independent (config, task) points and a passing pre-stated fit, else "not on the line here" (Could). Dawid-Skene: needs at least three conditionally independent sources including non-LLM anchors (Stretch). Weighted conformal: Stretch; report measured coverage instead.

**Validation, in the order it becomes possible.**
1. **MVP (Must): planted-error and placebo.** Corrupt a keyed output by known amounts; the estimate must move the right way. Shuffled labels must give baseline-equivalent wide intervals. Verifier sensitivity/specificity per run from controls. `estimator_version`, features and training hashes frozen in every estimate. Beat-baseline panel reads "not computable: k keyed regime(s)" and the passport defaults to the wide B2 interval for MODEL-ESTIMATED numbers.
2. **LORO table (Should, only if a second keyed regime exists**, for example a second USPVDB state with a different sensor/GSD, or the OSM-keyed bridge inventory step). Folds grouped by genuine regime (sensor, GSD, class, country), never by tile; spatial splits; distinct-regime count beside every coverage figure; under about 6 it is "pilot". Pre-registered success: coverage in range AND better log/interval score than B2 in a majority of folds; otherwise "no better than baseline (n regimes)". Spaced Virginia tiles count as one regime. With fewer than 3 regimes print only "n regimes = k, no validation possible". No Must hours are spent on LORO.

**The flagship reference (Nepal damage step).** No keyed source carries a damage state (xBD is a different object class and non-commercial). The claim rests on GOLD-ANCHORED evidence: about 20-25 random blind human labels plus same-batch placebo and test-retest controls. The card says "no keyed calibration for this family; nothing is borrowed from solar", and the width reflects `n`.

---

## A8. Statistics and comparisons

**Every comparison in the MVP is labelled exploratory** (few tasks). The MVP claims **method validity with honest error bars**, not a leaderboard; no model rankings are published from a handful of tasks.

- **Unit.** Task or region is the cluster; trials are repeated measures; items within a scene are correlated. Compare configs on the same tasks, seeds and pinned data (paired). Report **paired differences with cluster or paired bootstrap CIs**; Wilson intervals only for simple proportions.
- **Many small spaced tiles, not a few big tasks.** Illustratively, 4 tasks with paired SD 0.15 give about +/-0.24; 12 spaced tiles give about +/-0.10. USPVDB is nationwide so spaced keyed tiles are cheap (block bootstrap for spatial correlation). They are the comparison substrate, not independent LORO regimes.
- **Trials: fixed two-stage plan.** Stage 1: K=3 per (config, task) to measure cost and between-trial variance. Stage 2: spend the rest by a pre-declared allocation without looking at the contrast. No "add trials until narrow". Report mean accuracy, empirical pass^k and claim-set stability.
- **Sizing.** Size by the variance of the paired difference (up to 2*sigma^2*(1-rho)), not the single-mean formula. Report minimum detectable difference at actual N. Floor: at least 5 per arm to publish any difference.
- **Axes, one factor at a time.** Model vs model (cross-family); harness (only if the plain loop is built); tooling (with/without `clay_search`); verifier choice (same vs cross-family on keyed tasks).
- **Multiple comparisons.** Short pre-declared primary list with Holm correction, committed to the repo with a git timestamp before labelling; everything else exploratory. If the CI spans zero: "inconclusive at N=k; about M more runs would resolve it at $X".
- **Variance decomposition** (task, trial, config).
- **Budget ($500 hard cap; figures illustrative until measured).** Step 0: measure one real vision run (tokens, image tokens, bytes, dollars); N_total = floor(comparison budget / p90 cost per run). Planned <= $250, alarm $350, hard stop $450. Rough split: dev/smoke 25%, keyed sweep about 25%, Nepal about 20%, verifier about 15%, reserve about 15%. Verifier cost <= about 20% of worker's. Enforced by an in-app guard plus AWS Budgets alert if permitted. If the plan does not fit, cut configs, then task size, then N, never below the floor.
- **Cost levers.** Prompt caching, small AOIs, byte-range windows, cassette replay. Bedrock batch (about half price, up to about 24 h, uneven image/model support) only for post-hoc sweeps.

---

## A9. Interfaces

One Python service layer; CLI, API, MCP and UI are thin wrappers, so there is one code path for every number.

- **CLI (Must):** `treehouse task init|validate`, `run`, `check`, `score`, `trust`, `verify`, `replay`, `report`, `compare`.
- **Report (Must):** one self-contained HTML plus JSON bundle per run, with task card, trace hashes, scores, versions, license floor and "what would change this interval". Recomputable offline. The plain summary for a non-technical ADB officer covers what the agent did, found, what was checked and by whom, how far to trust it and why, what it could not see, cost and time. Served by local file or presigned URL by default.
- **MCP server: a thin read-only wrapper over the JSON bundle**, first item of Must-1 (about 1 h, cut first if H20 slips). Tools: `list_runs`, `get_scorecard`, `get_trust_passport`, `explain_trust(item)`, `get_plain_summary`, `get_claim`, `compare_configs`, `get_trace_span`; resource `treehouse://runs/{id}/report`. Write tools are off by default and need an explicit budget argument. stdio locally; streamable HTTP if hosted. Consumers receive the chip with the number.
- **API (Should):** FastAPI locally; Lambda Function URL only with `AWS_IAM` auth, or kept local. Every response carries `type`, `tier`, estimator version, `manifest_ref`.
- **UI (Should, built last):** static; run page with passport and plain summary in the first viewport; five-panel scorecard with chips; claim map and table (worker vs verifier vs key); trace timeline; trust card; compare view. Table alternative for every map; contrast, keyboard, 44 px targets. Hosted login is cut. **S3 static hosting likely collides with account Block Public Access**: use CloudFront with OAC or presigned URLs, or default to local files plus the self-contained HTML.

---

## A10. AWS integration map

**Principle: AWS-native, not AWS-locked.** A `backends:` config selects `aws` or `local` per seam; the manifest records which ran.

**Hour-0 execution-locus decision (first probe item).** The Workshop Studio account is reachable only through the browser (Kiro web IDE). Test in order:
- (a) can temporary CLI credentials be exported to the Mac, so everything runs locally with `backends: aws`?
- (b) otherwise run everything in the Kiro web IDE terminal with git push/pull as transport; check disk, CPU, session timeout, whether `cdk deploy` and docker work.
Record the result in `aws-capabilities.json`. **If (b):** docker-dependent items ("one image everywhere") and long agent loops fall to local stand-ins, and the 18-20 productive-hour estimate shrinks (re-plan at H1).

**Capability probe** (about 30 min, a Kiro script, one cheap call per service): execution locus; Bedrock model list; one real vision Converse call (cost, multimodal families); **quotas and throttle behaviour**; S3 versioning/Object Lock; Athena; Lambda; CloudWatch put; Step Functions; AgentCore; Budgets; invocation-logging bucket policy. Each row applies "if allowed" and degrades automatically.

**Guaranteed floor shown live in the demo:** Bedrock Converse for both roles (Strands) and an S3 versioned bucket with visible version history. Everything else is conditional.

| Service | Job | Tier | Local stand-in | Note |
|---|---|---|---|---|
| Capability probe | locus, models, quotas, services | Must-0 | hand-written json | Everything depends on it |
| Bedrock Converse | Worker, verifier, summarizer | Must-0 | Ollama / OpenAI-compatible | Cost from `usage` x dated price |
| S3 versioned bucket | Sealed run store | Must-0 | content-addressed dir + hash chain + `treehouse verify` | AWS floor |
| S3 Object Lock (governance) | Immutable store, denied-delete demo | Must-1 | as above | Works on existing buckets |
| IAM key-bucket Deny, KMS-encrypted key bucket | Key isolation | Must-1 (policy-simulator test: Should) | key dir outside worker volume | Manifest states which ran |
| CDK | Buckets, roles, log groups as code | Must-1 for what we deploy | `make local` | Modular; `cdk synth` needs no credentials |
| CloudWatch GenAI via OTel / AgentCore Observability | Second tracer, budget alarm | Should | JSONL | Needs Transaction Search once |
| Bedrock invocation logging | Provider-side witness | Should | none | Text/metadata only |
| Lambda | `imagery_window`, rules near the data | Should | in-process | Vantor us-east-1; Clay/NAIP us-west-2; GDAL packaging risk |
| CloudFront/OAC or presigned URLs | Hosted report | Should | local file | Not public S3 |
| AgentCore Evaluations (GA 2026-03-31) | Comparison column; grounding rule as Lambda evaluator | Could | Strands evals | Only if probe passes and Must done |
| Athena (+Glue) | SQL across runs | Could | DuckDB, identical SQL | DuckDB is the engine |
| Bedrock batch | Verifier sweeps | Could | on-demand loop | Coverage UNVERIFIED |
| Step Functions, AgentCore Runtime, KMS Sign, CloudTrail data events | fan-out, hosting, signed head, key-read proof | Could | asyncio pool, docker, local keypair | |
| Fargate + Cognito, S3 Vectors, EventBridge, A2I | Hosted login, vectors, re-check, review | Stretch | static UI, numpy, cron, CSV | |
| Cut | Knowledge Bases, Guardrails, SageMaker, DynamoDB | Cut | | Gateway owns enforcement |

**Judging view of the AWS story:** a real model path (Bedrock via Strands), a real audit store (versioned S3, Object Lock if allowed) with an IAM-enforced key boundary where permitted, a second tracer and independent witness if allowed, our checks inside AWS's evaluation service if time allows, deployable from code.

---

## A11. Act-on-the-world layer, simulation and hindcasting

- **Where it sits.** Downstream of the Certified Dataset, outside scoring, one-way dependency. The core never calls it.
- **Gate.** The card's pre-registered thresholds decide act / verify first / hold. Items without a sufficient tier go to human verification. "Do not rely" blocks action unless overridden with a logged reason.
- **MVP stub (Could): inspection-priority list for the bridge task.** Visible formula (damage probability x uncertainty x consequence proxy), every input shown, each row carrying tier, interval, evidence reference, estimator version; low-trust rows "needs field check". CSV/GeoJSON plus a one-page memo; a person approves; no real-world action and no structural-failure claims. ADB can replace it.
- **Hindcasting (stretch).** MVP builds only `as_of` gateway enforcement and the frozen claim table, enabling delayed keys. A real hindcast needs a past event with later-public truth (UNVERIFIED; the Nepal event has none yet; xBD is non-commercial). It is the only route to L4. MVP substitutes: placebo and planted-error tests.
- **Simulation (Stretch/Future).** Ship a **Simulation Card spec** only: editable inputs, user-selected place and click, "scenario, not prediction", human-verified, consuming only claims above the gate and stamped with the dataset's tier.

---

## A12. Cut line for a SOLO build due Thu Nov 5, 10:00

About 34 h remain including sleep: plan for about 18-20 productive hours, fewer if the locus is the Kiro terminal. **Rule:** one thin vertical slice beats broad half-built layers. **The freeze at T-6h is non-negotiable.** The demo is recorded from replayed traces regardless. The planted-trace replay is built right after the gateway, so the fallback exists early.

**MUST-0: the walking skeleton (about 9-10 h, done by H10).** One end-to-end story that is demoable alone:
1. Hour-0 probe (execution locus, quotas, vision cost, Object Lock), vision smoke test on real 0.5 m windows to pick worker/verifier models.
2. Task Card schema, `validate`, 2 cards (Virginia keyed, Nepal), India stub card only if cheap. Gateway with forbidden-source enforcement, backoff, concurrency cap.
3. Strands worker on Bedrock Converse (one harness), model registry, budget guard. Tools: `imagery_window`, `stac_search`, `clay_search`, `record_claim`, `note_limitation`.
4. Hash-chained per-trial JSONL tracer, manifest, frozen claim table, S3 versioned bucket plus local hash-chain store, planted-trace replay.
5. Deterministic rules including evidence-in-trace; keyed grader on Virginia with cluster-bootstrap CIs; cost/speed/data-touched panel.
6. Blind cross-family Strands verifier with probability sampling and controls; random-gold draw (seed committed); PPI passport on the Nepal damage step with B0/B1/B2, tier chips and abstain rule; static HTML report and CLI.

**H10 checkpoint and fallback.** By H10 one keyed Virginia run must go end-to-end (card, Strands on Bedrock, sealed trace, key grade, cost panel, CLI report). If not: drop the Nepal damage step to GOLD-ANCHORED-only with the verifier skipped (human labels on a random sample of worker claims), and keep the replay demo.

**MUST-1 (about 5 h, ordered; cut from the bottom).**
1. Labelling tool (CSV/static page) and the **fixed 60-90 min blind-labelling block before sleep** (about 20-25 labels plus 5 blind re-labels).
2. Five-panel scorecard with chips and Understanding checklist.
3. Plain summary with regex numbers lint.
4. Object Lock plus key-bucket IAM Deny (manual check), CDK for what is deployed.
5. Read-only MCP wrapper over the JSON bundle.
6. README, card template with worked example, Apache-2.0, license notes, ADR of decisions, clean-clone repro.

**SHOULD (about 5-6 h, ordered; cut from the bottom).**
1. Placebo and planted-error test suite beyond the minimum.
2. Minimal static UI with claim map and shift numbers.
3. Second plain Converse harness (and the harness comparison axis).
4. Predictive-validity strip (1b).
5. CloudWatch OTel second tracer.
6. Bedrock invocation-log witness.
7. Paired comparison over spaced tiles (with/without Clay; same- vs cross-family verifier).
8. LORO table, only if a second keyed regime exists.
9. CDK policy-simulator test; cassette miss-policy.
10. Lambda `imagery_window`; hosted report via CloudFront/OAC or presigned URL.
11. Leak detector with canaries (only if the OSM task is built).

**COULD.** Inspection-priority list; India run; Athena with DuckDB parity; AgentCore Evaluations column; Bedrock batch; Step Functions; AgentCore Runtime; Lincoln-Petersen bound; agreement-on-the-line (gated); KMS signing and CloudTrail proof; `start_eval` write tool; masked-block OSM keying; OpenAI-compatible adapter; API.

**STRETCH / FUTURE (FUTURE-WORK.md).** Hindcast run; simulation (card spec only); Dawid-Skene; weighted conformal; S3 Vectors; EventBridge; A2I; Fargate + Cognito; multi-user auth.

**Demo tasks.**
1. **Virginia solar farms, keyed** (USPVDB key, NAIP imagery; license, completeness, date alignment and requester-pays status UNVERIFIED in hour 0; if any fails, use a smaller AOI or the OSM masked-block key). Shows a KEYED grade, verifier sensitivity/specificity and the with/without-Clay ablation.
2. **Nepal Bhote Koshi / Trishuli bridges (flagship).** Inventory step partly keyed against OSM; damage step unkeyed, on the clearest of the 28 post-event scenes. The **cloud trap**, where `cannot_assess` is a gradable good answer, is the lead demo moment. Passport moves from MODEL-ESTIMATED to GOLD-ANCHORED when the labels are applied. Clay honesty note; "nothing borrowed from solar".
3. **Region swap:** the same card on a small India AOI passes `validate` and, if time allows, runs.
4. **Planted-trace replay** as the safety net.

**Demo script (about 3 min), mapped to the four judging criteria.**
- Impact: an ADB officer reads the plain summary and the verify-first list; the Nepal cloud trap shows abstention rewarded.
- Technological implementation: Bedrock/Strands worker and verifier, sealed versioned store, blind verifier, replay from sealed traces.
- Design: the typed chips and the passport in the first viewport.
- Innovation/generality: the same card across Virginia, Nepal, India; "I can't tell you" routed to a human.

**Hour order.** H0-4 probe, schema, gateway, one tool, replay stub. H4-10 harness, tracer, rules, key grade, skeleton checkpoint. H10-16 verifier, sampling, passport. H16-20 scorecard, store, labelling tool; labelling block. Sleep. Then MCP, report polish, Should items, clean-clone repro, freeze at T-6h, demo recorded from replays.

**Risks said out loud.**
1. Too few keyed regimes: LORO not computable; the trust claim is PPI plus tiers, not cross-regime validation.
2. About 20 human labels give wide intervals; the width is shown.
3. The gold labeller is the builder: "builder-checked", blind, with a test-retest (n=5 anecdotal).
4. No keyed calibration for bridge damage; nothing transfers from solar.
5. Workshop Studio may deny services or force the Kiro-terminal locus; the demo degrades to stand-ins.
6. Real vision cost and quotas unmeasured until hour 0-3.
7. Worker and verifier share pixels, so independence is partial.
8. Vantor is non-commercial; no pixels in repo or recording.
9. Model memory of OSM cannot be excluded.
10. No available model may see a footbridge at 0.5 m; then that is the finding.

**Pushback, one line each.** Do not blend process into the trust interval unless predictive validity supports it. Do not present agreement-on-the-line or Dawid-Skene as the trust method. Do not present Clay as bridge-finding. Ship the baselines, shift numbers, PPI and the abstain rule; let regime validation decide what else is displayed.

---

## Decisions table

| Area | Decision | Why | Who argued it |
|---|---|---|---|
| A1 | Two layers joined only by a Certified Dataset file; core never mutates the world | Cleanest boundary; ADB can swap the act layer | all |
| A1 | Freeze claim table to sealed storage before any key or verifier sees it | Makes delayed keys and hindcasting honest | aws-architect |
| A1 | Scorers are pure functions of stored records | Exact replay | statistician |
| Headline | State up front that the shipped trust claim is PPI plus tier plus abstain, with LORO "not computable" in the MVP | With 1-2 regimes the beat-baseline test is undefined; overclaiming fails a judge question | beneficiary-judge, agent-eval, statistician, remote-sensing |
| A2 | Keying per step; `cannot_assess` first-class and excluded from keyed denominator | Partly keyed tasks; gradable abstention | remote-sensing, statistician |
| A2 | Four-layer key enforcement; manifest states IAM-enforced vs local-convention | Do not claim the stronger guarantee when only the weaker ran | aws-architect (suggestion adopted) |
| A2 | Spatial-block OSM masking; `as_of` enforced at gateway | Random masking leaks; cheapest leak control | agent-eval, remote-sensing |
| A3 | Verifier is a Strands agent, different family, restricted tools | Matches Suhas's vision and the Technology criterion | beneficiary-judge |
| A3 | Plain-loop second harness demoted to Should; harness axis conditional on it | Solo feasibility; Strands alone is the Must | statistician, agent-eval, aws-architect, beneficiary-judge over earlier "all five" |
| A3 | Models chosen by a Day-0 vision smoke test, not family label | 0.5 m performance unmeasured | remote-sensing |
| A3 | Backoff and concurrency cap; size N from observed throughput | New-account Bedrock quotas can cap trials | aws-architect |
| A3 | Reasoning stored, never scored | Unfaithful reasoning | agent-eval |
| A4 | Per-trial chained JSONL with manifest chaining file heads | Parallel trials cannot fork one chain | agent-eval |
| A4 | Pin semconv; frozen-trace CI test | Development-status conventions | agent-eval |
| A4 | AWS floor = Bedrock + versioned S3; Object Lock is Must-1 with fallback to versioning plus hash chain | Guaranteed Technology-criterion floor despite unverified probe | beneficiary-judge (over aws-architect's CDK-first ordering) |
| A4 | Invocation logging text/metadata only, non-lock bucket | Avoids copying NC pixels and large payloads | aws-architect |
| A4 | Cassette replays same trajectory only; pinned snapshots for cross-model | Corrects an overclaim | agent-eval |
| A5 | Random-gold drawn from ALL sampled units including verifier abstentions; abstention is a third predictor category; abstention rate shown | Otherwise the estimate only covers the non-abstained subpopulation | statistician |
| A5 | Blind-labelling protocol (hide worker/verifier outputs, shuffle, seal before reveal, blind re-labels) | Anchoring to the verifier collapses the rectifier and falsely narrows the interval | statistician |
| A5 | Two human queues; adjudication never PPI gold | Disagreement selection biases the rectifier | statistician |
| A5 | Evidence-in-trace requires bbox to contain the claim geometry; weakness recorded | Overlap is too weak | agent-eval |
| A5 | Gold-vs-key disagreement logged as reference error; test-retest n=5 reported as anecdotal with kappa | No silent resolution | statistician |
| A5 | Different-family verifier by default; cap only where no gold exists | Under random-gold PPI independence affects width, not validity | statistician |
| A5 | Unreported-places frame random; key-derived candidates only an extra stratum | Key-only frame makes recall relative to OSM | remote-sensing |
| A5 | Pre/pre placebo only if >= about 10 bridges have a pair; else test-retest only | Pre-event scenes are scarce | remote-sensing |
| A6 | No default composite; five panels | Honest | all |
| A6 | Confidence calibration moved from Panel 1 to Panel 3 | It depends on verdicts, so it is not a pure trace function and broke "zero LLM-judged" | agent-eval |
| A6 | Predictive-validity strip demoted to Should | Solo feasibility; process is defined a priori either way | aws-architect, beneficiary-judge |
| A6 | Typed chips carried as data | Consumers cannot strip labels | agent-eval, statistician |
| A7 | One PPI family; lambda fixed at 1 when n_gold < 50; stratified bootstrap/exact intervals; method printed | Lambda estimated from 20 labels is unstable | statistician |
| A7 | LORO moved from Must to Should; "not computable: k regimes" displayed; no build hours | One keyed regime makes folds undefined; conflicting claim that it is Must lost on evidence of regime count | agent-eval, statistician, beneficiary-judge, remote-sensing over aws-architect's earlier LORO-in-Must |
| A7 | Rogan-Gladen as CALIBRATED-TRANSFER, existence only, inflated interval | Transport of error rates is the shift problem | statistician |
| A7 | Shift in two spaces; number and percentile shown | Embeddings describe landscape, not bridge visibility | remote-sensing |
| A7 | Baselines B0/B1/B2 and pre-registered beat-baseline test | Prevents manufactured confidence | statistician |
| A7 | Agreement-on-the-line, Dawid-Skene, conformal gated or stretch | Unproven for agents | all |
| A8 | Fixed two-stage trials; paired sizing; Holm; everything exploratory in the MVP | No optional stopping; few tasks | statistician |
| A8 | Primary list and gold seed committed before labelling with git timestamp | Makes "fixed before seeing output" checkable | beneficiary-judge |
| A9 | Library plus CLI one code path; MCP is a thin read-only wrapper (first of Must-1, cut first on slip); UI Should | Conflict: agent-eval wanted MCP in Must; four seats demoted it, and a wrapper over the JSON costs about 1 h | statistician, aws-architect, beneficiary-judge over agent-eval |
| A9 | Lambda URL uses IAM auth or stays local; hosting via OAC/presigned URL, not public S3 | Block Public Access in sandboxes | aws-architect |
| A10 | Hour-0 execution-locus decision (export credentials vs Kiro terminal) with consequences stated | Without it the plan cannot be executed | aws-architect |
| A10 | Probe adds quotas, invocation-log bucket policy | Silent caps | aws-architect |
| A10 | DuckDB is the engine; Athena is Could; Fargate/Cognito stretch | Failure modes without eval value | statistician, aws-architect |
| A10 | AgentCore Evaluations verified GA; Lambda evaluator; Could | Time-boxed real integration | beneficiary-judge, aws-architect |
| A10 | Lambda `imagery_window` after a local implementation | GDAL packaging time sink | aws-architect |
| A11 | Act layer is a Could stub; hindcast hooks only; simulation as card spec | Shows boundary without false expertise | all |
| A12 | Must split into Must-0 skeleton (about 9-10 h, H10 checkpoint, stated fallback), Must-1, Should with explicit cut order | Original Must was about 25 deliverables; no cut order existed | all four objectors |
| A12 | Fixed 60-90 min blind-labelling block before sleep; labelling tool built first | Gates the GOLD-ANCHORED flagship | statistician, aws-architect |
| A12 | Freeze at T-6h non-negotiable; replay demo recorded regardless; replay built early | Fallback must exist early | beneficiary-judge, agent-eval |
| A12 | Demo script maps each judging criterion to a visible moment | Judging alignment | beneficiary-judge |
| A12 | Three live tasks plus replay (not four live) | A fourth task with no key or labels can only abstain | remote-sensing |

---

## Sources

Statistics, trust and uncertainty:
- https://arxiv.org/abs/2301.09633 (Prediction-Powered Inference)
- https://arxiv.org/abs/2311.01453 (PPI++)
- https://arxiv.org/abs/2505.18659 (adaptive PPI) (unverified)
- https://arxiv.org/abs/2206.13089 (Agreement-on-the-Line)
- https://arxiv.org/html/2404.01542v1 (Agreement-on-the-line, foundation models)
- https://arxiv.org/abs/1904.06019 (weighted conformal under covariate shift)
- https://arxiv.org/abs/2005.07939 (Area of Applicability)
- https://cran.r-project.org/web/packages/CAST/vignettes/cast04-AOA-tutorial.html
- https://arxiv.org/pdf/2303.07334 (spatial structure inflates random CV) (unverified)
- https://rdrr.io/cran/epiR/man/epi.prev.html (Rogan-Gladen)
- https://projecteuclid.org/euclid.ss/1009213286 (Wilson intervals)
- https://aclanthology.org/2026.cas-1.11/ (Dawid-Skene over-estimates LLM accuracy) (unverified)
- https://ideas.repec.org/a/bla/jorssc/v28y1979i1p20-28.html (Dawid and Skene)
- https://arxiv.org/abs/1703.03022v5 (capture-recapture dependence bias)

Map accuracy and reference error:
- https://cendekia.unisza.edu.my/neuaxis-e/Record/nottingham-44846/Description (Olofsson et al.)
- https://eprints.nottingham.ac.uk/2274/ (Foody)

LLM judging and verifier independence:
- https://arxiv.org/abs/2404.13076
- https://arena.ai/blog/llm-judge-self-preference/ (unverified)
- https://icml.cc/virtual/2026/poster/61230 (unverified)
- https://arxiv.org/abs/2506.07962 (unverified)
- https://arxiv.org/pdf/2605.29800 (unverified)
- https://arxiv.org/abs/2410.10934
- https://arxiv.org/abs/2305.04388

Agent evaluation methodology:
- https://arxiv.org/abs/2411.00640
- https://arxiv.org/pdf/2510.04265 (unverified)
- https://arxiv.org/abs/2406.12045 (tau-bench)
- https://proceedings.iclr.cc/paper_files/paper/2025/hash/1b126cc38b8638e07bef37e7b2bb72bf-Abstract-Conference.html
- https://arxiv.org/abs/2510.11977 (unverified)
- https://inspect.aisi.org.uk/

Tracing:
- https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans (page now says GenAI conventions moved to the OpenTelemetry GenAI semantic conventions repository; see fact-check notes)

AWS:
- https://aws.amazon.com/about-aws/whats-new/2023/11/amazon-s3-enabling-object-lock-buckets/
- https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
- https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock-configure.html
- https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock-managing.html
- https://aws.amazon.com/about-aws/whats-new/2026/03/agentcore-evaluations-generally-available/
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluations.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/ground-truth-evaluations.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/results-and-output.html
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/omni-agents-evaluators.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-get-started.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html
- https://aws.amazon.com/blogs/aws/amazon-bedrock-agentcore-adds-quality-evaluations-and-policy-controls-for-deploying-trusted-ai-agents/
- https://aws.amazon.com/bedrock/pricing/
- https://aws.amazon.com/about-aws/whats-new/2024/08/amazon-bedrock-fms-batch-inference-50-price/
- https://docs.aws.amazon.com/step-functions/latest/dg/state-map-distributed.html
- https://aws.amazon.com/about-aws/whats-new/2025/12/amazon-s3-vectors-generally-available/

Strands:
- https://strandsagents.com/docs/user-guide/sdk/quickstart/overview/
- https://strandsagents.com/docs/user-guide/concepts/model-providers/
- https://strandsagents.com/docs/user-guide/evals-sdk/evaluators/trajectory_evaluator/
- https://strandsagents.com/docs/user-guide/evals-sdk/how-to/agentcore_evaluation_dashboard/

Data and licensing:
- https://www.openstreetmap.org/copyright (ODbL)
- https://arxiv.org/pdf/1911.09296 (xBD)

Local:
- council-brief.md (Vantor CC-BY-NC-4.0, 33 scenes with 28 post-event, scene-level cloud only; LGND 1.28 km, 256-d, Jan 2017 to Apr 2026, CC BY 4.0)
- review1-judge.md, review1-verifier.md, clay-vision-doc.txt, SCOPE.md@a23dec5

Caveat: no external papers were re-fetched in this revision. Citations are as given in the five proposals. Only the Object Lock and AgentCore Evaluations facts were freshly checked online earlier. Items marked UNVERIFIED remain unconfirmed.

---

## Fact-check notes

Scope and limits of this check: the fact-checker hit a tool spend limit partway through, so several web fetches failed. Items below are split into confirmed, corrected/flagged, and not checked. Nothing was silently changed; the only in-place edits are the "(unverified)" marks and the OTel source note above.

**Confirmed**
- AgentCore Evaluations reached GA on 2026-03-31. It offers online and on-demand evaluation, 13 built-in evaluators, custom LLM-based evaluators, and code-based evaluators in Python or JavaScript run through Lambda (so "grounding rule as Lambda evaluator" is valid). Results appear alongside AgentCore Observability data in CloudWatch. Source: https://aws.amazon.com/about-aws/whats-new/2026/03/agentcore-evaluations-generally-available and https://aws.amazon.com/blogs/aws/amazon-bedrock-agentcore-adds-quality-evaluations-and-policy-controls-for-deploying-trusted-ai-agents/
- Object Lock: works only in versioned buckets; governance mode lets users with `s3:BypassGovernanceRetention` override, so a "denied-delete demo" must use a role without that permission and without the console default bypass header (the console includes `x-amz-bypass-governance-retention:true` by default). Simple DELETE on a locked object returns 200 and adds a delete marker; only a versioned (permanent) DELETE returns 403. The demo must therefore delete a specific version id. Source: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
- arXiv 2404.01542 is "Predicting the Performance of Foundation Models via Agreement-on-the-Line" (Saxena, Kim, Mehra, Baek, Kolter, Raghunathan), consistent with its label. Source: https://arxiv.org/abs/2404.01542
- arXiv 1703.03022 is a post-stratified two-sample capture-recapture paper under dependence (Chatterjee and Bhuyan), consistent with its label. Source: https://arxiv.org/abs/1703.03022v5
- Arithmetic in A7: with n=20, p=0.8, z=1.645, the half-width is 1.645*sqrt(0.16/20) = 0.147 (the design's "0.15 to 0.20" is conservative for Wald and plausible for exact/Wilson intervals); n for +/-0.10 is 1.645^2*0.16/0.01 = 43.3, matching "about 43". Computed here, no external source.
- Data facts (Vantor 33 scenes / 28 post-event, scene-level cloud only, CC-BY-NC-4.0, us-east-1; LGND Sentinel-2, 256-d, 1.28 km, Jan 2017 to Apr 2026, CC BY 4.0, us-west-2) match council-brief.md.

**Corrected or flagged**
- OpenTelemetry source URL: the cited page now says GenAI semantic conventions have moved to the OpenTelemetry GenAI semantic conventions repository and the page is no longer maintained. The "Development" status and the `invoke_agent` / `chat` / `execute_tool` span names could not be confirmed from that page; marked "(unverified in this pass)" in A4. Builder should re-read the GenAI semconv repo and pin the version.
- Object Lock buckets "cannot be server-access-log destinations": not stated on the Object Lock overview page and could not be confirmed (search failed); marked "(unverified in this pass)" in A4. The design already routes invocation logs to a non-lock bucket, so the plan is safe either way.
- "Nine judges from seven families behave like about 2.2 independent votes": source is one of the unverified arXiv/ICML links; marked "(unverified)" in A5.

**Not checked (tool limit); marked "(unverified)" in Sources where cited**
- arXiv 2505.18659, 2303.07334, 2510.04265, 2506.07962, 2510.11977, 2605.29800; aclanthology 2026.cas-1.11; arena.ai blog; icml.cc poster 61230. Titles and claims attached to them in the design could not be matched.
- Not re-verified this pass (stated from the earlier check or general knowledge, and still carrying the design's own caveat): Object Lock enablement on existing buckets since Nov 2023; S3 Block Public Access defaults; Lambda Function URL `AWS_IAM` auth; Bedrock batch about 50% price (https://aws.amazon.com/about-aws/whats-new/2024/08/amazon-bedrock-fms-batch-inference-50-price/); S3 Vectors GA Dec 2025; Strands OTel support and provider matrix; Bedrock invocation-logging image-delivery option; USPVDB/NAIP terms and requester-pays status; Vantor off-nadir/sun-angle metadata; per-model training cutoffs; Wilson-interval citation (Brown, Cai, DasGupta 2001) and Dawid-Skene 1979 (JRSS C 28:20-28) bibliographic details; Olofsson et al. and Foody references; PPI (2301.09633), PPI++ (2311.01453), Agreement-on-the-Line (2206.13089), weighted conformal (1904.06019), AOA (2005.07939), tau-bench (2406.12045), xBD (1911.09296) arXiv ids.