# Future features and refinement roadmap

Updated November 4, 2026 after Suhas clarified that the product evaluates an agent's investigation,
decisions and resulting geospatial database. Current built scope is in [PRODUCT-STATUS.md](PRODUCT-STATUS.md),
the product definition in [OUTLINE.md](OUTLINE.md), and execution order in [PLAN.md](PLAN.md).
Older cut-line decisions remain in Git history and the council designs; they are not current delivery promises.

## Report-driven questions — not approved work packages

Suhas confirmed the minimal pipeline in [OUTLINE.md](OUTLINE.md). The broader
[LGND/ADB report context](LGND-REPORT-CONTEXT.md) raises these gaps for later scoping; the
confirmation does not commit to all of them:

- Asset/cell/site-aware grading: any-touch cell matching, object IoU, deduplication and dated updates
  differ from the current point-distance evaluator. Existing grades need their own version/meaning.
- Reproducible Table 9 workflows: fixed prompts, permitted examples, iterative labeling/refits,
  classifier choices and optional detector comparisons, with model/source/scale provenance.
- Review-effort learning curves, labels/seeds and frozen cross-city/cross-country transfer arms;
  compare like metrics on the same reference population, rather than ranking models from one score.
- Analyst-facing benchmark views: asset recall, cell precision, ranking/AP, review effort, unresolved
  areas and transfer gaps alongside the independently assessed agent decisions, confidence and cost.
- A verified imagery/reference eligibility record. Noncommercial demo sources and incomplete OSM
  catalogs do not establish permission or complete ground truth for an ADB deliverable.

T2 segmentation/size, T3 inventory updates and T4 post-event screening are report task families,
not delivery commitments. The first task, region and comparison protocol remain open. Section 5.8
supports the agent-evaluation focus; it does not supply a validated ready-made agent rubric.

## Next: Kiro integration and real evidence

| Feature | Why it matters | Required evidence |
|---|---|---|
| Real worker/foundation-model/classifier/source plugins | Turn the tested sandbox into an actual imagery investigation | Bounded model calls and real permitted pixels, source/model versions, observation-dependent decisions, sealed claims. |
| Real imagery windows and honest I/O accounting | Object scale and resolution must govern what can be established | Authorized source, exact footprint/date/GSD/license, pixel hashes; measured bytes or an explicit unavailable status. |
| Held-out real-data evaluation and adjudication | Establish accuracy separately from the agent's confidence | Spatially independent examples and heldouts, coverage/date/class definitions, one-to-one matching and incomplete-key caveats. |
| Distinct process reviewer connected to the UI | Assess strategy, evidence use, adaptation, uncertainty and stopping | Actual rubric-versioned review with cited decisions/evidence, separate model/context and model-estimated labels. No grade from persuasive prose alone. |
| Live decision/event transport | Let users watch exploration while it runs | Real ordered events, resume cursors/deduplication, error recovery and a separate sealed final record. No fabricated thinking stream. |

AWS challenge Runtime/KB/Gateway demonstrations remain optional. A successful challenge endpoint is
not by itself proof that the geospatial investigation, classifier or accuracy evaluator works live.

## Refinement after live testing

| Feature | Intended behavior | Boundary |
|---|---|---|
| Editable task/zone/model/source setup | Submit validated custom tasks from the Book instead of only pinned replays | Server-owned provider configuration, permissions and budget enforcement; no browser credentials or arbitrary plugin imports. |
| Task-scale strategy presets | Support large facilities, small panels and other target classes with appropriate search/image settings | Presets assist the agent; do not hardcode one strategy as the only correct path. |
| Exploration and coverage inspector | Show inspected/revisited/unexplored regions, failed branches and reasons for stopping | Distinguish image footprint coverage, visible coverage and actually assessed objects; multi-trial aggregates are explicit. |
| Target-zone map and richer prediction layers | AOI outline/basemap, candidate-versus-prediction layers, readable mobile markers and evidence selection | Preserve coordinates/CRS; never invent cell-to-object relationships. Current geographic scatter/table is not a surveyed map. |
| Paired agent/model/harness/tool comparisons | Compare strategies, with/without Clay, accuracy, confidence, speed and money on the same task | Predeclared comparison, adequate trials, independent labels and uncertainty; no default composite winner. |
| Human baseline and blind review | Compare actual expert time/accuracy and resolve disputed detections | Measure human work using a documented blind protocol; never substitute an assumed human score. |
| Confidence calibration and regime transfer | Test whether reported confidence predicts correctness across tasks and places | Sufficient independent labels, leakage controls and measured calibration. Current Brier examples do not prove general calibration. |
| Authorized image previews | Inspect real evidence beside claims | Short-lived controlled access, license attribution, no restricted pixels in public repo/self-contained exports. |
| Screen-reader and cross-browser refinement | Usable Narrator/Edge and another reader/browser, touch, zoom and low vision | Real manual observations; automated Chromium checks do not certify accessibility. |

## Reliability, evaluation and production extensions

- Repair and independently validate the separate trust-core audit cases before wiring a live passport.
  Keep output grading, process review, cost and any future trust decision separate.
- Stronger held-out isolation for untrusted agents requires OS/container or remote boundaries; local
  Python plugins are trusted code. Multi-user access needs authentication, authorization and tenant isolation.
- Versioned model/index/task/source manifests, immutable replay artifacts, external integrity witnesses,
  additional tracer reconciliation and reproducible comparison reports should follow actual live failures.
- Multi-agent planner/executor/checker traces, dynamic tool discovery, sensitivity analysis, temporal
  hindcasting and additional task families remain future experiments with independently specified tests.
- Statistical transfer methods, unreported-place sampling, paired comparisons and calibration studies
  require adequate labeled data. A small incomplete public reference fixture is not that validation.
- Broader non-Bedrock adapters, hosted partner accounts and continental-scale indexing are separately scoped.

## Stretch: Scene Builder and simulations

Scene Builder remains planned. It requires real terrain/elevation, geometry, permitted imagery,
units/timestamps, uncertainty and accessible alternatives. Structural/flood simulation additionally
requires an identified engine, boundary conditions and independent validation. Embedding similarity
or one satellite image cannot establish a trustworthy physical simulation. Generated geometry is
approximate; a scenario is not a measured prediction. These features follow a useful agent-evaluation
product and are not required for the current Kiro handoff.
