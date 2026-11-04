# Vote, round 2: AWS seat

VOTE: ACCEPT

## My blocking item is resolved

**AWS-B1 is resolved.** The probe's live Bedrock calls are now covered by the spend ledger. It is in three places:
- §3 `SpendLedger`, lines 297–298.
- §7 P6, both the contents cell and the acceptance cell.
- §0, the round-1 table.

What the text now says:
- Every probe call goes through `reserve(..., unpriced_cap_usd=0.25)` with `max_tokens ≤ 32`.
- The probe stops at a $3 total cap and reports the remaining checks as `skipped_budget`.
- Each call is committed at the `probe-ceiling.yaml` price and tagged `estimated: true`.
- A Stubber test shows that no Converse call happens without a reservation, and that the probe stops at the cap.

My round-1 non-blocking suggestion NB1 (keep the ledger in the repo during Kiro sessions) was also adopted, in §4 and in the §8 preamble.

## Other seats' fixes, checked for AWS-side regressions

I found no new blocking problem.
- **OBS-B1 (`MissingPixels`).** The image attached to the live K3 run comes from the synthetic render in `PixelCache`, so its bytes are present. The probe sends its own synthetic PNG and never goes through the gateway. Live calls therefore never see a byte-less `Image`.
- **OBS-B2 (decoded-array hash).** This keeps cassette keys stable across zlib and GDAL builds. That supports the Kiro-recorded, judge-replayed path, which is what I wanted.
- **RS-B1 (modelled bytes).** This is a chip and tag change only. It does not affect cost or the ledger.
- **STAT-B1 and STAT-B2** have no AWS impact.

## Non-blocking suggestions

1. **Add the missing price file to the §1 tree.** The `config/` line should list `prices/probe-ceiling.yaml`. Its placeholder prices should be deliberately high (for example $0.02 per 1k input tokens and $0.10 per 1k output tokens) and should say so in a comment.
2. **Exclude `.spend/` from the licence and pixel scan, but keep it tracked.** It must not be gitignored, and `.gitignore` should state that so nobody adds it later.
