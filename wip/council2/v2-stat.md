# STAT vote, round 2

**VOTE: ACCEPT**

## My blocking items are resolved

**STAT-B1 (the precision label).** Resolved in four places:
- **§0 row 26 and §2.** The `Estimand.kind` field now includes `verified_precision`. The passport carries `n_gold_cannot_assess` and the y=1 alternative, `precision_upper_if_unassessable_correct`, which is excluded from the disagreement check.
- **§3 PPI (line ~430).** A second `ppi_mean` call is made with y=1, and the estimand is named `precision` when no gold label is `cannot_assess`.
- **Gate (line ~465).** It names `verified_precision` and never uses the upper bound.
- **P8 acceptance.** It checks the naming rule and that the upper bound is at least the headline.

**STAT-B2 (the M5 knife edge).** Resolved in §6 M5: abstention is now 0.6 when y=0 and 0.1 when y=1, and the mutation draws gold only from non-abstained units. My reproduction (`proto/v1_m5.py`) gives:
- correct estimator: coverage 0.893, bias −0.007;
- mutation: |bias| 0.057–0.063, which clears the 0.04 threshold.

My non-blocking items NB2 (the "did not narrow" note) and NB3 (the hypergeometric comparator only under a full census, asserted in code) were also adopted.

## Other seats' fixes

None of them introduces a statistical problem:
- **AWS-B1** (probe spend reservation): no effect on estimators.
- **OBS-B1/B2** (image-hash keys on decoded arrays): these make the golden passport hash more stable, not less.
- **RS-B1** (overview-aware byte model): this changes a MEASURED Panel 5 number only, and it is chipped "modelled bytes".

## Non-blocking

1. **Disagreement rule (§3).** Compare only intervals of the same estimand kind. On a keyed step with gold, KEYED `precision` and PPI `verified_precision` can fail to overlap simply because human `cannot_assess` labels count as y=0. Suggested text: "Disagreement is checked only between estimates of the same `Estimand.kind`; when the headline is `verified_precision`, KEYED precision is compared against `precision_upper_if_unassessable_correct` ∪ headline (the union interval)."
2. **M14.** Add one EvidenceBundle row in which `n_gold_cannot_assess` > 0, to pin the naming rule in the tier tests.
