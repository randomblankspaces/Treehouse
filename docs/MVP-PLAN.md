# Treehouse MVP plan (authoritative for the build, 2026-11-04)

> **For agents (Kiro, Claude, Codex):** this is the plan to build the hackathon MVP. It supersedes the
> Nepal-bridges framing in older docs and refines [KIRO-NEXT-PROMPTS.md](KIRO-NEXT-PROMPTS.md). Read with
> [REPORT-TABLES.md](REPORT-TABLES.md) (the ADB/LGND report digest) and
> [LGND-REPORT-CONTEXT.md](LGND-REPORT-CONTEXT.md). Executable task list: `.kiro/specs/treehouse-mvp/tasks.md`.
> Deadline: public repo by **Thu Nov 5 2026, 10:00 EST**. Repo: github.com/randomblankspaces/Treehouse
> (Suhas's fork; never push to `VishalPatil18/...`).

## 1. The goal in one paragraph

An ADB analyst asks a geospatial question in plain language — for the MVP, **T1 retrieval: "where are all
the warehouses in this city?"** An AI agent (Strands on Amazon Bedrock) answers it by **using foundation
models as resources** (AEF, Clay, a Bedrock vision model) to build a georeferenced asset database, and
plots its predicted sites as **red markers** on a map. **Treehouse judges the agent's thinking**: every
decision it made (which model and imagery, what cell/chip size, which retrieval method, which classifier,
what threshold, how it merged cells into sites, when it revised its plan), whether each decision's
**"why" is valid**, and how that reasoning relates to the measured accuracy, stated confidence, time and
money. Clay is not the judge and not the agent; it is one tool the agent may choose.

## 2. Decisions (Suhas, 2026-11-04; aligned with the report)

| # | Decision |
|---|---|
| DM1 | **T1 retrieval is the MVP core.** T5 transfer (Nagoya → Gifu, same country) is in the MVP. T2–T4 are aims after T1 works. |
| DM2 | **Keyed scenario: warehouses in Nagoya** — PLATEAU is the report's only *complete* warehouse reference (warehouse use, ≥ 1,600 m²). **Transfer: Gifu**, no new labels. **Unkeyed scenario: a Bangladesh city** (e.g. Chattogram or Dhaka; confirm OSM `building=warehouse` coverage) — sparse OSM ⇒ precision within the OSM pool and honest limits only, never recall. |
| DM3 | **Foundation-model resources the agent can choose:** AEF precomputed 10 m annual embeddings; LGND Clay precomputed (1.28 km / 2.56 km cells — kept so a good agent can reject it for warehouses and say why); Clay v1.5 computed on 160 m Sentinel-2 chips (Should; GPU cost); a Bedrock vision model (Claude Sonnet 5.5 or Amazon Nova Pro, both probe-verified for images) on GSI 0.5 m aerial chips in Japan (with attribution) for zero-shot checks. **Maxar/Vantor imagery is excluded** (CC BY-NC; report Table 17). |
| DM4 | **Three separate scores, never blended:** (a) **reasoning validity**, (b) **confidence calibration**, (c) **predicted accuracy from reasoning** (for unkeyed runs). Output accuracy under the report's protocol is a fourth, separate panel; cost/time/data a fifth. |
| DM5 | **Classifier is switchable:** a linear probe (logistic regression) or linear SVM on embeddings (report Table 9), **or a Strands sub-agent classifier** using a Bedrock vision model on image chips. The main agent chooses and must justify; the choice is scored. |
| DM6 | **Strands is the agent harness** (the AWS-native piece). The plain loop stays as a comparison harness. Model, harness and tracer stay swappable. |
| DM7 | **Output grading follows report Table 7**: 160 m cell unit, any-touch matching, each asset once; metrics of Table 11. It is a **new versioned grader** beside the existing point-distance matcher, not a silent replacement. |
| DM8 | **Trust engine (PPI passport) is merged but not the headline.** Do not wire it into the headline until its audit issues (docs/PRODUCT-STATUS.md) are fixed. |
| DM9 | **Claim only what ran.** Anything not executed live is labelled "designed" or "roadmap" (defense book, docs/design/DEFENSE-BOOK.md). |
| DM10 | AWS: Compliance-mode Object Lock run store (done), Bedrock, Strands, **AgentCore Evaluations** (built-in + Lambda code-based evaluators), AgentCore Observability, CDK. Bedrock **batch inference is explicitly denied** in this account (probe) — do not use it. |

## 3. What already exists (do not rebuild)

- Sealed, hash-chained traces and store; `treehouse verify`; manifests pin task card, prompts hash, model, tools, prices, data sources (`src/treehouse/trace`, `store`, `schemas/manifest.py`).
- **Investigation sandbox** (`src/treehouse/investigation`, `docs/INVESTIGATION.md`): `record_decision` binds each action to a rationale, alternatives, confidence, parent decision and evidence before dispatch; partial/final sealed claims; post-seal evaluation; semantic process review by a different model; `VisionClassifier` plugin seam; UI views (Book, Living Sky, Atlas) with red predictions; read-only HTTP API.
- Tool Gateway (allow-list, forbidden sources, metering, budget), in-process MCP tool servers incl. Clay search, imagery windows, STAC (`src/treehouse/gateway`, `tools`).
- **Strands**: `harness/strands_harness.py` (`harness: strands`), `providers/strands_model.py`, `verifier/agent.py` (Converse and Strands verifiers), `tools/search_agent.py` (local ≤ 1 M vectors; Athena / S3 Vectors above), `harness/baseline.py` (no-tool baseline). See `docs/design/STRANDS.md`.
- Bedrock Converse provider, model registry, **filled price table**, spend ledger and budget guard (`providers/`, `config/`).
- Claim checks R1–R9, keyed match, leak and canary (`checks/`); trust core (`sampling/`, `trust/`, `stats/`) with raw-statistics export (`trust/export.py`).
- AWS prototype: `infra/` CDK (run store, key bucket, Lambda evaluators, AgentCore Evaluator registration, online eval config), `src/treehouse/aws/agentcore.py` (spans → AgentCore sessionSpans, reference inputs, evaluate wrapper), `aws/lambda_evaluator.py`, `scripts/agentcore_eval.py`, `docs/design/AWS-BLUEPRINT.md` (KA0–KA3).
- Probe results: `probe-report.json`, `aws-capabilities.json` (vision OK for Sonnet 5.5 and Nova Pro; AgentCore Evaluate/CreateEvaluator/Runtime/OnlineEval allowed; Transaction Search not yet enabled; CDK not bootstrapped; USPVDB unreachable; Overpass flaky).

## 4. Architecture of one MVP run

1. **Task card** (YAML): analyst question, AOI, target class with the Table 8 definition (positive/negative), time window, permitted sources and licences, forbidden sources (the grading reference), budget.
2. **Agent** = Strands agent on Bedrock (default Claude Sonnet 5.5; swappable). Before every tool call it records a decision (`record_decision`: rationale, alternatives, confidence, parent, evidence).
3. **Retrieval tools** (all through the Tool Gateway; every result recorded):
   - `list_embedding_sources(aoi)` → each source's model, resolution, cell size, date, licence, est. cost.
   - `build_index(source, cell_size_m, year)` → georeferenced cell grid + embeddings for the AOI (cached; S3 or local).
   - `get_examples(n)` → permitted few-shot examples from the **training split only** (Nagoya); never the held-out set.
   - `retrieve(method = zero_shot_text | few_shot | concept_vector, …, k)` → ranked cells.
   - `classify(method = linear_probe | linear_svm | vision_subagent, …)` → per-cell score; the vision sub-agent is a Strands agent that looks at GSI chips through Bedrock vision.
   - `imagery_window(cell)` → chip for visual checks (GSI in Japan; Sentinel-2 elsewhere).
   - `aggregate(threshold, merge_rule)` → sites, count with range, unreviewed-area estimate.
   - `record_claim(site, geometry, confidence, evidence_refs)`.
4. **Seal** the run before any grader sees it.
5. **Evaluate** (post-seal, independent): the five panels below.
6. **Report and UI**: red predicted sites linked to evidence; decision tree with rationales; the panels side by side; raw-statistics export.

## 5. The panels

| Panel | What it measures | How |
|---|---|---|
| **(a) Reasoning validity** | Is each decision's "why" valid? | **Rule checks** per decision (§5.1) + **reviewer model** of a different family scoring each rationale against `investigation/RUBRIC-v1.md` and §5.8 dimensions + **AgentCore Evaluations** (Builtin.ToolSelectionAccuracy, ToolParameterAccuracy, GoalSuccessRate with assertions, TrajectoryInOrderMatch, plus Treehouse code-based Lambda evaluators). Each source reported separately; per-decision and run-level breakdown. |
| **(b) Confidence calibration** | Does stated confidence match measured correctness? | Per-claim confidence vs correct/incorrect under the grader: Brier score, reliability bins with counts, ECE; per-decision confidence vs outcome where measurable. Keyed runs only. |
| **(c) Predicted accuracy from reasoning** | How accurate is this run likely to be, from its reasoning alone? | Fit on keyed runs: reasoning features (rule results, reviewer scores, chosen cell size vs object size, method, revisions, coverage) → measured site recall and cell precision. Apply to unkeyed runs with an interval, labelled MODEL-ESTIMATED; validate leave-one-config-out and on the Gifu transfer; baseline = mean of keyed runs; show "no better than baseline" honestly. |
| Output accuracy | Report Table 7/11 protocol | Site recall, recall@k, grid-cell precision, lift, count ratio, AUROC, AP, review effort to 50/80/90 %, transfer gap; complete vs incomplete reference declared (Bangladesh: precision within the OSM pool only). |
| Cost / time / data | Efficiency | Tokens, $, wall time, tool calls, bytes and cells touched, per decision and per run. |

### 5.1 Reasoning-validity rule checks (deterministic, versioned)

| Rule | Passes when |
|---|---|
| RV1 scale fit | Chosen cell/chip size is plausible for the target's size (report anchor: warehouses ≥ 1,600 m² ≈ 40 m side → 160 m cells work; 1.28 km cells do not) **or** the agent states the limitation and its consequence |
| RV2 imagery licence | Every imagery source used is reusable for ADB per Table 17 (Maxar/Vantor fails) |
| RV3 resolution fit | 10 m sources are not claimed to resolve objects smaller than a few pixels without a stated limitation |
| RV4 held-out isolation | No grading reference reached the agent; few-shot examples come from the training split only |
| RV5 prompt fixed | Zero-shot prompts are fixed before any test labels are seen |
| RV6 coverage | Searched area and period cover the requested AOI and window, or the gap is declared |
| RV7 evidence-consistent | Each claim cites evidence that actually covers it; stated counts match claims |
| RV8 honest limits | Unreviewed areas and the count range are stated; no claim of recall on an incomplete reference |
| RV9 revision quality | When new evidence contradicted the plan, the agent revised (or justified not revising) |
| RV10 definition fit | The class definition (Table 8 positives/negatives) is applied, e.g. factories and markets are not warehouses |

## 6. Experiments (the matrix judges see)

| Axis | Values |
|---|---|
| Model | Claude Sonnet 5.5 · Amazon Nova Pro (+ any probe-verified) |
| Harness | Strands · plain loop |
| Tool set | AEF only · LGND Clay precomputed only · all sources |
| Classifier | linear probe · linear SVM · Strands vision sub-agent |
| Task | Nagoya T1 (keyed) · Gifu T5 transfer (keyed) · Bangladesh T1 (unkeyed) |
| Trials | N = 3 per cell of the matrix that is run; size N from measured per-run cost |

Do not run the full product; run one-factor-at-a-time variants from a baseline (Sonnet + Strands + all sources + agent's own choice), staying under the spend guard.

## 7. AWS integration (what runs where)

| Service | Job | Tier |
|---|---|---|
| Amazon Bedrock (Converse) | Worker agent, vision sub-agent classifier, reviewer model | Must |
| Strands Agents | Agent harness and vision sub-agent | Must |
| AgentCore Evaluations | Built-in and code-based (Lambda) evaluators on the agent's spans; ground-truth assertions on keyed runs | Must |
| AgentCore Observability + CloudWatch Transaction Search | Second tracer; spans for AgentCore | Must (enable Transaction Search once) |
| S3 (versioned, Object Lock **Compliance**) + KMS key bucket with worker Deny | Sealed run store, grading references isolated by IAM | Must (CDK `infra/`) |
| AWS Lambda | Code-based evaluators (reasoning rules) | Must |
| CDK | Everything as code; `cdk bootstrap` then deploy | Must |
| SageMaker or EC2 GPU | Compute Clay v1.5 embeddings on 160 m Sentinel-2 chips | Should |
| Step Functions (Distributed Map) | Fan out the experiment matrix | Should |
| Athena / S3 Vectors | Embedding queries for large AOIs (routing rule, AWS-BLUEPRINT §2) | Could |
| AgentCore Runtime | Host the agent; online evaluation of live traffic | Could |
| Bedrock batch | **Denied in this account — do not use** | — |

Data: Sentinel-2 COGs (Earth Search / `sentinel-cogs`, us-west-2, open), LGND embeddings (`s3://us-west-2.opendata.source.coop/clay/lgnd-embeddings/`, CC BY 4.0), AEF (Google Satellite Embedding, CC BY 4.0 — **access path to verify**: Earth Engine or public cloud mirror), GSI seamless aerial tiles (Japan, attribution), PLATEAU Nagoya/Gifu (licence to record), OSM (ODbL, Overpass flaky — use a pinned extract). Never commit imagery pixels.

## 8. MVP acceptance checklist

- [ ] A live Strands-on-Bedrock agent completes T1 for Nagoya warehouses with ≥ 2 embedding sources available, records a decision before every action, and emits red predicted sites.
- [ ] The same agent configuration runs the Gifu transfer and the Bangladesh unkeyed task.
- [ ] Output panel reports report-Table-11 metrics for Nagoya and Gifu (with the transfer gap) and precision-within-pool for Bangladesh, with units and reference completeness declared.
- [ ] Reasoning-validity panel: RV1–RV10 per decision + reviewer-model scores + AgentCore Evaluations results, each separate; a planted bad agent (e.g. chooses 1.28 km cells for warehouses without justification; uses Maxar imagery) fails the right rules.
- [ ] Calibration panel on keyed runs (Brier, reliability bins with n).
- [ ] Predicted-accuracy panel on the Bangladesh run, labelled MODEL-ESTIMATED, with its validation result and baseline comparison.
- [ ] At least one model comparison and one classifier comparison (one factor at a time) with trial counts and intervals.
- [ ] Runs sealed in the Compliance-locked S3 store; a denied delete demonstrated; CDK deploy output committed.
- [ ] UI shows red sites linked to evidence, the decision tree with rationales, and the separate panels; raw statistics exportable.
- [ ] A recorded replay of the live runs is committed so the demo works offline; README quickstart runs on a fresh machine.
- [ ] `uv run pytest` green; spend under the guard; every live claim in README/demo backed by a committed artifact.

## 9. Out of scope for the MVP

T2 segmentation, T3 register update, T4 change detection (aims), active-learning label curves to 1,000 labels, YOLO baseline, FarSLIP (no AWS-hosted checkpoint confirmed), simulation, captions, purchasing imagery.
