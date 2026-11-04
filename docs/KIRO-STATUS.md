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
