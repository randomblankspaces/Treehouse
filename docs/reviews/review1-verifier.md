# Review 1: VERIFIER report

Method: every cited line was checked against `git show 373719c:docs/<file> | cat -n`, `git show a23dec5:docs/SCOPE.md | cat -n`, the FUTURE-WORK diff, and vision-doc (VD) lines 1–10 and 47–48. Outside-world claims were checked with public HTTP requests:
- the Vantor bucket listing: `https://vantor-opendata.s3.amazonaws.com/?list-type=2&prefix=events/Nepal-Flooding-Aug-2026/`;
- each scene's STAC JSON, plus `collection.json`;
- the LGND README: `https://data.source.coop/clay/lgnd-embeddings/README.md`.

"SCOPE" with no revision means SCOPE@a23dec5. Unless a row says otherwise, every quote it relies on is real, at the cited line, and not cut so as to change its meaning.

## Outside-world facts (both sides relied on these)

| Item | Result | Evidence |
|---|---|---|
| The Nepal event holds only the 5 scenes listed in SCOPE:156–162 | **WRONG** | The bucket holds **33 scenes** (110 keys). Three are pre-event: 2021-10-16, 2023-09-17 and 2024-05-29. **28 are post-event**, from 2026-08-27 to 2026-09-18, with a 2026-02-05 scene that is pre-event and 0 % cloud. All are from the bucket listing |
| "the post-flood scenes are 74–81 % cloud" (SCOPE:166) | **WRONG** for the event as a whole | That is true only of the two listed post scenes, CF1110 at 81 % and CF1210 at 74 %. Several other post scenes are far clearer: B1300011011E5610 at 18 % (85.31–85.42 / 28.12–28.35), B1300011011E5810 at 19 %, B030001100EF5510 at 24 % (85.06–85.23 / 27.82–27.97), B030001100EF5210 at 40 %, and B160001101ECBC10/ECBD10 at 7 % and 6 % (85.46–85.58 / 28.10–28.32). Values are each item's `eo:cloud_cover` |
| Listed scene facts (IDs, dates, cloud, bbox, about 0.5 m) | VERIFIED | The STAC items match SCOPE:158–162. CF1110 `pan_gsd` is 0.55. The CF1110 TIFF is 1.41 GB |
| Scene metadata can key "bridge under cloud" | **WRONG / UNSUPPORTED** | Each item has only `visual` and `thumbnail` assets, and `event.json` has `mask: False`. There is no cloud mask, and `eo:cloud_cover` is one per-scene percentage. Per-bridge cloud status can't be read deterministically from metadata. Coverage by footprint can |
| Where the event happened | Fact neither side used | `collection.json`: a glacier-collapse flash flood on 2026-08-26, Bhote Koshi River, **Rasuwa District** (upper Trishuli). Post scenes cluster at about 85.0–85.6 E, 27.6–28.5 N |
| Kathmandu has no post-flood imagery | **WRONG at bucket level; VERIFIED for the 5-scene table only** | Kathmandu is about 27.70 N, 85.32 E. B110001101165110 (2026-08-28, 78 % cloud) spans 85.32–85.44 / 27.55–28.53. B030001100EF5210 (2026-09-08, 40 %) spans 85.07–85.30 / 27.67–27.97 and reaches the valley's western edge. Coverage is a thin edge, but it isn't zero |
| Vantor license (doubter, "from memory": CC BY-NC) | VERIFIED | `collection.json` `"license": "CC-BY-NC-4.0"` |
| LGND: 2017 to April 2026, 1.28 km, 256-dim, CC BY 4.0 | VERIFIED | LGND README: "Jan 2017 - April 2026", `1280m` with `256`, "CC BY 4.0" |
| Kathmandu at about 27.7 N; Trishuli at about 27.9–28.2 N, 85.1–85.4 E (doubter, from memory) | VERIFIED (approximately) | The Trishuli corridor overlaps both listed post scenes, consistent with the bbox values above. The upper reach (Bhote Koshi) runs to about 28.3 N |
| stac-mcp / gis-mcp can read raster windows (defender, unverified) | UNVERIFIABLE (not checked) | Only their names and descriptions appear at EXTERNAL-DEPS@373719c:26 |

## Claim table

| Claim | Side | Statement checked | Result | Evidence | Note |
|---|---|---|---|---|---|
| C1 | doubter | S17 text at SCOPE:61; "about 100 runs" at OQ:10; "Nothing grades the damage step" at :167; S9 "verifiably and truthfully" at :53 | VERIFIED | SCOPE:61, :167, :53; OQ@373719c:10 | "mostly on other tasks (solar, bridge inventory)": the bridge inventory is a step of the same task, not another task. Minor wording |
| C1 | doubter | The trust model isn't recorded as provenance | VERIFIED | SCOPE:61, :131; F5 01:13; OQ6 OQ:12 | No estimator version field anywhere |
| C1 | defender | "100 runs" is "OQ4's text-task plan", and the idea "commits to no run count" | MISLEADING | OQ:10 | OQ4 never says "text". It is a decided default (D25, SCOPE:114) that a23dec5 leaves in force. The idea set no count, but the baseline count governs |
| C1 | defender | The inventory step is keyed by OSM | VERIFIED | SCOPE:167 | — |
| C1 | defender | D42 "core loop first" | VERIFIED | SCOPE:138 | — |
| C2 | doubter | VD:10 principle; F4 01:12; J1.4 04:14; J6.2 04:56 | VERIFIED | as cited | J4.3 (04:42) doesn't require the damage step, so "J4.3 can't pass" holds only if it is run on the damage step |
| C2 | defender | Known task :146–152; known input :156–162; OQ1 workflow spec OQ:7; VD:9 scoring definition; VD:10 "scores the agentic workflow itself" | VERIFIED | as cited | The input is 5 of 33 scenes (see above) |
| C2 | defender | J6.2 allows "(or planted traces)" | VERIFIED | 04@373719c:56 | — |
| C2 | defender | Bridges under cloud are "a deterministic answer key from scene metadata" | **WRONG** | Vantor STAC items | No cloud mask exists, only a scene-level %. Outside-footprint bridges are deterministic only for a fixed scene set, and the bucket has 28 post scenes, some clear |
| C3 | doubter | S14–S19 "after review" :58–63; cut line pending :140; baseline SCOPE:3 "raise it"; D24 solo; "11 Must features" | VERIFIED | SCOPE:58–63, :140, :113; SCOPE@373719c:3; 01:9–20 | F1–F12 with F8 Should makes 11 Must. "About 34 h" is consistent with D40's 23:11 timestamp (:136) and the Thursday 10:00 deadline (:39) |
| C3 | defender | SCOPE:3 declares that S14–S19 get their items "after the scope review" | VERIFIED | SCOPE:3 | The line names 01/02/04 only, not 05 (DoD) |
| C4 | doubter | 1.28 km / 256 / 2017–Apr 2026 at :132; floods Aug 2026; D38 at :134; "narrows the search" at :165; map layers banned at :152; EXT-DEPS:34 "Stretch" | VERIFIED | SCOPE:132–134, :137, :152, :165; EXT-DEPS@373719c:34; LGND README | The August date is also at :133 |
| C4 | defender | :165, :132 "isn't the whole picture", :134; F1 makes the LGND tool Must (01:9), so the EXT-DEPS tag is a stale baseline row | VERIFIED | SCOPE:132, :134, :165; 01@373719c:9 | The baseline inconsistency is real (Must F1 vs "Stretch (captions / retrieval)") |
| C5 | doubter | :131 OSM is an answer key; EXT-DEPS:26 osm/Overture servers; OQ4 tool sets; :140 pending | VERIFIED | as cited | — |
| C5 | defender | Prompt forbids map layers :152; OQ1 has "forbidden tools" OQ:7 | VERIFIED | as cited | — |
| C6 | doubter | OQ12 "never blended into them" OQ:18; OQ header :3; S16 :60; D33 "secondary" :129 | VERIFIED | as cited | — |
| C6 | defender | OQ12 forbids blending output *into the workflow scores* | VERIFIED | OQ:18 | That is the literal text |
| C7 | both | S18 :62 vs F4 01:12, SC3 02:10, J1.4 04:14 | VERIFIED | as cited | Both sides agree |
| C8 | doubter | :135 window read; :165 0.5 m; F1 tool list 01:9; D40 general access | VERIFIED | SCOPE:135–136, :165; 01:9 | — |
| C8 | defender | rasterio/GDAL in the stack; stac-mcp/gis-mcp on the shortlist | VERIFIED (the citation) | EXT-DEPS@373719c:67, :26 | Whether those servers read windows: UNVERIFIABLE (not checked) |
| C9 | doubter | "$5" at :152; "$30" in OQ4; $500 cap at :39 | VERIFIED | as cited | "100 × $5 = $500" applies $5 to all 100 runs. OQ4's 100 runs span 5 tasks, and $5 is a cap in the prompt, not a measured cost. The arithmetic is right, but the premise is an inference |
| C9 | defender | Size N from measured cost (OQ:10; 06:17); budget guard is Must (01:19) | VERIFIED | OQ@373719c:10; 06@373719c:17; 01:19 | — |
| C10 | doubter | F7 01:15; J2.3 04:25; D25; task-understanding definition at :201 | VERIFIED | as cited | — |
| C10 | defender | D25 bans an LLM judge for output only (:114); OQ1 allows an optional LLM evaluator (OQ:7); J2.3 tolerates variance (04:25); step-4 list at :150 | VERIFIED | as cited | OQ1's LLM evaluator rates "planning and recovery". Counting task understanding as process is an inference. The proposed check "cannot be assessed for cloud bridges" can't be deterministic without a cloud mask |
| C11 | doubter | OQ10 text OQ:16; D37 :133; no decision revises OQ10 | VERIFIED | as cited | Only SCOPE and FUTURE-WORK changed in a23dec5 (`git diff --stat`) |
| C11 | defender | Nothing deletes the OQ10 tasks; OQ10 keyed tasks are NAIP lookup, dataset IDs and solar vs USPVDB | VERIFIED (mostly) | OQ:16, OQ:18 | OQ10 names USPVDB as an answer key only for solar. The dataset-ID key comes from OQ12's example (OQ:18). NAIP lookup's key is unstated |
| C12 | doubter | "the agent's thinking" at :128; J3.2 "same schema" at 04:32 | VERIFIED | as cited | — |
| C12 | defender | J3.2 is the *tracer* swap, not the model swap | VERIFIED | 04@373719c:31–32 | The model swap is J3.1, which has no schema clause |
| C13 | doubter | VD:10 quote; FUTURE-WORK moves the simulation to #1; README:50–54 lists sensitivity analysis first | VERIFIED | VD:10; FUTURE-WORK diff; README@373719c:50–54 | — |
| C13 | defender | D41 "STRETCH / FUTURE only, not MVP" :137; D42 :138; FUTURE-WORK:3 "Nothing … promised" | VERIFIED | as cited | — |
| C14 | doubter | "See registry page" EXT-DEPS:33; committed traces DoD:18; CC BY-NC from memory | VERIFIED | EXT-DEPS@373719c:33; 05:18; collection.json | The license is **CC-BY-NC-4.0** (confirmed) |
| C14 | defender | The gap predates the idea; Vantor is allowed per VD:7/48; the output records image ID and date (:149) | VERIFIED | as cited | "Traces naturally carry IDs, not pixels" is an inference. A vision tool sends image windows to the model, so traces may hold pixels |
| C15 | doubter | VD:6 partner need; :146 "ADB is preparing…" | VERIFIED | as cited | — |
| C15 | defender | Task reference :190; F12 01:20; solar second task :133; synthetic label :144 | VERIFIED | as cited | The label is at :144, outside the quoted prompt (:146–152). The prompt text itself carries no "synthetic" mark |
| C16 | doubter | Post scenes :161–162 at 81/74 %; :159 "includes Kathmandu"; Kathmandu outside both post scenes | VERIFIED for the listed table; **MISLEADING** as a claim about available data | SCOPE:159–162; bucket listing | Kathmandu has thin post coverage (B110001101165110, EF5210), and much clearer post scenes exist along the corridor (18–24 %). "Even Trishuli may yield very few assessable bridges" rests on the incomplete table |
| C16 | defender | Region "to be decided later" :133, :140; the table "shows it did the homework" | VERIFIED (citation); **MISLEADING** ("homework") | SCOPE:133, :140, :158–162; bucket | The table lists 5 of 33 scenes and the 2 cloudiest-looking post scenes. The "designed trap" (:166) is an artifact of that selection |
| C17 | both | "Who calls it … is open" :130; SC11 02:19; hosted deployment pending :121 | VERIFIED | as cited | :121 is a round-4 pending item. It isn't on the round-5 list (:140) and isn't resolved |

## Rows the defender says the doubter misclassified

| Row | Defender's evidence | Result | Note |
|---|---|---|---|
| S12 | D33(2) "the output grade" at :19 | VERIFIED | — |
| SC9 / J6 / DoD 7 | J6.2 "(or planted traces)" at 04:56; coverage and cloud steps keyed | Citation VERIFIED; "cloud keyed" **UNSUPPORTED** | No cloud mask exists (see above) |
| F4, SC3, J1, DoD 2 | :166–167; coverage and cloud deterministic | PARTLY | Coverage can be deterministic for a fixed scene set. Cloud can't come from metadata |
| J4.3 | J4.3 doesn't require the damage step | VERIFIED | 04:42 |
| J3 | J3.2 is a tracer swap (04:32) | VERIFIED | — |
| D4 | :36 text | VERIFIED | — |
| OQ12 | OQ:18 wording; OQ1 at OQ:7 | VERIFIED | — |
| D24 | SCOPE:3, :140 | VERIFIED | — |
| D25 | D37 is logged | VERIFIED | It doesn't mention OQ10 or OQ12 |
| OQ10 | Nothing removes OQ10's tasks | VERIFIED | — |
| EXT-DEPS LGND "Stretch" | F1 Must at 01:9 | VERIFIED | — |
| OQ4 budget | OQ4 and 06:17 | VERIFIED | — |
| VD:10 known task + input + reference | OQ:7, SCOPE:166–167 | PARTLY | The cloud key is unsupported. VD:10 also says the reference was "confirmed … for the first two tasks" at scoping, which neither side cites |
| VD:6 domain experts | keyed sub-steps | PARTLY | Same caveat |
| VD:6 partners | 01:20, SCOPE:190 | VERIFIED | — |
| VD:10 "scores the agentic workflow itself" | SCOPE:18 | VERIFIED | — |
| Case point 5 | LGND CC BY 4.0, OSM ODbL | VERIFIED | 06@373719c risk row; LGND README. The defender didn't list Vantor's license, which is CC-BY-NC-4.0 |

## Corrections the judge must know

These are listed in order of importance.

1. **The scene table in SCOPE (:156–162) is incomplete, and both sides treated it as the full data.** The Nepal event folder holds 33 scenes, 28 of them post-event (2026-08-27 to 09-18). Several post scenes are much clearer than 74–81 %: 6, 7, 18, 19 and 24 % cloud, and some lie on the Trishuli/Bhote Koshi corridor. This weakens:
   - the doubter's C16 "post scenes are mostly cloud" and "very few assessable bridges";
   - the defender's "the table shows it did the homework";
   - the "designed trap" premise both sides accept (:166).

   It also makes "bridge outside post footprints → cannot be assessed" depend on which scenes the task supplies.
2. **The defender's "bridges under cloud are a deterministic key from scene metadata" (C2, C10, misclassification rows) is not supported.** The items carry only a visual COG and a thumbnail, and the event metadata has `mask: False`. There is no cloud mask, and `eo:cloud_cover` is one per-scene number. Only footprint coverage is metadata-deterministic. The defender's main downgrade of C2 (critical to major) and its re-mapping of SC9/J6/DoD 2/DoD 7 lean on this.
3. **The event is a Rasuwa District glacier-collapse flood on the Bhote Koshi (upper Trishuli)**, per `collection.json`. Neither side used this fact. Kathmandu isn't the flood zone, but it isn't strictly "no post imagery": B110001101165110 and EF5210 touch it at the edges.
4. **The Vantor license is confirmed as CC-BY-NC-4.0.** The doubter's from-memory claim (C14) is true. The defender's inference that traces carry "IDs, not pixels" is untested, since a vision tool sends pixels to the model.
5. **The defender's C1 rebuttal ("100 runs is OQ4's text-task plan; the idea commits to no count") is misleading.** OQ4 doesn't say "text", and OQ4 remains a decided default under D25.
6. **The doubter's C9 "100 × $5 = $500" applies a prompt cap as a per-run cost across all OQ4 runs, most of which aren't the Nepal task.** The arithmetic is right, but the premise is an inference.
7. Minor points:
   - SCOPE:3 defers 01/02/04 items for S14–S19 but doesn't mention 05 (DoD).
   - The "synthetic" label (:144) sits outside the prompt text (:146–152).
   - LGND facts and Kathmandu/Trishuli coordinates check out.
   - stac-mcp/gis-mcp window-reading ability was not checked.

Not checked: OSM footbridge completeness in Rasuwa/Trishuli; stac-mcp/gis-mcp capabilities; which of the 28 post scenes actually show the corridor clear at bridge locations (scene-level cloud % only).
