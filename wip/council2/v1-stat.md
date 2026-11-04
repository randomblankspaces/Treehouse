# STAT vote, round 1

**VOTE: REJECT.** Two blocking items. Each is a one-line text fix, and I will ACCEPT as soon as both are in.

I checked §6's PPI against `proto/ppi2.py`: the point estimate, pseudo-units, s_y², V, the bootstrap rescale and the t fallback all match. M1–M4, M6–M16, the tier ladder, the gate and rows 8–12 and 27 are fine.

## Blocking

**B1. Row 26, and §10 item 4: a human `cannot_assess` label counts as y=0, but the headline is still called "precision".**
- With y=0, the estimand becomes *verifiable* precision. That is a lower bound on true precision, not precision.
- Labelling it "precision" is a false claim, even though it errs in the conservative direction.
- I am not asking for those units to be dropped from G. Dropping them is non-random missingness and would break the design.
- Replacement text for row 26, Choice column:
  > Human `cannot_assess` is y=0 in the headline estimand, which is named `verified_precision` (chip text: "share of claims a blind human could confirm; lower bound on precision"). The passport also reports `n_gold_cannot_assess` and an upper-bound alternative that uses the same machinery with y=1 for those units (`precision_upper_if_unassessable_correct`, excluded from the disagreement check). When `n_gold_cannot_assess` = 0 the two coincide and the estimand is named `precision`.
- Matching change in §10 item 4: "…counts as 'not verified' (lower bound) for `verified_precision`, with a y=1 upper bound and the count reported."
- Cost: one extra `ppi_mean` call.

**B2. §7, test M5: the mutation threshold sits on the knife edge, so a correct implementation can fail it.**
- I reproduced M5 exactly (`proto/v1_m5.py`: g=20, N_h=20×3, abstention in stratum 3 at 0.5 when y=0 and 0.2 when y=1).
- The drop-abstentions mutation gives |bias| = **0.041**. With N_h=40×3 and g=30 it gives **0.039**. The threshold is 0.04.
- Small implementation differences flip the outcome, and the agent would then "fix" the estimator to make the test pass.
- With abstention at 0.6 when y=0 and 0.1 when y=1, the correct estimator holds coverage at 0.893 and bias −0.007, while the mutation shows bias 0.063 (seed 16) and 0.057 (seed 99).
- Replacement text for the M5 row, Test column:
  > abstention as a third category: in stratum 3, P(abstain) = 0.6 when y=0 and 0.1 when y=1; plus a mutation that draws gold only from non-abstained units
- Replacement text for the M5 row, Pass column:
  > coverage ≥ 0.86; mutation |bias| > 0.04

## Non-blocking (max 5)

1. **M2: widen the margin.** In `ppi2.py` the naive estimator scores 0.76 in the strong scenario against a < 0.80 threshold. Add a strong .95/.95 case with no abstention, where it scores 0.58, and require < 0.80 on either perfect or that case.
2. **Say plainly when PPI did not help.** When `width_ratio_vs_classical` ≥ 1, the passport should print "the verifier did not narrow the interval at n_gold=k" rather than leave only the ratio in `detail`. This is commitment 2 in spirit.
3. **Verify the census condition.** The classical `hypergeom_exact` comparator should be used only when every stratum is a census (n_h = N_h). Otherwise a stratified exact interval is wrong. Assert this in code.
4. **Put the rule in the gate text.** The gate's Rely rule should name `verified_precision` (from B1), so a gate threshold is never compared against the upper-bound variant.
5. **Freeze before K4, with a check.** `estimators.lock` (W13) should be frozen before K4. Add a CI check that K4's passport `code_sha` equals the lock.
