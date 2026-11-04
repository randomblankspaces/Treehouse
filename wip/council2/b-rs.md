# Council 2, round (b): RS rebuttal

## 1. Attacks (with evidence)

**A1. Every package plan except ADV's spends 20 h; ADV's 7.2 h is not credible either.**
STAT, OBS, AWS and my own a-rs §I7 are each about 20 h; I withdraw mine (C1). ADV §I7 gives 1.0 h for gateway plus all tools and 1.3 h for all of trust, while STAT sizes PPI, RG, sampling and controls at 4 h. The honest plan is about 9 h through the passport, with the demo skeleton by ADV's 04:30 checkpoint, which I adopt.

**A2. Nobody but me separates nominal from effective resolution. The evidence-sufficiency score is wrong without it.**
- OBS §I3 returns a single `gsd`. OBS Panel 1 says `evidence_sufficiency` means "GSD ≤ the card threshold". AWS §I3 says "downsampled to `max_image_px` (1024)".
- The resolution field in the Vantor items is `pan_gsd` (0.31–0.69 m). The `gsd` key in context.md does not exist; I fetched all 33 items.
- A 1 km window at 512 px is about 2 m effective on a 0.35 m scene, so a footbridge claim from it passes on `pan_gsd` while invisible. `effective_gsd_m = side_m / out_px` must be recorded and used by R5 and Panel 1.

**A3. "bytes read" has to be measured, and measurement has a trap nobody mentions.**
- OBS §I3 (`cog_reader.py`, "measured, not estimated") is right in principle.
- Tonight I ran `rasterio.open(url, opener=…)` (rasterio 1.5.2, GDAL 3.12.2) on B1300011011E5610. With **no block cache: 367 Range requests and 25 s for one 300 m window. With a 16 KB block cache: 5 requests, 81,920 bytes, 0.64 s.**
- A naive opener is 40 times slower and breaks the A8 N plan. The block cache and a "≤ 10 requests per 256 px window" test belong in the tools package.

**A4. ADV's demo-data choices.**
- (i) **Dialled outcomes** ("34 TP, 2 FP, 4 `cannot_assess`") prove the pipeline, not the method. Acceptable tonight; a pixel detector comes later.
- (ii) **A tile rendered without a COG** means `imagery_window`, the bbox check and `bytes_read` never touch a real raster in CI.
- (iii) **Synthetic points at real Bhote Koshi coordinates** can be misread as a bridge inventory. The label must sit on every row and in the CSV, not only in a banner.
- (iv) **The Nepal cloud trap cannot be keyed** (`mask: false` in event.json). `cannot_assess` is KEYED only through a per-scene `visible_in` field in a synthetic key, and neither ADV world has one.

**A5. Two places where a MEASURED tier would conflict with the spec.**
I support OBS's `MEASURED` tier for exact functions of a trace (cost, bytes, tool counts, grounding rate); otherwise these are bare floats, which ADV's own schema test rejects. But a replayed cost must carry `replayed=1`, and MEASURED never labels Panel 3: KEYED stays KEYED.

**A6. The AWS seat's P7 (CDK + moto + probe + OTLP, 2.5 h) does not belong overnight before the demo skeleton.**
I agree with ADV that CDK is out tonight. I side with AWS on **moto for S3, Stubber for Bedrock**: OBS's Stubber-only S3 cannot test version-delete denial or `IfNoneMatch`, and AWS ran both under moto 5.2.5. AWS's `AWS_ACCESS_KEY_ID=proxy-injected` finding makes the env scrub a P0 item.

**A7. What the replay demo runs.** In round (a) my `demo synth` re-ran the fake agents; ADV re-runs the pipeline from sealed records. ADV is right. The demo replays committed cassettes, re-seals and re-scores. **The tool cassette carries the recorded WindowResult, including `bytes_read`, `pixel_sha256` and `bbox_read`, so the replay needs neither rasterio nor pixels.** That settles ADV's rasterio-on-a-Mac worry. The rasterio-written synthetic COG is needed only when cassettes are recorded and in the geo tests.

## 2. Concessions

- **C1. Package plan.** I withdraw my 16 packages. My P2–P5 (geometry, STAC, imagery, synthetic world and Clay) collapse into one tools package. The order follows ADV: skeleton and demo first, checkpoint at 04:30.
- **C2. rasterio becomes the `[geo]` extra.** PyPI's rasterio 1.5.2 macOS wheels are `macosx_15_0` only, so macOS 14 falls back to a source build needing system GDAL. The demo replays without it (A7); CI installs `[geo]`.
- **C3. Module names**: adopt OBS's layout (`trace/`, `score/`, `checks/`, `tools/cog_reader.py`) and its import-boundary test. I add only `geo/` (geom.py, match.py) and `synth/`.
- **C4. Synthetic world**: one world, combining ADV's scripted policy set with my structure:
ADV's six policies (good, fabricator, key-peeker, looper, overconfident, budget-stop) beat my five. From mine come two steps (existence, then status), the cloudy `post_b`, the `visible_in` key and the `post_c` test-retest scene. Outcomes are scripted tonight; the pixel detector is a Should.
- **C5. PlainLoop is the Must-0 harness and the demo harness**, as OBS, ADV and STAT all say. Strands is a contract test with FakeModel; OBS has verified it runs offline.
- **C6. Socket guard**: OBS/ADV's monkeypatch, with loopback only under `@pytest.mark.localnet` (AWS), replacing pytest-socket.

## 3. Revised position (B = blocking for me)

1. **B.** Every `imagery_window` result records `nominal_gsd_m` (`pan_gsd`), `pixel_spacing_m` and `effective_gsd_m`. R5 and Panel 1 use the effective one.
2. **B.** `bytes_read` is measured by the counting opener with a block cache, and is tested with a synthetic COG plus a loopback Range server. In replay it is the recorded value, chipped MEASURED with `replayed=1`.
3. **B.** All rule evidence comes from WindowResults recorded by the gateway (`bbox_read`, scene id, scene datetime) and from footprints in the pinned STAC fixture. Nothing the agent asserts is used. Evidence-in-trace means **contains**.
4. **B.** A real Vantor STAC fixture (33 items, event, collection, `etags.json`, `LICENSE-DATA` CC-BY-NC-4.0, metadata only) is built **tonight**, since the bucket is reachable. `stac_search` returns per-AOI coverage fractions, and a golden test pins the Nepal scene list.
5. **B.** The synthetic key carries `visible_in[scene]`, so `cannot_assess` is graded KEYED in at least one task.
6. Geometry needs no shapely or pyproj at runtime. Shapely is a test oracle only. Keyed matching is one-to-one with `linear_sum_assignment` and per-class tolerances.
7. Nepal card: the Syabrubesi–Rasuwagadhi corridor from a-rs §5.2, smoke sub-AOI [85.33, 28.14, 85.37, 28.18], test-retest pair E5610/E5810. The passport says "pre/pre placebo unavailable (2 pre scenes, about 51 % overlap, 3–5-year gap)" unless hour-1 counting finds at least 10 pairs. AOI confirmed visually at K2.
8. Virginia: Sentinel-2 18STH, which is reachable and listable tonight. USPVDB is fetched at wake on the Mac. NAIP is out (requester-pays, 403).
9. India card is family `river-crossings-s2`, so the passport ABSTAINS from transfer.
10. **Overnight order (about 9 h; anything past the night slips to daytime):**

| # | Package | Hours |
|---|---|---|
| P0 | scaffold, guard, env scrub | 0.4 |
| P1 | schemas (incl. MEASURED), 4 cards, `validate` | 1.0 |
| P2 | store, tracer, seal, verify | 1.0 |
| P3 | gateway + tools (geo, STAC fixture, `cog_reader`, synthetic Clay, claims) | 1.6 |
| P4 | Fake/Replay providers, PlainLoop, `run --mode fake` | 1.0 |
| **P5** | **demo skeleton: synthetic world, scripted cassettes, `treehouse demo` replay (checkpoint 04:30)** | 0.8 |
| P6 | Bedrock provider (Stubber) | 0.6 |
| P7 | rules R1–R9, keyed matcher, Panels 1/2/3/5 | 1.2 |
| P8 | sampling, recorded verifier, PPI, B0–B2, abstain, passport | 1.5 |
| P9 | HTML report + lint | 0.8 |

    P6 sits before the rules so Kiro can run K3 at wake. In the daytime: Strands adapter, moto S3Store, MCP, RG, CDK.
