# RS vote, round 1

VOTE: REJECT. There is one blocking objection, and the fix is one sentence. I accept moving the real COG reader to W1 (⚔ row 6), as long as W1 runs before any real-pixel run (K2b, K4), as stated.

## Blocking

**B1. §0 row 6 and §3 imagery table (`SyntheticImagerySource`, "512-px × 3-byte block model"): with no overview selection, the model reverses the data-touched comparison.**

Why. A real COG read picks an overview from `out_px`, so a coarse wide window costs about the same as a fine small one. I measured this tonight on B1300011011E5610 with the counting opener and 16 KB cache:

| Window | Bytes read | Requests |
|---|---|---|
| 60 m / 128 px | 98,304 | 6 |
| 1000 m / 256 px | 114,688 | 7 |
| 1000 m / 2048 px | 1,261,568 | 77 |

A native-resolution 512-px, 3-byte model predicts about 0.8 MB for `good`'s 60 m window and about 28 MB (36 blocks) for `skimmer`'s 1000 m / 256 px window: about 35× more, where the real reader measures 1.2×.

Panel 5 and test I3 would then show the demo saying skimmer "touches far more data", which is false. The with/without-Clay comparison of bytes touched would be distorted the same way. These numbers are chipped MEASURED, so a reader would take them as fact.

Replacement text for the row 6 "Choice" cell, and the same words in the §3 imagery Sources cell:

> Tonight `SyntheticImagerySource` reports `bytes_read` from a declared, GDAL-like block model:
> - overview level `L = max(0, floor(log2(native_px_per_side / out_px)))`, with overviews 2, 4, 8, 16 declared on every synthetic scene;
> - count the 512-px blocks intersected **at level L**, plus a fixed 16 KB header on the first read of each scene;
> - multiply by a declared mean compressed block size of 48 KB.
>
> Every WindowResult carries `reader="synthetic-v1"` and `detail.bytes_model="synthetic-overview-block-v1"`. Chips read MEASURED, SYNTHETIC ("modelled bytes").
>
> I3 adds two checks, to be replaced by real numbers in W1:
> - `bytes(skimmer 1000 m/256 px) ≤ 2 × bytes(good 60 m/128 px)`;
> - `bytes(1000 m/2048 px) ≥ 8 × bytes(1000 m/256 px)`.
>
> W1 adds a calibration test: on the synthetic DEFLATE COG, the real reader's bytes for these three windows keep the model's order.

## Non-blocking suggestions (max 5)

1. **§5.2 `nepal-good`.** Its obscuration values and `bytes_read` are invented for real Vantor scene ids. Put `synthetic: true` on each WindowResult row in the report's claim and evidence table, not only in the banner.
2. **W1.** Add `treehouse fixture check-etags`, which HEADs every pinned .tif and compares it with `etags.json`. Run it before K2b.
3. **K2b.** Run the smoke test at three effective GSDs on the same E5610 points (0.35, 0.7 and 1.4 m). That grounds the R5 class limits in measurement.
4. **§5.1.** Make SYN-POST-C's footprint identical to A's ("as A") explicitly in the key. Then the 4 western-strip crossings are `visible_in` false there too.
