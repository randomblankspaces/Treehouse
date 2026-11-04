REEHOUSE — MASTER UI IMPLEMENTATION SPECIFICATION
Version: 1.0
Date: 2026-11-04
Status: Product/UI implementation handoff, not a claim that every feature exists
Repository: https://github.com/randomblankspaces/Treehouse
Intended audience: The next engineering/design agent implementing the frontend and required backend adapters
Primary mandate: Build an accessible, usable geospatial AI-agent observability and evaluation application, with a simple pixel-art narrative wrapper and a serious data interface.
Instruction to the implementing agent: Read this document first, then inspect the current main branch, open PRs, schemas, tests, and design docs. Do not implement against imagined APIs. Treat this specification as the UI/UX product contract; treat the repository's validated schemas and safeguards as the data contract. When the two conflict, preserve correctness, privacy, licensing, and sealed-run integrity, and document the discrepancy. Do not silently fabricate unavailable results, geospatial data, model states, or evaluation scores.

1. Product definition
Treehouse helps a person ask an AI agent to build or inspect a geospatial dataset, watch the observable work it performs, inspect actual satellite evidence, and judge whether to trust the outcome. The application should be understandable to a nontechnical partner while allowing a developer to drill into exact tool calls, model/harness/tracer configuration, costs, checks, and provenance.

The presentation metaphor is a small treehouse at night. A child reads a book and looks through a telescope. The book is the task-configuration interface; the telescope is only a transition into an explorable night sky. Stars represent Clay embedding search cells and candidate regions. A selected constellation leads to the dataset and evidence workspace. A future Scene Builder enables 3D reconstruction and simulations where sufficient data and validated capability exist.

What is most important, in order:
1. Living Sky — real Clay-search candidate visualization + ongoing agent activity.
2. Constellation Atlas — actual dataset, satellite evidence, plain summary, cost/speed, trace, scoring and trust.
3. Scene Builder — 3D spatial investigation and simulations (stretch goal, honestly labeled).
What is intentionally simple: logo arrival, zoom through window, child and book entrance, child looking through telescope. These are short scripted transitions, not explorable 3D environments and not separate dashboards.

Design maxim: The story gets users into the experience; the data is the product. Do not make a decorative animation block access to work.
2. Existing repo reality and scope boundaries
At the time this document was prepared, main contains a Python package and CLI with task cards, a plain agent loop, fake/replay/record modes, MCP geospatial tools, tracing and sealed storage, deterministic checks, score panels, an HTML report renderer, and an AWS/AgentCore prototype. There is an offline demonstration of recorded runs. The design docs describe a richer UI as deferred work. An open draft PR (#8 when inspected) covers replay/probe reliability, not the completed judge-facing UI. Recheck all these facts before coding.

Read these first:
- README.md, docs/README.md, docs/SCOPE.md
- docs/design/SYSTEM-DESIGN.md, docs/design/IMPLEMENTATION-DESIGN.md
- HANDOFF.md, TODO.md
- src/treehouse/service.py — current run/check/score/trust/report orchestration; note where the service is still wired to a stub passport despite a separate trust-core implementation.
- src/treehouse/schemas/{task,config,tools,trace,claims,numbers,scorecard,passport,bundle,manifest}.py
- src/treehouse/report/html.py — existing static, noninteractive report
- src/treehouse/aws/agentcore.py, docs/design/AWS-BLUEPRINT.md
Do not assume any of the following are already finished: React frontend, live trace stream/API, full real-image preview service, Strands end-to-end deployment, AgentCore live deployment, reliable trust-core integration into the reporting service, 3D reconstruction, physical simulation, hosted accounts/authentication. Feature-gate each until verified. Differentiate merged, branch-only, offline-tested, AWS-deployed, demo/replayed, and unavailable statuses.

Backend principle: One Python service path should provide the facts to CLI, report, API and UI. The frontend does not implement trust statistics, mint claims, recompute grading rules, or modify sealed runs. AgentCore evaluation outputs are a separate comparison signal, not replacements for Treehouse's own score panels.
3. Narrative and navigation contract
The experience comprises seven scenes but only three major information workspaces.
#	Scene	Type	Purpose	Developer mode
1	The Treehouse	Cinematic intro	Logo, arrival	Direct home / recent runs
2	Through the Window	Cinematic intro	Reveal child, book, telescope	Skip
3	The Book	Simple task setup	Query, context, model, harness, tracer, budgets and eval settings	Standard task-configuration form
4	Looking Through the Telescope	Cinematic transition only	Move to starfield after submit	Skip
5	The Living Sky	Core workspace	Clay embeddings and live observability	Graph/table + event log
6	The Constellation Atlas	Core workspace	Dataset, imagery, evidence, summary, cost, speed, trace, trust	Conventional multi-panel dashboard
7	The Scene Builder	Stretch workspace	Geographic reconstruction and simulations	Technical 3D controls and parameters


Recommended route model (actual router choice is an implementation decision): /, /new, /runs/:runId/sky, /runs/:runId/atlas, /runs/:runId/scene/:featureId, /runs/:runId/trace, /runs/:runId/report, /settings. Scenes 1, 2 and 4 should be view states/transitions, not mandatory URL destinations.

Navigation requirements:
- A persistent small navigation switcher for Living Sky / Atlas / Scene Builder, plus New task, Runs, Settings, Developer mode, and Skip animations.
- Every cinematic transition can be skipped immediately; returning to an existing run must never force an intro replay.
- URLs and deep links preserve selected run, selected star/cell/claim and active pane where feasible.
- Scene state and route changes must not mutate a run or interrupt a running backend job. “Pause visuals” means pause client-side animation, not the backend agent.
- Users can change Story/Developer mode in any workspace without restarting work or losing selection.
- Explain the relation between a Clay candidate cell and a claimed bridge/feature; they are not inherently the same entity.
4. Scene-by-scene interaction specifications
Scene 1 — The Treehouse (intro)
Full viewport in midnight navy. Treehouse logo centered, a small low-resolution silhouette behind it, one warm glowing pixel window, a few subtle stars. Logo/brand is legible without animation. Enter moves camera toward window with simple 2D layers/scaling. Keyboard focus goes to Enter Treehouse and Skip Intro. Optional Recent runs link. No spinning loader disguised as the intro. Keep this brief (target ~1–2 seconds, user skippable).

Developer mode: clean home page with New Task, Resume Run, Recent Reports. No mandatory scene animation.
Scene 2 — Through the Window (intro)
Quick visual approach through the window to a quiet pixel-art room. A child sits with an open book, telescope near the window. Warm orange light against cool blue outdoors. The camera moves into the book. Do not require a freely navigable avatar, collision system, physics engine or real-time 3D room.

Developer mode: immediate task setup. With reduced motion: dissolve or instant route switch; no fake zoom or parallax.
Scene 3 — The Book (task configuration, not the main dashboard)
The book fills the screen; its pages become an accessible, crisp web form with a friendly chat composer. The first visible question is “What would you like the agent to investigate?” Keep advanced controls folded into Agent setup and Evaluation settings.

Inputs: query/goal, selected task card, area of interest and time window, allowed datasets/tools, worker model/provider and family, optional verifier model/family, harness (plain_loop or strands when available), tracer/backend (local JSONL, OTLP, CloudWatch where available), recording/replay/live mode (only if supported), trials/seed/max turns, budget guard and limits, evaluation method and AgentCore comparison opt-in where deployed. Show input context/prompt and permissions, but do not expose protected answer keys or grader-only data to the worker. Task-card editing must follow validation rules, not free-form arbitrary schema mutation.

Provide Simple and Advanced setup within either UI mode. A nontechnical user can use a preset. A developer can inspect validation errors, model IDs, backend availability, exact hashes and configuration JSON. Present capability as Available / Offline demo / Not configured / Unsupported, derived from actual checks, not hopeful labels. Show estimated cost only with a valid price table and distinguish estimates from bills.

On Start: validate; show clear budget/risk warnings; submit the task through the backend; create or navigate to run; play one short transition into the sky only if full motion is enabled. Handle denied/invalid model access without losing the form.
Scene 4 — Looking Through the Telescope (transition only)
A single brief sequence: child lifts eyes from book, looks through telescope, viewpoint transitions to the starfield. No telescope options, no intermediate scene selection, no technical panel. This transition must not imply searching has already succeeded. If live startup is pending, show a genuine status such as Preparing run before the appropriate data exists.

Developer mode and reduced motion: skip straight to Living Sky.
Scene 5 — The Living Sky (first major information workspace)
The center shows an interactive midnight-blue field of small, pixel-influenced glowing stars. Each real, identifiable star represents a Clay search cell/candidate, with consistent cell_id. Stars appear from real search results or explicitly labeled demo fixtures. Highlight returned/selected candidates as tool results arrive. Gently dim candidates ruled out by recorded results; never imply nonreturned cells were evaluated or rejected. When evidence connects a cell to a candidate object, show that connection, but never invent graph edges.

Vital semantics: ClaySearchResult currently exposes cells[] (cell_id, geographic center, similarity) and coverage. It does not guarantee a full high-dimensional vector dump, nearest-neighbor adjacency graph, arbitrary pairwise links or a physical 3D star position. An initial implementation may position points deterministically from their geographic coordinates in a stylized canvas, or expose a clearly labeled 2D projection if actual embedding vectors become available. Label visual layout mode Geographic versus Embedding projection; never misrepresent one as the other. A connecting line must correspond to a defined relationship (for example selected search sequence), explained in a legend.

Layout: center 65–75% visual field; right compact Agent activity drawer; left small Layers & Filters toggle; top run name, task and mode; bottom optional trace timeline/progress. Responsive small screens move panels into tabs/sheets. Show a deliberate state machine: Waiting for search → Search started → Search returned → Evidence inspected → Run sealed → Checks/evaluation → Report ready. These are separate, evidence-backed states, not a fake linear loading animation.

Star states: result returned; currently inspecting; evidence read; candidate retained; rejected with reason; claimed feature associated; cannot assess; data unavailable. Use shape/outline/icon/text as well as hue. Tooltip and focus details: cell ID, geographic center, similarity/rank (when present), search context, coverage limitations, related tool/trace event, and linked claims/evidence if known. Relevance is not a probability that a bridge exists.

Agent activity panel: chronological events, tool name, observed status/duration, blocked calls, request/response identifiers and errors; privacy-safe summaries of recorded messages; image-read metadata; total current cost if measured and published. Do not promise access to hidden model chain-of-thought. Show only recorded reasoning summaries or tool-visible context explicitly available in traces.

Actions: inspect/select/star, filter by status/similarity/source, zoom/pan/reset, switch graph/table, pause decorative animation, open related satellite evidence, jump to Atlas, open trace event. Present source coverage and “Clay narrows; imagery determines” in plain English.

Developer mode: no twinkle/parallax; graph with precise labels + sortable data grid + timestamped trace log; event filtering by role, tool, status, trial, error. Keyboard selection and screen-reader results are equal citizens.
Scene 6 — The Constellation Atlas (second major workspace)
This is the core decision/inspection screen after a run. The selected star/cell/constellation stays visually identifiable at center, with nearby dataset and evidence panels. It should be practical for an ADB analyst and technically rigorous enough for engineers.

Desktop layout:
- Header: task, run status, real/synthetic/recorded indicators, execution mode, manifest verification status and export.
- Center: star/region viewer and linked geographical map switch; selected object marker and scene coverage.
- Left or lower panel: organized feature/claim table, search, sort, filter, download permitted data.
- Right top: plain-language summary: what the agent attempted, what it found, what it could/could not establish, key limitations and the next appropriate human action.
- Right lower tabs: Evidence, Trust, Evaluation, Cost & speed, Trace, Provenance.
- On mobile: center visualization becomes optional; Summary / Dataset / Evidence / Trust / Trace are accessible tabs. No information depends on a three-column view.
Dataset rows: feature/claim ID, class, location, status (present/absent/intact/damaged/destroyed/cannot_assess where applicable), agent-reported confidence clearly marked as the agent's claim, evidence refs, grounding/check result, linked Clay cell(s) if verifiably associated, source/date and synthetic status. Worker vs verifier vs keyed evaluation appear only when actually available. A selected row selects its star/marker; selected star filters/highlights matching rows. If no valid mapping exists, say No verified association, not an invented join.

Imagery panel: display authorized preview when available; otherwise show a metadata-only card: scene ID, acquisition date, bbox, resolution/effective GSD, coverage/obscuration, source/license, reader type and bytes-read status. Pre/post comparison only for actual paired evidence. Avoid accidental claims of surveyed locations, especially Nepal demo points. Restrict licensed pixels: the repository must not contain Vantor image crops or raw image bytes in fixture/demo/report exports. Any live preview needs an authorized short-lived backend-mediated path and clear license obligations; never embed prohibited pixels into a downloadable self-contained report or public demo.

Evaluation: keep separate: (1) Process — how the agent worked; (2) Task Understanding; (3) Output assessment; (4) Trust Passport; (5) Cost, Speed & Data. Do not create a default composite score. Include deterministic checks, keying scope, failure reasons and caveats. AgentCore evaluations, if run, are labeled a separate comparison column with their own status/error and method; do not silently merge them into Treehouse scores.

Trust: render TrustPassport gate exactly as provided (Rely, Spot-check, Do not rely) and headline TypedNumber with tier, interval, denominator, sample sizes, abstention, estimator version and reasons. If not issued, show Not issued and why. Keyed evaluations vs unkeyed estimates must be clearly distinguished. If trust engine integration is still a stub, label it as such. Never use trust as a color-only green/red assertion or portray model-estimated figures as verified truth.

Cost & speed: measured dollars (or unpriced), tokens, tool calls, imagery windows/bytes, latency and price-of-trust/verifier where available; dates and replay/synthetic labeling; distinguish modeled bytes from observed. Don't promise real-time dollar metering unless supported. Keep cost/speed separate from trust.

Provenance/export: task-card version and hash; manifest ref; actual backend selection and degradation; model/harness/tracer versions; trace verification; source licenses, attribution and noncommercial restrictions; the exact source of every typed metric. Export only approved bundle/CSV/JSON/HTML artifacts and never restricted pixel payloads. Exports preserve tier and synthetic indicators.

Developer mode: straight multipane tables, imagery inspector, trace timeline, raw safe report bundle JSON, scorecard, trust passport, backend manifest, optional AgentCore comparison. No cinematic animation.
Scene 7 — The Scene Builder (third major workspace; stretch)
User selects a geographic feature from Atlas or a specific candidate in Living Sky. Scene opens a georeferenced 3D view only when required data and capability are present: terrain/elevation raster, satellite textures where permitted, geographic feature geometry, metadata and uncertainty. A stylized conceptual reconstruction is not a surveyed bridge model. Distinguish real geometry, inferred geometry and purely illustrative material. Give explicit scale/units and source timestamps.

Potential future tools: orbit camera; pan/zoom; toggle terrain/imagery/water/infrastructure layers; inspect elevation and feature attributes; compare pre/post; initiate a simulation with scenario parameters; see outputs, inputs, confidence/validation and reproducibility identifiers.

Simulation constraints: floods and structural damage cannot be faithfully derived from an embedding similarity value or a single satellite image. Require real elevation, bridge geometry, forcing/boundary conditions and an identified simulation engine; warn when absent. Provide a simple placeholder Scene Builder is a planned feature rather than fake runnable simulations. Label generated geometry as approximate and avoid portraying hypothetical damage predictions as measured facts.

Developer mode: technical 3D view, source coverage, parameters, scenario results and provenance when implemented; otherwise truthful unavailable state.
5. Two complete modes, one application
Story mode (default for new nontechnical visitors): restrained pixel-art narrative, smooth transitions, friendly language, accessible drawers, concise summaries and guided context. The important data still looks like a professional data product.

Developer mode: navigation opens directly onto workspaces; no story animations; dense tables, raw IDs, status codes, explicit backend config, tool call logs, full typed metrics and trace inspector. It is a mode of the same application, not a second frontend or backend.

Mode switch must: be available persistently; preserve current run/scene/star/selected claim; never restart a run; be keyboard-operable; respect system reduced-motion; avoid storing sensitive run data in preferences. Preferences may be stored client-side for display only.

Important third distinction: Simple vs Advanced configuration is independent of Story vs Developer mode. A Story-mode user can expand technical options; a developer can choose a lightweight setup.
6. Visual design system
Style: tasteful modern pixel art, minimal, not a retro game imitation or a visual novel. Pixel-like art is for branding, treehouse/child/book/telescope silhouettes and small accents. Real data visualization, numbers, labels, maps, tables and forms use crisp vector/text rendering at normal pixel densities.

Starting palette (proposals, adjust to verified contrast):
- Midnight background #0B1830 / deep sky #091629
- Secondary ink-blue surface #172A40
- Warm window/star highlight #F5D48A
- Accessible cool teal accent #77C7BE
- Main text #F4F6FA; secondary #C3D1E0
- Error and warning require icon/word as well as color.
Keep relatively few stars, small luminous points, quiet connecting lines, delicate panel borders, soft focus treatment and generous whitespace. Avoid heavy particle effects, continuous camera movement, flashing, autoplay sound and ornamental glass UI that reduces readability. Do not bake text into art. Make the brand logo available as accessible text.

Motion: short intro/window/telescope sequences only; user skippable; CSS/SVG or small Canvas animations rather than a 3D world for intro. Reduced-motion default should use instant screen changes or a short fade; system preference must override to reduced motion unless user explicitly and knowingly chooses animation. No essential information is animation-only. Never use twinkling or changes in color as the only live-state signal.

Responsiveness: desktop 1440/1280, laptop 1024, tablet 768 and mobile 390/320 CSS pixels. Center sky can shrink or collapse into table view. Support 200% text zoom and browser zoom without clipping core controls.
7. Accessibility, Windows assistive support and narration
Target WCAG 2.2 AA for the web app. Use semantic HTML, visible focus, correct labels, logical tab order, skip links, dialogs with focus management, 44x44 CSS-pixel comfortable targets where practical, and contrast-checked text/status controls. Accessible experience is a first-class feature, not optional flavor.
- Windows Narrator, NVDA, JAWS, VoiceOver, TalkBack: standard ARIA and HTML semantics; don't build a custom accessibility API only for Windows. Screen-reader names for every star include cell ID, selection, relevance, approximate location and availability. A parallel results table is always available.
- Colorblind and low vision: use label/shape/outline/pattern plus color. Offer high contrast, light/dark contrast presets, adjustable text size, browser zoom; retain meaningful focus rings.
- Motor/keyboard: every function usable without mouse, including star selection, filters, maps/table alternative, scene controls, tabs and mode switching. Include no drag-only actions.
- Motion/vestibular: honor prefers-reduced-motion and provide Skip Intro, Disable Animations, Pause Visuals. Background activities continue even if animations are off.
- Hearing: optional narration must have corresponding text/captions and never be required.
- Cognitive accessibility: brief, descriptive labels; progressive disclosure; explain model statuses, costs, “trust,” “embedding” and “cannot assess” in ordinary English. Provide a clear “What happened?” summary.
- Live announcements: accessible, rate-limited status summaries (“Search returned 12 candidate cells”; “Run completed”) rather than reading every moving star or every token.
- Optional spoken narrator: user-controlled explanatory voice with mute, speed and voice selection if supported. Browser speech-synthesis availability varies; provide text fallback. This narrator must not auto-play over an operating system screen reader; users can disable it. Narrator voiceover is not the same as exposing full model reasoning.
- 3D fallback: keyboard camera controls, feature tree/list, accessible parameters and textual analysis for each scene; if equivalent information cannot yet be provided, label the 3D experience as incomplete for accessibility and keep a complete data alternative.
Test with Windows Narrator + Edge and at least one additional desktop screen reader/browser combination. Automated axe checks alone are insufficient.
8. Data contracts: use repo schemas, not invented UI numbers
The frontend should consume backend-validated typed JSON. Current relevant models include:
- TaskCard, RunConfig, RoleConfig, Budget, Backends in schemas/task.py and schemas/config.py.
- ClaySearchResult containing ClayCell { cell_id, center, similarity } and ClayCoverage; WindowResult containing scene IDs, date, bbox, GSD, bytes, reader, pixel hash, source/license and synthetic flag, in schemas/tools.py.
- SpanRecord with trace_id, span_id, parent_span_id, op, status, events, timing, attributes and possible error, in schemas/trace.py.
- Claim with location, class, status, agent's confidence, evidence references, grounded/contaminated flags and synthetic marker, in schemas/claims.py.
- ReportBundle containing manifest/card summaries, scorecard, passports, claims, evidence, ledgers, trace rows, facts, summary and synthetic marker, in schemas/bundle.py.
- TypedNumber with value, tier, panel, sample size, gold count, interval, estimator version, manifest ref, synthetic/replayed flags, reasons and details, in schemas/numbers.py.
- TrustPassport including gate, reasons, baseline comparison, controls and abstention in schemas/passport.py.
Evidence types and visible labels:
- KEYED: Checked — against a known key and its scope.
- GOLD-ANCHORED: Estimated from a random check.
- CALIBRATED-TRANSFER: Estimated from track record.
- MODEL-ESTIMATED: Rough model guess.
- ABSTAINED: Not issued with reason.
- MEASURED: Measured from trace, for supported process/understanding/cost/control measures only.
Always carry numeric denominator, intervals, estimator version and provenance when present. Preserve SYNTHETIC, recorded and modelled bytes labels. Do not write “validated bridge” merely because a high-similarity Clay cell was selected. Do not write “agent thought X” unless X is explicitly recorded or honestly summarized as observable behavior.

Selection/association rules: a ClayCell has a cell_id and center, not an inherent foreign key to a claim. Implement an explicit backend association by evidence/search provenance or a documented geospatial join, mark method and ambiguity, and preserve unmatched rows. Treat cells, image windows, claims and 3D features as distinct types with stable IDs.

No live capability? Use committed/offline fixtures with explicit REPLAYED / SYNTHETIC DEMO labels, or an unavailable state. Do not generate fake star relevances, live prices, trace tool calls or trust numbers solely for a beautiful animation.
9. Proposed frontend and backend integration
Frontend (recommended implementation, adaptable to repo conventions)
- TypeScript with React + Vite (or Next.js if hosting/server needs justify it). Type-check all API payloads; ideally generate TS types from Pydantic JSON schemas or maintain a validated shared contract.
- CSS design tokens, scoped components and accessible UI primitives; avoid unnecessary dependencies and proprietary assets/fonts.
- Canvas or SVG for starfield; SVG is simpler for small N and access focus, Canvas/WebGL only if performance necessitates it, with HTML/table accessibility overlay.
- WebGL/Three.js only for Scene Builder stretch; lazy-load it. The treehouse intro should not pull the 3D bundle.
- Application state: selected run, scene, cell, claim, filters, display mode and accessibility preferences; server state via a query/cache layer. Never treat animation state as canonical backend progress.
- Test on Windows/Edge plus Chromium/Firefox/WebKit browsers, and with touch/keyboard-only navigation.
Suggested component structure (create where appropriate after inspecting repository):
ui/
  src/
    app/                   # router, providers, mode and theme
    scenes/                # TreehouseIntro, BookSetup, TelescopeTransition
    workspaces/            # LivingSky, ConstellationAtlas, SceneBuilder
    features/
      agent-config/        # task, Bedrock, Strands, tracer, budget, eval config
      embeddings/          # ClayCell layers, star detail, candidate table
      runs/                # run state, event timeline, logs
      dataset/             # claim table, selection, exports
      evidence/            # imagery metadata/authorized preview
      evaluation/          # five panels, provenance labels
      trust/               # passport and abstention explanations
      accessibility/       # narration, contrast, motion controls
    components/            # accessible primitives and layout
    api/                   # typed client, schemas, event transport
    styles/                # tokens, themes, pixel-art assets
    tests/
Backend/API adapter — proposed, not currently guaranteed
Preserve the Python service as source of truth. Build a thin FastAPI/BFF layer only where needed. Never expose credentials to the browser; any AWS calls must be server-side and permission-scoped. Suggested semantic endpoints (confirm/change before implementation):
GET    /api/capabilities                  # verified model/harness/tracer/AWS feature availability
GET    /api/tasks                         # task card summaries and allowed presets
POST   /api/runs                          # validate config, start job, return run_id/status
GET    /api/runs                          # list available runs
GET    /api/runs/{id}                     # lifecycle, manifest metadata, status
GET    /api/runs/{id}/events              # SSE event stream OR paginated event retrieval
GET    /api/runs/{id}/bundle              # validated ReportBundle after evaluation
GET    /api/runs/{id}/clay-searches       # search results and coverage linked to trace
GET    /api/runs/{id}/associations        # authoritative cell -> evidence -> claim links
GET    /api/runs/{id}/verify              # read-only integrity verification result
GET    /api/runs/{id}/evidence/{resultId} # metadata; optionally authorized preview capability
GET    /api/runs/{id}/agentcore           # separate comparison, if available
Do not assume current service can execute live from the same code path: inspect provider/runtime wiring first. Do not expose grader-only answers/keys to workers or users without explicit authorization. New routes must enforce input validation, scope, size/rate limits, sensitive-data redaction, stable response errors and cancellation behavior.
Event protocol (new adapter if live streaming is built)
A server event should have event_id, run_id, trial_id?, sequence, time, type, status, source, and typed references to source records. Derive it from real traces and operations; possible event types include:
run.created
run.started
clay.search.started
clay.search.completed
imagery.window.completed
trace.span.completed
claim.recorded
run.sealed
checks.completed
score.completed
trust.completed
report.ready
run.failed
This list is a proposal, not evidence that the current code already emits these events. SSE is sufficient for one-way UI updates; WebSockets are optional. Provide replay/resume with sequence cursor and idempotent deduplication, bounded queue/history, reconnect status and backpressure. Do not stream raw private prompts, chain-of-thought, image bytes or secrets to an unauthorized client. Existing offline recordings may be presented as replay playback, clearly marked, with a synthetic timeline but no false claim of a live agent.
AWS integration UX
Expose Amazon Bedrock, Strands Agents, tracing backend, and AgentCore Evaluations as independently verified capabilities. Model availability comes from an actual registry/probe, not hardcoded assumptions. Strands uses the configured provider/harness seam where implemented. Tracing describes where it ran (local JSONL, OTLP, CloudWatch if deployed); manifest backends_resolved should control the displayed truth. AgentCore comparisons are opt-in/on-demand or separately configured and preserve raw JSON and errors; they do not alter sealed records or Treehouse trust gates.

Do not require AWS for offline demo. Never initiate unbudgeted live model/evaluator runs, deployments or paid simulations from passive page loads. Honor cost guard and show price limitations.
10. Screen layouts and user flows
Flow A — New nontechnical user
1. Treehouse logo, Enter or Skip.
2. Through window to child/book.
3. User enters an inquiry (“Find likely flood-damaged bridges in the selected corridor”), selects a validated task preset, optionally expands model settings.
4. Submit; see preparing state; child looks through telescope only if animations enabled.
5. Living Sky displays recorded Clay candidates and activity. Explain in simple language: “These stars are search regions, not confirmed bridges.”
6. On completion, Atlas displays the organized claims, evidence, plain summary and trust gate. User chooses a row/star and checks the corresponding imagery metadata/preview and reason.
7. If Scene Builder exists and sufficient sources exist, open it; otherwise say feature planned and remain on Atlas.
Flow B — Developer
1. Open directly to home/New Task, choose Bedrock model (or replay), Strands/plain harness, tracing backend, budgets and evaluation configuration.
2. Launch and inspect live event log with exact IDs and per-tool statuses in Living Sky.
3. Inspect Atlas claims, span hierarchy, evidence/metadata, checks, typed score panels, AgentCore comparisons and manifest verification.
4. Download allowed reproducible report/records.
Flow C — Assistive technology
1. Skip intro, enter book with keyboard; all fields announced with labels and validation.
2. On submit, arrive at Living Sky results table by default if nonvisual mode selected, with a brief live-region status announcement.
3. Navigate candidate cells by row; press Enter for detail; go to corresponding claim/evidence if association exists.
4. Atlas defaults to logical summary-first reading order. Trust labels, errors and limitations are text, not color.
5. 3D concepts provide tabular/elevation/feature text alternatives.
Empty/error/edge states (mandatory)
- No tasks/runs yet; no Clay cells returned; no cell coverage; out-of-date data; high obscuration; no matching claims; no preview license; key not available; unkeyed grading; trust abstention; recorded-only replay; unavailable Bedrock/Strands/AgentCore; tool denied; budget exceeded; run failed; disconnected event stream; partial evaluation; invalid task card; missing 3D inputs; simulation unavailable. Every state offers a plain-language reason and appropriate next action.
11. Security, integrity and scientific honesty
- A run's trace and manifest are sealed before scoring; frontend interactions must not change them. Use read-only references and separately versioned evaluation outputs.
- Respect hash chains, verification and actual backends_resolved values. A badge saying “Verified” requires a successful backend integrity check, not mere presence of a hash.
- Keep keyed answer sources protected and separated from worker/verifier tool access. Do not render answer keys in live task setup.
- Preserve source license and noncommercial restrictions. Do not commit or export restricted imagery pixels.
- Do not treat model self-reported confidence as ground truth or output trust.
- No default composite of process, output, trust, cost and speed. Show five distinct evaluative areas, with method labels.
- Separate checked, estimated, measured, recorded, synthetic and unavailable, consistently across visualizations, tables and downloads.
- Avoid fabricated “live thinking” or chain-of-thought. Display observable traces and summaries of recorded activity.
- Geospatial accuracy matters: preserve CRS/coordinate units, scene time, image GSD, cloud/coverage and geographic vs semantic similarity distinctions.
- Simulations must not be presented as engineering-grade predictions without a validated engine, inputs and uncertainty documentation.
12. Phased implementation order
Phase 0 — Repository audit and contracts
- Inspect main, all relevant open PRs, current service and schemas, existing reports, tests and available AWS features.
- Document exact capabilities, missing API endpoints and fixture paths. Lock an initial JSON contract. Avoid altering statistical semantics.
Phase 1 — Usable nonanimated application (highest priority)
- Build TypeScript shell, routing, accessibility settings, developer/simple navigation, task form, run list and read-only Atlas from real ReportBundle.
- Add table-based Clay results, trace table, claims/evidence linking, typed scores/trust, explicit feature availability, legal/synthetic indicators and exports.
- The result should already be useful without art or AWS.
Phase 2 — Living Sky + replay/live observability
- Add starfield synchronized to actual Clay cell results, selection and filters, deterministic positioning/legend, parallel accessible table, and true trace event adapter. Start with offline replay; add live transport only when backed by real events.
Phase 3 — Story mode polish
- Logo intro, zoom/window, child/book, telescope transition; pixel-art assets or SVG/CSS; mode switch, motion preference, optional narration, performance tuning. Keep transitions brief and skippable.
Phase 4 — AWS/agent configuration integration
- Verify or implement backend adapters for Bedrock, Strands, tracer choices, budgets and AgentCore comparison. All behind actual capability checks, no secret leakage and clear errors.
Phase 5 — Scene Builder stretch
- Only when real spatial/elevation inputs and a justified reconstruction technique exist: 3D viewport, provenance, accessible alternative. Add simulations only behind an actual modeling engine and validation path. Otherwise retain disabled/planned entry point.
Rule: Do not spend early delivery time building an elaborate 3D treehouse while the dataset, evidence, scoring and accessibility views remain incomplete.
13. Acceptance tests / definition of done
The implementing agent should deliver testable evidence for the following:
1. Scene fidelity: logo → window → book → telescope → Living Sky; telescope is only a transition. Users can skip all intro motion. There is no dedicated telescope settings page.
2. Main-workspace fidelity: the Living Sky, Atlas and (feature-gated) Scene Builder have independent direct navigation and preserve selected run/entity.
3. Story/Developer equivalence: switching modes retains state and shows the same substantive results, with simpler presentation and zero decorative motion in Developer mode.
4. Configuration: valid task/run config is accepted; unavailable Bedrock/Strands/AgentCore options are visibly disabled/explained; task validation prevents forbidden data leakage; budgets are honored.
5. Clay accuracy: each star maps to an actual ClayCell.cell_id; similarity, center, coverage and source can be inspected; no fabricated graph links or physical location implications.
6. Live honesty: event panel matches trace/tool results in order, distinguishes replay and live, reconnects without duplicate status and reports failures clearly.
7. Evidence fidelity: selecting a claim/evidence gives matching claim_id/`result_id` with the correct satellite metadata; no unlicensed pixel data appears in repo/demo exports.
8. Trust fidelity: no default composite; every number retains tier, synthetic/recorded/modelled annotations, denominator, interval and abstain reasons where appropriate; stub is not falsely labeled live trust engine.
9. AgentCore honesty: displayed as separate optional comparison result; unavailable deployment is marked unavailable.
10. Accessibility: keyboard-only flow for all core tasks; screen reader usable; high contrast and colorblind-safe indicators; no information conveyed by color alone; a nonvisual star table is usable; no unwanted autoplay sound; reduced-motion works end to end.
11. Responsive: tested at phone/tablet/laptop/desktop and 200% zoom, without trapping or hiding important controls.
12. Security: no exposed credentials, grader-only keys, raw private chain-of-thought or restricted imagery payloads; run data remains read-only after sealing.
13. Performance: first meaningful UI does not require WebGL; large result sets do not freeze controls; lazy-load Scene Builder; transitions never delay direct user access.
14. Offline demonstration: run uv sync, uv run treehouse demo with a fresh output directory as documented in repo; show the recorded nine-run demo without claims of live AWS. Confirm existing golden heads/tests still pass.
15. Validation: TypeScript type-check, lint, component tests, API contract tests, E2E user flows and manual accessibility testing; document any explicitly deferred feature.
For visually comparing the frontend and backend, build an E2E fixture asserting that star/cell IDs, claim IDs, evidence refs, aggregate metrics and trace statuses match an actual stored bundle; no screenshot-only proof.
14. Deliverables for the next agent
1. A scoped implementation plan tied to actual repo files and current branch status.
2. TypeScript frontend and reusable design-system components.
3. Thin Python API/event adapter if needed; no duplicate evaluator math or fabricated data.
4. Working Story and Developer modes with a skip/reduced-motion path.
5. Implemented Living Sky and Atlas on real/offline Treehouse records.
6. Explicit capability and error states for Bedrock, Strands, AgentCore and simulation.
7. Accessibility checks, automated tests, a short manual Narrator checklist, responsive checks.
8. README with run/build commands, integration setup, screenshots or short demo (without restricted imagery), and honest implementation status.
9. A final matrix: Built / Offline-demo only / Partially integrated / Planned stretch, with source links, tests and blockers.
Ready-to-paste commissioning prompt
Implement Treehouse's frontend according to TREEHOUSE_MASTER_UI_IMPLEMENTATION_SPEC.md in randomblankspaces/Treehouse. Start by auditing current main, open PRs, source schemas, README/HANDOFF and design docs; report capabilities and gaps, then implement in small tested phases. Prioritize a usable accessible TypeScript Atlas and Living Sky over decorative animation. Story mode has short pixel-art logo/window/book/telescope transitions; telescope is visual only. Developer mode has no animations and direct technical controls. Reuse authoritative Python ReportBundle, ClaySearchResult, SpanRecord, TypedNumber and trust/evaluation data. Never fabricate stars, traces, scores, AWS availability, model thinking, imagery or simulations. Preserve sealed-run integrity, keyed-data isolation, synthetic and evidence-tier labels, source licenses and cost guards. Scene Builder/simulations are stretch features and require real geometry/terrain/simulation support. Deliver code, tests, documentation, accessibility evidence and a built/blocked feature matrix. Do not deploy to AWS, spend credits, or expose restricted imagery without explicit authorization.

15. Open choices (defaults provided; don't block initial build)
- Framework: React + TypeScript + Vite by default; replace only with a documented reason.
- Sky spatial layout: start with deterministic geo-derived arrangement and a clear Geographic label; add true embedding projection only if raw vectors/metadata exist.
- Art direction: restrained pixel-art vector assets with crisp technical UI; keep any custom image asset license clear.
- Narrator: off by default, opt in only; captions/text always present.
- Navigation: workspaces direct-linked; avoid narrative navigation gates.
- Simulation: unavailable until real sources and engine exist; no pretend interactivity.
- Backend deployment: prefer existing service adapters and local offline demo first; hosted authentication/login can be separately scoped.
Final product vision: A small, inviting treehouse opens onto a serious, trustworthy scientific observatory. The user begins with a question in a book, sees Clay's candidates appear as stars, watches recorded agent actions, inspects a verified/provenance-aware dataset and satellite evidence, and—eventually—explores correctly labeled 3D reconstructions and simulations. The magic is in the transition; the truth is in the dat