# Treehouse product UI

The React/TypeScript application is the main Treehouse interface. Living Sky reads actual Clay cells from verified stored traces; Atlas reads the server's projected, reconstructed ReportBundle. A small optional AWS challenge panel remains at `/judge/`. Opening pages makes no paid model calls.

## Run a local offline demonstration

Use Node 22.12+ (or Node 24) and Python 3.12+. From the repository:

```sh
uv sync --locked --extra api
uv run treehouse demo --out /absolute/fresh/path/demo
cd ui
npm ci
npm run build
cd ..
uv run --extra api treehouse ui serve --store /absolute/fresh/path/demo/store
```

Open http://127.0.0.1:8765. Choose an existing run, or use **New task** to start a pinned offline replay with a unique new run ID. The demo command refuses to overwrite an existing demonstration; use a fresh output directory. Store paths are operator settings, never browser inputs. Keep new persistent task outputs under `/Users/suhas/Codex` on this workstation.

For frontend development, start the Python server on 127.0.0.1:8765 and run `npm run dev` from `ui/`. Vite proxies `/api` and `/judge` to that local server. Configure the Python server's exact origin for the dev page, for example `--origin http://127.0.0.1:5173`. The backend rejects foreign Host/Origin values; the proxy must preserve the configured browser Host. Use a same-origin production build for final browser checks.

Kiro can serve the same built frontend with a private port preview:

```sh
uv run --extra api treehouse ui serve --store /absolute/path/demo/store --host 0.0.0.0 --origin https://YOUR-EXACT-PREVIEW-HOST
```

This is a private operator application, without a hosted multi-user authentication system. Do not expose the preview publicly. Add `--judge-config /absolute/path/judge-config.json` only in the explicitly provisioned Kiro/AWS environment to enable the optional challenge workbench; see [JUDGE-UI.md](JUDGE-UI.md) and the separate deployment handoff. No AWS execution is required for the product demonstration.

## What is built

| Surface | Status | Evidence and limits |
| --- | --- | --- |
| Main shell and navigation | Built | Direct Home/New task/Runs/Settings and run workspace links; no narrative gate. |
| Story and Developer modes | Built | Same records and URL selections; Developer removes decorative motion and shows exact labels/raw safe metadata. |
| Treehouse/Book/telescope wrapper | Built, restrained | Small original SVG silhouette, brief skippable window/book transition, short telescope transition only. No 3D world. |
| Book setup | Offline demo only | Committed replay presets; recorded goal/model/harness/tracer/budget are read-only. Arbitrary goals/live model selection remain unavailable. |
| Living Sky | Built on offline records | Actual Clay cell IDs/coordinates/similarity and coverage, deterministic geographic layout, filters, SVG/table, keyboard selection, zoom/reset, recorded activity. No embedding-vector projection or invented edges. |
| Atlas | Built on offline records | Claims, evidence references, satellite metadata, original typed metrics, five separate assessments, trace and provenance. No frontend evaluation math or composite score. |
| Imagery preview | Not configured | Metadata only; no licensed pixel payloads, fake scenes or invented pre/post imagery. |
| Trust integration | Stub, visibly Not issued | Original passport numbers/reasons/gate remain inspectable. A separate trust implementation does not establish reporting integration. |
| Live observability | Not configured | Completed recorded spans, no fabricated playback clock, private model reasoning or streaming claim. |
| Scene Builder and simulations | Planned | Missing terrain/geometry/validated engine is explained. No false runnable controls. |
| Display accessibility | Built; manual testing remains | Semantic headings/forms/tables, visible focus, keyboard controls, dark/light/high-contrast, large text, reduced motion. Narration planned/off. |
| Optional AWS challenges | Separate optional panel | `/judge/`; live receipts require actual server-side Kiro invocation. Samples remain unverified. |

The API's pinned replay path, not decorative animation, controls run status. Pages never modify a sealed run. Starting a new replay uses the existing Python service and preset budgets; refreshes only read local status. A Clay cell and a claim are distinct records: the current backend records no authoritative association, so the UI does not invent one. Claims select evidence through their actual `evidence_refs`.

Metrics retain value, type, tier, sample/denominator, gold/verified counts, intervals, reasons, estimator and manifest. SYNTHETIC/recorded/modelled-bytes labels remain attached. Agent-reported confidence is identified as the agent's own figure. Cost panels preserve unpriced values and distinguish estimates or modelled bytes from measurements; they are not AWS billing statements.

## Routes and preferences

`/runs/:runId/sky`, `/runs/:runId/atlas`, `/runs/:runId/trace`, and `/runs/:runId/scene` are direct links. Atlas uses `?pane=summary|dataset|evidence|evaluation|trust|trace|provenance`. Selection query parameters `search`, `cell`, `claim` and `evidence` persist across workspace links; a cell is identified together with its search ID. Browser Back/Forward restores URLs. Display mode/contrast/text/motion are the only localStorage preferences; run content and credentials are not stored there.

The results table is available alongside the geographic sky or by selecting **Table only**. System reduced motion overrides story animations. Pausing visuals changes presentation, never backend execution. Narration is off and planned; complete text remains available.

## Build and verification

```sh
cd ui
npm ci
npm run typecheck
npm run build
npm run test:e2e
```

`test:e2e` runs the separately authored independent browser acceptance script. Set its documented base URL/store expectations before running against a disposable offline browser store. `PLAYWRIGHT_CHROMIUM_EXECUTABLE` may select system Chrome; CI can install its pinned browser with `npx playwright install chromium`. Test authorship and verdict are recorded separately from builder render observations. TypeScript uses strict checks; Vite's transpilation alone is not a type check.

Browser screenshots/interaction observations are under the integration handoff's `work/treehouse-pr/` directory. Builder observations do not substitute for independent acceptance. Browser automation uses actual API data and no AWS. Windows Narrator/Edge, NVDA/Firefox, VoiceOver and real touch/device checks require manual sessions; Chromium emulation does not establish them. Cross-browser and 200% zoom checks must be recorded explicitly rather than inferred from a desktop screenshot.

## Manual assistive-technology checklist

1. With Narrator + Edge, use headings/landmarks to reach Book, preset, goal and setup details. Confirm the goal is announced as read-only and live options are unavailable.
2. Operate New task, mode/settings, results selection, filters and all workspace links by keyboard. Confirm visible focus and no trap or automatic run restart.
3. In Living Sky choose Table only, inspect a cell's ID/coordinates/similarity, and verify selection/deep links survive Developer mode and Atlas navigation.
4. In Atlas navigate Summary/Dataset/Evidence/Trust/Trace. Confirm the exact evidence references, synthetic labels, confidence explanation, Not issued reasons and metric methods are read.
5. At 200% browser/text zoom and high contrast, confirm controls reflow, tables scroll within their regions, and meaningful content remains available. With reduced motion, confirm no window/telescope animation is forced.

Sources used for setup: [React createRoot](https://react.dev/reference/react-dom/client/createRoot), [Vite guide](https://vite.dev/guide/). Product UI motion/forms/accessibility guidance informed native forms, labeled controls, table alternatives, explicit focus and per-animation reduced-motion handling.

## Agent investigations and final prediction database

The **Investigation** Atlas pane separates agent decision observations from the MCP
Trace. For an opt-in sealed investigation, it shows contemporaneously recorded
rationale, alternatives and their stated reasons, self-reported decision
confidence, prior evidence references, explicit parent/revision links, the planned
tool parameters, and the actual linked action status/result/span. Flags and missing
action bindings remain visible. Recorded model IDs/settings/region are shown only
when the public span metadata actually includes them; absent values say not recorded.

The pathway consists only of recorded edges. It is not private model reasoning and
is not evidence that the explanation faithfully describes internal computation.
Process measurements, catalogue matching, confidence calibration and cost/speed
stay separate. Semantic reasoning quality is **Not assessed** unless a separately
stored independent rubric review is integrated; this pane never starts a reviewer
model from a GET. Missing prices remain unpriced. A logical clock is disclosed in
the metric detail, rather than presented as physical wall time.

The geographic prediction view reads the verified GeoJSON database. Red diamond
markers mean **positive agent predictions**, not confirmed ground truth. Each marker
and its equivalent table row preserve the original claim/trial identity, lon/lat,
class, predicted status, agent confidence, evidence references and recorded decision
binding. Enter/Space selects a marker. Selection persists in the URL through mode
and workspace changes. Decision links open the actual recorded record; evidence
links open imagery metadata when present. A prior non-imagery result remains an
identified tool result, not an invented image. Clay candidate cells are distinct;
no nearest-cell/claim association is fabricated.

Positive statuses are present/intact/damaged/destroyed. The SQLite export also
retains nonpositive claims; the red map deliberately does not reinterpret absent or
cannot-assess records as detections. Database downloads are produced separately by
the trusted CLI/core export path; opening this pane writes no SQLite or GeoJSON
files. CLI investigation execution accepts a registered trusted local provider;
Book continues to offer only immutable offline replay presets until live execution
is separately configured.

Legacy runs show **Decision explanations unavailable** and their actual positive
claims with no invented decision binding. Missing grading reference, incomplete
coverage, early stop, denied tools and insufficient observations retain their
explicit no-grade/limitation explanations. Catalogue coordinate matching against a
small public labelled reference is not a measurement of image-classifier accuracy,
exhaustive geographic inventory quality, or parity with a human investigation.
