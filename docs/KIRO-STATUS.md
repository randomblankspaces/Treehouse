# Kiro build status

Live log of what Kiro ran against the Workshop AWS account, with artifacts and blockers. Account IDs/ARNs
are redacted to role/resource names. One section per task.

Region: us-east-1. Identity: `WSParticipantRole` (assumed-role session).

---

## Task 0 — Environment and AWS foundation

**Status:** done (one non-blocking blocker recorded).

### Environment
- `uv sync --locked --all-extras` — ok (added CDK/FastAPI extras).
- `uv run pytest` baseline — **green**, 3 skipped, 0 failed (on `origin/main` @ `56e9182`). The failures
  listed in `probe-report.json` were against a stale local `main`; the current `main` is clean.
- `ui/`: `npm ci && npm run build` — ok (vite build, 288 kB JS bundle).
- `uv run treehouse budget status` — ok, ledger `$0.1053`, under $350 alarm.

### AWS foundation (CDK)
- `cdk bootstrap aws://<redacted>/us-east-1` — ok (CDKToolkit stack created; account was not bootstrapped,
  per probe).
- `cdk deploy --all -c retention_days=1 -c lock_mode=compliance` — ok after the OnlineEval fix below.
- Stacks deployed and verified live:
  - **TreehouseRunStore** (`CREATE_COMPLETE`): sealed run store S3 bucket with **Object Lock COMPLIANCE,
    1-day default retention** + versioning (both verified via `get-object-lock-configuration` /
    `get-bucket-versioning`); KMS-encrypted key bucket with an explicit Deny for the worker role; worker +
    grader IAM roles.
  - **TreehouseEval** (`CREATE_COMPLETE`): two code-based evaluator Lambdas
    (`treehouse.aws.lambda_evaluator.handler`) and their AgentCore Evaluator registrations.
    `list_evaluators` confirms `treehouse_rules` and `treehouse_guard` are **ACTIVE**; both Lambda
    functions exist.
- Outputs committed (account redacted): `infra/cdk-outputs.json`.

### CloudWatch Transaction Search (AgentCore Observability prerequisite)
- Created CloudWatch Logs resource policy `TransactionSearchAccess` granting `xray.amazonaws.com`
  `PutLogEvents`/`CreateLogStream` on `aws/spans` and `/aws/application-signals/data` (scoped by
  `aws:SourceAccount` / `aws:SourceArn`).
- `UpdateTraceSegmentDestination(Destination=CloudWatchLogs)` and
  `UpdateIndexingRule(Default, Probabilistic 100%)` applied. Destination reports `CloudWatchLogs` /
  status `PENDING`; activation completes asynchronously (minutes). Re-check with
  `aws xray get-trace-segment-destination`.

### Blocker (non-blocking, worked around)
- **AgentCore `OnlineEvaluationConfig` create fails** with `ValidationException: One or more specified log
  groups do not exist`. The config references a hosted-agent log group
  (`/aws/bedrock-agentcore/runtimes/treehouse-DEFAULT`) that does not exist because no AgentCore Runtime is
  hosted yet (that is KA3 / a "Could"-tier step). The control plane validates the log group at create time
  even though the config ships `DISABLED`.
  - **Workaround:** gated the `OnlineEvaluationConfig` behind `-c online=true` in `infra/app.py` /
    `EvalStack(..., with_online=...)`, default off. The two evaluators + Lambdas (the Must-tier pieces)
    deploy without a runtime. Enable online eval later once a runtime log group exists.

### Artifacts
- `infra/cdk-outputs.json` (redacted), `infra/treehouse_infra.py` + `infra/app.py` (online-eval gate).
- `aws-foundation.json` (deployed resource ids, redacted; repo root, like `aws-capabilities.json`).

---

## Live-AWS window note (recorded 2026-11-04 ~21:05 UTC)

- Session AWS credentials expire **21:22:08 UTC** today (per probe). At the time task 0 finished there were
  ~18 minutes left — not enough to build tasks 1–3 and fire a clean live Nagoya agent run.
- **Live Bedrock is already proven** for this account by the master probe (`aws-capabilities.json`,
  `probe-report.json`): Claude Sonnet 5.5 and Nova Pro both returned `ok` for user-turn and tool-result
  images; prices verified (`treehouse prices check` → "worker and verifier are priced"). Those probe calls
  are in `.spend/spend.jsonl` (ledger $0.1053, estimated at probe-ceiling prices).
- Decision: build the offline-buildable tasks (1 cards/data, 2 embedding sources, 3 retrieval tools, 6
  grader, 8 calibration/predicted-accuracy) now; fire the **live Nagoya Strands-on-Bedrock run under task 4
  the moment credentials are valid and task 3 has landed** (the live path is `treehouse sandbox run
  --provider <module:factory>`; `treehouse run --mode live` is deliberately refused). Any remaining live gap
  at the deadline is flagged here and the matching acceptance item left unticked.

---

## Task 1 — Reference data and task cards

**Status:** done (external sources unreachable → committed fixtures, blocker recorded).

- `scripts/fetch_plateau_warehouses.py` → `keys/plateau/{nagoya,gifu}-warehouses.geojson` (+ provenance,
  split, SHA256SUMS). Nagoya 46 pts (16 train / 30 held-out), Gifu 12 (0 train — transfer, no new labels).
  Class = PLATEAU `bldg:usage` warehouse (441), footprint ≥ 1,600 m² (Table 8).
- `scripts/fetch_osm_warehouses.py` → `keys/osm/chattogram-warehouses.geojson` (18-pt pool, ODbL,
  `reference_quality: incomplete`, precision-within-pool only). Chose Chattogram over Dhaka.
- Task cards: `tasks/t1-nagoya-warehouses.yaml` (keyed), `tasks/t5-gifu-warehouses.yaml` (keyed transfer),
  `tasks/t1-bangladesh-warehouses.yaml` (unkeyed). All pass `treehouse task validate`; golden card-hashes
  updated. Each states the Table-8 positive + negatives (factories/markets/hangars) to the worker, forbids
  `keys/` and Maxar/Vantor, and binds `record_decision` + the retrieval tools.
- Added `LicenseRef-gsi-japan-attribution` to the licence registry (GSI seamless aerial, Japan: reusable
  with attribution, Table 17); GSI imagery is permitted only in the Japan cards, never Bangladesh.

### Blocker (worked around)
- **Overpass unreachable** (empty/connection failure here; probe saw 406/502) and a **full PLATEAU CityGML
  parse is out of scope** for the Workshop window. Both fetch scripts therefore emit committed,
  deterministic, AOI-sized **fixtures** (`synthetic_fixture: true`) with the real access path recorded, so
  the grader/calibration/report pipeline has reference geometry. These are NOT the report's real counts
  (Nagoya 403 / Gifu 63 full-city); replace with real CityGML/OSM extracts before claiming real output
  accuracy. Recorded in each `*-provenance.json`.

### Class-agnostic registry (Req 1.4) and second class (Req 1.5)
- `config/asset-classes.yaml` + `src/treehouse/assets.py` (`AssetClasses.load()`): all six Table 8 classes
  (warehouse, oil/fuel tank, bridge, substation, ground solar, wind) with positive/negative, min/typical
  size, min area, suitable GSDs, the 160 m grid unit and reference sources + licences. RV1/RV3 sizing helpers
  (`cell_fits`, `resolvable_at`) read sizes from here — no class-specific code. `cell_fits("warehouse",1280)`
  is False (the 1.28 km LGND index is too coarse), the anchor the RV1 planted-bad test will use.
- Req 1.5 (second class): the committed **USPVDB ground-solar** reference (`keys/public-benchmark/`) + the
  existing `tasks/virginia-solar-18sth.yaml` card already provide a usable second class, so a separate GRW
  fetch was not run in this window (GRW was reachable in the probe; deferred to avoid another flaky-source
  pass). The `ground_solar` registry entry lists both GRW and USPVDB references.

### Artifacts
- `config/asset-classes.yaml`, `src/treehouse/assets.py`, `keys/plateau/*`, `keys/osm/*`,
  `tasks/t1-nagoya-warehouses.yaml`, `tasks/t5-gifu-warehouses.yaml`, `tasks/t1-bangladesh-warehouses.yaml`,
  `scripts/fetch_plateau_warehouses.py`, `scripts/fetch_osm_warehouses.py`,
  `tests/unit/{test_reference_fetch,test_assets}.py`, licence addition in `src/treehouse/cards.py`.

---

## Credential window update (2026-11-04 21:24 UTC)

The session's AWS credentials **auto-refresh from the instance profile** (role `WSParticipantRole`); the
metadata endpoint now reports expiry `2026-11-05T03:05Z` and renews. The earlier 21:22 UTC concern was the
first short-lived token, not a hard session end. The live-AWS window is therefore effectively open for the
rest of the build, so the live Nagoya Strands-on-Bedrock run (task 4) can proceed once tasks 2–3 land.

---

## Task 2 — Embedding sources

**Status:** done (real AEF / LGND reads blocked → committed synthetic fixtures).

- `src/treehouse/tools/sources/embedding_source.py`: `EmbeddingSource` protocol
  (`index(aoi_bbox, cell_size_m, year) -> CellIndex`), `CellIndex` (grid, cell size, CRS, centroids, float32
  unit embeddings, source, dates, resolution, licence, cost, provenance), `pool_to_grid` mean-pooling.
  `CellIndex.to_npz_arrays()` matches the existing `clay` server's npz layout, so the server works unchanged.
- `aef.py` (AEF, 10 m, CC BY 4.0; pools to any cell ≥ the fixture's 160 m base) and `clay_lgnd.py` (LGND
  Clay, 1,280 / 2,560 m only, CC BY 4.0). `clay_compute` (Should) not built; seam documented.
- `scripts/make_embedding_fixtures.py` → `fixtures/embeddings/{aef,lgnd}-{nagoya,gifu,chattogram}.npz`
  (byte-stable, 16 dims, `synthetic: true`; cells holding a reference warehouse share a direction so retrieval
  has signal).

### Blockers (worked around)
- **AEF access path not verified** from the Workshop (Earth Engine export / public mirror not reachable
  here) → committed AOI-sized fixture, `access: fixture` + real path in provenance.
- **LGND GeoParquet not parsed**: `pyarrow` is not a dependency (design says no new deps) → committed
  fixture with the same 1,280 m cells; real path `s3://us-west-2.opendata.source.coop/clay/lgnd-embeddings/`.

---

## Task 4 — Strands agent run end to end (offline + live)

**Status:** done. Live Strands-on-Bedrock Nagoya run sealed locally and to the Compliance S3 store; it made
no red-site claims (the agent refused without imagery; see below).

- Offline: `tests/investigation/test_warehouse_strands_e2e.py` runs the Nagoya card through the **Strands
  harness** with a scripted provider exercising every retrieval tool and sealing ≥ 2 warehouse claims, plus a
  "live-like" variant where ToolUse ids are assigned independently of the decision label.
- Live factories: `treehouse.providers.factories:bedrock_recording` / `:replay`; configs in
  `fixtures/live/configs/`; `scripts/make_live_config.py`; `scripts/publish_run_s3.py`.
- Live runs (model `us.anthropic.claude-sonnet-5-5`, harness strands, all on 2026-11-05 UTC):

| run | calls | $ (ledger) | outcome |
|---|---|---|---|
| `t1-nagoya-sonnet-strands-1` | 21 | 0.50 | **0 actions executed**: every action refused `missing_decision` (defect, fixed) |
| `t1-nagoya-sonnet-strands-2` | 6 | 0.12 | decisions bound; Bedrock returned `stop_reason=content_filtered` with empty content after 3 actions |
| `t1-nagoya-sonnet-strands-3` | 15 | 2.82 | completed: submit_understanding → sources → train examples → AEF 160 m index → linear probe → 2 imagery attempts (no imagery source wired) → limitation → 1 `cannot_assess` claim. Agent rejected LGND 1.28 km cells for warehouses and refused to claim sites it could not see. |

- Evidence committed: `fixtures/live/cassettes/t1-nagoya-sonnet-strands-{1,2,3}.model.jsonl` (pixel-free,
  replayable: `TREEHOUSE_CASSETTE_IN=... treehouse sandbox run --provider treehouse.providers.factories:replay`
  reproduced run 3 offline), `fixtures/live/runs/<run>/` (SEALED, manifest, investigation ledger, claims),
  `fixtures/live/receipts/t1-nagoya-sonnet-strands-3.s3.json` (8 objects in the run store, each
  `ObjectLockMode: COMPLIANCE`, retain-until 2026-11-06).
- Ledger after task 4: $3.55 (46 calls).

### Defects found by the live run and fixed here
1. **Decision binding was impossible for a live model.** `record_decision` required `action_id == ToolUse.id`,
   but Bedrock assigns ToolUse ids. Now a decision also binds to the next action with the identical tool and
   parameters (still one decision per action, before dispatch). The frozen acceptance test's `wrong_id`
   variant was retired as **contract v2** with a replacement test (`test_label_only_mismatch_binds_by_exact_plan`);
   wrong tool / wrong parameters / post-hoc decisions still fail.
2. `record_decision.alternatives` is now a typed `{option, reason}` list so the tool schema tells the model
   the keys (run 2 sent `why_not` and every decision was flagged `invalid_alternatives`).
3. `score/scorecard.py` crashed post-seal when a run had no imagery windows (`bytes_model: "mixed"`).

### Open issues (carried forward)
- `imagery_window` has no source for the warehouse cards, so the agent cannot verify candidates visually →
  wire GSI (Japan) chips (task 5).
- `classify` returns all 3,430 cell scores, which inflates context (run 3 cost $2.82) → cap the returned list.
- `content_filtered` (run 2) is unexplained; watch for recurrence.
- `publish_run_s3.py` uploads the run directory (manifest, traces, claims, ledger) but not the store-level
  request/response blobs; those are covered by the committed cassette.

---

## Task 5 — Strands vision sub-agent classifier (merged, PR #23)

- `classify(method="vision_subagent")` sends a GSI 0.5 m aerial tile per cell (Japan only, attribution
  recorded) to a Bedrock vision model through the Treehouse provider path (metered, cassette-recorded).
  Injected into live runs with `--servers treehouse.providers.factories:vision_servers`; replay uses a
  pixel-free GSI tile log, so no pixels are committed.
- Design choice (labelled): one direct `ModelRequest` per cell rather than a Strands `Agent` loop.
  Classification has no tools or iteration, so the "sub-agent" is a provider-backed classifier.
- `classify` probe/SVM output is now capped at k=200 cells with `n_scored` and `score_summary`.
- Live: two vision-enabled Nagoya runs (`t1-nagoya-sonnet-strands-vision-{1,2}`). **Neither run called
  `vision_subagent`.** Both agents tried `imagery_window` (no imagery source on the warehouse cards) and
  then fell back to embeddings. Vision run 2 recorded **5 `present` warehouse claims at confidence 0.3**,
  labelled embedding-only and unverified. The vision path is tested offline but **not exercised live**.

## Task 7 — Reasoning validity, score (a)

- Rules RV1–RV10 (`investigation/reasoning_rules.py`), now **rv-v2**. Two false positives seen on live runs
  are fixed: an omitted `get_examples` split is the server default "train" (RV4); a missing numeric
  `stated_count` is not_applicable, because `note_limitation` only takes free text (RV7). Planted-bad-agent
  tests still fail RV1 / RV2 / RV4.
- Live rule results: `fixtures/live/rules/*.rv.json`. Run 3 fails RV7 (its claim cites no evidence).
  Vision run 2 fails RV7 (no cited evidence) and RV8 (unreviewed area not stated).
- **Reviewer model (live):** Nova Pro (`us.amazon.nova-pro-v1:0`, a different family from the Claude worker)
  reviewed vision run 2 against `RUBRIC-v1.md`: strategy supported, **evidence_use contradicted** ("claims
  recorded as present without imagery"), adaptation supported, uncertainty supported, stopping supported.
  Evidence: `fixtures/live/review/t1-nagoya-sonnet-strands-vision-2.nova-pro.{review.json,model.jsonl}`.
  The first attempt stopped at `max_tokens`, so the review output cap was raised from 800 to 2,000.
- **AgentCore Evaluations (live):** on run 3 with `Builtin.ToolSelectionAccuracy` (9/10 tool calls Yes),
  `Builtin.ToolParameterAccuracy` (8/10 Yes), `Builtin.TrajectoryInOrderMatch` (Yes), `Builtin.GoalSuccessRate`
  (Yes, judged against the card's assertions), plus the Treehouse Lambda evaluators `treehouse_rules` (FAIL:
  R4 fabrication, the claim cites no evidence) and `treehouse_guard` (PASS).
  Evidence: `fixtures/live/agentcore/t1-nagoya-sonnet-strands-3.agentcore.json` (account id redacted).
  - Fix needed first: AgentCore accepts only Strands/LangChain span scopes and needs message content.
    `aws/agentcore.py` now emits scope `strands.telemetry.tracer` with inline `gen_ai.*` events (the "unified
    telemetry" format in the AgentCore docs), plus tool arguments taken from the investigation ledger.
- Each source above is reported separately; none is blended into another.
