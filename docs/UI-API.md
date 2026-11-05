# Offline product API

`treehouse.ui.web.create_app(store_root, *, origin='http://127.0.0.1:8765',
frontend_dist=None, judge_app=None, server_reference=None)` serves the product contract in
`work/treehouse-pr/PRODUCT-UI-CONTRACT.md`. The optional `api` extra supplies
FastAPI. Importing the package does not import FastAPI or AWS clients.

The server chooses one local store root. GET does not create a missing root,
replay runs, execute agents or model reviewers, append evaluation records, or write cached reports. The investigation endpoint may compute a pure read-only report from verified sealed observations. The product supports nine
committed replay presets from `fixtures/demo/runs.yaml`; it accepts no custom
model, goal, budget, tracer, file path, script or live-mode override. Preset goals
and settings are recorded, read-only descriptions. Each explicit POST creates a
fresh `replay-<uuid>` run and executes existing `service.run` and `service.evaluate`
on one worker thread. Their real outcomes determine queued/running/report-ready/
failed state. The immutable preset has one trial and at most 40 turns. No AWS
client or external API is invoked.

## Snapshot and numerical report

`GET /api/runs/{id}/snapshot` is the verified bridge for the Story and Developer shell. A sealed run remains inspectable when optional evaluations are missing. Pending runs have empty trace/prediction collections, null metrics and explicit reasons. Corruption fails closed. Exact claim status, claim/trial IDs, decision IDs and support references survive adaptation/export; present is a prediction, not confirmed ground truth.

Snapshot mode, embedding/reference provenance, actual vision availability and limitations travel with all reports. Each separate evaluation section has status/value/reason and named `scores` with metric, numeric value, unit, numerator, denominator, basis and availability reason. Rules pass rate excludes not-applicable criteria; precision and recall use their declared protocol/population. ECE is percent, Brier raw. Missing reviewer/AgentCore scale or validated predicted-accuracy evidence stays unavailable. Constructed reference-derived inputs stay method_test_only.

`thinking_summary` is a deterministic, bounded summary of recorded decisions and action outcomes, including model/harness, reasons, alternatives and stopping where recorded. Omitted coverage is explicit. It does not recover hidden reasoning. UI and readable Markdown show these scores and narrative alongside optional raw details; JSON/GeoJSON retain evidence identity.

Historical cell output/calibration require a sealed reference/split binding; mutable adjacent split files cannot define a historical score. An explicit server-owned `--reference` provides a separate current catalogue comparison, validated and frozen at server startup with a content reference. The browser cannot choose its path or obtain label features. A supplied comparison is not rewritten into the sealed historical run.

Public tool parameters and nested metadata use explicit field projections, with normalized sensitive-key and known token redaction as defense in depth. No arbitrary nested tool input, raw imagery, model-message blobs or key material belongs in the snapshot. This remains a local trusted-store interface, not a multi-user security boundary.

## Read contract

- `GET /api/capabilities`: offline capability reasons, one-run concurrency limit,
  and `/judge/` only when the caller mounts the separate optional judge app.
- `GET /api/tasks`: safe summaries and informational RunConfig projections.
  Worker/verifier/summarizer script and cassette pointers are omitted. TaskCard
  keys, source paths, grader plans and forbidden-source definitions are absent.
- `GET /api/runs` and `/api/runs/{id}`: recorded run summaries and actual current
  worker state.
- `GET /api/runs/{id}/bundle`: reconstruct `ReportBundle` with existing
  `service.build_bundle`, after `service.load_sealed` verifies the sealed run and
  ledger. Load the latest rules, score and trust records through ledger-driven
  `LocalStore.list_records`; verify score/trust refer to this manifest. Missing
  evaluations or integrity failure return 409. Mutable `bundles/*.json` are never
  used as evidence.
- `GET /api/runs/{id}/investigation`: exactly the core
  `evaluate_investigation(store, id, reference=server_reference)` report after store
  inspection and sealed verification. Decision/action bindings and pathway edges
  are not inferred by the HTTP layer. Legacy runs return empty decision/pathway
  arrays with explicit unavailable-reasoning limitations. This read does not call
  an agent/reviewer/classifier or append a report record.
- `GET /api/runs/{id}/database`: exactly the pure core
  `database_geojson(store, id)` FeatureCollection, reused by the separate file
  export. It contains positive claims only, with their original geometry,
  claim/trial/class/status/confidence/evidence/decision/synthetic properties.
  Reading never creates a database or export directory. Legacy decision IDs are
  null. A broken seal fails both endpoints with 409.
- `GET /api/runs/{id}/clay-searches`: validate actual successful `clay_search`
  result payloads as `ClaySearchResult`. Preserve real cells, coverage, result,
  trial and span IDs. Search identity is `trial_id:span_id`; `trace_ref` is the
  existing `span:<id>` reference. Cell IDs may repeat across searches. Empty results
  include a reason; no synthetic stars are added to absent searches.
- `GET /api/runs/{id}/events?after=0&limit=100`: one event per completed recorded
  span, ordered by end time then trial then span. Sequence begins at 1. `after`
  means number already consumed; limit is 1–200. Events carry recorded end time,
  not a fabricated playback clock. Pending jobs return an empty incomplete page.
- `GET /api/runs/{id}/associations`: explicitly empty, because no verified
  cell-to-claim relation exists. Claim-to-image evidence refs remain in the bundle.
- `GET /api/runs/{id}/verify`: sealed-run and evaluation-ledger verification,
  manifest ref, ledger head, sanitized problems and bundle provenance. This is
  tamper evidence within the local store, not external attestation. No independent
  expected head is accepted from the browser.
- `GET /api/runs/{id}/export`: attachment with the public bundle and snapshot when evaluated, or the inspectable snapshot when optional score ledgers are missing; no image bytes or private store files.

All errors have a string `detail`. Invalid parameters return 400, missing runs
404, integrity/not-ready/busy 409, POST bodies over 4096 bytes 413, unknown preset
422, and missing frontend build 503. Run IDs are one safe store segment, maximum
128 characters. Raw blob, file and key routes do not exist.

## Public projection and safety boundary

Numeric values, tiers, panels, intervals, denominators, `n`, `n_gold`, reasons,
details, synthetic flags and replay flags are preserved from the authoritative
bundle. Stored bundle statistics are preserved. The read-only snapshot derives named rule percentages, a recorded narrative and any explicit current-reference comparison locally without model calls or store writes. Trust remains the existing stub:
**Not issued**, never a claimed production trust assessment.

Trace attributes are an explicit allowlist of public IDs, tool names/results
references, costs, token counts and process facts. Raw input/output messages,
model output text, final text, cassette paths and arbitrary attributes are not
exported. Recorded raw span error messages are withheld. Generic public fields
redact unsafe control text, oversized strings, obvious credential assignments,
answer-key paths, image data URIs, and local absolute paths. Private dictionary
fields such as prompts, keys/labels, credentials, scripts, cassettes and pixel/blob
payloads are removed. Ordinary public narrative and metric semantics remain;
this projection is not an automatic PII detector for arbitrary prose.

Before store reads or replay writes, reject symlinks and special files beneath
the canonical server root and enforce 20,000 entries / 256 MiB inspection limits.
The reader avoids LocalStore's mkdir constructor on GET. Verification may inspect
all blobs and the ledger; large stores cost more time and fail closed at the
inspection bound. Existing stores may still be rewritten entirely by someone
with filesystem access. This local app assumes no hostile concurrent filesystem
writer; pre-read path checks do not replace an operating-system access boundary.
The worker serializes its own writes against sealed-data reads. There is no
multi-process job coordinator or Windows store implementation; current LocalStore
uses `fcntl`, and native Windows operation remains unverified.

Host and Origin are checked against localhost defaults and the exact configured
preview origin, including its port. Every POST requires an application/json content
type and an Origin exactly matching the configured origin; missing/different Origin
or Sec-Fetch-Site: cross-site is refused with 403. Capability rows independently
report Bedrock, Strands, AgentCore and simulation (unsupported: no simulation engine,
terrain, validated geometry or boundary conditions are configured; recorded presets
are not simulations); historical probes, installed
packages and configured judge URLs do not mark live execution available. The preview origin has no trailing slash.
This is not public authentication. Same-origin CSP disallows external scripts,
inline script/style, framing and object content. Browser code receives no AWS
credentials. The caller may mount the reviewed judge workbench at `/judge`; its
relative routes and its own guards remain separate from the product workflow.

Production static serving supports index-based SPA fallback and selected compiled
assets (JS/CSS/font/SVG), rejects symlinks and traversal, and never falls back for
`/api` or `/judge`. Source maps, JSON/config files and dotfiles are not served as
assets. With no build, API endpoints still work and homepage returns 503.

## Local commands and verification

Run these from the reviewed repository root under `/Users/suhas/Codex`:

```sh
uv sync --locked --extra api --extra aws --extra strands
uv run --extra api pytest -q tests/unit/test_ui_api.py
```

The feature author's supplemental checks use a fresh real nine-run demo store:
actual facts/scorecards/cells/events, before/after file hashes for all GETs, forged
unhashed bundle rejection, symlink and evaluation tampering, origin/host/ID/body
validation, and an actual pinned replay with a one-job busy guard. These are not
independent acceptance tests. The parent task separately assigns independent
black-box tests and fresh review before integration. No actual AWS, browser,
Windows accessibility or physical hardware behavior is proven by these API tests.

The integration owner adds the `treehouse ui serve` CLI and builds the React UI.
The factory can be used directly before that CLI is merged:

```python
from pathlib import Path
import uvicorn
from treehouse.ui import create_app

app = create_app(Path('/Users/suhas/Codex/path/to/demo/store'),
                 frontend_dist=Path('/Users/suhas/Codex/path/to/treehouse/ui/dist'))
uvicorn.run(app, host='127.0.0.1', port=8765)
```

For Kiro port preview, use its exact HTTPS origin and the integration CLI's bind
option. Retain the existing store and proof artifacts. A server restart loses
in-memory queued/running job status; sealed results remain discoverable. Partial
interrupted runs are not presented as successful reports. Stop and diagnose a
failed replay before starting another; no repair or cleanup occurs on GET.


## Investigation grading boundary

`server_reference` is an optional trusted operator Path passed to `create_app`.
Browser query/body fields cannot choose a reference file, plugin, URL or store.
Only aggregate grading/provenance is returned; held-out feature labels, grader keys
and image pixels are excluded. The HTTP investigation response preserves the exact
core public-report dictionary; security/privacy of its selected fields belongs to
that shared core report, rather than a second UI evaluator. Existing public bundle
redaction and the separate endpoint's integrity checks remain in place.

The new UI JSON decoders validate the report schema, decision/action/edge fields,
confidence ranges, typed numeric records, and positive GeoJSON point features.
Malformed records fail closed. Prediction coordinates must be finite EPSG:4326
lon/lat and duplicate `(trial_id, claim_id)` identities are refused. No frontend
catalogue grading or semantic reasoning score is computed.

Independent frozen HTTP acceptance is in the separately authored
`test_investigation_http.py` suite: exact report/GeoJSON equality with core and
export, GET file-hash stability, tamper rejection and legacy unavailable reasoning.
The separately authored `investigation-browser.cjs` checks actual seeded decisions,
self-reported confidence, alternatives, outcome, prediction table and keyboard
marker selection. Builders do not change these expectations to fit their code.
