# MVP integration and presentation readiness

> Superseded on 2026-11-05 — see [README.md](../README.md) and [docs/KIRO-STATUS.md](KIRO-STATUS.md).

This page supersedes earlier UI-not-built and documentation-only status notes. Historical run artifacts remain unchanged. The product evaluates the observable workflow of an agent creating a geospatial database, and independently evaluates the resulting predictions. It does not recover hidden internal reasoning.

## Report contract

Evaluation is numerical where the evidence supports it, with metric name, units, denominator/population and limitations. Rule coverage is passed assessed criteria / all assessed criteria, shown as a percentage with not-applicable criteria excluded. Output precision and recall are distinct percentages with their declared cell/asset denominators. Expected calibration error is a percentage; Brier remains its raw score. These are separate measurements, not a composite intelligence or trust score. Missing labels, an undefined split or an unknown reviewer scale means unavailable, not zero or pass.

A readable thinking summary follows the recorded sequence: model and harness, selected tools/settings, recorded reasons and alternatives, explored paths/revisions, errors/stopping and prediction outcome. These are recorded explanations, not independently verified mental states. Cost stays in USD and duration keeps its measurement basis; replay timing and historical recorded charges are not a new live run.

The verified snapshot keeps predicted present, absent and cannot-assess statuses, claim/trial IDs, decision links and evidence references. A predicted site is not confirmed ground truth. Saved runs can be inspected without launching models. JSON/Markdown/GeoJSON exports retain these distinctions. Synthetic reference-derived embeddings demonstrate mechanics and cannot establish operational accuracy or generalization.

## Current verification checkpoint

Paused at the user's request on November5. The branch is **not ready to merge**. Full offline verification after round2: **970 passed,3 skipped,1 deselected**, with two expected pricing-test warnings;18 Node checks, Ruff and the frontend build passed. Independently frozen assertions and historical fixture/reference hashes remain unchanged. Fresh Terra review still fails one public-surface case: `/investigation` can expose out-of-coverage catalogue precision/Brier while snapshot/bundle/export correctly abstain. Rendered browser QA is pending. Green tests do not override this review finding.

After two incomplete corrections around the same scope boundary, reassess the architecture before another patch: the current guard is attached to snapshot construction, while investigation calls the legacy evaluator directly. Use a shared public comparison projection for every HTTP surface; freeze an additional independent investigation-endpoint regression before repair. Preserve the direct legacy grading protocol and all prior frozen tests.

## Fresh bounded AWS observations through Kiro

Kiro reported two new Sonnet Bedrock calls, estimated$0.0278: text plus accepted predefined tool history and generated gradient-image content. The model was not asked to choose a tool autonomously. Nova had zero calls because the probe reserved its remaining cap; skipped is not tested. The gradient result does not prove actual geospatial vision performance.

One fresh code-based AgentCore guard evaluation on a copy of an existing sealed run returned1.0. This verifies that guard invocation, not database accuracy or a full workflow evaluation. Strands1.63.0 imported but had no fresh end-to-end run in this check. Online AgentCore evaluation had no configs/runtime and remains blocked; Transaction Search was active. Existing experiment vision calls errored. The application fixture embeddings/references remain synthetic. A subsequent bounded public-data read is recorded below; real AEF access remains untested.

Evidence was observed in the authorized Workshop Kiro chat, not re-executed from this Mac. Private remote outputs are under `/workshop/Treehouse/out/aws-readiness/`, including `readiness-20261105T0350Z.md` and `probe-20261105-cap050.json`. The application spend ledger reported$11.0014/309 calls afterward; this is distinct from AWS account billing and Kiro credits. Preserve the modified spend ledger. No deployment or permissions changes were requested.

## Actual public Clay read — separate from an agent run

Kiro reported an actual unsigned read of LGND/Clay v1.5 Sentinel-2 embeddings for Nagoya:56 Major TOM cells,1280m each,256 float32 dimensions, EPSG:4326, scene `S2B_53SPU_20240419_0_L2A` dated2024-04-19. Source is public CC BY4.0 with LGND attribution. An AOI-centre cell was chosen geometrically, then55 other cells ranked by cosine similarity; no warehouse reference labels or synthetic vectors were used. Similarity is not object probability or detection accuracy.

Object: `s3://us-west-2.opendata.source.coop/clay/lgnd-embeddings/monthly-aggregated/model_version=v1.5/collection=sentinel-2-l2a/chip_size=1280m/dims=256/geohash=xn/year=2024/month=04/f245cf636488.parquet`. ETag `950e31d6f74248597449567ab9bbfcdb-34`; VersionId `3kUvL5ybcZw4I2Cb9kfO56TYt3yOtY0x`. Kiro reported30,404,395 data-file bytes in31range requests, plus69.8KB footer/READMEs, under32MiB total. Raw vector reconstruction used a bounded Parquet-page reader. This was observed through the Kiro UI; raw files have not yet been locally inspected or independently reproduced.

Remote scratch evidence: `/workshop/Treehouse/out/real-data-probe/{lgnd_probe.py,README.md,result-nagoya-2024-04.json,inspect.json}`. Ephemeral environment reported Python3.13,pyarrow26.0.1,numpy2.5.4,boto3 1.43.123. Script exposes region/endpoint/profile and uses unsigned requests by default. These versions/commands need clean-device verification before a portability claim. Kiro reported13.5credits for this experiment and no Bedrock calls; tracked source was untouched.

The actual vectors are **not yet wired into the agent's source adapter**. No new live agent investigation or warehouse detections were produced by this experiment. LGND Geo MCP is unconfigured; the user reports no account/unsure. Its [official connection guide](https://lgnd.ai/resources/lgnd-geo) names `https://geo.lgnd.ai/mcp`; account authorization remains a user-owned step. Public [Clay embeddings](https://source.coop/clay/lgnd-embeddings/monthly-aggregated) remain a working alternative input path. Primary next goal is the actual traced agent run on permitted public satellite data; a clearly labeled demo/design is the fallback if services block it.

## Remaining presentation gates

1. Close the shared public-comparison scope boundary, then pass independent review, rendered browser QA and CI. Numeric scores/summary and the existing offline suite are implemented and passing.
2. Pull the reviewed main in Kiro without losing its billing ledger or uncommitted work. Run one small guarded Strands investigation end to end and inspect the exact run in the UI.
3. Repair actual permitted imagery/vision and real embedding-source access before claiming real geospatial detection. Until then, use a conspicuously labeled recorded/synthetic method demonstration.
4. Bind reference/split/version and declare class, AOI, date, completeness and matching protocol before reporting held-out accuracy. Historical unbound splits cannot establish a fixed evaluation population.
5. Keep custom live UI launch, runtime deployment/online evaluations and broader task families explicitly unavailable until exercised. Trust issuance remains a stub; no human baseline has been measured.

Presentation artifacts and source-document extracts remain outside the repository under the user's Codex workspace. The supplied documents are context; broader benchmark studies, captioning, a second task and simulation are not automatically part of this repair.
