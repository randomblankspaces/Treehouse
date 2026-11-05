# Future features

What Treehouse should do next, written so another agent (Codex, Kiro, Claude) can pick any item up. Ordered by how much
each one strengthens the core idea: **see the agent's thinking and judge whether it earned its answer.**

## 0. The core loop, in plain words

1. **The analyst asks in natural language:** "Where are all the warehouses in Nagoya's port district?"
2. **The agent decides how the foundation model should see the area** — which model (Clay, AEF), which chip/cell size
   (e.g. 160 m chips for ~40 m warehouses, 1,280 m for wind-farm clusters), which year, which imagery — and says why.
3. **The agent searches the embeddings** for the object: few-shot from examples, a concept direction, or clusters when
   it has no examples, then classifies candidates (linear probe, SVM, or a Strands vision sub-agent that looks at the
   aerial chip).
4. **The agent records each find** as a database row (location, class, status, confidence, evidence) — the red dots.
5. **Treehouse verifies independently** against a reference database known to contain the real objects (PLATEAU,
   OpenStreetMap, Global Renewables Watch, USGS), using the report's 160 m cell protocol, and judges every decision
   the agent made on the way.

Today steps 1, 3, 4, 5 run; step 2 runs **only as a choice between precomputed grids** (see F1).

## F1. Agent-chosen chips: compute Clay embeddings on demand  *(highest value)*

**Today:** the agent can choose LGND Clay (precomputed, fixed 1,280 m / 2,560 m cells, real data) or AEF (10 m, pooled
to any cell ≥ 160 m). It cannot ask Clay to embed chips of a size it picks.

**Build:** a `clay_compute` embedding source — Clay v1.5 weights (Hugging Face `made-with-clay/Clay`, Apache-2.0) run on
Sentinel-2 L2A chips the agent specifies (chip size, stride, bands, date) on a SageMaker endpoint or one GPU instance,
cached to S3 by `(scene, chip size, stride)`. Multi-scale: let the agent embed the same area at 160 m and 640 m and
compare. Every request is a `build_index` decision, so Treehouse can judge **why** the agent chose that chip size
(RV1 scale fit against the asset registry; cost vs benefit).

**What the demo would show:** "The agent asked Clay for 160 m chips because warehouses are ~40 m; the coarse 1,280 m
grid would put 20+ warehouses in one cell."

## F2. A thinking view people understand at a glance

1. **One card per decision, one sentence:** "Chose **AEF at 160 m** over **Clay at 1,280 m** because warehouses are ~40 m."
   Confidence bar · verdict chip (✓ sound / ⚠ questionable / ✗ invalid, from RV1–RV10) · evidence badge.
2. **"Why is this red dot here?"** — click a site; see the short chain data → cell size → method → check → claim.
3. **Confidence-earned gauge** per claim: stated vs earned ("said 90 %, 1 of 4 checks done → unearned").
4. **Scale card first:** the cell/chip-size decision is pinned at the top with the object's size from the registry, the
   chosen cell drawn to scale on the map, and the alternatives the agent rejected.
5. Narrated by Amazon Polly; colour-safe themes; status shown by shape as well as colour.

## F3. How confidence is gauged (and what to add)

- **Stated confidence** — the agent reports a number (0–1) with every decision and every claim. It is self-reported.
- **Calibration (score b)** — on keyed areas Treehouse grades each claim against the reference and compares stated
  confidence with correctness: Brier score and reliability bins with counts (a well-calibrated agent that says 0.8 is
  right about 80 % of the time).
- **Deliberation / earned confidence (inside score a)** — from the recorded decisions and the model's thinking:
  alternatives considered and actually tried, key choices compared (model, cell size, method, threshold), independent
  checks (second source or vision) before the claim, revisions after new evidence. High confidence with none of these is
  flagged **unearned**; low confidence after a passed check is **under-confident**.
- **Predicted accuracy (score c)** — for areas with no answer key, a model fitted on keyed runs predicts recall/precision
  from those reasoning features, labelled MODEL-ESTIMATED with its validation.
- **Add next:** per-claim evidence strength (how many independent signals agree), confidence intervals that widen with
  unreviewed area, and a calibration curve drawn in the UI.

## F4. More traceability

- OTLP export of the same spans to any tracing tool (Langfuse, Phoenix, X-Ray via ADOT) beside the sealed log.
- Signed run manifests (KMS sign) so a third party can verify a run without trusting the store.
- Diff two runs decision-by-decision ("where did Sonnet and Nova diverge, and which choice was right?").
- AgentCore Runtime + online evaluation so every production run is scored as it happens.
- Lineage from each red dot to the exact embedding rows, image tiles and model calls that produced it.

## F5. Verification against databases that are known to be right

- Pluggable reference adapters per asset class (PLATEAU, OSM, GRW, USGS USPVDB/USWTDB), with completeness recorded so
  incomplete references never report recall.
- Train-in-one-region / test-in-another splits (ADB's suggestion) as a standard task-card field.
- A verifier agent (Strands + vision) that samples claimed sites and checks them on imagery, scored separately from the
  worker.

## F6. Few or zero examples

- User-supplied examples (20–30 points) and a cluster survey that finds "clumps" (e.g. wind farms) with no examples,
  then confirms a few with the vision sub-agent and expands from them (package WP-007).
- Text-to-image retrieval with a vision-language embedding model (FarSLIP-style) for zero-shot queries.


## F7. Remaining live-run matrix (deferred from the 2026-11-05 final push)

The reduced real-data pass ran two runs on `tasks/t1-nagoya-warehouses-real.yaml` (Sonnet adaptive-thinking ON,
Haiku), both sealed under `fixtures/live/real/`. Deferred under the credit/time stop, each a one-command follow-up:

- **AgentCore Evaluations** on `nagoya-real-sonnet-thinking-1` (built-ins + Treehouse Lambda evaluators), then
  commit the result JSON with the account id redacted (`src/treehouse/aws/` helpers; `scripts/agentcore_eval.py`).
- **Nova Pro ×1** and a second Sonnet trial on the same real card, for a model comparison with intervals.
- **Chattogram fuel tanks** live run (`tasks/t1-chattogram-fuel-tanks.yaml`, WP-003 card) once its reference pool
  is fetched.
- A **real vision-subagent** success: both committed real runs recorded `cannot_assess` because no fine imagery
  resolved; wire a GSI/Sentinel window the vision sub-agent can actually read at the candidate cells.
- Compute Clay embeddings on agent-chosen chips (F1) would let these runs pick a 160 m cell instead of the
  precomputed 1.28–2.56 km grid, which is why the agents declined to assert warehouses.
