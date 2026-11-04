# Opt-in investigation sandbox

The sandbox accepts an injected `ModelProvider` and uses the existing `execute`, `PlainLoop`,
`ToolGateway`, policy, `BudgetGuard`, `ClaimLedger`, trace chain and seal. The framework does not
prescribe a search strategy. Existing replay runs retain their original MCP catalog and
trace heads. Only cards explicitly allowing `record_decision` can start an investigation.

This is a trusted local Python evaluation environment, not OS isolation. Installed plugin code has
the permissions of the server process. The browser cannot supply a Python import or provider URL.
Use public benchmark inputs; the public projection scrubs explicit credential/prompt/pixel fields
and familiar credential strings, but cannot guarantee detection of secrets in arbitrary prose.

## Offline local demonstration

From the repository, choose a new store/run ID. The command refuses to overwrite a sealed run:

```sh
.venv/bin/python -m treehouse.cli sandbox demo \
  --store /Users/suhas/Codex/treehouse-investigation-demo/store \
  --run-id investigation-demo

.venv/bin/python -m treehouse.cli ui serve \
  --store /Users/suhas/Codex/treehouse-investigation-demo/store
```

The demo explicitly calls `service.evaluate` after sealing to prepare the existing UI bundle.
It does not call AWS or any paid model. Its example controller selects a scene from actual STAC
observations, reads real synthetic pixel bytes, and records a brightness-component candidate with
low agent confidence and an explicit coverage limitation. It imports no grading key or world
generator. The brightness rule is an unvalidated synthetic-specific heuristic, not a foundation
model, a detector benchmark or evidence of real-world geospatial accuracy.

The prepared browser-validation store is
`/Users/suhas/Codex/2026-11-04/alr/work/treehouse-pr/investigation-browser-store`, run
`investigation-demo`. Its manifest is
`sha256:8358a0cf5abc9f7f923225b9ef09e77112c089165ef5892c16de6336d1e41097`.
It contains one positive synthetic claim, prior imagery evidence, actual decision parents, and a
standard UI bundle. This is a recorded local result, not a live model measurement.

## Provider and tool plugins

`treehouse.investigation.example:make_provider` is a working offline factory. A provider factory
accepts `card=` and `config=` and returns an object implementing:

```python
async def complete(request, *, role, trial_index, turn) -> ModelResponse: ...
```

The provider must expose `provider_name`. The request carries public goal, AOI, class scale,
permitted sources, windows, steps and effective budget. It excludes card `keying`, key paths,
grading masks and grader notes. Tool results and image bytes reach the provider normally; sealed
model request/response blobs contain only pixel-free messages. There is no automatic fallback to
a scripted agent or another provider.

A real configured run uses an opted-in task YAML and a matching `RunConfig` JSON:

```sh
.venv/bin/python -m treehouse.cli sandbox run \
  --task /Users/suhas/Codex/my-investigation/task.yaml \
  --config /Users/suhas/Codex/my-investigation/config.json \
  --provider treehouse.investigation.example:make_provider \
  --run-id example-plugin \
  --store /Users/suhas/Codex/my-investigation/store
```

`config.task_ref` must equal the opted-in card's `ref()`. Adding tools changes the card hash; create
the config after updating the card. Tool calls, tokens, bytes, dollars and wall time use the stricter
enabled limits from card/config. Original runner behavior is unchanged outside investigation opt-in.
Provider/runtime exceptions preserve and seal partial claims with an explicit error stop. Budget,
max-turn and normal agent stops are preserved and do not imply exhaustive coverage.

`--classifier module:factory` optionally creates a trusted classifier. Its protocol is:

```python
async def classify(*, window: WindowResult, image: Image, cls: str) -> dict:
    # Required: label, confidence (0..1), explanation, model_id.
    # Optional: usage {input_tokens, output_tokens, ...}, cost_usd.
    ...
```

For an existing genuine vision `ModelProvider`, use:

```python
from treehouse.investigation import VisionClassifier
from treehouse.schemas.config import InferenceParams

classifier = VisionClassifier(vision_provider, model_id,
                              InferenceParams(max_tokens=512, temperature=0))
```

`classify_window(result_id, cls)` requires prior successful imagery and actual transient image
bytes. It returns the original `evidence_ref`, `source: model_estimated`, response model ID, model
confidence and usage/cost where supplied. No grader reference enters the classifier. Missing cost
is `null`/unpriced and missing usage is unknown. Classifier charges share the same budget guard;
reported cost and tokens include calls whose response subsequently fails parsing. The ordinary
worker-only scorecard remains unchanged; the investigation report displays worker/classifier cost
separately and abstains on a complete total when prices are unknown.

`--servers module:factory` passes a trusted callable to each trial. It receives `card`, `ledger`,
`pixels`, and `default_servers` and returns the server map. For a custom imagery source, replace
`default_servers['imagery']` with `make_imagery_server(source)`. The source must implement the
existing `ImagerySource.window` protocol, return a valid `WindowResult`, and put actual encoded
pixels in the supplied `PixelCache` under their decoded pixel hash. Existing Clay search is reused.

Default imagery remains synthetic or pinned recorded metadata. A live COG reader and measured
network-byte implementation are not delivered here. A plugin must not label modeled/unknown
bytes as measured. Source licenses, scene IDs, as-of bounds and returned strings still pass through
the gateway's existing checks. Trusted server plugins remain responsible for their own actual I/O.

## Decision and evidence contract

Before each action, the agent calls `record_decision` with the future `ToolUse.id` as `action_id`,
the exact tool and parameters, concise rationale, considered alternatives, confidence, optional
prior `parent_id`, and prior successful `evidence_refs`. The runtime refuses reused IDs, post-hoc
decisions, unknown parents, future/error/blocked evidence, and mismatched tools/parameter hashes.
A refusal does not authorize the action. One valid decision binds one action before dispatch,
including actions later blocked by policy, budget or tool failure.

The sealed per-trial `*.investigation.json` stores decisions, action attempts, exact arguments,
result IDs, sequence, flags, stop details and actual trace span references. The report preserves
missing edges as missing. Explanation availability, consistency and evidence linkage are observable;
rationales remain agent self-reports, not proof of hidden internal reasoning.

## Independent post-seal reports and exports

```sh
.venv/bin/python -m treehouse.cli sandbox evaluate investigation-demo \
  --store /Users/suhas/Codex/treehouse-investigation-demo/store

.venv/bin/python -m treehouse.cli sandbox export investigation-demo \
  --store /Users/suhas/Codex/treehouse-investigation-demo/store \
  --output /Users/suhas/Codex/treehouse-investigation-demo/export
```

Evaluation verifies the manifest, seal, task, claims, trace chain and blobs first. It never contacts
the worker or rewrites the store. Export verifies first and requires a new destination directory.
SQLite `detections` contains every sealed claim, with composite `(trial_id, claim_id)` identity;
GeoJSON contains only present/intact/damaged/destroyed claims. Both preserve original coordinates,
class, status, agent confidence, evidence and bound decision ID. No guessed markers are added.
`database_geojson(store, run_id)` is the pure verified equivalent for read-only UI views.

Legacy sealed runs return empty decisions/pathways with an explicit missing-record limitation;
their actual claims can still be displayed/exported with `decision_id: null`. No old decisions are
inferred or added to old traces.

Pass a normalized grader-only `treehouse.reference/1` JSON through `--reference path.json` to the
evaluation command. Required fields are `source` (dataset/version/url/license/attribution),
`quality` (complete/incomplete), `coverage` (GeoJSON Polygon or null), and unique-ID `features`
with `lon`, `lat`, `cls`, and `split` (reference/holdout). Only holdout features inside reference
coverage and task AOI are matched. IDs/splits, coordinates, classes and coverage are validated.
Matching is one-to-one and class-aware using card class tolerances; duplicates, wrong classes,
and outside-AOI predictions receive no credit. Repeated trials are evaluated separately.
Correct predictions of permitted reference examples are explicitly excluded from heldout counts,
precision and confidence calibration, while their original database records remain unchanged.
Overlapping reference/holdout matching neighborhoods abstain as ambiguous rather than arbitrarily
assigning a prediction to either split.

Complete scoped keys support catalog TP/FP/FN, precision, recall and confidence Brier records.
Brier targets catalogue presence of positive predictions; it does not calibrate damage status,
global detection probability or private reasoning. Empty/ambiguous reference scope abstains.
Incomplete catalogues abstain on definitive unmatched-prediction FP/precision and calibration;
unmatched predictions require adjudication and unreviewed areas remain unknown. Listed-object
match recall is not global recall. Source provenance and coverage are reported.

All numeric report entries use existing `TypedNumber` records. Process diagnostics measure
decision coverage, unsupported claims, cited-image GSD limits, unavailable evidence attempts and
repeated windows. Approximate image coverage samples a 30×30 AOI grid; footprint coverage does not
establish visibility, semantic correctness, or exhaustive search. Reported footprint coverage unions
observations across trials, rather than measuring each trial. Logical-clock elapsed time is explicitly
identified and is not a measured wall-time benchmark. No composite trust score is issued.

## Optional semantic process review

`review_investigation(store, run_id, reviewer, model_id=..., params=...)` performs one fresh
`process_reviewer` call with no tools and at most 800 output tokens. Its configured and returned
model IDs must differ from configured and observed worker IDs. The exact independently authored
rubric is packaged as `treehouse/investigation/RUBRIC-v1.md` (SHA-256
`66900d40d18f47dc80a845648c1eac56a4934f8098ceb31d7e4a883f6870f38f`).

The reviewer sees public task constraints, sealed decisions/actions, evidence metadata and claims.
It sees no worker conversation, raw reasoning blocks, grading key or held-out labels. The helper
validates the five permitted rubric criteria, assessments, actual record citations, bounded output,
and distinct response identity. It returns a `treehouse.process-review/1` model-estimated report,
with nullable cost, and never changes the store or issues Rely. Metadata cannot resolve pixel
content or causal intent by itself; the rubric requires insufficient-evidence findings where needed.

```sh
# Explicit inference action, only on Kiro when using a paid provider:
.venv/bin/python -m treehouse.cli sandbox review investigation-demo \
  --store /Users/suhas/Codex/treehouse-investigation-demo/store \
  --reviewer my_server_plugins:make_reviewer \
  --model-id separately-configured-review-model \
  --output /Users/suhas/Codex/treehouse-investigation-demo/process-review.json
```

Review output is a new standalone file, not auto-loaded mutable evaluation state. UI GETs never
invoke a reviewer or worker. Python plugins must use the existing provider/spend-ledger path for
actual paid models. No paid calls, AWS deployment, purchases or model-ID verification were
performed on the Mac; real source/model configuration and live validation remain a Kiro step.

## Evidence and remaining limits

The independently authored cases were frozen before implementation (the later classifier adapter
and review cases used isolated contexts and were frozen before their respective helpers). Builders
did not write or edit their assertions. The integrated suite currently contains 50 offline cases,
including reference-example isolation, ambiguous split neighborhoods and malformed classifier accounting:

```sh
.venv/bin/python -m pytest tests/investigation --override-ini addopts='' -q
.venv/bin/python -m pytest tests/journeys/test_demo.py tests/integration/test_loop_gateway_e2e.py -q
.venv/bin/ruff check src/treehouse/investigation src/treehouse/runner.py \
  src/treehouse/gateway/gateway.py src/treehouse/cli.py
```

The integrated independent cases passed 50/50; the original demo/loop checks passed 29/29,
including the nine unchanged golden replay heads. These exercise transport, causality, budgets,
integrity, sealed data export, catalogue matching, reviewer isolation and public incomplete-reference
handling. Synthetic providers and catalogue comparisons do not establish actual model imagery
accuracy, physical-world performance, or human-baseline superiority. Next experiment: use one
verified Kiro-only provider and permitted public imagery source, retain grader isolation, and
independently adjudicate unmatched detections before making accuracy claims.
