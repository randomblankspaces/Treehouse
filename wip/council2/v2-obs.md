# Vote, round 2: OBS

**VOTE: ACCEPT**

## My round-1 blocking items, checked in the r2 text

- **OBS-B1 is resolved.**
  - §3 gateway step 9 now attaches the same `Image(format, sha256, bytes_=None)` for recorded and pixel-free sources, and `key()` is identical with or without bytes.
  - §2 `model_io` adds `MissingPixels` for live providers.
  - The acceptance test is in P3: a live-recorded key equals its pixel-free replay key, and a live provider refuses a byte-less image.
- **OBS-B2 is resolved.**
  - §2 states that `Image.sha256` and `pixel_sha256` hash the decoded C-order uint8 array plus its shape.
  - Encoded PNG bytes are transport only (§3 imagery table).
  - The re-encode test is in P4.

## Other seats' fixes: no new blocking problem

- **AWS-B1:** the probe now goes through `SpendLedger.reserve` with a $3 cap and placeholder prices tagged `estimated: true`. That keeps the cost of record honest. Probe spend never reaches a scorecard.
- **STAT-B1:** the `verified_precision` lower bound plus a y=1 upper-bound alternative is a correct label. The gate uses only the lower bound.
- **STAT-B2:** the M5 change is test-only.
- **RS-B1:** the overview-aware block model is deterministic, a pure function of `side_m` and `out_px`. Golden heads stay stable, and the "modelled bytes" chip keeps Panel 5 honest.

## Non-blocking

1. **Pixel-hash scope.** For `CogSource` (W1), the decoded array of a JPEG-compressed Vantor COG still depends on the GDAL or libjpeg build (RS's caveat). State in §9 risk 10 that `pixel_sha256` is environment-scoped for real COGs. Replay is unaffected, because the replay key uses the recorded sha, not a re-read.
2. **Lint coverage of the "did not narrow" sentence.** Make sure the STAT NB2 sentence ("the verifier did not narrow the interval at n_gold=k") is emitted as a fact slot, so the summary numbers lint can check it.
