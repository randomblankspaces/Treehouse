# Design — Treehouse MVP

Full rationale: `docs/MVP-PLAN.md` §4–§7. This file fixes the integration points so tasks can be built
independently.

## Run pipeline
task card → `treehouse sandbox run --harness strands` (investigation runtime, `record_decision` bound
actions) → Strands agent (Bedrock) → retrieval tools via Tool Gateway → sealed claims + traces → post-seal
evaluators (output grader v2, reasoning validity, calibration, predicted accuracy, AgentCore) → report/UI.

## New modules (keep inside existing layers)
| Module | Responsibility | Notes |
|---|---|---|
| `tools/retrieval.py` | MCP server: `list_embedding_sources`, `build_index`, `get_examples`, `retrieve`, `classify`, `aggregate` | Pure numpy for probe/SVM (no new deps; implement logistic regression and a linear SVM via subgradient or reuse scipy.optimize). Every result returns provenance (source, date, resolution, cell size, licence). |
| `tools/sources/aef.py`, `tools/sources/clay_lgnd.py`, `tools/sources/clay_compute.py` | Embedding sources behind one protocol `EmbeddingSource.index(aoi, cell_size_m, year) -> CellIndex` | `clay_lgnd` reads source.coop GeoParquet (1.28/2.56 km). `aef` reads AEF 10 m and pools to the chosen cell size. `clay_compute` (Should) runs Clay v1.5 on Sentinel-2 chips via SageMaker/EC2 GPU and caches to S3. Offline tests use small committed fixtures. |
| `tools/sources/gsi.py` | GSI seamless aerial tiles (Japan) for imagery windows | Attribution string in every result; pixels never committed. |
| `verifier/vision_classifier_agent.py` (or reuse `investigation.VisionClassifier`) | Strands sub-agent classifier on chips | Selected by `classify(method="vision_subagent")`; usage and cost metered. |
| `checks/protocol_grader.py` | Report Table 7/11 grader, version `grade-lgnd-v1` | 160 m grid, any-touch, one count per asset; incomplete reference ⇒ precision-in-pool only. |
| `investigation/reasoning_rules.py` | RV1–RV10 per decision | Deterministic, versioned, append-only records. |
| `investigation/review.py` (extend) | Reviewer model of a different family scoring each rationale | Existing semantic process review; keep separate from rules. |
| `score/calibration.py` | Brier, reliability bins, ECE | Keyed runs only. |
| `score/predicted_accuracy.py` | Fit reasoning features → accuracy on keyed runs; apply to unkeyed with interval | Leave-one-config-out validation; mean baseline. |
| `aws/agentcore.py` (exists) | On-demand AgentCore Evaluations; add Treehouse reasoning rules as code-based Lambda evaluators | Results stored as `agentcore` eval kind, never blended. |
| `scripts/fetch_plateau_warehouses.py`, `scripts/fetch_osm_warehouses.py` | Build `keys/plateau/{nagoya,gifu}-warehouses.geojson` and a Bangladesh OSM pool, with provenance + sha256 | Train/held-out split recorded; licence recorded. |

## Data contracts
- `CellIndex`: grid id, cell size (m), CRS, cell polygons/centroids, embeddings (float32), source, date, resolution, licence, cost.
- Claim geometry: site polygon or point + member cell ids; confidence 0–1; evidence refs.
- Grader v2 input: sealed claims + reference GeoJSON + completeness flag + 160 m grid over the AOI.

## UI
Reuse the existing Atlas/Living Sky views: red site markers, decision tree with rationales, and five separate
panels (reasoning validity, calibration, predicted accuracy, output accuracy, cost/time/data). Add
"Download raw statistics".

## AWS
CDK `infra/` (exists) deploys the run store (Compliance) and Lambda evaluators; extend with any new Lambda
evaluator. Enable CloudWatch Transaction Search once for AgentCore Observability. Optional: Step Functions
Distributed Map for the experiment matrix; SageMaker/EC2 GPU for Clay compute.
