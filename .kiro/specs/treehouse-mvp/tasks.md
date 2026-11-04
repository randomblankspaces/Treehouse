# Tasks — Treehouse MVP

Work top to bottom. For each task: branch `kiro/<n>-<slug>`, tests first, `uv run pytest` green, PR into
`main` of `randomblankspaces/Treehouse`, merge, tick the box here in the same PR. Before any live AWS step,
run `uv run treehouse budget status` (stop at exit 2/3). If a task hits a hard AWS blocker, record it in
`docs/KIRO-STATUS.md` and continue with the next task that does not depend on it.

- [x] 0. Environment and AWS foundation
  - `uv sync --locked --all-extras`; `uv run pytest` baseline green; `npm ci && npm run build` in `ui/`.
  - `cd infra && npx -y aws-cdk@2 bootstrap aws://<account>/us-east-1` then `npx -y aws-cdk@2 deploy --all --outputs-file cdk-outputs.json` (run store in Compliance mode, key bucket, Lambda evaluators, AgentCore evaluators). Commit `cdk-outputs.json` with account IDs redacted.
  - Enable CloudWatch Transaction Search for X-Ray spans (AgentCore Observability prerequisite); record the setting.
  - Write `docs/KIRO-STATUS.md` (what ran, outputs, blockers). _Req: 9.1, 9.2_

- [ ] 1. Asset-class registry, reference data and task cards
  - `config/asset-classes.yaml` for every report Table 8 class (warehouses, oil/fuel tanks, bridges, substations/transmission, ground solar, wind): positive and negative definitions, minimum/typical size, suitable resolutions, reference sources with completeness and licence. RV1 and the grader read sizes from here; no class-specific code anywhere. _Req: 1.4_
  - Second class: `scripts/fetch_grw_solar.py` (or reuse the one on branch `pkg/t5-golden-tasks` if present) → ground-mounted solar reference for an ADB-country AOI; task card `tasks/t1-<country>-solar.yaml`. _Req: 1.5_
  - `scripts/fetch_plateau_warehouses.py` → `keys/plateau/nagoya-warehouses.geojson`, `gifu-warehouses.geojson` (warehouse use, ≥ 1,600 m²), with licence, snapshot date, sha256; record a train/held-out split for Nagoya few-shot examples.
  - `scripts/fetch_osm_warehouses.py` → Bangladesh city pool (pick the city with the best `building=warehouse` coverage among Chattogram/Dhaka; pin an extract, Overpass is flaky).
  - Task cards `tasks/t1-nagoya-warehouses.yaml`, `tasks/t5-gifu-warehouses.yaml`, `tasks/t1-bangladesh-warehouses.yaml` with Table-8 positive/negative definitions, AOI (keep AOIs small enough for budget: start with a ~10 × 10 km Nagoya port/logistics district), permitted sources + licences, forbidden sources, budget. `treehouse task validate` passes. _Req: 1.2, 1.3_

- [ ] 2. Embedding sources
  - `EmbeddingSource` protocol + `clay_lgnd` (source.coop GeoParquet) + `aef` (verify the AEF access path first: Earth Engine export or public cloud mirror; if unavailable from Workshop, record the blocker and use committed AOI-sized fixtures) + offline fixtures for tests.
  - Should: `clay_compute` on 160 m Sentinel-2 L2A chips (Clay v1.5 weights from Hugging Face `made-with-clay/Clay`, Apache-2.0) on SageMaker or a GPU EC2 instance; cache to S3. _Req: 2.2, 2.5_

- [ ] 3. Retrieval tool server
  - `tools/retrieval.py`: `list_embedding_sources`, `build_index`, `get_examples`, `retrieve` (zero_shot_text via Bedrock vision on chips / few_shot / concept_vector), `classify` (linear_probe, linear_svm, vision_subagent), `aggregate` (threshold, merge neighbours into sites, count with range). Provenance on every result. Gateway refuses Maxar/Vantor (RV2). GSI imagery source for Japan chips with attribution. _Req: 2.3, 2.5, 2.6_

- [ ] 4. Strands agent run end to end (offline first, then live)
  - Card opts into `record_decision`; `harness: strands`; system prompt states the analyst question and Table-8 definition only.
  - Offline: scripted provider test that exercises every tool and seals red sites.
  - Live: one Nagoya T1 run on `us.anthropic.claude-sonnet-5-5`; seal to the S3 run store; commit the pixel-free cassette for replay. _Req: 2.1, 2.4, 3.1, 9.2, 10.1_

- [ ] 5. Strands vision sub-agent classifier
  - `classify(method="vision_subagent")` → Strands agent with Bedrock vision on GSI chips; metered; switchable with probe/SVM. Live run once. _Req: 2.3_

- [ ] 6. Output grader v2 (report protocol)
  - `checks/protocol_grader.py` (`grade-lgnd-v1`): 160 m grid, any-touch, one count per asset; site recall, recall@k, grid-cell precision, lift, count ratio, AUROC, AP, review effort 50/80/90 %, transfer gap; incomplete reference ⇒ precision-in-pool only. Hand-computed tests on a toy grid. _Req: 4.1–4.3_

- [ ] 7. Reasoning validity (score a)
  - `investigation/reasoning_rules.py` RV1–RV10 with planted-bad-agent tests (1.28 km cells for warehouses unjustified ⇒ RV1 fail; Maxar ⇒ RV2 fail; uses held-out labels ⇒ RV4 fail).
  - Reviewer model of a different family (Nova Pro when the worker is Claude) scores each rationale against `investigation/RUBRIC-v1.md` + report §5.8.
  - AgentCore Evaluations on the live run: Builtin.ToolSelectionAccuracy, ToolParameterAccuracy, TrajectoryInOrderMatch, GoalSuccessRate (assertions from the card), plus RV rules deployed as code-based Lambda evaluators via `infra/`. Commit results JSON. _Req: 5.1–5.4, 9.2_

- [ ] 8. Confidence calibration (score b) and predicted accuracy (score c)
  - `score/calibration.py`: Brier, reliability bins with n, ECE on keyed runs.
  - `score/predicted_accuracy.py`: fit reasoning features → site recall / cell precision on keyed runs; leave-one-config-out + Gifu validation; mean baseline; apply to Bangladesh labelled MODEL-ESTIMATED. _Req: 6.1, 7.1, 7.2_

- [ ] 9. Experiments
  - Baseline: Sonnet + Strands + all sources + agent's own choices, N = 3 on Nagoya, then Gifu and Bangladesh.
  - One-factor variants: model (Nova Pro), classifier (probe vs SVM vs vision sub-agent), tool set (AEF only vs LGND-Clay only). Size N from measured per-run cost; stay under the guard. Should: fan out with Step Functions Distributed Map.
  - Commit sealed-run manifests, metrics JSON and pixel-free cassettes. _Req: 8.1_

- [ ] 10. UI and report
  - Red sites linked to evidence; decision tree with rationales and RV results; five separate panels; raw-statistics download. Screens checked at 1440 and 390 px. _Req: 3.2_

- [ ] 11. Demo, README and evidence
  - Offline replay of the live runs (`treehouse demo` or a new `treehouse demo --scenario warehouses`), README quickstart for a fresh machine, denied-delete demo against the Compliance bucket (as admin, specific versionId), CDK outputs and AgentCore results committed, `docs/KIRO-STATUS.md` final. Update `docs/design/DEFENSE-BOOK.md` claims to match what actually ran. _Req: 9.1, 10.1–10.4_
