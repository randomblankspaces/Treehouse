# Council 2, round (b): STAT debate

Code: `proto/ppi2.py`, `proto/b_check.py` (numpy 2.5, scipy 1.18, R=300 seeded populations, 90% level).

## 1. Attacks

**A1. Two proposed method tests would fail a correct estimator, so the overnight agent would "fix" the estimator until it is wrong.**
- In `b_check.py` I replicated ADV's scenario: N=200, n_gold=24, verifier sensitivity .85 and specificity .80, true precision 0.8.
- Shuffling the verifier verdicts gives a PPI width of **0.34**. The default B2 width is **0.51**, centred at 0.5.
  - **ADV I6** asks for "shuffled → B2-equivalent width within 20%". The actual ratio is 0.67, so the test fails.
  - **OBS I6** asks for "width ≥ 0.9 × B2 and covers the B2 point". Both parts fail: the interval is about [0.63, 0.97], which does not contain 0.5.
- The right null reference is the **classical gold-only interval**. Gold validity does not depend on the verifier, so a useless verifier collapses PPI to the gold-only interval (slightly wider at λ=1), not to the no-information prior.
- What passes on a correct estimator:
  - PPI width ≥ 0.95 × the exact hypergeometric width: 0.344 vs 0.272.
  - Coverage holds: 0.877 at R=300. That is inside 2.3 standard errors of 0.90.

**A2. ADV's and OBS's PPI coverage tests have no power against the real bug.**
- The bug is the naive bootstrap without pseudo-disagreements, which under-covers when the verifier is good.
- In ADV's own 85/80 scenario the naive version scores **0.853**, so it passes ADV's ≥ 0.85 check.
- The failure only shows with a strong verifier. At .95/.95 the naive version gives **0.58** coverage; the fixed one gives 0.97.
- Whatever suite we adopt must include a strong-verifier scenario and a mutation test asserting that `pseudo_weight=0` fails it.

**A3. "PPI never wider than gold-only when the verifier is good" (ADV, OBS) is fragile.** At 85/80 the mean width is 0.256 vs 0.268 (4% narrower on average, often wider per run). With λ=1 and ~20 gold, narrowing is a reported finding. Assert it only as a mean in the strong scenario (0.176 vs 0.268).

**A4. RS P11 "study.py coverage in [0.85, 0.95]" over 200 full-pipeline seeds.** The upper bound rejects the conservative fixed interval (0.97–1.00 for strong and perfect verifiers), and 200 rasterio pipeline runs cannot fit in 10 s. Keep the estimator Monte Carlo at array level in CI and make `study.py` a `-m slow` report.

**A5. Rogan–Gladen abstain rules differ.** OBS uses se+sp−1 < 0.1 on the point estimate; ADV and I use 0.2. A point threshold ignores that the controls are only 15+15. Under "the α/2 quantile of the bootstrapped J ≤ 0.2", a weak verifier (J≈0.15) abstains in 98% of draws (`rg.py`). One rule, in `TrustConfig`.

**A6. Package count vs overnight hours.** My plan (~20 h), OBS (20 h) and AWS (~21 h) do not fit overnight; only ADV does (7.2 h for P0–P8, 04:30 demo checkpoint). But ADV's trust package (P7, 1.3 h) is too small for sampling, PPI, baselines, abstain, passport and real method tests; that is how A1/A2-type tests get written in a hurry.

**A7. OBS's MEASURED tier** is right: cost and Panel-1 numbers need a tier, which my round (a) missed. It must never label a trust estimand.

**A8. What the replay demo runs.** ADV is right: re-run from sealed records, never render pre-baked JSON. AWS's `replay … && report` and my round (a) are ambiguous. Check, score and trust must re-execute, with the passport recomputed from the committed seed and its hash golden.

**A9. Synthetic world.** RS `synth-crossings` is richer (accuracy comes from a real detector; post_c is a genuine test-retest pair) but needs rasterio COGs at runtime. ADV `synthetic-sites` is pure numpy. Statistically either works, because the estimators are validated at array level. ADV's synthetic points on the real Bhote Koshi corridor need a per-row synthetic chip, not only a banner.

**A10. Module names** conflict (`trace/` or `tracing/`, `score/` or `scoring/`, stats inside `score/`). What matters is that stats is a **leaf package** with an import-boundary test, so it can be frozen by source hash.

## 2. Concessions

1. **Spine before maths** (OBS risk 6, ADV checkpoint). I drop "stats early": I accept ADV's order with the demo skeleton first.
2. **Adopt ADV's overnight budget** (about 7.5 h, P0–P8). Rogan–Gladen, B0 beyond its closed form, cross-fit λ, Holm, permutation and the unreported-places frame generator move to Wednesday.
3. **MEASURED tier accepted**, with a validator: allowed only for `type ∈ {usd, seconds, bytes, tokens, count_of_events}` and Panels 1, 2 and 5. `select_tier` never returns it, and the passport rejects it.
4. **The demo world is ADV `synthetic-sites-v1` overnight.** RS synth-crossings and its post_c test-retest pair is Wednesday or Should. RS's real Nepal post/post twin (E5610/E5810, 30 s apart) is adopted for test-retest, with the caveat RS gives.
5. **Plain loop is the replay engine overnight; the Strands adapter (FakeModel) comes Wednesday morning before Kiro K3.** This deviates from A3 and is logged in the ADR.
6. **Use moto for S3 and Stubber for Bedrock** (AWS evidence: versioning, Object Lock and version-delete denial reproduced). It is a dev-only dependency.
7. Module names: I take ADV's tree, with one change: `stats/` as a leaf. I drop my separate `sampling/` package and use `verify/sampling.py`, provided it stays pure numpy.

## 3. Revised position: decisions I insist on

| # | Decision | Blocking? |
|---|---|---|
| S1 | PPI interval is the two-phase rescaled bootstrap with **half-weight pseudo-disagreements** in the variance only. The correction term is pooled across strata while n_gold < 50, and λ=1. The **exact hypergeometric gold-only interval** and the width ratio are printed beside it. | **Blocking** |
| S2 | Method-test specs:<br>- One-sided coverage check (≥ 0.86 at 90%, R=300) for 6 scenarios, including **strong and perfect** verifiers.<br>- Mutation test: `pseudo_weight=0` must fail.<br>- Shuffled-verifier reference is **classical, not B2**.<br>- No per-run "never wider" assertion.<br>- Narrowing asserted only as a mean in the strong scenario.<br>- No upper coverage bound.<br>- All array-level, `-m method` < 6 s; full-pipeline studies `-m slow`. | **Blocking** |
| S3 | Gold drawn from **all** sampled units, including abstentions. Abstention is a third predictor category. The gold draw is committed before the first verdict, and `select_tier` downgrades if not. | **Blocking** |
| S4 | The trust core is **inside the overnight set**, after the P5 demo checkpoint, sized at 1.8 h, not 1.3. It covers: sampling with stored π, gold draw, PPI and classical, B2 default, B1, tier ladder, the estimators-disagree rule and the passport, with the S2 tests. | **Blocking** |
| S5 | The demo re-executes check, score and trust from sealed records with committed seeds. The passport hash is golden. Synthetic runs show a "truth reveal" row (true value vs interval), labelled SYNTHETIC. | Non-blocking (strongly preferred) |
| S6 | The Rogan–Gladen abstain rule is the α/2 quantile of the bootstrapped J ≤ 0.2. It applies to existence only, and damage-state estimands raise an error. Wednesday. | Non-blocking |
| S7 | `stats/` is a leaf package, with an import-boundary test and an `estimators.lock` source hash plus a version-bump test. | Non-blocking |
| S8 | MEASURED tier is limited to Panels 1, 2 and 5 by a validator. | Non-blocking |
