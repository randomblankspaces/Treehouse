# DOUBTER: SYSTEM-DESIGN.md overnight edits (diff vs origin/main)

Scope: the pass-2 fact-check edits, new section A13, and the "Fact-check pass 2" notes block. Read with A1-A12, council-brief.md (ADDED BY SUHAS 23:58), design-decisions.md, review1-judge.md and scratchpad fc-keep.md. The repo was not edited.

Checks I ran myself (2026-11-04):
- **Vantor listing:** an anonymous S3 listing returns 110 keys, not truncated. That is 33 scene triplets (jpg/json/tif) plus `collection.json`, `event.json` and a `stereo/` folder (4 `.ideal.tif`/`.rpc` pairs and a README).
- **STAC items:** I fetched all 33 items. `phase` gives **4 pre and 29 post**, which confirms the edit. All 33 carry `view:off_nadir`, `view:sun_elevation` and `view:sun_azimuth`, which also confirms the edit. GSD is held in `pan_gsd` (0.43-0.71 m) and `multispectral_gsd`. No item has a plain `gsd` field.
- **Range read:** an anonymous range read on a `.tif` returns HTTP 206. "Vantor COGs are anonymous HTTPS" holds.
- **Footprints vs corridor points:** I ran a point-in-polygon test of each scene footprint against approximate points for Rasuwagadhi (85.38E, 28.27N), Timure (85.37, 28.24) and Syabrubesi (85.345, 28.16). Only the **2021-10-16 and 2023-09-17** pre scenes cover the upper corridor. The 2024-05-29 and 2026-02-05 pre scenes do not. The two clearest post scenes (2026-09-18, 6-7 % cloud) do not cover it either. The 2026-09-07 scenes (18-19 % cloud) do.
- **July 2025 flood:** a web search confirms that a 2025-07-08 Bhote Koshi flood destroyed the Miteri (Nepal-China friendship) bridge at Rasuwagadhi (Kathmandu Post, 2025-07-08; ekantipur, 2025-07-08). So the corridor had real damage between the pre and post scenes, before the 2026 event.
- **OTel repo:** I could not check it. GitHub API access to `open-telemetry/*` is not enabled in this session.

Severity counts: **blocking 3 (1, 14, 26), major 18, minor 15.**

---

## A. Statistics in A13: wrong or overstated

**1. A13 table 2, row V9 (capture-recapture): bias direction is wrong and the row contradicts itself and A5.**
- *Doubt.* "What it catches" says "An upper bound on how many items all sources missed". "What it misses" says dependence "usually underestimates misses". Those two statements cannot both hold. Under positive dependence (both runs find the same easy items, which is the normal case for two runs of similar models on the same pixels), the overlap m is inflated. Then N̂ = (n1+1)(n2+1)/(m+1) - 1 is too small. The estimated misses are therefore a **lower** bound on misses. Equivalently, the implied recall is an **upper** bound. A5 item 4 states this correctly: "recall upper bound only".
- *Evidence.* A13 V9 against A5.4. Standard Lincoln-Petersen under positive dependence. The Chapman correction fixes small-sample bias, not dependence.
- *Severity.* **blocking.** It is a statistical error in the table Suhas made top priority, and a statistician judge will catch it.
- *Fix.* "What it catches": "A recall **upper bound** (equivalently, a lower bound on the number of items all sources missed) inside the frame both sources searched." "What it misses": "Positive dependence between sources (same pixels, related models) inflates the overlap, so misses are underestimated and recall is overstated. Chapman corrects small-sample bias only, not dependence. Two runs of one model are not independent sources."

**2. A13 §3 "What the MVP can and cannot claim", and rows U1 and V4: "U1 is valid without assuming the verifier is right" overstates.**
- *Doubt.* PPI validity is relative to the human labels, which are builder-labelled, bounded by the pixels, and have a test-retest of n=5. The validity is also asymptotic. With n_gold of about 20, and a rectifier (human minus verifier) that is mostly zeros, a bootstrap interval can be near-degenerate and undercover. V4's "the only claim whose validity does not depend on the verifier" repeats the problem. An ADB reader will hear "valid" as "correct".
- *Evidence.* A5 item 5 ("builder-checked human reference, not truth"). A7: "Any PPI narrowing must be demonstrated on keyed tasks". The current text names no coverage check at n≈20.
- *Severity.* **major.**
- *Fix.* "U1's point estimate does not rely on the verifier being right. It does rely on (a) the random gold draw, (b) the builder's blind labels being right (test-retest n=5, anecdotal) and (c) n_gold≈20. Interval coverage at that n is checked by simulation (§4) and printed. It is an estimate against a human reference, not against truth."

**3. A13 intro and the column header "Validated on keyed data by": the blanket claim is false for several rows.**
- *Doubt.* The intro says "Each method below is validated by running it on a keyed task as if the key were hidden". The rows say otherwise:
  - V3: validated by a seeded **simulation**, not keyed data.
  - U4: validated by "Same LORO table", which A7 and A12 say is not computable in the MVP.
  - U2: LORO, or same-batch controls only.
  - V10: "It is itself a key".
  - U10 and U3: validated through the 1b strip, which is a Should.
  - V5: see doubt 6.
  - Pass 2 also replaces the only real keyed task offline with a synthetic one (doubt 14).

  Suhas asked how each method is validated. The table answers as if every validation runs in the MVP, and most do not.
- *Evidence.* A7 Validation items 1-2. A12 Should items 4 and 8. The pass-2 note on the synthetic keyed task.
- *Severity.* **major.**
- *Fix.* Reword the intro: "Where a keyed task exists, a method is validated by running it as if the key were hidden. The column says how, and a new column, **'Validation in MVP?'**, says Yes / Simulation only / Not computable (k keyed regimes) / Stretch." Fill that column truthfully for each row.

**4. A13 V3 (stratified design-based sampling): "unbiased for the whole table" and "covers at its nominal rate" are overstated.**
- *Doubt.* There are four problems.
  - Horvitz-Thompson makes the verifier-verdict mean design-unbiased for what the verifier would say over the frame. It is not unbiased for correctness. Only the PPI rectifier moves it toward the human reference.
  - A ratio (Hajek) mean is not exactly unbiased.
  - A5 stratifies by class × confidence tercile × cloud class, which can be 18 or more strata, over about 40-60 claims. Many strata will hold 1-2 units, so the within-stratum variance cannot be estimated. A nominal-coverage criterion will likely fail in the planned simulation.
  - Gold is a second-phase subsample of the verifier sample. The variance is a two-phase variance, and a naive stratified bootstrap with a finite-population correction does not handle that automatically.
- *Evidence.* A5 item 3 (strata, "sample most of them, FPC"). A7 ("stratified bootstrap or exact/hypergeometric").
- *Severity.* **major.**
- *Fix.* "Makes the verifier-verdict mean design-unbiased over the frame. Correctness comes only after the PPI rectifier. Strata are collapsed until each holds at least 2 sampled units and at least 1 gold unit (rule pre-registered). Variance is two-phase (verifier sample, then gold subsample). The simulation reports actual coverage at n_gold≈20 and prints it if it falls below nominal."

**5. A13 V3 "gives an omission estimate", and V2 "misses in unreported places": with rare objects this estimate will be near-empty.**
- *Doubt.* Random draws over a corridor frame will mostly contain no bridge. With about 10 draws and 0 found, the 95 % upper bound on the miss rate is about 3/10 = 30 % (rule of three). A judge will read "omission estimate" as informative.
- *Evidence.* A5 item 3 frame design. Bridge density in a mountain corridor.
- *Severity.* **minor.**
- *Fix.* Append: "within the frame only. With rare objects the interval is expected to be very wide (for example 0/10 draws gives an upper bound of about 30 %), and it is shown as such."

**6. A13 V5 (placebo/test-retest) validation column: this is cross-family borrowing, which A7 forbids.**
- *Doubt.* "Placebo false-alarm rate must match the specificity seen on keyed negatives." No keyed source carries damage state (A7 flagship paragraph). The only keyed negatives are solar-existence negatives, on synthetic data offline. Comparing bridge-damage false alarms with solar-existence specificity is exactly the "borrowed from solar" step that A7 and A12 rule out. "Must match" also has no test and no tolerance, and n is tiny.
- *Evidence.* A7 ("no keyed calibration for this family; nothing is borrowed from solar"). A5 controls ("they do not calibrate damage state").
- *Severity.* **major.**
- *Fix.* "Validated by: placebo false-alarm rate reported with a Wilson interval. On keyed existence tasks only, the placebo design is checked against known negatives of **that** family. No cross-family comparison is made for damage."

**7. A13 V5 "pre/pre pairs: no change expected" is false for the flagship corridor, and pass 2 did not catch it.**
- *Doubt.* The only pre-event scenes covering the upper Bhote Koshi corridor are 2021-10-16 and 2023-09-17. The 2024-05-29 and 2026-02-05 scenes miss it, per my footprint check. A real flood on 2025-07-08 destroyed the Miteri bridge at Rasuwagadhi. So:
  - (a) Pre/post damage comparisons in the upper corridor span both the 2025 and 2026 floods, and would credit 2025 damage to the 2026 event.
  - (b) Only one pre/pre pair (2021/2023, at 46 % cloud) exists there, so the A5 condition "at least about 10 bridges with a pre/pre pair" will almost certainly fail.
  - (c) The clearest post scenes (2026-09-18, 6-7 %) do not cover the upper corridor.

  A12's "clearest of the 29 post-event scenes" therefore does not mean clear at the bridges.
- *Evidence.* STAC footprints listed above. Kathmandu Post and ekantipur reports of 2025-07-08.
- *Severity.* **major.** It affects the flagship reference and the damage rubric.
- *Fix.* Add to A5 (controls) and A13 V5: "Pre-event coverage of the upper corridor is 2021-10 and 2023-09 only. A real flood on 2025-07-08 destroyed the Miteri bridge, so the damage rubric is 'state in post-event imagery', not 'change caused by the 2026 event'. Placebo pairs must not straddle July 2025. Expect test-retest only." In A12 demo task 2, replace "clearest of the 29" with "the clearest post-event scene **covering the AOI's bridges** (the 18-19 % scenes of 2026-09-07 cover the upper corridor; the 6-7 % scenes of 2026-09-18 do not)". Add the footprint check to the hour-1 probe.

**8. A13 V7 (metamorphic): "shift the AOI by a known offset → claims shift by it" is wrong.**
- *Doubt.* Bridges do not move when the AOI moves. The correct relation is that claims inside the overlap keep their geographic coordinates, and claims enter or leave only at the edges. "Claims shift by it" holds only if the image **georeference** is perturbed on purpose, which is a synthetic test. Separately, "verifier crop/offset invariance is built into V2" overstates: V2's different crop is there for blindness, and no paired invariance comparison is made.
- *Evidence.* A13 V7 text. A5 item 3.
- *Severity.* **major.** A logical error in Suhas's own example list.
- *Fix.* Two relations:
  - "Shift the AOI by a known offset: claims in the overlap keep their coordinates (within tolerance), and only edge items enter or leave."
  - "Shift the image georeference by a known offset (synthetic): claims shift by that offset."

  Change the MVP cell to "Stretch (not in A12). V2's crop offset gives blindness, not a metamorphic test."

**9. A13 U9 (abstention quality): "catches agents that guess under cloud" at cost 0 contradicts the no-cloud-mask finding.**
- *Doubt.* Review 1 correction (b) and A5 say there is no cloud mask, only a scene-level %. The obscuration heuristic "may raise a flag; it cannot decide" and must first be validated against human gold. So guessing under cloud cannot be scored deterministically at cost 0. Only abstention for "no covering footprint" is correct by construction. The A12 lead demo moment, the cloud trap, rests on this row.
- *Evidence.* review1-judge correction (b) and C10. A5 item 1, last bullet.
- *Severity.* **major.**
- *Fix.* "What it catches": "Guessing outside the footprint (deterministic). Guessing under cloud or below resolution **only on items that human gold marks obscured** (or a gold-validated heuristic marks obscured)." Change the cost to "0 (footprint) / H (cloud)".

**10. A13 U8 (confidence calibration): the row contradicts itself and A6, and ECE at this n is unreliable.**
- *Doubt.* The row says "meaningless with no gold" and also "Must (where verdicts exist)". Verifier verdicts exist without gold. A6 Panel 3 says calibration on "verified/keyed claims". Calibrating against verifier verdicts measures agreement with the verifier, not calibration. Binned ECE on 20-40 items is biased upward and noisy.
- *Evidence.* A13 U8 against A6 Panel 3.
- *Severity.* **minor.**
- *Fix.* "Must on KEYED and human-gold items only. On verifier-only items it is labelled 'agreement with verifier', not calibration. Report a Brier score plus a reliability plot with at most 3 bins and a bootstrap CI. No ECE headline at n<50."

**11. A13 U2 (Rogan-Gladen): the misses column omits the method's actual failure modes.**
- *Doubt.*
  - Rogan-Gladen assumes Se and Sp are constant across the target population (non-differential misclassification), but cloud and GSD change them.
  - It gives an aggregate prevalence only, not per-item correctness.
  - It can fall outside [0,1] and needs truncation.
  - With controls at 10-25 % of a 40-60 item batch (about 5-15 items), Se and Sp are very imprecise.
  - The abstain threshold is not pre-registered: "approaches 1" needs a number.
  - "Catches: existence errors" is wrong. Rogan-Gladen does not catch errors; it corrects a rate.
- *Evidence.* A7 tier ladder. A5 controls.
- *Severity.* **minor.**
- *Fix.*
  - "What it catches": "Corrects the verifier's observed existence rate for its measured Se/Sp when no human time exists."
  - "What it misses": "Se/Sp differences across cloud and GSD strata. Item-level errors. Estimates outside [0,1] are truncated and flagged."
  - Add: "Abstain if the lower 90 % bound of Se+Sp-1 is below 0.3 (pre-registered)."

**12. A13 U3 (process-signal model): "what it catches" is misattributed.**
- *Doubt.* "Runs that skipped evidence, fabricated citations or looped" are caught deterministically by V1 and Panel 1. A P(correct) model predicts accuracy; it does not detect fabrication.
- *Evidence.* A5 item 1 (evidence-in-trace) and A6 Panel 1.
- *Severity.* **minor.**
- *Fix.* "What it catches": "Shifts in expected accuracy when trace features look unlike keyed runs, **if** a feature is shown to predict keyed accuracy (Panel 1b). Fabrication and loops are caught by V1 and Panel 1, not here."

**13. A13 §3 "Disagreement is a signal": non-overlap of intervals is a near-powerless test.**
- *Doubt.* Non-overlap is far more conservative than a test of the difference. Against a wide B2 interval, a PPI interval will almost never fail to overlap, so the warning will rarely fire and its silence will read as agreement.
- *Evidence.* A7 Combination and A7 MVP ("defaults to the wide B2 interval").
- *Severity.* **minor.**
- *Fix.* Append: "Overlap is a weak check. Silence does not mean the estimators agree. The passport shows both intervals side by side."

## B. A13 against the cut line (A5/A7/A12): Must work added silently

**14. Pass-2 "Decision weakened" note and A12 demo task 1: the synthetic keyed substitute changes scope, and the reason given is wrong.**
- *Doubt.* There are five problems.
  - (a) Requester Pays needs only AWS credentials. Both hour-0 loci in A10 have them: (a) exported credentials on the Mac, (b) the Kiro terminal inside AWS. NAIP reads therefore work in both. Egress is free within us-west-2.
  - (b) The demo is recorded from replayed traces (A12), and NAIP is public domain, so NAIP crops **can** sit in a committed cassette (Vantor crops cannot). The offline demo does not need live NAIP, so offline does not justify a synthetic task.
  - (c) The change silently breaks other parts of the doc:
    - the H10 checkpoint ("one keyed **Virginia** run must go end-to-end");
    - the up-front claim ("one keyed regime (Virginia solar)");
    - demo task 1's "verifier sensitivity/specificity and with/without-Clay ablation", which are meaningless on synthetic items (no real pixels, no Clay embeddings);
    - A13's "validated on keyed data".
  - (d) Nothing says that synthetic tasks carry a SYNTHETIC chip, or that they never count as a keyed regime toward LORO or "k regimes".
  - (e) An overnight agent made this decision inside a fact-check note, and Suhas has not logged it in design-decisions.md.
- *Evidence.* A10 hour-0 locus. A12 H10 and the demo script. fc-keep "Decisions affected" item 1 ("Mitigation: use signed rasterio/GDAL reads with `AWS_REQUEST_PAYER=requester`").
- *Severity.* **blocking**, until it is reconciled or Suhas decides it.
- *Fix.* Replace the sentence with: "NAIP is Requester Pays: window reads use signed requests with `AWS_REQUEST_PAYER=requester`. That works in either A10 locus. The offline demo replays a cassette that may include NAIP crops (public domain). A synthetic keyed task is used **only for offline unit tests**. It carries a SYNTHETIC chip, never counts as a keyed regime, and never backs a KEYED number in the demo. (Proposal; needs Suhas's decision.)" Update the pass-2 "Decision weakened" bullet to match.

**15. A13 U3 "Must (wide prior)": this silently adds a Bayesian logistic model to Must.**
- *Doubt.* A7 MVP and the up-front section both say the passport "defaults to the wide **B2** interval for MODEL-ESTIMATED numbers". A12 Must-0 item 6 lists B0/B1/B2 and PPI, not a process-feature logistic. With one keyed regime (now synthetic offline), any fitted model is trained on that one regime alone.
- *Evidence.* A7 Validation item 1. A12 Must-0 item 6.
- *Severity.* **major.**
- *Fix.* MVP cell: "Should. In the MVP, MODEL-ESTIMATED numbers use B2 (U4). U3's features are logged so it can be fitted later."

**16. A13 U2 "Must (existence only)": not in A12, and it depends on an OSM key the cut line does not budget.**
- *Doubt.* Calibrated transfer for Nepal bridge existence needs same-family keyed controls. Solar cannot be used (trust transfers within a family only, A7). That means OSM bridges as a key, but:
  - OSM masked-block keying is Could;
  - the canary leak detector is Should "only if the OSM task is built";
  - fc-keep notes that overpass-api is blocked from the container.

  A12 Must-0 never lists Rogan-Gladen or an OSM key fetch.
- *Evidence.* A2 (masked-source keying Could). A12 Should item 11 and the Could list. A7 ("Trust transfers within a family, never across").
- *Severity.* **major.**
- *Fix.* "Should. It runs only if a same-family existence key (OSM bridges, pinned snapshot) is loaded. Otherwise the existence step reports GOLD-ANCHORED or MODEL-ESTIMATED. Never calibrate from solar."

**17. A13 U5 cost "$$" vs "Must (K=3)": the cost is double-counted or unbudgeted.**
- *Doubt.* If A8's Stage-1 K=3 per (config, task) already covers Nepal, U5's marginal cost is 0 (vote fractions are computed from stored runs). If it does not, U5 roughly triples Nepal worker vision spend, the dominant cost, to feed U3, which the MVP does not use (doubt 15). Two further problems:
  - K=3 gives vote fractions in {1/3, 2/3, 1} only.
  - Matching claims across trials needs the A2 one-to-one spatial match rule. That is extra code A12 does not list.
- *Evidence.* A8 Trials and Budget (Nepal about 20 %). A12 Must-0.
- *Severity.* **major.**
- *Fix.* Cost: "0 marginal given A8's K=3; otherwise K× worker cost". MVP: "Must only as a stored feature from A8's K=3 runs. Cross-trial matching reuses `match_rule`. No extra runs are bought for it."

**18. A13 V2 validation "same- vs cross-family error correlation (phi)", under a Must row.**
- *Doubt.* It requires running two verifiers on keyed items. That is A8's "verifier choice" axis, which sits under A12 Should item 7 (paired comparison). Listing it as the validation of a Must method implies Must work.
- *Evidence.* A12 Should item 7. A5 DECISION ("Measure, do not assume").
- *Severity.* **minor.**
- *Fix.* Append "(phi: Should, A12 Should item 7)".

**19. A13 V4 validation "gold vs key disagreement logged on keyed items": no human labels on keyed items are planned.**
- *Doubt.* The 60-90 minute labelling block covers the Nepal damage step, which is unkeyed. With Virginia now synthetic offline, the MVP has no keyed items with human labels. Human reference error is therefore unmeasured, except through test-retest at n=5.
- *Evidence.* A12 Must-1 item 1. A5 item 5.
- *Severity.* **major.** It undercuts doubt 2's caveat.
- *Fix.* Either add "5 of the 20-25 gold labels are drawn from keyed items, blind, to measure reference error", or state "Reference error unmeasured in MVP (test-retest n=5 only)".

**20. A13 §3 MVP set vs the rows: they are inconsistent, and the H10 fallback is missing.**
- *Doubt.*
  - V6 is labelled "Must (synthetic planted traces)" and V11 "Must (queue)", but neither is in the MVP set.
  - The A12 H10 fallback (verifier skipped, human labels on a random sample of worker claims) removes V2, U1-as-PPI and U2. A13 does not give the fallback MVP combination. Suhas asked "which combination is MVP".
  - The row MVP labels (U3, U5, U8) disagree with A12 (doubts 15-17).
- *Evidence.* A13 rows V6 and V11 against §3. A12 H10.
- *Severity.* **major.**
- *Fix.* Make §3 the single source of truth: "**MVP (Must-0/1):** V1, V2, V3, V4, V5 (test-retest), V6 (planted traces only), V10 hooks, V11 queue; U1, U4, U9 (footprint part), U10. **Must if data exists:** U8 (keyed and gold only). **Should:** U2, U3, U5-as-model, V7 partial. **H10 fallback:** V1 + V4 human-only estimate (GOLD-ANCHORED, no PPI) + U4 + U9 + U10." Then make every row's MVP cell match it.

**21. A13 §3 tiers: process and cost numbers are forced into "estimated".**
- *Doubt.* "Each number is a TypedNumber with tier ∈ {KEYED, …, ABSTAINED}", and "All other tiers are estimated". Panel 1 process scores, Panel 5 cost, time and bytes are exact measurements from the trace. Under this wording, the report either labels the dollar cost "estimated" or has no tier for it. "Everything else is a labelled estimate" also contradicts "KEYED numbers are evaluated" two lines above.
- *Evidence.* Commitment 2 (`type` and `tier`). A6 Panels 1 and 5.
- *Severity.* **major.** It decides whether the evaluated/estimated split reads right to an ADB reader.
- *Fix.* "Accuracy and trust numbers carry a tier. KEYED is **evaluated**, all other tiers are **estimated**, and ABSTAINED shows a reason. Process, cost, time and data-touched numbers are `type: measured` (exact from the sealed trace) and are labelled 'measured'." Change "Everything else is a labelled estimate" to "Every other accuracy number is a labelled estimate."

**22. A13 §4: "Every method above has a seeded offline simulation test (IMPLEMENTATION-DESIGN.md §test strategy)".**
- *Doubt.* IMPLEMENTATION-DESIGN.md does not exist in the repo; grep finds only this reference. The seven tests listed cover U1, V3, V5 and U2 only. Nothing covers U5, U8, U9, U10, V7, V9, and the Could/Stretch rows (U6, U7, V8, V10) will not be built. So "every method" is false.
- *Evidence.* `grep -rn IMPLEMENTATION-DESIGN` returns only SYSTEM-DESIGN.md:428.
- *Severity.* **major.** It is an unsupported claim with a dangling reference.
- *Fix.* "Each **MVP** method has a seeded offline test with known ground truth (planned; test strategy to be written in IMPLEMENTATION-DESIGN.md):" then the list, plus "U9 footprint-abstention unit test, U10 coverage arithmetic, V9 Chapman on a seeded population (if built)". Drop "every method above".

**23. A13 V7, V8 and V11 introduce items absent from A12.**
- *Doubt.*
  - Metamorphic tests appear nowhere in A12's Should list.
  - Cross-source triangulation (Overture) is not in the Could list or the toolset.
  - The adjudication queue is "Must (queue)", but A12 does not list it.
- *Evidence.* A12 lists.
- *Severity.* **minor.**
- *Fix.* Add them to A12 (V7 partial: Should, last; V8: Could; V11 queue: Must-1 under the labelling tool), or change the A13 cells to "not in cut line".

## C. Does A13 meet Suhas's priority (council-brief, ADDED 23:58)?

**24. A13 overall: the coverage of his list is good, but "compare and choose" is thin.**
- *Doubt.* Every method Suhas named appears. The table does not say **why** each non-MVP method was not chosen, which was his ask ("compare and choose"). Three gaps:
  - "Rule/physics checks" is reduced to schema and footprint rules. There are no physical-plausibility rules, such as "a bridge geometry crosses a waterway or road from a non-key source" or "a damage claim lies within the flood reach".
  - "Label-free accuracy estimation" is matched only by U3 and U6, with no mention of confidence-based estimators.
  - Cost appears as symbols only, with no scale.
- *Evidence.* council-brief lines 53-57.
- *Severity.* **major.**
- *Fix.*
  - Add a column "Why (not) in MVP", one line per row (for example U6: "needs ≥8 config-task points; we have ~2").
  - Add a row **V1b, physical-plausibility rules** (a bridge must intersect a waterway from a non-key hydrography source such as DEM-derived flow lines; status claims only inside the event footprint), labelled Should.
  - Add cost scale: "$ ≈ verifier sample, ≤ ~20 % of worker spend (A8); $$ ≈ K× worker spend; H ≈ the 60-90 min labelling block".

**25. A13 header: "then put through a doubter and a judge pass" has no record.**
- *Doubt.* The council-1-log addendum says "It went through a doubter pass and a judge pass; results are below", but nothing follows it. A project whose product is provenance should not claim a review it cannot show. (This doubter pass is apparently the review now under way.)
- *Evidence.* docs/design/council-1-log.md, final line.
- *Severity.* **major.**
- *Fix.* Remove the clause until the results are committed, or commit them (for example docs/reviews/a13-doubter.md and a13-judge.md) and link them.

## D. Fact-check pass 2 edits: errors and unsupported claims

**26. A4 Object Lock: "the demo object is written after enablement" is not enough, and the fix dropped the retention requirement.**
- *Doubt.* Enabling Object Lock does not lock new objects either. An object is protected only if the bucket has a **default retention** or the PUT sets retention or a legal hold. fc-keep row 13 says "written after enablement **or given retention explicitly**". As edited, the denied-delete demo can fail. Using "a dedicated demo bucket" also conflicts with A10's "Immutable store … works on existing buckets": the sealed run store would then not be locked at all.
- *Evidence.* fc-keep row 13. Object Lock semantics (retention is per object version). A10 table row.
- *Severity.* **blocking**, because the demo step would silently not work.
- *Fix.* "Enabling Object Lock locks nothing by itself. Set a bucket default retention (governance, short) or pass `x-amz-object-lock-mode`/`-retain-until-date` on PUT. The demo object is written after that. If a dedicated demo bucket is used (the setting is permanent), say so, and note that the run store itself is versioned, not locked." Update the A10 row to match.

**27. A4: "(verified, pass 2)" covers three Object Lock facts, but one was only VERIFIED-K.**
- *Doubt.* "Cannot be disabled once on" is VERIFIED-K (not fetched) in fc-keep row 14. The parenthetical upgrades it.
- *Evidence.* fc-keep rows 13-15.
- *Severity.* **minor.**
- *Fix.* "…cannot be disabled once on (known record, not re-fetched), and Object Lock buckets cannot be server-access-log destinations (verified, pass 2)."

**28. Pass-2 notes "The full table is kept in the council-1 log": false.**
- *Doubt.* The log holds only the counts. The table exists only in the session scratchpad (fc-keep.md), which is not in the repo.
- *Evidence.* docs/design/council-1-log.md.
- *Severity.* **major** (dangling provenance).
- *Fix.* Commit the table as `docs/reviews/factcheck-pass2.md` and point to it, or reword to "The full table was not committed."

**29. Pass 2 says "marks removed", but contradictions remain elsewhere in the doc.**
- *Doubt.*
  - A4 Licenses still reads "USPVDB and NAIP redistribution terms UNVERIFIED", although pass 2 verified both as public domain.
  - A3 still says "Verify the Strands provider matrix in live docs; sources disagreed", right below the new Strands sentence.
  - A8 still says "Bedrock batch (about half price…)", not "for select models".
  - The pass-1 "Confirmed" bullet still says "Vantor 33 scenes / 28 post-event … match council-brief.md".
- *Evidence.* A4 line 146, A3 line 107, A8 line 248, Fact-check notes line 592.
- *Severity.* **major** (internal contradictions).
- *Fix.*
  - A4: "USPVDB: public domain (CC0-1.0), attribution requested. NAIP: public domain."
  - A3: "Provider matrix differs by doc version and between Python and TS; Python has Bedrock, OpenAI, Anthropic, Ollama, LiteLLM and a custom `Model` base class (pass 2)."
  - A8: "about half price for select models".
  - Pass 1: add "(superseded by pass 2: 29 post-event)".

**30. Sources "Local": the entry credits council-brief.md for a fact it contradicts.**
- *Doubt.* The entry reads "council-brief.md (… 33 scenes: 4 pre-event, 29 post-event …)", but council-brief.md and review1 say 28. The pass-2 explanation "Earlier docs said 28; the 2026-02-05 scene is pre-event" does not explain the gap: calling a pre scene "pre" cannot turn 28 into 29.
- *Evidence.* council-brief.md line 25. review1-judge correction (a).
- *Severity.* **minor.**
- *Fix.* Sources: "Vantor STAC items, checked 2026-11-04: 33 scenes, 4 pre / 29 post by `phase` (council-brief.md and review1 say 28 post; superseded)." Notes: "Earlier docs said 28 post-event; the cause of the discrepancy was not identified."

**31. A4 OTel: "v1.42.0, June 2026" is pinned on one secondary source, and the release may belong to the core repo.**
- *Doubt.* fc-keep row 5 says the move happened "on 12 June 2026 (v1.42.0)" per Dash0, and that the repo was not fetched. v1.42.0 is probably the **core** semantic-conventions release at the time of the move, not a version of the new genai repo. Then "pin that repo's version" has no known value. I could not check this: GitHub API access to open-telemetry is not enabled here. A second issue: Strands puts an event-loop-cycle span between the agent span and the chat/tool spans, so "`chat` and `execute_tool` children" of `invoke_agent` may not match Strands's actual tree.
- *Evidence.* fc-keep row 5. Strands traces doc (cited in Sources).
- *Severity.* **minor.**
- *Fix.* "(the move coincided with core semconv v1.42.0, June 2026, per one secondary source; the genai repo's own version is pinned at hour 0)". Also: "match on `gen_ai.operation.name` and allow intermediate spans (Strands event-loop cycles)."

**32. A9: "Public S3 static hosting is blocked by default" drops the account-level point.**
- *Doubt.* Bucket-level Block Public Access is on by default, but the bucket owner can switch it off. The real sandbox risk is account-level BPA or an SCP, and fc-keep recommended keeping "may also be blocked at account level". The pass-2 note "not 'likely'" overcorrects: blocked by default is not the same as enforced.
- *Evidence.* fc-keep row 11.
- *Severity.* **minor.**
- *Fix.* Append: "…and Workshop Studio may also enforce account-level BPA or an SCP, so it cannot be relied on even if the bucket setting is changed."

**33. Sources: the parenthetical on the neurips.cc link overgeneralises.**
- *Doubt.* fc-keep row 19 found the ICML id did not match **either of the two** known papers. It did not show the id matched "no known paper". The NeurIPS link is the listing for Kohli 2026, and the entry does not say so.
- *Evidence.* fc-keep rows 16 and 19.
- *Severity.* **minor.**
- *Fix.* "https://neurips.cc/virtual/2026/161256 (NeurIPS 2026 listing of Kohli 2026; replaces icml.cc poster 61230, which matched neither cited paper)".

**34. A5: "nine judges from seven families" keeps an unchecked detail inside a newly "verified" sentence.**
- *Doubt.* fc-keep row 16 verifies n_eff 2.18 and the range 1.9-2.5. It does not confirm "seven families". The range is also across prompts, temperatures, chain-of-thought **and RewardBench**, not "on MNLI".
- *Evidence.* fc-keep row 16.
- *Severity.* **minor.**
- *Fix.* "nine LLM judges behave like about 2.2 independent votes (Kish n_eff 2.18 on MNLI; 1.9-2.5 across prompts, temperatures, CoT and RewardBench; arXiv 2605.29800; text tasks, not imagery)".

**35. A3 and A7: "0.5 m" and the "GSD" covariate do not match the STAC fields.**
- *Doubt.* The items carry `pan_gsd` (0.43-0.71 m) and `multispectral_gsd` (1.7-2.9 m), and no `gsd`. The A7 GSD covariate must name its field. The vision smoke test should state which GSD the delivered `.tif` has (pan-sharpened or multispectral).
- *Evidence.* My fetch of the 33 items.
- *Severity.* **minor.**
- *Fix.* A7: "GSD (`pan_gsd`, 0.43-0.71 m across the 33 scenes)". A3: "on real Vantor windows (pan GSD 0.43-0.71 m; confirm the delivered band set)".

## E. Wording that misleads a judge or ADB reader (not covered above)

**36. A13 U4: "B1 self-stated confidence" is tiered MODEL-ESTIMATED, and B0 is undefined for the flagship.**
- *Doubt.* B1 is the agent's self-report, not a model estimate. B0 (pooled keyed precision for the same family) does not exist for bridge damage, where there is no keyed family. A judge asking "did you beat B0 on Nepal?" gets no answer from A13.
- *Evidence.* A7 Baselines. A7 flagship paragraph.
- *Severity.* **minor.**
- *Fix.* "B1 is shown as 'self-reported', never as a trust tier. B0 is 'not computable (no keyed data for this family)' on the Nepal damage step."
