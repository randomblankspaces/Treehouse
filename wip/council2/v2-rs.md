# RS vote, round 2

VOTE: REJECT. There is one blocking item, and it is an erratum in my own RS-B1 text. Every other RS item is resolved: the overview-aware model, the `bytes_model` tag, the "modelled bytes" chip, the W1 calibration, and NB1. The fixes from the other seats (OBS-B1/B2, AWS-B1, STAT-B1/B2) introduce nothing that breaks the geo side.

## Blocking

**RS-B1-erratum (§6 I3 and §0 row 6, "I3 order checks").** I ran the block model as now specified on the design's own world (2400 px scene, 0.5 m, 512 px blocks, overviews up to 16). At the scene centre the block counts are:

| Window | Level L | Blocks |
|---|---|---|
| good, 60 m / 128 px | 0 | 1 |
| skimmer, 1000 m / 256 px | 2 | 4 |
| 1000 m / 2048 px | 0 | 25 |

Across 2,000 random centres, the worst-case ratios are skimmer/good = 4.0 and 2048/skimmer = 4.0. The checks I wrote (≤ 2× and ≥ 8×) therefore **fail for a correct implementation**. That would stall P4, or invite the agent to "fix" the model.

Replace the I3 order-check sentence with:

> Order checks, on block counts with the scene header excluded, for any window centre fully inside the scene (replaced by real numbers in W1):
> - `blocks(skimmer 1000 m/256 px) ≤ 4 × blocks(good 60 m/128 px)`;
> - `blocks(1000 m/2048 px) ≥ 4 × blocks(1000 m/256 px)`;
> - at the scene centre, the exact counts are 1, 4 and 25.

This keeps the honest claim: a 70× larger area costs at most 4× more, not 35×.
