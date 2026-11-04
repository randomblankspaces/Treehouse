# ADV vote, round 2

**VOTE: ACCEPT**

No blocking objections.

I checked the round-1 fixes against scope, hours, the demo by 08:00, and claims.

- **Claims.** These changes make the claims more honest:
  - STAT-B1: the headline is renamed `verified_precision`, it is a lower bound, and it gets a y=1 upper bound.
  - RS-B1: a "modelled bytes" chip.
  - RS-NB1: a SYNTHETIC chip on Nepal WindowResults.
  - STAT-NB2: the passport says when PPI did not narrow the interval.

  My NB2–NB4 were adopted word for word (C3 README honesty, Strands fallback wording). No new overclaim appears.
- **Demo by 08:00.** Unchanged. C1 is now H4.5 and the P5 skeleton still comes before any trust maths. C2 still forces P6 by 08:00. The AWS-B1 ledger reservation adds a few lines to P6. It also makes the K1 probe safe to run at $0 known price, which protects the morning.
- **Scope.** OBS-B1/B2 (image-hash key equality, hashing the decoded array) and the P8 additions are tests plus small code. They are correctness fixes, not new features. Nothing from my not-tonight list (D5) has crept back in.
- **Hours.** The total still reads 8.05 h, but P4 (1.2 h) and P8 (1.8 h) have absorbed extra acceptance tests without re-estimation. This is a schedule risk, not a correctness one. The cut order covers it.

## Non-blocking suggestions (2)

1. **§7 cut order.** Add: "If C1 fires, the overview-aware block model (RS-B1) moves to W1. The synthetic source keeps the 'modelled bytes' chip with `bytes_model: flat-v0`, so the numbers stay labelled."
2. **§7 P8.** If the night runs short, the `verified_precision` upper-bound alternative may render as "upper bound: pending (P8b)". The lower-bound headline and its rename are never cut.
