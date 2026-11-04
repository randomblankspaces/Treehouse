# ADV vote, round 1

**VOTE: ACCEPT**

## Why I accept although rows 2 and 3 go against me

- **Row 2 (Strands moves to W2).** D4 existed so that Kiro *runs* code and never *writes* it. That intent holds. K1 (probe), K2a (prices) and K3 (live keyed run with the plain loop on Bedrock) need only P6, which has a hard deadline: C2 pre-empts at 07:15 and P6 must be merged by 08:00. Strands is first needed by K4. K4 already waits for W1 (about 09:45) because real windows need the reader. Merging Strands earlier buys nothing in the morning, so I drop D4's Strands half.
- **Row 3 (trust core at 1.8 h).** STAT's rationale is evidence-based: wrong method tests came from rushing. P5 now ships a trust stub that reports `ABSTAINED: trust engine not yet built`. So if P8 lands late, the 08:00 demo is still honest, just incomplete. That is acceptable. A false number would not be.
- **My other blocking items are met.**

  | My item | Where it is met |
  |---|---|
  | D1 (demo before trust maths) | P5, gate C1 |
  | D2 (demo re-runs the pipeline) | row 20 and §5.3 |
  | D3 (synthetic labels) | §5.1 required display strings and test I5 |
  | D5 (not tonight) | rows 6, 7 and 16; W1–W15 |
  | D6 (no bare floats, chip invariant) | P1 walker and the never-cut list |

## Non-blocking suggestions (5)

1. **§7 C1 timing.** The planned path reaches P5 at H4.15 (0.25+0.8+0.6+0.6+1.2+0.7), before any review time. A checkpoint at H4.0 therefore fires by default and strips P7 down to R4 plus keyed precision. Replace with: "C1 (H4.5): P5 must be merged."
2. **§7 overnight total and §9 risk 2.** The total is 8.05 h, plus about 1.5 h of review passes, against a 7–8 h night. P8 will probably land after 08:00. Add to C3: "The 08:00 TODO.md states which of P7–P8 are merged. The README quickstart describes only what the merged demo shows, for example 'trust passport: stub' until P8."
3. **Row 6 and the `bytes_read` chip.** "MEASURED" on a number from a declared block model is not a measurement. Its hover text must read "SYNTHETIC: declared 512-px block model, not measured". The real MEASURED value arrives with W1.
4. **W2 and K4.** If W2 slips, K4 runs on the plain loop. The manifest `harness` field, the report and the demo script must then not claim Strands. Add to the K4 preamble: "If W2 is not merged, run with `--harness plain`; the demo narrative says 'Strands adapter: offline-tested only'."
5. **W0 (P9).** P9 carries the plain summary for the ADB officer, the Impact moment. Keep it first in the Wednesday queue and do not let W1 jump ahead of it. If the night has room, add a lint-free template fact table into P7 so the 08:00 report already reads in plain English.
