# Council 2, round (a): RS (remote-sensing scientist) implementation proposal

Centre of gravity: the geo tools, geometry, deterministic rules, keyed matching, task cards and an offline synthetic keyed world. Everything else is covered more briefly but in full (I1–I9).

## 0. Facts I measured tonight (they change the implementation)

From this container, 2026-11-04 ~00:30 EST. Scratch scripts are in my scratchpad.

1. **The Vantor visual COGs are EPSG:4326**, so windows need no reprojection: 3-band uint8, 512 px tiles, YCbCr JPEG q75, overviews 2–258, nodata unset (black collar), pixel spacing ≈ 0.343 × 0.345 m at 28.16 N, 1–1.6 GB each. **The GSD field is `pan_gsd` (0.31–0.69 m), not `gsd`.** Items also carry `view:off_nadir`, `view:sun_elevation`, `vehicle_name`, `phase` (pre/post) and the scene-level `eo:cloud_cover`. The bucket listing gives a pinnable **ETag per .tif**.
2. **Byte counting works with `rasterio.open(url, opener=...)`** (rasterio 1.5.2, GDAL 3.12.2): a Python file object issues the Range GETs and counts bytes. With no block cache, one window took **367 requests and 25 s**. With a 16 KB block cache, a 300 m window at 256 px took **5 requests, 81,920 bytes, 0.64 s**. The block cache is mandatory, and "bytes read" means bytes fetched, reported with the block size.
3. **Sentinel-2 L2A COGs and item JSONs on `sentinel-cogs` (us-west-2) are reachable** and listable; tile 18STH covers central Virginia. Blocked: NAIP (403, requester-pays), USGS/USPVDB, Planetary Computer, Earth Search, Overpass, source.coop and Hugging Face.
4. **Vantor has no India event** (12 events in the catalog), so the India stub uses Sentinel-2.

## I1. Repo and module layout

`src/treehouse/` subpackages: `schemas/`, `geo/` (geom.py, match.py), `tools/` (stac.py, imagery.py, rangeio.py, obscuration.py, clay.py, claims.py, servers.py), `gateway/`, `providers/`, `harness/`, `tracing/`, `store/`, `checks/` (rules.py, keyed.py, ledger.py), `verifier/`, `trust/`, `scoring/`, `report/`, `synth/` (world.py, agents.py, study.py), `cli.py`, `mcp_read.py`. Top level: `tasks/` (4 cards), `fixtures/stac/vantor-nepal-aug-2026/` (33 items, collection, event, etags.json, `LICENSE-DATA` CC-BY-NC-4.0, metadata only), `fixtures/stac/sentinel2-18STH-2024-06/`, `keys/` (synth/, uspvdb/, osm/; outside every tool root), `scripts/` (build_vantor_fixture.py, build_s2_fixture.py, fetch_uspvdb.py, fetch_osm_bridges.py).

**Dependencies.**
Runtime: pydantic, numpy, scipy, httpx, pyyaml, typer, mcp, strands-agents, **rasterio** (wheel bundles GDAL and PROJ). Extras: `[aws]` boto3, `[clay]` pyarrow. Dev: pytest, pytest-socket, hypothesis, shapely (test oracle only).

**Geometry decision: no shapely and no pyproj at runtime.** Claims are points (plus an optional bbox). Footprints and AOIs are polygons or multipolygons. Keys are points, linestrings (OSM bridge ways) or polygons (USPVDB). That needs only ray-casting point-in-polygon with holes (boundary inside, ε = 1e-10°), bbox containment, haversine, and point-to-segment distance in a local equirectangular frame (error < 0.1 % under 20 km): about 120 lines. For Sentinel-2 UTM windows, `rasterio.warp.transform_bounds` uses rasterio's bundled PROJ, so pyproj is never needed. Shapely appears only in hypothesis tests as an oracle (`pytest.importorskip`).

## I2. Core schemas: the geo-relevant fields

The trace, typed-number and passport schemas are the shared council core. My additions:

- **TaskCard** (A2, plus): `event: {date, footprint_ref}`; `as_of`; `imagery_sources: [{source_id, kind: static_catalog|s3_listing, fixture_path, item_ids[], etags{}, license}]`; `classes: {name: {min_size_m, max_effective_gsd_for_existence_m, max_effective_gsd_for_status_m, match_tolerance_m, key_geometry: point|line|polygon}}`; `windows: {max_side_m: 1500, max_out_px: 1024, max_bytes_per_run}`; `smoke_aoi`.
- **Claim**: `id`, `geometry` (GeoJSON Point), `class`, `status` ∈ {present, absent, intact, damaged, destroyed, cannot_assess}, `confidence`, `reason`, `evidence: [{tool_result_id, role: pre|post|existence}]`. The agent never supplies scene ids or bboxes; they are resolved from gateway-recorded tool results.
- **WindowResult** (the gateway's record of every `imagery_window`):
  - identity: `result_id`, `source_id`, `scene_id`, `etag`;
  - space: `bbox_requested`, `bbox_read` (snapped to pixel edges), `footprint_coverage_fraction`;
  - time: `scene_datetime`, `phase`;
  - resolution: `nominal_gsd_m` (pan_gsd), `pixel_spacing_m` (from the transform with cos φ), `effective_gsd_m` (= side_m / out_px, the number that decides what is visible), `overview_level`;
  - acquisition: `scene_cloud_pct`, `off_nadir_deg`;
  - integrity and cost: `out_shape`, `resampling`, `pixel_sha256`, `bytes_read`, `requests`, `block_size`, `gdal_version`;
  - obscuration: `{bright_lowvar_fraction, nodata_fraction, method: "heuristic:v1"}`;
  - `license`, `pixels_ref` (private cache path, never in the run dir).
- **CheckLedger rows**: `{claim_id, layer: rule|key|verifier|human|overlap, check_id, version, result: pass|fail|flag|n/a, detail}`.

## I3. Interfaces and implementations: the geo tools

### `stac_search` and `scene_info`

`StacSource` protocol: `search(aoi, datetime_range, as_of) -> [SceneSummary]` and `get(scene_id) -> Scene`.

**`StaticCatalogSource`** (default, offline) reads `fixtures/stac/<source>/items/*.json`.
- **Discovery filter:** bbox prefilter, then exact intersection of the footprint polygon with the AOI by sampling (polygon-polygon intersection without shapely: any AOI vertex in the footprint, any footprint vertex in the AOI, or any edge crossing; O(n·m) on fewer than 800 vertices is fine).
- **Date filter:** `datetime ≤ as_of` and inside the task's `time_window`.
- **Allow-list:** only the card's pinned `item_ids`.
- **Returned fields:** id, datetime, phase, scene cloud %, pan_gsd, off-nadir, sun elevation, footprint, and **`aoi_coverage_fraction`** (30×30 grid sampling, the same code I ran tonight).

**`S3ListingSource`** (live, Should) builds the same summaries from a bucket listing plus item JSONs. It is used for Sentinel-2 and for re-pinning ETags. `scripts/build_*_fixture.py` turns the live source into a static fixture with ETags. **The Vantor fixture is built tonight**, since the bucket is reachable.

`scene_info(scene_id)` returns the full metadata, including the asset href and ETag.

### `imagery_window(scene_id, center | bbox, side_m, out_px ≤ 1024, resampling="average")`

1. **Pre-checks**, each a typed `ToolError(code)`: `not_allowed` (scene not pinned), `not_available_as_of`, `no_coverage` (centre outside the footprint polygon), `out_of_bounds` (fully outside the raster), `window_too_large`, `budget_exceeded`.
2. **Read** through `rangeio.RangeFile`: httpx, a 16 KB LRU block cache keyed by (url, etag), `If-Match: <etag>` on every GET (412 → `snapshot_changed`), backoff on 5xx. Local paths use a counting file object through the same opener. `rasterio.open(href, opener=...)`, then `from_bounds` (transformed with `rasterio.warp.transform_bounds` when the CRS is not 4326), then `read(window, out_shape, resampling, boundless=False)` after clipping to the raster. GDAL picks the overview, and we record which one.
3. **Post-processing**: partial windows are clipped and report `footprint_coverage_fraction` (< 0.5 → `insufficient_coverage`); `nodata_fraction` = all-zero RGB (black collar); obscuration heuristic; pixel hash = SHA-256 of the C-order uint8 array plus shape.
4. **Return**: MCP ImageContent (PNG) to the model and structured content (the WindowResult minus `pixels_ref`) to the trace. Pixels go to `~/.cache/treehouse/pixels/<sha>.png`, mode 0600 and gitignored. The trace stores the hash only.

**Caveat.** The Vantor COGs are JPEG-compressed, so decoded pixels, and therefore hashes, can change with the libjpeg or GDAL build. `gdal_version` goes in every result, and pixel-hash equality is asserted only within one environment. The synthetic COGs use DEFLATE, so their hashes are stable everywhere.

### Obscuration heuristic v1

For the window:
- `bright_lowvar_fraction` = the share of pixels with min(R,G,B) ≥ 200 **and** a local 5×5 std of the grey image < 6;
- `nodata_fraction` as above.

Labelled `heuristic:v1`; validated before any rule uses it: on synthworld masks (fraction error ≤ 0.03, IoU ≥ 0.85); in the morning against the Sentinel-2 **SCL band** (classes 8–10) on 18STH windows, the one real per-pixel cloud reference we can reach; on Nepal via an "obscured?" checkbox in the human gold labels.

**Known false positives**: snow and glacier above Rasuwagadhi, bright gravel bars and new debris fans. The heuristic can only raise a flag, never decide (A5).

### `clay_search(aoi, query: {cell_id | lonlat | vector}, k)`

`EmbeddingIndex` loads either `npz {ids, lon, lat, date, cell_m, emb[N,D]}` or GeoParquet through pyarrow. The real LGND column names are UNVERIFIED, so the loader takes a column map in the card.

- Scoring: cosine similarity over cells whose centre is inside the AOI, computed with numpy.
- Returns ranked `{cell_id, center, similarity}` plus a **coverage report**: `source`, `cell_m`, `date_range`, `predates_event`, `aoi_cells_expected` vs `aoi_cells_present`, `smallest_resolvable_m` vs each class's `min_size_m` ("cannot resolve footbridges"), `synthetic`.

Tests use synthetic vectors only (source.coop is blocked): planted clusters recovered at recall ≥ 0.9, missing-cell reporting, the date flag, dimension mismatch as an error.

### Other tools

- `record_claim` and `note_limitation` as in A3.
- **`key_lookup` exists only as a forbidden decoy** in synthworld, to exercise the leak path.

## I4. Storage layout (geo parts)

`runs/<id>/trials/<k>/trace.jsonl` (WindowResults inline, no pixels); `runs/<id>/claims.jsonl` frozen at seal; `evals/<run_hash>/<scorer_ver>/ledger.jsonl`. Pixels only in private `~/.cache/treehouse/pixels/` (S3: separate private prefix). The gateway refuses any path under `keys/`, and a test asserts it.

## I5. CLI, API and MCP surface (geo commands)

- `treehouse task validate` checks: valid AOI polygon (no self-intersection), AOI intersects an allowed scene, every item id resolves with an ETag, license floor, per-step `keying`, non-empty `forbidden_sources` for keyed steps.
- `treehouse scenes <card>` prints the coverage table in §5.2, derived not hand-written.
- `treehouse synth build --seed N`.
- `treehouse demo synth` runs the full offline pipeline.
- Tool MCP servers run in-process for tests and over stdio for real runs. The read-only results MCP is shared council design.

## I6. Test strategy (geo focus)

**Offline guarantee.**
- pytest-socket with `--disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1` in `pyproject` addopts.
- Live tests are marked `@pytest.mark.live` and deselected by default. Two are allowed: a Vantor window read on the Syabrubesi smoke AOI, and the Sentinel-2 listing.

**Synthetic COG fixture** (session-scoped, generated at test time, about 0.2 s): 512×512 3-band uint8, EPSG:4326, bbox [0, 0, 0.0025, 0.0025] (≈0.54 m), DEFLATE, 256 px tiles, overviews 2/4/8 (rasterio `driver="COG"`, verified tonight). Contents: analytic pattern (R = col % 251, G = row % 241), a planted 120×120 white "cloud", a black collar triangle, and a footprint polygon excluding the collar.

**imagery_window tests**:
1. A native-resolution read equals the analytic array exactly, by hash, and `bbox_read` is within half a pixel of the request.
2. `bytes_read` > 0, < the file size, and monotone: a smaller window reads ≤ bytes, and an overview read (large side, small out_px) reads fewer bytes than full resolution.
3. A loopback `ThreadingHTTPServer` with a 30-line Range handler gives the same hash as the file path. `bytes_read` equals the sum of the served Content-Lengths. A wrong ETag gives `snapshot_changed`.
4. `no_coverage` for a point in the bbox but outside the footprint; `out_of_bounds`; partial-window clipping with a correct coverage fraction; `not_available_as_of`; `window_too_large`; `budget_exceeded` through the gateway meter.
5. Obscuration: the planted block gives a fraction within ±0.02; a bright high-variance texture gives below 0.05; a dark uniform window gives 0; the collar shows in `nodata_fraction`, not in obscuration.
6. Determinism: the same call twice gives the same hash and the same bytes when the cache is cold.

**STAC tests**: on the real Vantor fixture, `search(nepal_aoi)` returns the §5.2 golden list; `as_of` = 2026-09-01 drops later scenes; `phase` agrees with `event_date`.

**Geometry and matching property tests** (hypothesis): PIP agrees with shapely (boundary excluded); haversine symmetric and triangle-inequal; local point-segment distance within 0.1 % of densified haversine; matching is permutation-invariant, every pair within tolerance, cardinality equals brute-force maximum bipartite matching for n ≤ 7, and a far-away extra claim changes nothing.

**Rules golden tests**: one hand-built claim per rule outcome, including the "fetched any window, cited it" weakness. That case passes evidence-in-trace by design and is recorded as such.

## A5 deterministic rules and keyed matching (what `checks/` implements)

Every rule takes only (frozen claims, sealed trace, card, pinned fixture), never agent-supplied metadata.

- **R1 schema**: the claim parses and its class is in the card.
- **R2 inside AOI**: PIP on the card AOI.
- **R3 inside cited footprint**: for each evidence ref, the claim point is in the scene's fixture footprint (not the window's).
- **R4 evidence-in-trace**: each `tool_result_id` is an earlier `imagery_window` result in this trial whose `bbox_read` **contains** the claim point (optional `edge_margin_m`; all vertices for polygon claims). Otherwise `fabrication` (no such result) or `ungrounded` (does not contain).
- **R5 evidence sufficiency**: existence needs `effective_gsd_m ≤ max_effective_gsd_for_existence_m`, status `≤ max_effective_gsd_for_status_m`; a Clay hit alone never suffices.
- **R6 post-event footprint**: `intact/damaged/destroyed` needs at least one evidence window whose scene has `datetime > event.date` and whose footprint contains the point. `cannot_assess` is exempt.
- **R7 date logic**: cited scenes `≤ as_of` and inside `time_window`; `pre` before the event, `post` after; `damaged/destroyed` without pre evidence is a *flag*, not a fail (Nepal pre scenes are 3–5 years old); the pre-to-post gap is recorded as a covariate.
- **R8 forbidden and budget**: comes from gateway spans.
- **R9 obscuration flag**: status claimed on a window with `bright_lowvar_fraction` > 0.3 → flag only.

**Keyed matching** (`geo/match.py`):
- **Per-class distance**: point–point haversine; point–line uses the local-ENU segment distance to an OSM bridge way; point–polygon is 0 if inside, else the distance to the boundary.
- **Feasible pairs**: distance ≤ `match_tolerance_m` and the key item is inside `key_coverage_mask`. A grid hash with cell = tolerance avoids O(nm).
- **Assignment**: one-to-one, per connected component, with `scipy.optimize.linear_sum_assignment` on cost = distance, infeasible pairs = 1e9. This maximises cardinality first, then minimises total distance. Ties are broken by sorted ids, so the result is deterministic.
- **Outputs**: TP, FP (to adjudicate when the key is incomplete), FN; `cannot_assess` excluded from the precision denominator and reported as coverage loss; status accuracy on matched pairs; cluster bootstrap by scene or 1 km block.
- **Tolerances** (in each card's `match_rule`): Nepal bridges 20 m to the way; Virginia solar inside the polygon or ≤ 60 m; synthetic crossings 6 m.
- **Leak detector hook**: a TP whose claim has no R4-valid evidence is a probable leak.

## A12 / I7 task cards to ship

### 5.1 Synthetic keyed demo, `synth-crossings`: fully offline, the demo and trust-validation substrate

**`synth/world.py`** (seeded) builds a fictional 1.2 km × 1.2 km AOI at [0, 0, 0.0108, 0.0108]. It is labelled SYNTHETIC in the card, the STAC fixture and every report. It has a dark meandering river, 40 "crossings" (bright 8×30 px decks), 15 off-river bright distractors (real false positives) and low-frequency terrain texture.

**Scenes** (0.5 m DEFLATE COGs, real-shaped STAC items with pan_gsd, cloud % from the mask, footprints): `pre` (clear); `post_a` (about 25 % of decks damaged, middle third removed); `post_b` (70 % cloud, footprint covers 80 % of the AOI, exercising `no_coverage`); `post_c` (`post_a` re-rendered with a 3 px shift and new noise: the test-retest pair).

**Key** (`keys/synth/`): id, point, class, status, `visible_in[scene]` from the cloud mask (so **the cloud trap is KEYED here** and `cannot_assess` is gradable as correct), plus 3 canary decoys at empty coordinates.

**Embeddings**: 64 m synthetic cells. River cells sit near a prototype vector; the coverage report says synthetic, predates the event, cell 64 m.

**Scripted worker policies** emit real tool calls through FakeModel into the Strands harness, or the plain loop if the Strands fake proves flaky. Each policy decides from **a real deterministic detector on the returned pixels** (deck-brightness profile across the river), so the accuracy numbers are outcomes, not dialled constants:

| Policy | Behaviour |
|---|---|
| `careful` | Clay narrows; windows at 0.5–0.6 m effective GSD; `cannot_assess` when obscuration > 0.3 |
| `skimmer` | Reads at 4 m effective GSD, so it misses decks and fails R5 |
| `guesser` | Claims a status under cloud |
| `fabricator` | Cites windows that do not contain the point |
| `leaker` | Calls `key_lookup`: blocked, a contaminated item, a canary |

**Scripted blind verifier**: the same detector on `post_c` at a different offset and zoom ladder, plus a seeded confusion (sensitivity 0.85, specificity 0.9) on top of its real decisions; key positive/negative controls; `pre`/`post_c` placebo pairs.

**Simulated human gold**: key truth with 3 % label flips, drawn by a committed seed.

**Outputs**: real KEYED precision, recall, F1 and status accuracy; cannot_assess coverage; verifier sensitivity and specificity from controls; then the **same run treated as unkeyed** (key hidden) to give the PPI passport with B0/B1/B2. **`synth/study.py`** runs 200 seeds × policies and reports empirical coverage of the 90 % PPI interval against the true keyed value, width against human-only, planted-error monotonicity (corrupt 0/10/20/40 %), and shuffled-label equivalence to the B2 width.

These are the trust-validation numbers. They are labelled "SYNTHETIC regime: validates the estimator mechanics, not field transfer", and they never count as a keyed regime for LORO.

### 5.2 Nepal flagship, `nepal-bhote-koshi-bridges` (family `river-crossings-vhr`)

**AOI**: the Bhote Koshi from Syabrubesi to Timure/Rasuwagadhi, a parallelogram following the river and kept inside the event polygon: (85.330, 28.150), (85.375, 28.150), (85.400, 28.290), (85.345, 28.290), about 4.5–5.5 km × 15.5 km. The town coordinates I used to place it (Syabrubesi ~85.345/28.160, Timure ~85.370/28.250, Rasuwagadhi ~85.380/28.276) are from memory, UNVERIFIED. **Hour-0 step: confirm the river channel lies inside the AOI from a thumbnail, viewed and not committed.**

**`smoke_aoi`**: Syabrubesi, [85.33, 28.14, 85.37, 28.18]. It is 100 % covered by both pre scenes and every clear post scene.

Measured scene coverage of the AOI (bbox version; `treehouse scenes` regenerates it):

| Role | Scene | Date | Cloud % | pan_gsd | Off-nadir | AOI coverage |
|---|---|---|---|---|---|---|
| post, clearest | B1300011011E5610 | 2026-09-07 01:43Z | 18 | 0.35 | 13.2 | 100 % |
| post, test-retest twin | B1300011011E5810 | 2026-09-07 01:44Z (30 s later, same LG03 pass) | 19 | 0.37 | 18.6 | 100 % |
| post | B1300011011F4F10 | 2026-09-08 | 44 | 0.37 | 18.7 | 91 % |
| post, **cloud trap** | 13 scenes, 08-27 to 09-12 (881410, 881610, 882F10, CF1310, CF1610, 165110, A2910, 153A10, 226410, …) | | 71–94 | 0.31–0.69 | | 64–100 % |
| pre | 10300100C86CED00 | 2021-10-16 | 22 | 0.57 | 27.5 | 70 % |
| pre | 10500100364E8400 | 2023-09-17 | 46 | 0.43 | 11.8 | 75 % |

**Consequences**:
1. **Pre/pre placebo is only possible on the about 51 % of the AOI where both pre scenes overlap**, and their pre-to-post gaps are 3–5 years, so construction confounds change. Expect fewer than 10 bridge pairs. By the A5 rule, that means **post/post test-retest only**, using E5610 against E5810. This is near-identical illumination with a different view angle: it measures verifier self-consistency, not robustness to conditions, and the passport says so.
2. Footbridge decks are about 1–2 m wide, so status needs `max_effective_gsd_for_status_m` = 0.5 for suspension footbridges and 1.0 for road bridges. An agent that reads 1 km windows at 512 px (≈2 m) fails R5.
3. The cloud trap is real and per-scene. A good agent selects E5610 or E5810 and does not average over the cloudy scenes.

**Keying and pins**: inventory step partly keyed against an OSM bridge snapshot fetched on the Mac or by Kiro (Overpass blocked here; ODbL; completeness caveat; 20 m to the way). Damage step unkeyed, gold plan 20–25. `forbidden_sources`: overpass-api.de, *.openstreetmap.org, any OSM/Overture tool, `keys/`. `as_of` 2026-09-18T23:59Z. All 23 intersecting item ids and ETags pinned.

**Lower-Trishuli alternate** ([85.10, 27.90, 85.20, 27.99]): a 2026-02-05 pre scene (0 % cloud, 0.35 m) and a 2026-09-08 post scene (EF5510, 24 %) overlap on 56 % of it. This is the best pre/post pair in the event, but it lies downstream of the flash flood's main impact. It is kept as the second Nepal card only if time allows.

### 5.3 Virginia solar, `virginia-solar-18sth` (family `solar-farm-s2`)

- **AOI**: [−77.95, 38.05, −77.70, 38.25], inside tile 18STH (Louisa/Spotsylvania; exact farm counts UNVERIFIED).
- **Imagery**: Sentinel-2 L2A TCI at 10 m from `sentinel-cogs`, which is reachable tonight. The fixture is built tonight from the June 2024 item JSONs, and the clearest date is picked by cloud %. This matches the Clay embeddings' sensor, so the with/without-Clay ablation is meaningful. NAIP is requester-pays, and is a Kiro-only optional extra.
- **Key**: USPVDB, public domain, clipped to the AOI and **filtered to facilities with install year ≤ imagery year and area ≥ 1 ha** (10 m visibility). Matching is point-in-polygon or ≤ 60 m, one-to-one by facility id.
- **Reachability**: USGS is blocked here, so the card ships with `key.status: pending_fetch`; **`scripts/fetch_uspvdb.py` runs on Suhas's Mac at wake** and the key is committed under `keys/uspvdb/` with its SHA-256 pinned. Fallbacks: Global Renewables Watch v1.0 (MIT, via git if attachable), else synthworld is the only keyed calibration and the report says so.

### 5.4 India stub, `india-brahmaputra-bridges` (family `river-crossings-s2`)

The Nepal card shape on a small Brahmaputra reach near Guwahati with Sentinel-2 imagery (tile 46RCQ/46RCP, chosen by `stac_search`; 46RCP verified to reach 26.22 N). It passes `validate`; `known_limits` derive from GSD ("10 m: only large road and rail bridges"). It is deliberately a different family, so the passport **ABSTAINS from transferring Nepal VHR trust**: the generality and honesty moment.

## I7. Ordered package plan (branch + PR each, tests first)

| # | Package | Est. | Acceptance | AWS? |
|---|---|---|---|---|
| P0 | scaffold: uv, ruff, pytest-socket guard, CI | 0.5 h | `pytest` green with sockets blocked | no |
| P1 | schemas + 4 cards + `validate` | 1.5 h | all cards validate; bad cards are rejected with reasons | no |
| P2 | `geo/` geom + match | 1 h | property tests vs oracle and brute force | no |
| P3 | STAC sources + Vantor and S2 fixtures (built tonight, live) | 1 h | golden Nepal scene table | no |
| P4 | rangeio + `imagery_window` + obscuration | 2 h | the 6 test groups in I6 | no |
| P5 | synthworld + `clay_search` | 1.5 h | world reproducible by hash; clay recall ≥ 0.9 | no |
| P6 | gateway + MCP tool servers + `record_claim` | 1.5 h | forbidden call → span + contamination; `as_of`; meter | no |
| P7 | tracer, store, seal, verify | 1 h | tamper test breaks the chain | no |
| P8 | providers (fake, scripted, replay; Bedrock with Stubber) + Strands adapter | 2 h | scripted `careful` run seals end-to-end | stub only |
| P9 | `checks/` rules R1–R9 + keyed grader + ledger | 1.5 h | golden per-rule claims; synth KEYED numbers | no |
| P10 | sampler + blind scripted verifier + controls + gold sim | 1.5 h | inclusion probabilities sum correctly; blindness test (verifier input has no worker fields) | no |
| P11 | trust: PPI, B0/B1/B2, abstain, Rogan-Gladen | 2 h | `synth/study.py` coverage within [0.85, 0.95]; planted errors monotone | no |
| P12 | panels, HTML report, summary lint | 1.5 h | report regenerates byte-identical from a sealed run | no |
| P13 | `treehouse demo synth` + committed sealed synth runs | 0.5 h | fresh clone: `uv run treehouse demo synth` < 90 s, offline | no |
| P14 | read-only results MCP | 1 h | in-process Client lists tools; chips present | no |
| P15 | live: Vantor smoke reads, Bedrock vision smoke, real Nepal/Virginia runs | morning | | **yes** |

**Cut order if late** (bottom first): P14, Rogan-Gladen, S3ListingSource, the India card's S2 fixture (keep the card), and the second Nepal card. **Never cut**: P4 tests, P9 R4/R6, P13.

## I8. Kiro / morning prompts

1. **Locus probe**, plus Bedrock vision model list.
2. **Vision smoke**: send E5610 windows on the smoke AOI at 0.35, 0.7 and 1.4 m effective GSD and ask "bridge visible?". Record tokens, image tokens, bytes and dollars, and choose the worker and verifier families.
3. **Keys**: run `fetch_uspvdb.py` and `fetch_osm_bridges.py` (Overpass, AOI, snapshot date pinned) from the Mac or Kiro, then commit to `keys/` with hashes.
4. **S3 versioned bucket** for sealed runs (plus Object Lock if allowed).
5. **Live runs**: Virginia K=3 and Nepal K=3 under the budget guard, sealed, then cassettes recorded for the replay demo.
6. **Obscuration validation** against the SCL band on 18STH windows.
7. A Lambda `imagery_window` only if all of the above are done.

## I9. Risks (geo)

1. Footbridges may be unresolvable even at 0.35 m off-nadir, so `cannot_assess` dominates; that is reported as a finding.
2. JPEG decode drift across GDAL builds changes pixel hashes; hashes are environment-scoped.
3. The 3–5-year pre/post gap confounds damage with construction; pre evidence is a flag, not required.
4. Snow, gravel and debris fans trip the obscuration heuristic; it only flags.
5. OSM may be very incomplete for rural footbridges; unmatched claims go to adjudication.
6. USPVDB may be unreachable or misaligned in date with the imagery; filter by install year, with GRW or synth as fallbacks.
7. Vantor STAC *metadata* (CC-BY-NC-4.0) in an Apache-2.0 repo needs a separate `LICENSE-DATA`; pixels are never committed.
8. Without the block cache, range reads take 25 s per window; request count ≤ 10 per 256 px window is a tested invariant.
9. The AOI was placed from town coordinates given from memory; it needs visual confirmation at hour 0.

Sources:
- Vantor STAC: https://vantor-opendata.s3.amazonaws.com/events/Nepal-Flooding-Aug-2026/ (collection.json, event.json, item JSONs, bucket listing ETags) and https://vantor-opendata.s3.amazonaws.com/events/catalog.json
- Sentinel-2 COGs: https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/18/S/TH/2024/6/S2B_18STH_20240616_0_L2A/S2B_18STH_20240616_0_L2A.json
- rasterio `opener=` (1.4+, verified on 1.5.2 tonight): https://rasterio.readthedocs.io/en/stable/topics/vsi.html
- USPVDB: https://eerscmap.usgs.gov/uspvdb/
- GRW: https://github.com/microsoft/global-renewables-watch/releases/tag/v1.0
