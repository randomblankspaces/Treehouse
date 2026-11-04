## A13. Unkeyed methods compared (Suhas's top priority)

Added after council 1 (post-merge addendum by the overnight agent, then put through a doubter and a judge pass). It brings together, in one place, the method choices that A5 and A7 make piece by piece. **Unkeyed is the normal case.** Keyed tasks exist to calibrate and to test these methods. Each method below is validated by running it on a keyed task **as if the key were hidden**, then comparing what it says to the hidden key. The column "Validated on keyed data by" says how.

Costs are planning estimates: **$** = model calls on a sample, **$$** = model calls on every item or several runs, **H** = human minutes, **0** = free (computed from stored records).

### 1. Scores for unkeyed output (what number the report shows)

| # | Method | What it catches | What it misses | Cost | Validated on keyed data by | Tier | MVP? |
|---|---|---|---|---|---|---|---|
| U1 | **PPI over a blind sampled verifier + random human gold** (A7 core) | Systematic verifier bias (the rectifier corrects it); total error rate on the whole claim table, including abstentions | Errors that both humans and verifier make from the same pixels; anything outside the sampling frame | $ + H (about 20–25 labels) | Coverage of the PPI interval vs hidden key over seeded resamples of a keyed task; planted-error monotonicity | GOLD-ANCHORED | **Must** |
| U2 | **Verifier-only, error rates transferred (Rogan-Gladen)** | Existence errors when no human time is available | Damage state (never transferred); regime shift beyond the observed between-regime spread | $ | Leave-one-regime-out once at least 2 keyed regimes exist; before that, controls in the same batch only | CALIBRATED-TRANSFER | Must (existence only) |
| U3 | **Process-signal model** (grounding rate, evidence breadth, cross-trial vote, cloud/GSD → P(correct)) | Runs that skipped evidence, fabricated citations or looped | Confident, well-evidenced wrong answers; any signal that does not predict accuracy | 0 | Predictive-validity strip (Panel 1b): correlation with keyed accuracy, partial on model; "style, not signal" if none | MODEL-ESTIMATED | Must (wide prior); 1b is Should |
| U4 | **Baselines B0/B1/B2** (pooled beta-binomial; self-stated confidence; intercept-only) | Nothing new. They set the bar the engine must beat | — | 0 | Same LORO table as the engine; B0 is Suhas's "simple probability model" | MODEL-ESTIMATED | **Must** |
| U5 | **Self-consistency across K trials** (vote fraction per item, claim-set stability) | Unstable, guess-like claims; model nondeterminism | Stable but systematically wrong claims, where all trials share the bias | $$ (K runs) | Correlate vote fraction with keyed correctness; feed U3 as one feature | feeds U3 | Must (as a feature, K=3) |
| U6 | **Cross-model agreement / agreement-on-the-line** | Configuration-level accuracy shifts without labels | Item-level errors; works only if the fitted line holds | $$ | Needs at least about 8 (config, task) points with a passing pre-stated fit, else "not on the line here" | diagnostic | Could |
| U7 | **Dawid-Skene latent-class over worker runs + verifier + rules** | Per-source reliability with no key | Correlated sources (same pixels, related models) inflate accuracy | 0 after sources exist | Recover known source accuracies on keyed tasks; needs at least 3 conditionally independent sources, including a non-LLM one | diagnostic | Stretch |
| U8 | **Confidence calibration** (reliability of the agent's own confidence) | Over- or under-confident agents | Needs verdicts; meaningless with no gold | 0 | Expected calibration error on keyed and gold items | Panel 3 | Must (where verdicts exist) |
| U9 | **Abstention quality** (`cannot_assess` where the data cannot show the object) | Agents that guess under cloud, outside the footprint or below resolution | Wrongful abstention when the item is visible (needs gold) | 0 | Keyed: abstention on items with no covering footprint is correct by construction; gold labels for the rest | Panel 1 / 2 | **Must** |
| U10 | **Coverage and evidence-quality scores** (share of the AOI and frame actually inspected at sufficient GSD, bytes read) | Lazy or partial searches; claims based on embeddings alone | Correctness of what was inspected | 0 | Correlate with keyed recall (U3 strip) | Panel 1 / 5 | **Must** |

### 2. Testing and verification methods for unkeyed datasets (how claims are checked)

| # | Method | What it catches | What it misses | Cost | Validated on keyed data by | MVP? |
|---|---|---|---|---|---|---|
| V1 | **Deterministic rules** (schema, inside AOI and cited footprint, evidence-in-trace bbox containment, post-event footprint for status claims, date logic, forbidden calls) | Fabricated or impossible claims; key leakage attempts | Plausible wrong claims | 0 | Planted-violation traces: detection rate must be 100 % | **Must** |
| V2 | **Blind sampled verifier agent** (different family, own windows, cannot tell claims from controls) | Wrong existence/status on sampled items; misses in unreported places | Errors it shares with the worker (same pixels); anything not sampled | $ | Sensitivity and specificity on keyed controls in the same batch; same- vs cross-family error correlation (phi) | **Must** (DD1) |
| V3 | **Stratified design-based sampling** (inclusion probabilities stored; claimed items plus an unreported-places frame) | Makes V2 and V4 estimates unbiased for the whole table and gives an omission estimate | Strata that the frame does not define | 0 (it decides where $ and H go) | Seeded-population simulation: Horvitz-Thompson estimate is unbiased and the interval covers at its nominal rate | **Must** |
| V4 | **Human spot check + PPI** (random gold, blind protocol) | Verifier bias; gives the only claim whose validity does not depend on the verifier | Human error (builder-labelled; test-retest reported) | H | Gold vs key disagreement logged on keyed items as reference error | **Must** |
| V5 | **Placebo and test-retest controls** (pre/pre pairs: no change expected; post/post re-reads) | Verifier false alarms on "damage"; verifier instability | True-change sensitivity (needs real damaged examples) | $ | Placebo false-alarm rate must match the specificity seen on keyed negatives | **Must** (test-retest at least) |
| V6 | **Planted canaries / synthetic decoys** (in key copies we host; synthetic planted items in synthetic tasks) | Key leakage; verifier that just agrees | Real-world leakage via model memory | 0 | A decoy appearing in claims marks the run INVALID_FOR_ACCURACY; detection rate measured on planted runs | Should (leak), Must (synthetic planted traces) |
| V7 | **Metamorphic / perturbation tests** (shift the AOI by a known offset → claims shift by it; rotate or crop windows → same verdict; rephrase the prompt → same claim set; drop a scene → those items become `cannot_assess`) | Brittle agents and verifiers whose output depends on irrelevant changes | Consistent but wrong behaviour | $$ (re-runs) | On keyed tasks the metamorphic relation must hold where the key says it should; violations correlate with keyed error | Should (verifier crop/offset invariance is built into V2); full suite Stretch (sensitivity analysis) |
| V8 | **Cross-source triangulation** (OSM where it is not the key, Overture, other imagery dates) | Single-source artefacts | Shared upstream errors; sources that are also the key (forbidden) | $ | Agreement rate vs key on keyed tasks | Could |
| V9 | **Capture-recapture (Chapman-corrected Lincoln-Petersen)** over two independent runs or sources | An upper bound on how many items all sources missed (recall) | Dependence between sources biases it (usually underestimates misses) | 0 after two sources | Compare the estimated total with the keyed total | Could |
| V10 | **Temporal hindcast** (freeze claims with `as_of`; grade later when truth arrives) | Real outcome accuracy, the only route to the L4 rung | Needs an event with later public truth; slow | 0 now, H later | It is itself a key that arrives later | Stretch (hooks are Must: `as_of`, frozen claim table) |
| V11 | **Human adjudication of disagreements** | Explains and fixes errors | Biased if used as gold (selected on disagreement) | H | Never used as PPI gold unless inclusion-probability weighted | Must (queue), labelling optional |

### 3. MVP combination and how the report shows it

- **MVP set:** V1 + V2 + V3 + V4 + V5 (test-retest at least) + U1 + U2 (existence only) + U3 (wide) + U4 + U5 (K=3) + U8 + U9 + U10. Hindcast hooks (V10) only.
- **How every number is labelled:** each number is a `TypedNumber` with `tier` ∈ {KEYED, GOLD-ANCHORED, CALIBRATED-TRANSFER, MODEL-ESTIMATED, ABSTAINED}. In the report:
  - KEYED numbers are **evaluated**.
  - All other tiers are **estimated**, and each shows `n`, its interval and its method.
  - ABSTAINED shows a reason and no number.
- **Disagreement is a signal:** if two estimators' intervals do not overlap, the passport reads "estimators disagree: treat as unverified".
- **What the MVP can and cannot claim** (restating the headline up front): U1 is valid without assuming the verifier is right. Everything else is a labelled estimate. Cross-regime validation (LORO) is "not computable" until a second keyed regime exists.

### 4. How each method is tested in code (offline)

Every method above has a seeded, offline simulation test with known ground truth (IMPLEMENTATION-DESIGN.md §test strategy):
- Interval coverage over many synthetic populations.
- Planted-error monotonicity.
- A shuffled-label null.
- A placebo false-alarm rate.
- Rule-violation detection.
- Horvitz-Thompson unbiasedness.
- Rogan-Gladen recovery and abstain trigger.
