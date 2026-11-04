# Treehouse: implementation design

> **LGND/ADB context — minimal agent-evaluation scope confirmed:** read [the report brief](../LGND-REPORT-CONTEXT.md).
> Keep existing code/grades versioned. The report raises capability gaps; it does not authorize replacing the grader or starting its old package queues.
> Suhas confirmed an agent-evaluation sandbox; Strands is part of the workflow being assessed.
> See the report brief and Kiro prompts for that scope; broader benchmark studies remain future work.

> Current context, November 4: Suhas clarified that Treehouse evaluates an agent's complete
> investigation and the accuracy of its resulting geographic database, across configurable tasks
> and zones. Agent explanations/confidence are self-reports; held-out evaluation and separate-context
> process review have distinct evidence labels. Independent test authorship precedes implementation.
> The current delivery sequence and superseding scope are in [../OUTLINE.md](../OUTLINE.md)
> and [../PLAN.md](../PLAN.md). Earlier Nepal-only, UI-deferred and old overnight ordering below
> are historical where they conflict; preserved decisions are not new execution authority.


Target path: `docs/design/IMPLEMENTATION-DESIGN.md`. This document implements `docs/design/SYSTEM-DESIGN.md`, including §A13 from the `docs/system-design-factcheck` branch. The neutral moderator merged it from the round-a and round-b texts of STAT, RS, OBS, AWS and ADV. Choices rest on evidence, not votes. Deviations from SYSTEM-DESIGN are marked **[DEV]** and listed in §10.

Constraints:
- One autonomous agent builds for about 7–8 hours overnight, with no AWS and with offline tests. It builds on the merged P0 scaffold (`pkg/p0-scaffold`).
- The demo skeleton is merged before any trust maths.
- Kiro needs the probe and the Bedrock adapter by 08:00 EST Wednesday.
- Every number carries a synthetic flag.

## 0. Status and conflict resolutions

Status: **adopted, unanimous at vote round 3** (5/5; see [council-2-log.md](council-2-log.md)). The fact-check corrections in the last section **override the text above** wherever they differ. The r3 status note follows. r3 changes only the §6 I3 order checks (RS round-2 erratum). In the round-2 vote ADV, STAT, OBS and AWS accepted r2; RS rejected only on its own erratum. In the round-1 vote, ADV accepted; AWS, OBS, STAT and RS rejected with blocking objections. r2 adopts every blocking fix using the seats' own replacement text, plus the cheap non-blocking suggestions. The round-1 table at the end of §0 lists them. Every seat's BLOCKING items are now met. Where two of them conflicted (marked ⚔), the moderator chose and gives the reason.

| # | Issue | Options | Choice | Why | May upset |
|---|---|---|---|---|---|
| 1 | Overnight scope | ~20 h plans (STAT, RS, OBS, AWS) or demo-first ~8 h (ADV) | Demo-first: P0b–P8 overnight (~8 h); P9 is the first Wednesday item | Four seats conceded. Cutting a 20 h plan from the bottom loses the demo. | STAT, RS |
| 2 ⚔ | Strands before 08:00 (ADV D4) or on Wednesday (OBS, STAT, brief) | — | Bedrock adapter and probe before 08:00. Strands is W2. | K1 and K3 do not need Strands: the plain loop runs live on Bedrock. The brief already puts Strands on Wednesday. | ADV |
| 3 ⚔ | Trust package size: ADV 1.3 h vs STAT 1.8 h (blocking) | — | 1.8 h, placed after the rules and panels | Rushed trust work is how the wrong method tests got proposed (STAT A1, A2). | ADV |
| 4 | Where the AWS-a package goes | — | P6, directly after the demo skeleton; hard 08:00 deadline | AWS blocking item | — |
| 5 | Synthetic world | ADV rectangles or RS COG crossings | RS's world rendered in numpy (`synth-crossings-v1`), ADV's policy roster plus RS's `skimmer`, scripted outcomes. The pixel detector is a Should. | Keeps the bridge family, the cloud trap and the `visible_in` key (RS B5) without needing rasterio. | STAT, RS |
| 6 ⚔ | Real COG reads and measured `bytes_read` tonight (RS B2) or not tonight (ADV D5) | — | The rasterio reader, block cache and loopback Range test are **W1**, before K2b and K4. Tonight `SyntheticImagerySource` reports `bytes_read` from a declared, GDAL-like block model. Overview level is `L = max(0, floor(log2(native_px_per_side / out_px)))`, with overviews 2/4/8/16 declared on every synthetic scene. It counts the 512-px blocks intersected **at level L**, plus a 16 KB header on the first read of each scene, × a 48 KB mean compressed block. Results carry `reader="synthetic-v1"` and `detail.bytes_model="synthetic-overview-block-v1"`, chipped MEASURED, SYNTHETIC ("modelled bytes"). I3 order checks stand in until the W1 calibration. | The night is full and the demo needs no GDAL. B2 still holds before any real pixels are read. | RS |
| 7 | Vantor STAC fixture tonight (RS B4) vs "no HTTP" (ADV D5) | — | Fetched tonight by a script, outside pytest, metadata only | Compatible: D5 is about pixels and the test path. | — |
| 8 | MEASURED fence | by type (STAT) or by panel (OBS, RS) | By panel: process, understanding, cost, and `controls` agreement statistics. Never output or trust. | A grounding rate is an exact proportion of the trace; STAT's type list would leave it untyped. | STAT, ADV |
| 9 | Verdict vocabulary | present/absent (ADV) or yes/no/abstain (STAT) | `answer ∈ {yes, no, cannot_assess}` plus `question_id` (AWS) | Serves both the existence and the damage questions. | ADV, STAT |
| 10 | Reference for the shuffled-label test | B2 width (ADV, OBS, A7 wording) or classical gold-only (STAT) | Classical gold-only **[DEV]** | Measured: a correct estimator fails the B2 test (width 0.34 vs 0.51, and the interval excludes 0.5). | ADV, OBS |
| 11 | PPI coverage criterion | two-sided [0.85, 0.95] or one-sided ≥ 0.86 plus mutation | One-sided ≥ 0.86 plus mutation (STAT) | The fixed interval is conservative by design, and only the strong-verifier scenarios expose the known bug. | RS, OBS |
| 12 | Rogan–Gladen abstain rule | point se+sp−1 < 0.1 (OBS) or bootstrap rule | α/2 quantile of J\* ≤ 0.2; built in W4 | With 15+15 controls a point estimate is too noisy to trust. | OBS |
| 13 | Bedrock retries and concurrency | botocore adaptive (AWS) or our own loop (OBS); concurrency 4 (OBS) or 2 | botocore `total_max_attempts=1` (standard mode) plus our own jittered loop, one span event per attempt; concurrency 2 | Makes "every throttle is a span event" true; quotas are unknown. | AWS, OBS |
| 14 | How Strands reaches Bedrock | `BedrockModel` or our wrapper | `TreehouseStrandsModel` over our `ModelProvider`, with `SequentialToolExecutor` | One Bedrock adapter, working cassettes, fixed tool order (OBS t5). | — |
| 15 | S3 test double | Stubber or moto | moto, in W5 | Only moto exercises put-once, compare-and-swap and version-delete denial. | — |
| 16 ⚔ | Probe test doubles tonight: moto + Stubber (AWS) or no moto (ADV D5) | — | Stubber only tonight. moto arrives with S3Store. | Satisfies both: the probe is merged tonight, moto is not. | AWS |
| 17 | Offline guard | — | P0b extends P0: fake credentials, `AWS_CONFIG_FILE=/dev/null`, a `getaddrinfo` block and a boto3 canary. Marker names stay `live` and `allow_loopback`. | AWS blocking item; reuses the merged code. | — |
| 18 | Packaging | — | `mcp` becomes a core dependency (the gateway is MCP); `rasterio` is the `[geo]` extra; `boto3` and `strands` are extras imported lazily | OBS A5; RS C2 (macOS-14 wheel gap) | — |
| 19 | Cassette key | request hash, or (role, trial, turn, hash) | Look up by `(role, trial_index, turn)`; the request hash detects divergence | Request hash alone collides across trials. | — |
| 20 | What the demo runs | render JSON, or re-run | Re-run the cassettes through loop, gateway and **live in-process MCP servers** (results compared with the tool cassette), seal into a fresh store, then check, score, trust, report and `verify` | ADV D2, OBS B4, STAT A8 | — |
| 21 | How images reach the model | MCP ImageContent, or a side channel | Tools return a structured `WindowResult` with `pixel_sha256`; the gateway builds the `ImageBlock` from an in-process `PixelCache` | mcp 2.3 fills structured content only for Pydantic returns. Returning image plus structure via `-> mcp.types.CallToolResult` is now **verified** (OBS `t6.py`), so the stdio path is open. The side channel stays tonight because it keeps pixels out of MCP payloads and cassettes. | RS, OBS |
| 22 | Names and locations | — | OBS's module map plus `stats/`, `sampling/`, `geo/`, `synth/`. `fixtures/` and `keys/` sit at the repo root. Per-run budget in `gateway/budget.py`; spend ledger in `providers/spend.py`. | Convergent in round b | ADV |
| 23 | Cards | 3 (ADV) or 4 (RS) | 4: synth, Nepal, Virginia (`pending_fetch`), India stub | Virginia costs minutes. | — |
| 24 | Nepal controls | — | Test-retest on E5610/E5810 only; the passport prints why placebo is unavailable | RS measured ~51 % pre/pre overlap and a 3–5 year gap. | — |
| 25 | `estimators.lock` | tonight, or later | W13, frozen before the first live GOLD-ANCHORED run (K4) | The code is still churning. | STAT |
| 26 | Human `cannot_assess` gold label | — | A human `cannot_assess` is y=0 in the headline estimand, which is named `verified_precision` (chip: "share of claims a blind human could confirm; lower bound on precision"). The passport also reports `n_gold_cannot_assess` and an upper-bound alternative. The upper bound uses the same machinery with y=1 for those units (`precision_upper_if_unassessable_correct`) and is excluded from the disagreement check. When `n_gold_cannot_assess` = 0 the two coincide and the estimand is named `precision`. | A claim never becomes correct because nobody checked it (A5), and naming it a lower bound keeps the label honest (STAT-B1). Dropping those units would be non-random missingness. | — |
| 27 | Tier of the test-retest kappa | — | MEASURED, on panel `controls`, with a bootstrap interval and an anecdotal flag | It is exact agreement between recorded verdicts, not a trust estimand. | STAT, ADV |
| 28 | Checkpoint time | 04:30 or 04:00 wall clock | H4.5 after build start (the plan reaches P5 at H4.15) | Build start depends on the vote. | — |
| 29 | U3 process-signal model | — | Tonight MODEL-ESTIMATED means the B2 wide interval. The logistic model is W11. | Follows A7. | — |
| 30 | Vision smoke test timing | 08:00, or after the reader | After W1 (about 09:45). K3, a live synthetic keyed run, goes first. | Real windows need the reader. | ADV, AWS |

### Round-1 objections and resolutions

| Seat | Objection | Resolution | Section |
|---|---|---|---|
| AWS-B1 (blocking) | At K1 every price is null, so the probe's live Bedrock calls are either refused or bypass the ledger | Every probe call goes through `SpendLedger.reserve(..., unpriced_cap_usd=0.25)` with `max_tokens ≤ 32`. The whole probe is capped at $3; later checks report `skipped_budget`. Commits use actual usage at a placeholder price from `config/prices/probe-ceiling.yaml`, tagged `estimated: true`. Stubber tests show no Converse call without a reservation, and a stop at the cap. | §3 SpendLedger, §7 P6 |
| OBS-B1 (blocking) | A text placeholder for recorded images gives replay a different key from live, so real runs never replay | Recorded and pixel-free sources attach the same `Image(format, sha256, bytes_=None)`. `key()` is identical with or without bytes. Live providers refuse a byte-less Image (`MissingPixels`). Test: a live-recorded key equals its pixel-free replay key. | §2 model_io, §3 gateway step 9, §7 P3, P4 |
| OBS-B2 (blocking) | Golden heads would depend on zlib's PNG bytes | `Image.sha256` and `pixel_sha256` hash the decoded C-order uint8 array plus its shape string, never encoded bytes. Test: re-encoding at another zlib level leaves `key()` and the trace head unchanged. | §2, §7 P4 |
| STAT-B1 (blocking) | y=0 for a human `cannot_assess` makes "precision" a false label | Headline renamed `verified_precision` (a lower bound). Added `n_gold_cannot_assess` and a y=1 upper-bound alternative. The gate names `verified_precision`. | §0 row 26, §2 passport, §3 PPI and gate, §10 |
| STAT-B2 (blocking) | The M5 mutation threshold sits on a knife edge (\|bias\| 0.041) | P(abstain) is now 0.6 when y=0 and 0.1 when y=1. The mutation draws gold only from non-abstained units (measured bias 0.057–0.063). | §6 M5 |
| RS-B1-erratum (round 2, blocking) | The round-1 order checks (≤ 2×, ≥ 8×) fail for a correct implementation of the specified block model (worst cases 4.0 and 4.0 over 2,000 centres) | Order checks restated on block counts: ≤ 4×, ≥ 4×, exact centre counts 1/4/25 | §6 I3 |
| RS-B1 (blocking) | A native-resolution block model makes skimmer look about 35× costlier; the measured ratio is 1.2× | Overview-aware block model, a `bytes_model` tag and a "modelled bytes" chip; I3 order checks; W1 calibration test | §0 row 6, §3 imagery, §6 I3, §7 W1 |
| ADV NB1 | C1 at H4.0 fires by default | C1 is now H4.5 | §7 |
| ADV NB2 | P8 may land after 08:00 | C3: TODO.md states which of P7–P8 are merged. The README describes only what the merged demo shows (for example "trust passport: stub"). | §7 |
| ADV NB3 | Hover text for modelled bytes | Superseded by RS-B1's "modelled bytes" chip | §2 chip() |
| ADV NB4 | No Strands claims if W2 slips | If W2 is not merged, K4 runs with `--harness plain_loop`. The manifest, report and demo script then say "Strands adapter: offline-tested only". | §8 |
| OBS NB1 | `CallToolResult` image plus structure verified (t6.py) | Recorded in row 21; the side channel stays tonight | §0 row 21 |
| OBS NB2 | K5 and K6 have no W number | Added W3b: `cassette export`, `fetch_uspvdb.py`, `fetch_osm_bridges.py` | §7, §8 |
| AWS NB1 | A Kiro reset silently zeroes the ledger | The Kiro preamble sets `TREEHOUSE_SPEND_LEDGER=$REPO/.spend/spend.jsonl` and commits and pushes it after every K step | §4, §8 |
| STAT NB2 | Say plainly when PPI did not narrow | When `width_ratio_vs_classical` ≥ 1 the passport prints "the verifier did not narrow the interval at n_gold=k" | §2, §3 PPI |
| STAT NB3 | Validity of the hypergeometric comparator | `hypergeom_exact` only when every stratum is a census (n_h = N_h), asserted in code | §3 PPI |
| RS NB1 | nepal-good WindowResults are invented values on real scene ids | Every WindowResult row in the claim and evidence table carries `synthetic: true` and a SYNTHETIC chip | §5.2, §6 I5 |

## 1. Module layout

```
pyproject.toml  core: pydantic pyyaml numpy scipy typer mcp>=2.3,<3 httpx
                extras: aws=[boto3] strands=[strands-agents>=1.63,<2] geo=[rasterio>=1.4] api=[fastapi,uvicorn]
                dev: pytest ruff hypothesis boto3 (moto[s3] from W5)
src/treehouse/
  canon.py  clock.py (Clock, WallClock, LogicalClock)  ids.py (seeded IdSource)  paths.py (roots, tool-root/key guard)
  schemas/    numbers geo task config model_io trace tools claims checks sampling verdicts scorecard passport manifest bundle
  geo/        geom.py (PIP w/ holes, bbox, haversine, local-ENU seg distance, coverage grid)  match.py (1:1 LSA)
  stats/      intervals.py bootstrap.py agreement.py (tests.py W8)                          LEAF: numpy/scipy only
  sampling/   design.py gold.py blind.py                                                    LEAF: numpy/scipy only
  providers/  base.py fake.py cassette.py bedrock.py registry.py prices.py spend.py
  harness/    base.py plain_loop.py prompts/ (strands_adapter.py W2)
  gateway/    gateway.py policy.py budget.py meter.py tool_cassette.py pixel_cache.py
  tools/      servers.py stac.py imagery.py clay.py claims.py decoy.py png.py sources/{synthetic,recorded,cog(W1)}.py
  synth/      world.py render.py policies.py nepal.py fixtures.py
  trace/      chain.py tracer.py (otlp_mirror.py W9)
  store/      base.py local.py seal.py verify.py backends.py (s3.py W5)
  checks/     rules.py keyed.py leak.py ledger.py
  verifier/   recorded.py (agent.py W2)
  trust/      config.py ppi.py baselines.py tiers.py controls.py passport.py (rogan_gladen.py W4)
  score/      process.py understanding.py output.py cost.py scorecard.py
  summary/    facts.py template.py lint.py (phrase.py W14)
  report/     bundle.py html.py
  runner.py (task × config × K → harness/gateway/tracer/seal)  service.py (single code path)  demo.py  cli.py
  mcp_server.py (W7)  api.py (W12)
scripts/  build_vantor_fixture.py make_demo_fixtures.py aws_probe.py
config/   models.yaml  prices/bedrock-us-east-1.2026-11-04.yaml (nulls)  prices/fixture.yaml (synthetic)
prereg/   trust-config.yaml gold-seed.txt primary.yaml
tasks/    synth-crossings-v1 nepal-bhote-koshi-bridges virginia-solar-18sth india-brahmaputra-bridges (.yaml)
fixtures/ stac/{synth-crossings-v1,vantor-nepal-aug-2026}/ embeddings/ demo/{runs.yaml,configs,cassettes,verdicts,gold,nepal} golden/
keys/     synth/*.key.json synth/nepal-demo-truth.json   (outside every tool root)
tests/    unit property method golden integration journeys live
```

**Import boundary.** An AST test enforces these rules, and a planted bad file proves the test can fail.
- `stats/` and `sampling/` import only the stdlib, numpy and scipy.
- `schemas/` imports only pydantic, the stdlib and `canon`.
- `geo/`, `checks/`, `score/`, `trust/`, `summary/` (except `phrase.py`) and `report/` never import `providers`, `harness`, `gateway`, `tools`, `store`, `runner`, `boto3`, `botocore`, `httpx`, `strands`, `mcp`, `rasterio` or `socket`. They receive a `SealedRun` object from `service`.
- `boto3`, `strands` and `rasterio` are imported lazily. A test imports every module with `sys.modules[x]=None` for each of them.

## 2. Schemas

All schemas are Pydantic v2 and inherit `class Frozen(BaseModel): model_config = ConfigDict(frozen=True, extra="forbid")`. Top-level records carry `schema_version`. `treehouse schema <name>` exports JSON Schema, and a golden test diffs the export.

```python
class Tier(StrEnum): KEYED="KEYED"; GOLD_ANCHORED="GOLD-ANCHORED"; CALIBRATED_TRANSFER="CALIBRATED-TRANSFER"
                     MODEL_ESTIMATED="MODEL-ESTIMATED"; ABSTAINED="ABSTAINED"; MEASURED="MEASURED"
NumType = Literal["proportion","count","flag","usd","seconds","bytes","tokens","ratio","kappa"]
PanelName = Literal["process","understanding","output","trust","controls","cost"]
class Interval(Frozen): lo: float; hi: float; level: float; method: Literal["wilson","clopper-pearson","hypergeom-exact",
    "ppi-2phase-rbs-v1","cluster-bootstrap","betabinom-predictive","poisson-binomial","kappa-bootstrap",
    "rg-bootstrap-inflated-v1"]; B: int|None=None; seed: int|None=None; fpc: bool=False
class TypedNumber(Frozen):
    metric: str; value: float|None; type: NumType; tier: Tier; panel: PanelName; rung: Literal["L1","L2","L3","L4"]|None=None
    n: int|None; n_gold: int|None=None; n_verified: int|None=None; abstention_rate: float|None=None
    interval: Interval|None=None; estimator_version: str; config_hash: str|None=None; manifest_ref: str
    reasons: list[str]=[]; synthetic: bool  # required, no default
    replayed: bool=False; detail: dict[str, str|int|float|bool]={}
```

**TypedNumber validators** (each is a row in a table test):
- `value` may be None only when the tier is ABSTAINED (with non-empty `reasons`), or when the tier is MEASURED and `reasons` contains `"unpriced"`.
- KEYED requires `detail.key_version` and `n`.
- GOLD-ANCHORED requires `n_gold ≥ 1`, `abstention_rate` and `interval`.
- CALIBRATED-TRANSFER and MODEL-ESTIMATED require `interval`.
- MEASURED requires `panel ∈ {process, understanding, cost, controls}`, and its interval is None unless `detail.aggregate_over` is set.
- A proportion must lie in [0, 1].

`chip()` returns the plain-English label: "Checked", "Estimated from a random check", "Estimated from track record", "Rough model guess", "Not issued" or "Measured from trace". It adds "SYNTHETIC" when `synthetic` is set and "recorded" when `replayed` is set. A `bytes_read` from the synthetic block model reads "Measured from trace · SYNTHETIC · modelled bytes", with the hover text "declared overview-block model, not measured" (RS-B1).

A field-walker test fails on any bare `float` anywhere in `Scorecard`, `TrustPassport` or `ReportBundle`.

```python
BBox = tuple[float,float,float,float]; Point(type="Point", coordinates); Polygon(type: Polygon|MultiPolygon, coordinates)
# task.py
DataSource(source_id, kind: stac|imagery|embeddings|vector, access: static_catalog|s3_listing|synthetic|recorded,
           fixture_path|None, item_ids, etags: dict, license (SPDX/LicenseRef), status: pinned|unpinned|pending_fixture)
ClassSpec(min_size_m, max_effective_gsd_for_existence_m, max_effective_gsd_for_status_m, match_tolerance_m,
          key_geometry: point|line|polygon)
Keying(mode: keyed|partly_keyed|unkeyed, key_source|None, key_path|None, version_hash|None, license|None,
       reference_quality: complete|incomplete|synthetic|None, completeness_caveat|None, key_coverage_mask: Polygon|None,
       match_rule: {tolerance_m: dict[cls,float], one_to_one: True}|None, status: present|pending_fetch|none)
Step(step_id, question_id: exists|damaged, statuses_allowed, keying: Keying)
ForbiddenSource(kind: host|url_prefix|s3_prefix|dataset_id|tool|path, pattern)
NoticeItem(id, kind: mentions_any|plans_tool|declares_limit, terms, tool|None, weight=1.0)
SamplingPlan(strata_keys ⊆ {class,conf_tercile,cloud_class}, min_N_h=4, n_total, census_if_N_le=60, seed,
             controls: {keyed_pos,keyed_neg,placebo_pairs,retest_pairs: int}, unreported_frame: dict|None  # W10)
GoldPlan(n_gold, rubric, labeller, date, seed_file, blind_protocol: {hide: list, shuffle: True, seal_before_reveal: True, relabels: 5})
TaskCard(schema_version="treehouse.task/1", id, version, title, family, synthetic: bool, synthetic_notice|None, goal,
         aoi: Polygon, smoke_aoi: BBox|None, time_window: (start,end), as_of, event: {date, footprint_ref}|None,
         data_allowlist: list[DataSource], tools_allowed, needs_vision, classes: dict[str,ClassSpec],
         windows: {max_side_m, max_out_px, max_bytes_per_run}, steps: list[Step],
         forbidden_sources: list[ForbiddenSource]  # required; [] only if no step is keyed
         must_notice, known_limits, sampling_plan, gold_plan|None, thresholds: {rely_lo}, budget)  .card_hash()
# config.py
InferenceParams(max_tokens, temperature|None, top_p|None, seed|None)
RoleConfig(provider: fake|replay|bedrock|openai_compat, model_key, family, params, tools, script|None, cassette|None)
Budget(enabled, usd|None, tool_calls|None, bytes|None, wall_s|None, tokens|None)
Backends(store: local|s3, key_isolation: local|iam, tracer: list[jsonl|otlp|cwlogs], tool_locus: inproc, allow_degrade=True)
RunConfig(schema_version="treehouse.runconfig/1", task_ref "id@sha256:…", mode: fake|replay|record|live, worker,
          verifier|None, summarizer|None, harness: plain_loop|strands, max_turns=40, tool_executor="sequential",
          trials=1, seed, clock: wall|logical, budget, backends, allow_same_family=False, tool_mode: live|verify)
          # validators: cross-family unless allow_same_family; needs_vision rejects non-vision registry rows
EvalSpec(run_ref, scorers: dict, key_version|None, verifier: {mode: recorded|agent, …}, gold: {labels_path, draw_ref}|None,
         trust_config_hash, estimator_version, seed)
TrustConfig(level=.90, B=2000, pseudo_weight=.5, lam_fixed_below=50, j_min=.2, tau_floor=.5, kappa0=10,
            min_runs_mle=3, g_min_label=5, max_abstention_for_rely=.3, placebo_far_max=.10, anecdotal_below=10)
# model_io.py
# Image.sha256 and WindowResult.pixel_sha256 = sha256 of the decoded C-order uint8 array plus its shape string, never of
# encoded PNG/JPEG bytes. Encoded bytes are transport only and never enter keys, traces or heads (OBS-B2).
# Image(bytes_=None) is accepted only by ReplayProvider; live providers raise MissingPixels (OBS-B1).
Block = Text(text) | Image(format, sha256, bytes_|None) | ToolUse(id,name,input) | ToolResult(tool_use_id,status,content)
      | Reasoning(text, signature);  Message(role, content); ToolSpec(name, description, input_schema)
ModelRequest(model_id, system, messages, tools, params).key()   # canon with each Image reduced to (format, sha256): same with or without bytes_
Usage(input_tokens, output_tokens, cache_read, cache_write, image_input_tokens|None)
ModelResponse(message, stop_reason: end_turn|tool_use|max_tokens|stop_sequence|content_filtered|guardrail, usage,
              latency_ms, response_model_id, request_id|None)
# trace.py
SpanRecord(trace_id, span_id, parent_span_id|None, name, op: invoke_agent|chat|execute_tool, start_ns, end_ns,
           status: ok|error, error: {source: agent|tool|infra|budget|policy, type, message}|None,
           attributes: dict[str, scalar|list[str]], events: list[{name, ts_ns, attributes}])
ChainLine(seq, prev, rec, h = sha256(prev + canon(rec)));  ChainHead(head, n_lines, file_sha256)
# tools.py
SceneSummary(scene_id, datetime, phase: pre|post|None, cloud_pct, pan_gsd_m, off_nadir_deg|None, sun_elevation_deg|None,
             footprint, aoi_coverage_fraction, license)
WindowResult(result_id, source_id, scene_id, etag|None, bbox_requested, bbox_read, footprint_coverage_fraction,
             scene_datetime, phase, nominal_gsd_m (pan_gsd), pixel_spacing_m, effective_gsd_m (=side_m/out_px),
             overview_level, scene_cloud_pct, off_nadir_deg|None, out_shape, resampling, pixel_sha256, bytes_read,
             requests, block_size, reader: synthetic-v1|recorded|rasterio-<v>, gdal_version|None,
             obscuration: {bright_lowvar_fraction, nodata_fraction, method: "heuristic:v1"}, license, synthetic,
             detail: {bytes_model: "synthetic-overview-block-v1" | "measured", …})
ClaySearchResult(cells: [{cell_id, center, similarity}], coverage: {source, cell_m, date_range, predates_event,
                 aoi_cells_expected, aoi_cells_present, smallest_resolvable_m, synthetic})
StacSearchResult(scenes, as_of_applied, dropped_after_as_of); ToolError(code, message)
ClaimReceipt(claim_id, grounded, unresolved_refs); LimitationReceipt; UnderstandingReceipt
# claims.py
Claim(claim_id, run_id, trial_id, step_id, geometry: Point, bbox|None, cls,
      status: present|absent|intact|damaged|destroyed|cannot_assess, confidence, reason,
      evidence_refs: list[{result_id, role: pre|post|existence}], span_id, grounded, unresolved_refs, contaminated, synthetic)
UnderstandingStatement(goal_restated, scope, planned_data, known_limits, span_id)
# checks.py
CheckResult(claim_id, layer: rules|key|verifier|human|overlap|leak, check_id, version, result: pass|fail|flag|n/a,
            code|None, detail, record_ref)
CheckLedger(claim_id, results, resolved: correct|incorrect|fabrication|ungrounded|contaminated|to_adjudicate|unchecked,
            resolved_by)   # rule fail > human > key > verifier > unchecked
# sampling.py
SampledUnit(unit_id, kind: claim|control_pos|control_neg|placebo|retest|unreported, ref, stratum, pi, order)  # kind/ref sealed
SampleDesign(design_id, seed, rng="numpy.PCG64", algorithm="strat-srswor-v1", frame_hash, N_h, n_h, units, created_seq)
GoldDraw(draw_id, design_id, seed, n_gold, unit_ids, pi2, committed_ref, committed_seq)
BlindItem(unit_id, lon, lat, object_definition, question_id, scene_ids)          # nothing else, ever
# verdicts.py
VerifierVerdict(unit_id, question_id, answer: yes|no|cannot_assess, verifier_config_hash, request_hash, span_ref|None,
                recorded, synthetic, created_seq)
GoldLabel(unit_id, question_id, label: yes|no|cannot_assess, labeller, labeller_kind: human|synthetic,
          blind_protocol_hash, ts, sealed_ref, is_relabel, synthetic)
# scorecard.py / passport.py
Panel(name, version, numbers: dict[str,TypedNumber], evidence_span_ids: dict[str,list[str]], no_grade_reason|None)
Scorecard(run_ref, process, understanding, output, cost, trust_ref|None, versions)       # no composite field (test)
Estimand(name, kind: precision|verified_precision|count|miss_rate, step_id, question_id, population: claim_table|unreported_frame)
   # verified_precision (lower bound) when any gold label is cannot_assess; precision when n_gold_cannot_assess = 0
ControlsReport(se, sp, placebo_far, retest_kappa, relabel_kappa: TypedNumber|None, unavailable: list[str])
TrustPassport(schema_version="treehouse.passport/1", estimand, headline (detail.width_ratio_vs_classical),
              alternatives: list[TypedNumber]  # classical gold-only, B0, B1 "agent's claim", B2, RG,
                                               # precision_upper_if_unassessable_correct (y=1; not in disagreement check)
              n_gold_cannot_assess: int, narrowing_note: str|None,  # "the verifier did not narrow the interval at n_gold=k"
              disagreement: list[(str,str)], gate: Rely|Spot-check|Do not rely, gate_reasons, controls, shift: dict,
              beat_baseline: str, process_facts: dict[str,TypedNumber], truth_reveal|None (synthetic only),
              sample_design_id, gold_draw_id|None, trust_config_hash, estimator_version, code_sha, manifest_ref, synthetic)
# manifest.py
BackendResolution(requested, ran, degraded_from|None, reason|None, evidence, statement|None)
   # validator: ran==requested or (degraded_from and reason); ran ∈ {s3, iam} requires read-back/denial evidence
TrialHead(trial_id, role, trace_file, head: ChainHead, claims_sha256, stop: completed|max_turns|budget|error)
DataPointer(scene_id, href|None, etag|None, bbox, datetime, license)
Manifest(schema_version="treehouse.manifest/1", run_id, created_at, task{id,version,hash}, config_hash, config, mode,
         backends_resolved: dict[store|key_isolation|model.worker|model.verifier|tracer, BackendResolution],
         versions{treehouse, git_sha, uv_lock_sha256, python, harness, prompts_sha, semconv_ref, price_table, registry},
         trials, cassettes{model_sha, tool_sha}, data_pointers, key_isolation_statement, license_floor, nc_notice,
         synthetic_data, prev_manifest_hash|None, manifest_hash)
ReportBundle(manifest summary, card, scorecard, passports, claims+ledgers, trace rows, facts, summary+lint, synthetic)
```

`task validate` checks the following:
- the AOI is a valid polygon and intersects a pinned footprint;
- every pinned item has a fixture and an ETag;
- every keyed step has non-empty `forbidden_sources`;
- `key_path` is under `keys/` and not under any tool root;
- the license floor is computed.

`pending_fetch` keys and `unpinned` sources only produce warnings.

## 3. Interfaces

```python
class ModelProvider(Protocol):
    provider_name: str   # gen_ai.provider.name
    async def complete(self, req: ModelRequest, *, role: str, trial_index: int, turn: int) -> ModelResponse
FakeProvider(script: YAML[{expect, respond}] | Callable)  # failed expect -> ScriptDivergence; tokens=len(text)//4
RecordingProvider(inner, cassette)                        # appends {role,trial_index,turn,request_hash,response,…}
ReplayProvider(cassette, miss="fail")                     # CassetteMiss(key, first_divergent_message_index)
BedrockConverseProvider(client_factory, registry, prices, ledger: SpendLedger, region, concurrency=2, max_attempts=6)
OpenAICompatProvider(base_url, api_key_env)               # Could; httpx.MockTransport tests
```

**Bedrock adapter.**
- **Call shape.** `converse(modelId=<inference profile>, system, messages, toolConfig, inferenceConfig)`.
- **Image delivery.** The registry entry sets `image_delivery`: either `tool_result` or `user_turn`. It is applied *after* the request key is computed.
- **Retries.** The botocore config is `retries={"total_max_attempts":1,"mode":"standard"}, read_timeout=300`. Our own jittered backoff retries `Throttling`, `ServiceUnavailable` and `ModelNotReady`, with one `treehouse.retry` span event per attempt. A semaphore caps concurrency.
- **Usage.** Cache tokens are mapped. `reasoningContent` is stored and never scored. Cost is usage × the dated price.
- **Spend.** `ledger.reserve()` runs before each call and `commit()` after it.
- **Stubber tests:**
  - a text turn and a tool-use turn;
  - both image modes;
  - two throttles, then success;
  - `ValidationException` mapped to a typed error;
  - stop-reason mapping;
  - an unpriced model refused;
  - the same-family rule and the vision rule.

`config/models.yaml` rows hold: key, family, model_id, inference_profile, region, vision, tool_use, image_delivery, max_image_px, price_ref and quota_note. Defaults: worker `claude-sonnet-5-5`, verifier `nova-pro`. Both are UNVERIFIED until K1. A null price produces `UNPRICED`, which means MEASURED with value None and reason "unpriced".

```python
SpendLedger(path=$TREEHOUSE_SPEND_LEDGER or ~/.treehouse/spend.jsonl, planned=250, alarm=350, hard_stop=450)
  .reserve(model_key, est_input_tokens, max_tokens, *, allow_over_alarm=False, reason=None, unpriced_cap_usd=None) -> Reservation
  .commit(reservation, usage) -> float;  .status() -> SpendStatus
  # worst case = in_est*in_price + max_tokens*out_price; spent+reserved > 450 -> BudgetHardStop (replay only);
  # > 350 needs flag + logged reason; > 250 warns; null price refused unless unpriced_cap_usd
  # probe (AWS-B1): every call reserve(..., unpriced_cap_usd=0.25), max_tokens ≤ 32, probe total cap $3 then
  # skipped_budget; commit actual usage at config/prices/probe-ceiling.yaml placeholder prices, tagged estimated: true
class Harness(Protocol):
    name: str; version: str
    async def run(self, *, system, user, provider, gateway, tracer, budget, max_turns, role, trial_index) -> HarnessResult
HarnessResult(final_text, stop: completed|max_turns|budget|error, turns)   # never claims
```

**Harnesses.**
- **`PlainLoop`** (about 100 lines; the demo and replay engine) repeats: open a `chat` span, then append the assistant message, then run `gateway.call` for each ToolUse, then append one user message of ToolResults. It stops on end_turn, max_turns or BudgetExceeded.
- **`StrandsHarness`** (W2) builds `Agent(model=TreehouseStrandsModel(provider, tracer, budget), tools=gateway.as_strands_tools(), tool_executor=SequentialToolExecutor(), callback_handler=None)`, with Strands OTel off. Its contract test: the same script gives identical request hashes and an identical claim table under both harnesses.

```python
ChainedJsonlWriter(path, genesis=sha256("treehouse/trial/"+trial_id)).append(rec) -> h; .close() -> ChainHead
TrialTracer(writer, *, trace_id, clock: Clock, ids: IdSource, base_attrs).span(name, op, **attrs) -> ctx  # .set .event .error
```

**Span records.** Each span is written when it ends. These attributes are mandatory:
- **Run context:** `treehouse.{task.id, task.hash, run.id, trial.id, trial.index, role, config.hash}`.
- **Cost and replay:** `treehouse.{cost.usd, price_table.version, cassette, recorded_latency_ms}`.
- **Tool calls:** `treehouse.{tool.args_hash, tool.result_id, tool.result_ref, tool.bytes_read, tool.blocked, tool.block_reason, key_access_attempt}`.
- **Data and claims:** `treehouse.{image.sha256, scene.id, license.spdx, claim.id, evidence.refs, budget.remaining_usd}`.
- **GenAI semconv:** `gen_ai.provider.name`, `gen_ai.usage.*`, `gen_ai.input.messages_ref`.

Message bodies go into blobs. Under `LogicalClock`, with ids from `IdSource(seed)`, a replay produces a byte-identical trace.

```python
class ToolGateway:
    def __init__(self, servers: Mapping[str, MCPServer], policy, tracer, budget: BudgetGuard, meter, pixels: PixelCache,
                 tool_cassette: ToolCassette|None, mode: Literal["live","verify"], as_of, store)
    async def __aenter__(self)   # one in-process mcp.client.Client(srv) per server; catalog from list_tools()
    def specs(self) -> list[ToolSpec]; async def call(self, name, args, *, call_id) -> ToolOutcome
    claims: ClaimLedger; limitations: list; understanding: UnderstandingStatement|None
ToolOutcome(result_id, status: success|error|blocked, content, bytes_read, latency_ms, block_reason|None)
BudgetGuard(Budget).reserve/commit   # usd, tool calls, bytes, wall s, tokens; events at 50/80/100 %; enabled=false: no limits
```

**`call` steps, in order:**
1. Open an `execute_tool` span.
2. Apply the policy:
   - a tool off the allow-list gives `not_allowlisted`;
   - any URL, `s3://` path, filesystem path, dataset id or tool name that matches `forbidden_sources` or the key root gives `forbidden_source`, with `key_access_attempt=true`;
   - data after the `as_of` date is refused with `as_of`.

   A blocked call returns an `is_error` result reading "blocked by policy: …". It never raises.
3. Check the budget.
4. Call `client.call_tool`. Bad arguments come back as `is_error`.
5. Re-check every returned href against the deny-list.
6. In `verify` mode, compare the result digest with the tool cassette. A mismatch raises `ToolDivergence`.
7. Meter the call and write the result to a blob.
8. Inject `result_id = r-{seq:04d}` into what the model sees.
9. For `imagery_window`, attach `Image(format, sha256, bytes_)`, with `bytes_` taken from `PixelCache` when present. Recorded and pixel-free sources attach the same block with `bytes_=None`. `key()` is identical with or without bytes. Live providers refuse an `Image` whose `bytes_` is None (`MissingPixels`); only ReplayProvider accepts it.

`record_claim`, `note_limitation` and `submit_understanding` are intercepted by the gateway:
- unresolved `evidence_refs` set `grounded=false`;
- citing a blocked result sets `contaminated=true`.

**MCP servers.** Each is an in-process `MCPServer`. **Every tool returns a Pydantic model**, and a test asserts that `structured_content` is non-null for every tool.

| Server | Tools | Sources |
|---|---|---|
| stac | `stac_search(aoi_bbox, start, end) -> StacSearchResult` (pinned ids only; `as_of`; coverage on a 30×30 grid). `scene_info(scene_id) -> SceneSummary` | static fixture JSON |
| imagery | `imagery_window(scene_id, lon, lat, side_m, out_px=512, resampling="average") -> WindowResult` | `SyntheticImagerySource`: numpy render; deterministic PNG (transport only). `bytes_read` comes from the overview-block model: L = max(0, floor(log2(native_px_per_side/out_px))) with overviews 2/4/8/16; 512-px blocks intersected at level L; plus a 16 KB header on the first read of each scene; × 48 KB per block. `detail.bytes_model="synthetic-overview-block-v1"`, chip "modelled bytes". `RecordedImagerySource`: WindowResults from a cassette, no pixels. `CogSource` (W1): rasterio, counting opener, 16 KB block cache, `If-Match` ETag |
| clay | `clay_search(aoi_bbox, lon, lat \| cell_id, k) -> ClaySearchResult` | numpy cosine over npz; the loader takes a column map |
| claims | `record_claim`, `note_limitation`, `submit_understanding` | gateway ledger |
| decoy | `key_lookup` | exists only to be forbidden |

Imagery error codes: `not_allowed`, `not_available_as_of`, `no_coverage`, `out_of_bounds`, `window_too_large`, `budget_exceeded`, `insufficient_coverage`, `snapshot_changed` (W1).

```python
class Store(Protocol):
    def put_blob(self, data: bytes, *, media_type: str, license: str) -> str      # CAS, idempotent
    def put_once(self, key: str, data: bytes) -> None                               # AlreadyExists
    def get(self, ref: str) -> bytes
    def append_record(self, kind: str, run_id: str, rec) -> RecordRef               # refuses unsealed runs
    def ledger_seq(self) -> int
LocalStore(root)  # O_EXCL + chmod 0444; atomic rename from runs/.tmp-<id>; chained ledger.jsonl
seal(store, tmp_run, parts) -> Manifest   # hash files, manifest LAST, SEALED, ledger append
verify(store, run_id|None) -> VerifyReport  # lines, file shas, heads, manifest hash, ledger chain, blobs, evals→sealed
resolve_backends(cfg, probes) -> dict[str, BackendResolution]   # local tonight; S3/IAM read-backs + canary denial W5
S3Store (W5): PutObject(IfNoneMatch="*", ChecksumAlgorithm="SHA256"); HEAD CAS via IfMatch on chain/HEAD; moto tests
```

**Rules** (`checks/rules.py`, pure). Inputs are the frozen claims, the WindowResults in the sealed trace, the card and the pinned STAC fixture. Nothing the agent asserts about scenes or bboxes is used.

| Rule | Checks |
|---|---|
| R1 | Schema and class |
| R2 | Point inside the AOI |
| R3 | Point inside the cited scene's fixture footprint |
| R4 | Evidence-in-trace: the cited result is an earlier `imagery_window` in this trial whose `bbox_read` **contains** the point. Gives `fabrication` if no such result exists, `ungrounded` if it does not contain the point. |
| R5 | `effective_gsd_m` is within the class limit (existence or status). A Clay hit alone never suffices. |
| R6 | A status claim needs a post-event footprint covering the point. `cannot_assess` is exempt. |
| R7 | Cited scenes are ≤ `as_of` and inside the time window. Damage without pre evidence gives a *flag*. |
| R8 | Forbidden calls and budget, taken from spans |
| R9 | A status claim on a window with obscuration > 0.3 gives a flag |

**Keyed match** (`geo/match.py`):
- Pairs are feasible within the per-class tolerance and inside the coverage mask, found with a grid hash.
- Each connected component is solved one-to-one with `linear_sum_assignment` (infeasible cost 1e9, ties broken by sorted ids).
- `cannot_assess` claims leave the precision denominator and are graded against `visible_in`.

**Leaks** (`checks/leak.py`):
- An in-tolerance TP that has no R4-valid evidence is a `probable_leak`.
- A canary in the claims makes the run `INVALID_FOR_ACCURACY`.

```python
# stats/ (leaf; dataclass returns)
wilson(k,n,level) clopper_pearson(k,n,level) hypergeom_exact(k,n,N,level)  poisson_binomial_interval(p,level)
cluster_bootstrap(values, clusters, *, stat, weights, B, level, seed) -> Est;  cohen_kappa(a,b,*,B,seed) -> Est
# sampling/ (leaf)
assign_strata(units,*,keys,min_N_h=4,collapse_order=("cloud_class","conf_tercile"))  allocate(N_h,n_total,*,min_per_stratum=2,census_if_N_le=60)
stratified_sample(frame, n_h, *, seed)   # pi=n_h/N_h, PCG64       ht_mean(y, pi, N)
draw_gold(design, n_gold, *, seed, committed_ref, committed_seq)  # SRSWOR from ALL of S; takes no verdicts
assemble_verifier_batch(design, controls, *, seed, hmac_key) -> (list[BlindItem], SealedMap)
# verifier/
RecordedVerifier(verdicts_path)  # refuses any verdict with created_seq < gold_draw.committed_seq
AgentVerifier (W2)               # second harness run; tools [imagery_window, stac_search]; prompt only from BlindItem
# trust/ (pure)
predictor_values(answers, claimed_status, strata) -> (f, abstain_mask)
ppi_mean(design, gold, f, abstain, y_gold, *, cfg, seed) -> PPIResult;  classical_gold_only(design, gold, y_gold, *, cfg)
baseline_b0(keyed_runs, family, model, harness, toolset, n_new, cfg) -> TypedNumber|None
baseline_b1(confidences, level);  baseline_b2(keyed_runs, model, harness, n_new, cfg);  betabinom_fit / betabinom_predictive
controls_report(verdicts, sealed_map, key|None, cfg) -> ControlsReport
select_tier(ev, cfg) -> TierDecision;  disagreements(nums);  gate(headline, threshold, disagree, controls, cfg)
build_passport(estimand, ev, cfg, *, seed) -> TrustPassport
```

**PPI (`ppi-2phase-rbs-v1`).** Port `scratchpad/council2/proto/ppi2.py` and copy it to `tests/method/_reference_ppi.py` as the test oracle.

Definitions:
- Strata h have frame size N_h and sample size n_h. Weights are W_h = N_h/N and w_i = N_h/n_h.
- f_i = 1 when the verifier's answer agrees with the claimed status, else 0. For an abstained unit, f_i is the mean of the non-abstained f in its stratum of S. If the stratum has none, use the pooled mean; if there are no verdicts at all, use 0.5.
- G ⊂ S is the gold set, drawn SRSWOR with size g. y_i = 1 when the human label agrees with the claim. A human `cannot_assess` is y=0, so the estimand is `verified_precision`, a lower bound. A second `ppi_mean` call with y=1 for those units gives `precision_upper_if_unassessable_correct`. `n_gold_cannot_assess` is reported. When it is 0 the estimand is named `precision`.

Point estimate, with λ = 1 while g < 50:

θ̂ = Σ_h W_h f̄_{S_h} + Σ_G w_i(y_i−f_i)/Σ_G w_i

Variance:
1. Let d = y−f on G. Append two pseudo-units, d = +1 and d = −1, each with weight `pseudo_weight`·mean(w_G).
2. Let g_eff = (Σw)²/Σw², and s_d² = [Σw(d−μ)²/Σw]·g_eff/max(g_eff−1, 1).
3. Let s_y² be the variance (ddof 1) of y_G ∪ {1, 0}.
4. V = Σ_h W_h²(1−n_h/N_h)s_y²/n_h + (1−g/n)s_d²/g.

Interval:
1. Draw B bootstrap replicates of S, resampling within strata. Gold flags travel with their units.
2. If v\* = Var(θ\*) > 0, set r = √(V/v\*) and take the percentiles of θ̂ + r(θ\*−θ̂).
3. Otherwise use θ̂ ± t_{g−1}√V.
4. Clip the interval to [0, 1].

The classical comparator is `hypergeom_exact` only when **every** stratum is a census (n_h = N_h, asserted in code), and otherwise the same machinery with f ≡ 0. `width_ratio_vs_classical` goes in `headline.detail`. When the ratio is ≥ 1, `narrowing_note` reads "the verifier did not narrow the interval at n_gold=k", and the report prints it beside the headline. Cross-fitted λ is a Wednesday item.

**Tier ladder** (first match wins; reasons are recorded):
1. **KEYED (L1)**: the key covers the estimand.
2. **GOLD-ANCHORED (L3, or L2 if same-family)** requires all of these:
   - at least one gold label;
   - `committed_seq` smaller than every verdict's `created_seq`;
   - a recorded blind protocol.

   If any check fails, the tier drops and the reason `gold-not-precommitted` is recorded. When n_gold < 5 the chip says "anecdotal".
3. **CALIBRATED-TRANSFER**: Rogan–Gladen did not abstain (W4); capped at Spot-check.
4. **MODEL-ESTIMATED**: uses the B2 interval.
5. **ABSTAINED**: anything else, including another `family` with no gold.

**Disagreement.** It is checked across {KEYED, PPI, classical, MODEL-ESTIMATED, B0 (same family)}. Non-overlap adds "estimators disagree: treat as unverified" and forces "Do not rely". B1 is shown as "agent's claim" and is excluded from the check.

**Gate:**
- **Rely**: KEYED or GOLD-ANCHORED, the lower bound of `verified_precision` (or `precision`) ≥ `rely_lo`, no disagreement, abstention ≤ 0.3, and the placebo false-alarm upper bound ≤ 0.10 where measured. The gate never uses the upper-bound alternative.
- **Spot-check**: hi ≥ the threshold.
- **Do not rely**: otherwise.

**Scorers** are pure: `score_x(run: SealedRun, card, *, version) -> Panel`.

| Panel | Tier | Numbers |
|---|---|---|
| 1 | MEASURED, n = denominator | `grounding_rate`; `evidence_sufficiency` (containment plus effective GSD); `tool_validity`; `error_recovery`; `coarse_to_fine` (flag); `redundancy`; `max_loop`; `abstention_appropriateness`; `guessed_under_obscuration`; `forbidden_attempts`; `budget_adherence`; `aoi_inspected_fraction` (U10) |
| 2 | MEASURED | `must_notice_coverage`; `plan_action_jaccard` |
| 3 | KEYED, or `no_grade_reason` | precision; recall; F1; status accuracy; `cannot_assess_correct`; coverage loss; ECE (U8). Cluster bootstrap over 300 m blocks or scenes. |
| 5 | MEASURED, `replayed` when replayed | USD per role; tokens (cache and image); calls; windows; `bytes_read`; recorded model latency p50/p95; `cost_per_correct` (only when Panel 3 is KEYED); verifier cost as "price of trust" |

Under `LogicalClock`, tool latency is "not measured in replay". A blend test asserts that no Panel 5 value appears in Panels 1–4. Re-scoring appends a new versioned record and never overwrites one.

**Summary.**
- `facts.build(scorecard, passports) -> [{slot, display_str, typed_number, span_ids}]`.
- `TemplateSummarizer` is deterministic and is the default.
- `phrase.py` (W14) has the model fill `{{slot}}` placeholders and cite `[span:…]`.
- `lint` rejects any regex number (`-?\d+(?:[.,]\d+)?%?`) that is not a fact `display_str`, with dates and ids whitelisted. It also rejects a sentence without a valid span, and "verified" or "accurate" next to a non-KEYED number.
- If lint fails, the template text is used and the failure is stored. The text is labelled "narrative, not scored".

**Report.** `html.render(bundle)` writes one file: inline CSS, no JS, everything passed through `html.escape`.
- First viewport: a verdict line, the summary and the passport.
- Then the five chipped panels and the claim table (worker | verifier | key | ledger).
- Then the trace timeline, the licence floor, the NC notice and "what would change this interval".
- A synthetic banner, driven by `manifest.synthetic_data`, plus a SYNTHETIC chip on each synthetic row.
- Never any image bytes.

**Service and CLI.** `service.py` holds the functions and the typer CLI wraps them.
- Tonight: `validate_task`, `schema`, `run`, `check`, `score`, `trust`, `report`, `verify`, `replay --rescore`, `demo`, `probe_import`, `budget_status`/`budget_plan`, `prices_check`.
- Wednesday: `label_export`/`label_import`, `prereg_commit`, `compare`, `store_push`, `smoke_vision`, `cassette_export`, `trace_reconcile`, `mcp_serve`.

**MCP server (W7).** A read-only server over the bundles. Its tools are exactly `list_runs`, `get_scorecard`, `get_trust_passport`, `explain_trust`, `get_plain_summary`, `get_claim`, `compare_configs` and `get_trace_span`, plus the resource `treehouse://runs/{id}/report`. Every number is returned as a TypedNumber.

**API.** FastAPI, in W12.

## 4. Storage layout

```
$TREEHOUSE_STORE (default ./.treehouse; demo: out/demo/store)/
  ledger.jsonl                         chained {seq, prev, kind, ref, run_id}; seq orders gold draw vs verdicts
  blobs/sha256/ab/<hex> + .meta.json   {license, media_type}
  runs/<run_id>/ task.yaml config.json manifest.json SEALED trials/<tid>.{trace,claims}.jsonl trials/<tid>.understanding.json
                 cassette/{model,tool}.jsonl                         (pixel-free: images are {sha256, bytes, redacted})
  evals/<run_id>/<kind>/<record_hash>.json   kind ∈ rules|key|leak|sample|gold_draw|verifier|gold|score|trust|summary
  evals/index.jsonl                    chained; names run manifest hash + input versions; refused for unsealed runs
  bundles/<run_id>/{bundle.json,report.html}
out/demo/index.html;  ~/.cache/treehouse/pixels/ (0600, never committed);  ~/.treehouse/spend.jsonl (Kiro: $REPO/.spend/spend.jsonl, committed after each K step);  keys/ (gateway-denied)
```

## 5. Synthetic demo world and Nepal example

### 5.1 `synth-crossings-v1`

Generated with seed 20261104. It is labelled SYNTHETIC everywhere.
- **AOI**: [0, 0, 0.0108, 0.0108] in EPSG:4326. That is about 1.2 km square at "Null Island", at roughly 0.5 m per pixel (2400² px).
- **River**: 30 m wide. Its centreline is y = 0.0054 + 0.0018·sin(3πx/0.0108).
- **40 crossings**: 24 `road_bridge` (deck 6×15 m) and 16 `footbridge` (deck 2×15 m), at least 20 m apart. After the event, 30 are intact, 6 damaged (middle third removed) and 4 destroyed.
- **15 distractors**: bright rooftops.

Scenes are rendered lazily in numpy and cached per process.

| Scene | Date | Cloud | Footprint | Role |
|---|---|---|---|---|
| SYN-PRE-1, SYN-PRE-2 | 07-01, 07-15 | 0 % | full | pre evidence; placebo pair |
| SYN-POST-A | 08-30 | 3 % | AOI minus the western 15 % strip | main post scene |
| SYN-POST-B | 08-28 | 70 % (mask polygons) | eastern 20 % missing | cloud trap; `no_coverage` |
| SYN-POST-C | 08-30 | 3 % | as A, shifted 3 px, new noise | test-retest twin |

The event date is 2026-08-26. The 4 crossings in the western strip are cloud-covered in POST-B, so they are `visible_in` no clear post scene. For them, `cannot_assess` is the KEYED correct answer.

**Key** (`keys/synth/synth-crossings-v1.key.json`): `{id, point, line, cls, status_post, visible_in{scene: bool}}` per crossing, plus 3 canary decoys at empty coordinates and a `version_hash`.

**Embeddings**: 64 m cells (19×19), D=64. River cells sit near a prototype vector. The coverage report says it is synthetic and that `cell_m` is 64 (real LGND uses 1280).

**Policies** (`synth/policies.py`) are FakeProvider callables. They read the key only while fixtures are recorded.

| Policy | Behaviour |
|---|---|
| good | understanding (mentions cloud and resolution) → stac → clay → 60 m / 128 px windows (effective 0.47 m) on POST-A. Makes 36 status claims (35 correct), 1 distractor false positive and 4 `cannot_assess`. |
| overconfident | like good, but guesses the 4 hidden crossings at confidence 0.95 and claims 3 distractors |
| skimmer | 1000 m / 256 px windows (effective 3.9 m), so R5 fails |
| fabricator | 10 claims cite unfetched ids, 10 cite windows that only overlap, 16 are fine |
| key-peeker | calls `key_lookup` and a `keys/` href (2 blocked spans), then claims all 40 crossings plus 1 canary, 20 of them without imagery |
| looper | 6 identical `stac_search` calls, bad args, a nonexistent tool, then gives up with 5 claims |
| budget-stop | good, under `Budget(tool_calls=12)`, so it ends with `stop="budget"` |

The corruption series (used by test I4) flips 0, 10, 20 and 40 % of good's correct claims.

**Recorded verifier for good (run as if unkeyed)**: a seeded oracle against the key, with sensitivity 0.85 and specificity 0.80. It abstains 10 % of the time overall and 30 % in the cloud stratum. Controls: 6 keyed positives, 6 keyed negatives, 10 placebo pairs (PRE-1/PRE-2) and 10 retest pairs (POST-A/POST-C).

**Synthetic gold**: 24 labels taken from the key with 3 % flips, `labeller_kind=synthetic`, seeded from `fixtures/demo/prereg/gold-seed.txt`.

**Required display strings** (ADV D3; asserted by I5):
- gold: "SYNTHETIC GOLD, not human labels";
- verdicts: "recorded fake verifier";
- Nepal rows: "illustrative, not surveyed bridges";
- banner: "SYNTHETIC DEMO DATA".

### 5.2 Nepal (`nepal-bhote-koshi-bridges`, family `river-crossings-vhr`)

**STAC fixture.** `scripts/build_vantor_fixture.py` runs once tonight with network access, outside pytest. It writes 33 real items plus `event.json`, `collection.json`, `etags.json` and `LICENSE-DATA` (CC-BY-NC-4.0). Metadata only.

**Card.**
- AOI: the RS parallelogram (85.330, 28.150), (85.375, 28.150), (85.400, 28.290), (85.345, 28.290). **UNVERIFIED**; to be confirmed at K2b.
- `smoke_aoi`: [85.33, 28.14, 85.37, 28.18].
- `as_of`: 2026-09-18T23:59Z.
- Steps: `inventory` is partly keyed against OSM (`pending_fetch`); `damage` is unkeyed, with a gold plan of 24.
- Forbidden sources: `overpass-api.de`, `*.openstreetmap.org`, `keys/`, OSM tools.
- Controls: retest pair E5610/E5810. Placebo is "unavailable: 2 pre scenes, ~63 % of the AOI covered by both (fixture footprints; RS measured ~51 %), 3–5-year gap".

**Demo inputs.**
- **Points.** 30 synthetic candidate points along `fixtures/demo/nepal/corridor.geojson`, each inside both the AOI and E5610's footprint. Every row and CSV line carries `synthetic: true` and the text "illustrative, not surveyed bridges".
- **`nepal-good` cassette.** Picks E5610 and avoids the 16 cloud-trap scenes. Its `RecordedImagerySource` WindowResults use real scene ids and `pan_gsd`, computed bboxes and effective GSD, and a modelled `bytes_read`. `pixel_sha256` is the sha256 of a deterministic synthetic array keyed by `result_id` (same array-hash rule as OBS-B2). Every WindowResult has `synthetic: true` and shows a SYNTHETIC chip on its row in the claim and evidence table. It makes 22 status claims and 8 `cannot_assess`, the latter where recorded obscuration exceeds 0.3.
- **`nepal-guesser` cassette.** Makes status claims on those 8 obscured windows.
- **Verdicts.** Recorded from a fake verifier against `keys/synth/nepal-demo-truth.json`: sensitivity 0.85, specificity 0.80, 15 % abstention, plus 10 recorded retest pairs.
- **Gold.** Synthetic, n=24.

**Passports.** Two are produced: one without gold (MODEL-ESTIMATED, wide B2) and one with gold (GOLD-ANCHORED, shown with the gold-only interval and the width ratio).

### 5.3 `treehouse demo` (offline, no rasterio, no AWS; target under 60 s)

1. **Fresh store** at `out/demo/store`.
2. **Replay every run in `fixtures/demo/runs.yaml`** (7 synth runs and 2 Nepal runs) with `mode=replay`, `clock=logical` and `tool_mode=verify`. Each run goes PlainLoop with ReplayProvider → ToolGateway → live in-process MCP servers → TrialTracer, and is then sealed.
3. **Assert** that the trace heads match `fixtures/golden/heads.json`.
4. **Check**: rules, keyed match, leaks and ledgers.
5. **Verify and label** synth/good and both Nepal runs:
   - sample the design;
   - draw gold, with `committed_ref` set to the sha of the gold-seed file;
   - run RecordedVerifier, which refuses if a verdict's seq precedes the draw;
   - load the gold labels.
6. **Score** every run.
7. **Trust.** synth/good gets a hidden-key PPI plus a KEYED truth reveal. Nepal gets both passports.
8. **Write** the summary and report for each run, then `out/demo/index.html`.
9. **Verify the store**; it must exit 0.

`scripts/make_demo_fixtures.py` rebuilds every cassette, verdict and gold file. A test checks that a rebuild is byte-identical.

## 6. Test strategy

**Offline guard** (P0 plus P0b). An autouse fixture does the following:
- blocks non-loopback `connect`, `connect_ex` and `getaddrinfo`;
- clears `AWS_*`, then sets `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` to `testing`, `AWS_DEFAULT_REGION=us-east-1`, `AWS_CONFIG_FILE` and `AWS_SHARED_CREDENTIALS_FILE` to `/dev/null`, and `AWS_EC2_METADATA_DISABLED=true`;
- points `TREEHOUSE_STORE` and `TREEHOUSE_SPEND_LEDGER` at tmp paths.

Canary: an unstubbed `boto3.client("s3").list_buckets()` must raise, and the guard must record the attempt.

Markers:
- `live`: skipped unless `TREEHOUSE_LIVE=1`.
- `allow_loopback`.
- `slow`: deselected by default.
- `method`: a session timer fails the suite if it runs longer than 8 s.

A licence scan rejects any PNG, JPEG or TIFF magic bytes, or base64 image data, in `fixtures/`, `tasks/` and `docs/`.

**Unit and property tests** (hypothesis, under 20 s):
- canon stability;
- chain tamper detection (flip, delete, reorder, truncate) reports the exact seq;
- `key()` ignores image bytes;
- the validator table and the MEASURED fence;
- ledger resolution order;
- geometry against shapely (`importorskip`);
- matching is permutation-invariant and equals brute force for n ≤ 7;
- the spend ledger never passes $450, and replay costs $0;
- import boundary;
- non-null `structured_content`.

**Golden tests**: demo trace heads, scorecard JSON, passport hash, JSON Schema exports, `replay --rescore` equality, and a frozen-trace semconv test.

**Method tests** (`tests/method/`) cover the A13 methods built tonight. All are array-level. Seeds come from `seeds.py`: BASE = 20261104, PCG64, with numpy pinned by `uv.lock`. Unless stated, R=300 populations and B=400 bootstrap replicates.

| ID | A13 | Test | Seed | Pass | Time |
|---|---|---|---|---|---|
| M1 | U1, V4 | PPI coverage in the 6 `ppi2.py` scenarios: moderate .85/.70, shuffled, strong .95/.90, perfect, high-precision, two-phase N=300 n=60. g=20; abstention .05/.10/.35 | +10…15 | coverage ≥ 0.86 each; no upper bound | ≤ 2.0 s |
| M2 | U1 mutation | `pseudo_weight=0`, strong and perfect scenarios | +12, 13 | coverage < 0.80 | ≤ 0.7 s |
| M3 | U1 | narrowing in the strong scenario (reuses M1) | — | mean width ≤ 0.85 × the hypergeom-exact width | 0 |
| M4 | U1 null | shuffled verdicts (reuses M1) | +11 | coverage ≥ 0.86 and mean width ≥ 0.95 × classical | 0 |
| M5 | U1, V4 | abstention as a third category: in stratum 3, P(abstain) = 0.6 when y=0 and 0.1 when y=1. Plus a mutation that draws gold only from non-abstained units | +16 | coverage ≥ 0.86; mutation \|bias\| > 0.04 | ≤ 0.6 s |
| M6 | core | exact coverage: hypergeom N=60, n=20, all K; Clopper-Pearson n ∈ {5, 10, 20, 40} over a p grid in 0.01 steps; Wilson n=20 | — | hypergeom ≥ 0.90; CP ≥ 0.95; Wilson mean in [0.93, 0.97] and min ≥ 0.83 | ≤ 0.5 s |
| M7 | V3 | N_h = (30, 20, 10), n_h = (10, 10, 5), 5000 draws. Mutation: uniform π, with y correlated with the stratum | +20 | every inclusion frequency within 4 SE of π; Σπ = n; HT \|bias\| ≤ 3 SE; same seed gives the same `design_id`, a different seed gives a different one; mutation bias > 4 SE | ≤ 1.0 s |
| M8 | U1 validity | planted errors: 60 keyed items, flip k ∈ {0, 6, 12, 18, 24}, Se .85 / Sp .80, gold = key on a random 20, 50 reps | +30 | means strictly decreasing; \|mean − truth\| ≤ 0.05 | ≤ 0.5 s |
| M9 | V5 | placebo: 40 pairs, q ∈ {0, 0.1, 0.3}, plus an always-"damaged" stub | +40 | CP 90 % covers q in ≥ 0.88 of reps; the stub yields `verifier-fails-placebo` and never Rely | ≤ 0.3 s |
| M10 | V5 | test-retest at agreement 0.8 | +41 | n=200: \|κ̂ − κ\| ≤ 0.1; n=5: flagged anecdotal | ≤ 0.3 s |
| M11 | determinism | same inputs → passport bytes; seeds +42 vs +43 at B=2000 | +42, 43 | identical bytes; endpoints differ by < 0.02 | ≤ 1.0 s |
| M12 | Panel 3 | 12 clusters × 8 items, ICC 0.3, R=200 | +50 | cluster CI coverage ≥ 0.85 at 95 %; naive iid < 0.85 | ≤ 1.5 s |
| M13 | U4, U3 | B1 vs a 20 000-draw Monte Carlo; B2 with no data, n_new=40; B0 from 30 runs of BB(16, 4, n=40); B0 from a single run | +60, 61 | B1 within ±1 count; B2 width ≥ 0.4; B0 μ within 0.03 and κ within ×2; single run uses the `kappa0` path | ≤ 0.5 s |
| M14 | tiers | about 15 EvidenceBundle rows, including late gold and adjudication-queue gold | — | exact tier, rung and reasons; `gold-not-precommitted`; adjudication gold refused; non-overlap gives "estimators disagree" and Do not rely | ≤ 0.2 s |
| M15 | U8 | ECE with n=2000: calibrated confidences, then confidence .95 at accuracy .60 | +70 | ≤ 0.03; ≥ 0.3 | ≤ 0.1 s |
| M16 | V3, V4 | gold drawn from all units: 15 % abstention, 50 seeds | +80 | some draw contains an abstained unit; `draw_gold` has no verdict parameter | ≤ 0.1 s |
| M17 | V2 | blindness (hypothesis, 200 examples) | — | changing only label, confidence or reason leaves the BlindItem bytes identical; claims and controls have the same keys; no worker id, label or confidence string appears in verifier input | ≤ 1.0 s |

**Pipeline tests** (`tests/integration/`, on the demo fixture):

| ID | Covers | Pass |
|---|---|---|
| I1 | V1 | Every planted violation is detected: fabricator gives 10 fabrication and 10 ungrounded; skimmer fails R5 on all status claims; key-peeker gives 2 `key_access_attempt`, 20 `probable_leak` and `INVALID_FOR_ACCURACY`; `as_of` is refused. **Mutation**: replacing R4 with `bbox_intersects` lets the overlap claims pass, and the test asserts the difference. |
| I2 | U9 | good: `cannot_assess_correct` is 4/4 and appropriateness 1.0. overconfident: `guessed_under_obscuration` is 4. nepal-good scores above nepal-guesser. |
| I3 | U10 | good evidence sufficiency ≥ 0.95; skimmer = 0; `bytes_read` equals the overview-block-model sum. Order checks, on block counts with the scene header excluded, for any window centre fully inside the scene (replaced by real numbers in W1): blocks(skimmer 1000 m/256 px) ≤ 4 × blocks(good 60 m/128 px); blocks(1000 m/2048 px) ≥ 4 × blocks(1000 m/256 px); at the scene centre the exact counts are 1, 4 and 25 |
| I4 | U1 | The corruption series through `build_passport` gives a strictly decreasing headline, and the KEYED value moves by exactly the flipped fraction. |
| I5 | D3 | Every TypedNumber in the demo bundles has `synthetic=True`. Every Nepal claim row and every Nepal WindowResult evidence row carries a SYNTHETIC chip. |
| I6 | chips | Every digit-bearing text node (ids and dates aside) has an ancestor with `data-tier`. |
| I7 | lint | A planted number, a missing citation or a bad span id is rejected; a correct paraphrase passes. |

**Wednesday tests, specified now:**
- U2 Rogan–Gladen (W4): prevalence .7, Se .85, Sp .80, 15+15 controls. No-shift coverage ≥ 0.86. Coverage at τ=0.5 ≥ coverage at τ=0. J ≈ 0.15 abstains ≥ 90 % of the time. `damage_state` raises.
- U5 and U3 (W11): with shuffled features, width ≥ B2.
- Unreported frame (W10).
- Permutation and Holm (W8): n=5 with all differences positive gives p = 0.0625.
- `-m slow`: the 200-seed `study.py`.
- Not built: V7–V10 (V10 hooks only), U6, U7.

**Journeys** (`tests/journeys/`):

| J | When | Assertion |
|---|---|---|
| J1 | offline twin: P5, P7; live: K3 | manifest holds every config field; at least one MCP call; complete spans; summary order; report contents |
| J2 | P5 | no Bedrock call while sockets are blocked; deterministic scores match exactly |
| J3 | model and evaluator: P7; tracer: W9; harness: W2 | swaps are config only; re-score appends a new record |
| J4 | P4, P7 | tool error, unknown tool, malformed args and the looper are logged and summarised; wrong output scores lower |
| J5, J6.1, J6.3 | W8 | compare report, paired CI, "inconclusive at N=k" |
| J6.2 | P7 | good and fabricator KEYED CIs separate |
| J7 | P4, P5 | budget-stop names the limit it hit; with the guard off the run completes |
| J8 | P5 | clean-clone CI: `uv sync --frozen && uv run treehouse demo` |
| J9 | P1 (schema lists model, harness, tracer, evaluator, tools, task, trials, budget); W12 (API) | |
| J10 | W7 | exactly 8 read-only tools, numbers typed |
| J11 | P7 | `must_notice` coverage: good > looper |
| J12 | P8 | a rule-failed claim is Do not rely whatever the verifier says; `process_facts` appear beside the interval |
| J13 | P8 | M1–M17 pass; "not computable: 1 keyed regime" |
| J14 | P7 | Panel 5 is typed; blend test |
| J15 | P5, P7 | cloud-trap reward; India card validates; no lat/lon literals or place names in `src/` |

## 7. Ordered package plan

Working rules:
- One branch and one PR per package, against the fork's `main`. Write tests first and merge when CI is green.
- Each PR gets one doubter→judge pass, run concurrently on a stacked branch.
- H0 is the build start, which follows the vote. The spec-sheet step is deferred until after P6.

| P | Branch | Contents | Acceptance (tests first) | h | Deps |
|---|---|---|---|---|---|
| P0 | `pkg/p0-scaffold` | merged | — | — | — |
| P0b | `pkg/p0b-guard` | mcp moved to core; hypothesis; guard additions; `clock`, `ids`, `paths`; boundary test; licence scan; CI runs `treehouse --help` | boto3 canary; getaddrinfo blocked; determinism of LogicalClock and IdSource; a planted violation fails | 0.25 | P0 |
| P1 | `pkg/p1-schemas` | §2 schemas; `schema`; 4 cards; `task validate`; prereg trust-config equals the defaults | round-trip, frozen and forbid; validator table; fence; no-bare-float walker; cards validate (India unchanged); bad cards rejected with field paths; stable hashes; J9 partial | 0.8 | P0b |
| P2 | `pkg/p2-trace-store` | chain, TrialTracer, LocalStore, ledger, seal, manifest, local `resolve_backends`, `verify` | tamper property tests; `put_once` twice raises; eval on an unsealed run refused; manifest written last; isolation statement; `verify` exits 1 with path and seq | 0.6 | P1 |
| P3 | `pkg/p3-providers-loop` | model_io; Fake, Recording and Replay providers; PlainLoop; BudgetGuard | `key()` is identical with or without image bytes; a live-recorded request key equals its pixel-free replay key (OBS-B1); a live provider raises `MissingPixels` on a byte-less Image; ScriptDivergence; CassetteMiss with index; trial-scoped keys; 3 stop paths; no claims API | 0.6 | P2 |
| P4 | `pkg/p4-gateway-tools` | `geo/geom`; gateway, policy, meter, PixelCache, tool cassette; 5 MCP servers; synthetic and recorded sources; `png`; `synth/world`, `render`; Vantor fixture (script); Clay npz | `structured_content` non-null; `is_error` on bad args; every forbidden kind blocked with a span; `as_of`; `not_allowlisted`; `r-0001`; grounded and contaminated; GSD triple; error codes; golden Nepal scene list; Clay recall ≥ 0.9 and coverage report; re-encoding the same array at another zlib level leaves `pixel_sha256`, `key()` and the trace head unchanged (OBS-B2); overview-block-model bytes (RS-B1); J4.1 | 1.2 | P3 |
| P5 | `pkg/p5-demo-skeleton` | policies, `synth/nepal`, `make_demo_fixtures.py` plus fixtures, `runner`, `run --mode`, `demo` (R1/R2/R4, Panel 5, generic chip renderer, trust stub reporting ABSTAINED "trust engine not yet built"), index, README quickstart, clean-clone CI job | J2, J8; demo under the guard in under 60 s; golden heads; byte-identical regeneration; I5, I6; licence scan | 0.7 | P4 |
| P6 | `pkg/p6-aws-a` | BedrockConverseProvider, registry, prices (null plus fixture), SpendLedger, `aws_probe.py` (Stubber), `probe import`, `budget`, `prices check`, `@live` twins. `aws_probe.py` makes every Bedrock call through `SpendLedger.reserve(..., unpriced_cap_usd=0.25)`, with `max_tokens ≤ 32`. The probe stops at a $3 total cap and reports the remaining Bedrock checks as `skipped_budget`. Each reservation is committed with actual `usage` at a conservative placeholder price from `config/prices/probe-ceiling.yaml`, tagged `estimated: true`. | §3 Stubber list; ledger property test; unpriced refused; probe Bedrock calls are reserved in the ledger and the $3 cap is enforced (Stubber: no Converse call without a reservation); probe output matches the `treehouse.aws-capabilities/v1` golden schema; classifies ok, denied, unavailable or error and never aborts | 1.0 | P3 |
| P7 | `pkg/p7-checks-panels` | R1–R9, keyed match, leak and canary, ledgers, `stats` intervals and cluster bootstrap, Panels 1/2/3/5, scorecard, re-score append | M6, M12, M15; I1–I3; J3.4, J4.2–3, J6.2, J11, J14, J15 | 1.1 | P5 |
| P8 | `pkg/p8-trust-core` | `sampling/`, RecordedVerifier, gold draw, PPI and classical, B0/B1/B2, controls, tiers, disagreement, gate, passport, adjudication file; demo wired up | M1–M5, M7–M11, M13, M14, M16, M17; I4; J12, J13; golden passport hash; estimand named `verified_precision` when any gold label is `cannot_assess` and `precision` when there is none; upper bound ≥ headline and excluded from disagreement; `narrowing_note` set when ratio ≥ 1; `hypergeom_exact` raises unless every stratum is a census | 1.8 | P7 |
| P9 | `pkg/p9-report-summary` | facts, template summarizer, lint, first-viewport layout, legend, "what would change this interval" | I7; J1.3, J1.5 | 0.6 | P8 |

The overnight path P0b–P8 takes about 8.05 h. P9 becomes W0.

**Checkpoints:**
- **C1 (H4.5): P5 must be merged.** If it is not, stop widening and do P5, then P6, then the P8 core (keep only R4 and keyed precision from P7).
- **C2 (07:15 EST): if P6 is not merged, pre-empt the current package.** P6 must be merged by 08:00 EST.
- **C3 (08:00): push everything** (WIP included) and update TODO.md and the overnight report. The 08:00 TODO.md states which of P7–P8 are merged. The README quickstart describes only what the merged demo shows, for example "trust passport: stub" until P8 lands.

**Cut order**, first to go first:
1. P9.
2. R9, `plan_action_jaccard` and `aoi_inspected_fraction`.
3. The B0 MLE path (the "not computable" row stays), relabel kappa and the adjudication file.
4. Placebo and retest controls (they are then listed under `unavailable`).
5. `probe import`.

**Never cut:**
- P0b–P6.
- From P8: PPI and classical, gold drawn from all units, the tier ladder, abstain and disagree rules, the gate, the passport, and M1, M2, M4, M5.
- The chip invariant, re-run semantics and synthetic labelling.

**Wednesday queue** (the agent works it in parallel with Kiro):

| W | Contents | h | Needed by |
|---|---|---|---|
| W0 | P9 | 0.6 | |
| W1 | `CogSource`: counting opener, 16 KB block cache, `If-Match`; synthetic DEFLATE COG and loopback Range-server tests (≤ 10 requests per 256 px window); calibration test: the real reader's bytes for the three I3 windows on the synthetic COG keep the block model's order; `smoke vision` | 1.5 | K2b, K4 |
| W2 | StrandsHarness, `TreehouseStrandsModel`, AgentVerifier; contract test | 1.0 | K4 |
| W3 | Blind label export and import (CSV or static page), `prereg commit` | 0.5 | K4, human block |
| W3b | `cassette export --pixel-free`; `scripts/fetch_uspvdb.py`, `scripts/fetch_osm_bridges.py` (snapshot pinned, hashes written) | 0.5 | K5, K6 |
| W4 | Rogan–Gladen and DerSimonian–Laird τ | 1.0 | |
| W5 | S3Store (moto), `store push`, read-back resolvers | 0.75 | K8 |
| W6 | CDK `infra/` with Template tests | 1.0 | K7 |
| W7 | MCP server | 1.0 | |
| W8 | `compare`: permutation, Holm, paired bootstrap | 0.75 | |
| W9 | cwlogs/OTLP mirror and reconcile | 0.75 | K9 |
| W10 | Unreported frame and miss rate | 0.75 | |
| W11 | U5, U3 | 1.0 | |
| W12 | FastAPI | 0.5 | |
| W13 | `estimators.lock`, `study.py`, detector policies | 1.0 | K4 |
| W14 | `phrase.py` | | |
| W15 | README, FUTURE-WORK, ADR | | |

## 8. Kiro prompts

The full text goes in TODO.md later. Every prompt opens with the same preamble:
- `git pull`;
- `uv sync --extra aws --extra strands --extra geo`;
- no pixels or credentials in commits;
- `export TREEHOUSE_SPEND_LEDGER=$REPO/.spend/spend.jsonl` (no secrets in it); commit and push it after every K step, so a Kiro session reset cannot zero the guard;
- run `treehouse budget status`, and stop if spend is above $350.

| K | Title | Needs from the code |
|---|---|---|
| K1 | Capability probe, `aws-capabilities.json` | `aws_probe.py`, `probe import`, registry (P6) |
| K2a | Fill the price table | `prices check` (P6) |
| K3 | Live keyed run: synth-crossings, plain loop, Bedrock, K=3, `--mode record`; p90 cost; `budget plan` | P5–P7 |
| K2b | Vision smoke test on real 0.5 m Vantor windows; choose the worker and verifier; confirm the Nepal AOI | `smoke vision` (W1) |
| K4 | Commit the gold seed, then a live Nepal run with the cross-family blind verifier. If W2 is not merged, run with `--harness plain_loop`. The manifest, report and demo script then say "Strands adapter: offline-tested only" and claim no Strands run. | W1, W3, W13 (W2 optional) |
| K5 | Export pixel-free cassettes and run a replay check | `cassette export` (W3b) |
| K6 | Fetch keys: USPVDB on the Mac, OSM through Overpass; commit with hashes | `scripts/fetch_*.py` (W3b) |
| K7 | CDK deploy and `probe verify-infra` | W6 |
| K8 | `store push` to versioned S3; CLI version-delete denial | W5 |
| K9 | Tracer reconcile | W9 |
| H | 60–90 min of blind human labelling, then re-run `trust` | W3 |

## 9. Risks

1. **Hour estimates are optimistic.** AWS expects 9–10 h. C1 and C2, the cut order and the fixed P6 deadline contain this.
2. **Review passes cost about 1.5 h in total.** One pass per PR, run concurrently.
3. **The spec-sheet step eats night hours.** Run it after P6 or in parallel.
4. **The agent may simplify the estimator.** Mutations M2 and M5, the oracle, and `estimators.lock` before K4 guard against this.
5. **numpy drift breaks golden hashes.** `uv.lock` pins numpy, and each design records its rng and algorithm.
6. **mcp 2.3 or Strands APIs churn.** Mitigated by pins, contract tests, one wrapper module, and the image side channel.
7. **Synthetic numbers get quoted as real.** The required `synthetic` field, row chips and the banner guard against this.
8. **The Nepal AOI corners come from memory.** The fixture builder checks footprint intersection, plus a K2b visual check.
9. **No model may see footbridges at 0.5 m.** That is then a finding (`cannot_assess` dominates).
10. **JPEG pixel hashes depend on the environment.** They are compared only within one environment; synthetic hashes are stable everywhere.
11. **The Workshop role is not the worker role.** The manifest says "local convention" unless the canary is denied.
12. **The demo depends on an editable install** (`fixtures/` at the repo root). uv installs editable by default, and `paths.py` errors clearly otherwise.

## 10. Decisions for Suhas to confirm

1. **[DEV] MEASURED is a sixth tier** for exact trace numbers: Panels 1, 2 and 5, and the controls kappa.
2. **[DEV] The plain loop is the Must-0 demo engine.** Strands comes on Wednesday through our provider.
3. **[DEV] The shuffled-label test is referenced to the gold-only interval**, not B2.
4. **A human `cannot_assess`** counts as "not verified" (lower bound) for `verified_precision`. A y=1 upper bound and the count are reported beside it.
5. **Demo data:** a Null-Island synthetic world, plus Nepal synthetic points on a real corridor with synthetic gold. Your labels replace that gold.
6. **Morning order:** K1, prices, K3 (live synthetic, about $15), then the vision smoke test after W1 (about 09:45).
7. **Default models:** Claude Sonnet 5.5 as worker, Nova Pro as verifier. Both UNVERIFIED; the smoke test decides.
8. **Nepal AOI corners** need your visual check.
9. **Virginia ships as `pending_fetch`.** USPVDB is fetched on your Mac.
10. **Images travel through an in-process side channel**, not MCP ImageContent.
11. **Spend thresholds** are $250, $350 and $450. Live calls are refused while prices are null.
12. **The spec-sheet update is deferred** until after P6.


---

## Fact-check of r3 (normative corrections)

A fact-checker tested 35 library and API claims, mostly by running code against the pinned libraries: mcp 2.3.0, strands-agents 1.63, botocore/boto3 1.43, moto 5.2.5, rasterio 1.5.2, scipy 1.18 and numpy 2.5. Result: 22 verified, 11 corrected, 2 unverifiable. numpy.org and docs.aws.amazon.com were blocked, so those facts come from search results. **Where this section differs from the text above, this section wins.**

| # | Where | Correction |
|---|---|---|
| F1 | §0 row 13, §3 retries | **`retries={"max_attempts":1}` makes 2 HTTP attempts**, one of them a hidden botocore retry. This was counted against a local server that always returns 429, in both legacy and standard modes. Use `{"total_max_attempts":1,"mode":"standard"}` (now applied in the text above). Stubber skips botocore's retry layer, so also add a loopback-server test that counts attempts. |
| F2 | §3 retryable errors | Retry `ThrottlingException`, `ServiceUnavailableException`, `ModelNotReadyException`, `ModelTimeoutException` and `InternalServerException`. **Never** retry `ServiceQuotaExceededException`. |
| F3 | §2 `ModelResponse.stop_reason` | Also map `malformed_model_output`, `malformed_tool_use`, `model_context_window_exceeded`, `guardrail_intervened` and `content_filtered`. Stubber accepts invented values, so the mapping test loops over the stopReason enum in botocore's service model. |
| F4 | §3 Stubber tests | Stubber checks the shape of a request, not its allowed values. The adapter itself must reject image formats other than png, jpeg, gif and webp. |
| F5 | §0 row 21 | mcp fills structured content for typed returns such as `-> dict[str,int]`; only a bare `-> dict` gives None. The rule that every tool returns a Pydantic model still stands. A tool that raises comes back as `is_error` with its message hidden, so tools return typed `ToolError`s instead of raising. |
| F6 | §3 keyed match | `linear_sum_assignment` always fills as many pairs as possible, so it also returns infeasible pairs. **Drop pairs with cost ≥ 1e9 after solving.** |
| F7 | §0 row 6, §3 imagery, W1 | The overview levels a scene can have depend on its size: the 2400 px synthetic scene has only 2 and 4. The block model caps L at the overviews that scene would have. If the W1 test COG needs overviews 8 and 16, it must be at least 8192 px. |
| F8 | §2 SampleDesign, §9 risk 5 | numpy does not guarantee `Generator.choice` or `permutation` streams across versions. Pin numpy in `uv.lock` and record `numpy.__version__` in every SampleDesign. Build `strat-srswor-v1` on `bit_generator.random_raw()`, selecting by sorted keys, not on `choice`. |
| F9 | W5 | moto does not return `ChecksumSHA256` on Get or HeadObject. Read-back tests compare against the PutObject response or a locally computed hash. Object Lock default retention must be set while the bucket is still empty. A delete without `VersionId` only writes a delete marker, so the K8 denial test must pass `VersionId`. |
| F10 | §3 span attributes | `gen_ai.input.messages_ref` is not an OTel attribute; use `treehouse.input.messages_ref` instead. For Bedrock, `gen_ai.provider.name` is `"aws.bedrock"`. |
| F11 | §3 `hypergeom_exact` | Use unambiguous argument names (`successes_in_sample`, `sample_size`, `population_size`). The draft's `n` and `N` have the opposite meanings in scipy. |
| U1 | `config/models.yaml` | **UNVERIFIED:** whether Sonnet 5.5 accepts an image inside a tool result; botocore's docs list only Nova and Claude 3/4. Ship `claude-sonnet-5-5` with `image_delivery: user_turn` and let the K1 probe decide. The model id, from search results, is `anthropic.claude-sonnet-5-5`, called through a `us.`, `eu.` or `global.` inference profile (the bare id reportedly fails). |
| U2 | `config/models.yaml` | Nova Pro (`amazon.nova-pro-v1:0`, with `us.`, `eu.` and `apac.` profiles but no `global.`) accepts image input through Converse. Source: search results. |

**Verified conditions the build must respect:**
- **Strands:**
  - A custom `Model` implements `get_config`, `update_config`, `stream` and `structured_output`.
  - `strands.tools.executors.SequentialToolExecutor`, `Agent(tool_executor=...)` and `callback_handler=None` all work, and tool order held across a full agent run.
  - Strands OTel has no off switch; its spans stay no-op only while no global tracer provider is set. Set `OTEL_SDK_DISABLED=true` in tests, and give the W9 mirror its own provider.
- **mcp 2.3:** an in-process `Client(server)` works, and a `CallToolResult` carrying an image plus structured content works.
- **moto:** `IfNoneMatch="*"` and a stale `IfMatch` both return 412. A version delete under governance without the bypass returns 403.
- **rasterio:** a custom `opener` must return a file object that works as a context manager.
- **PPI:** §3 matches `proto/ppi2.py`, with two notes:
  - g_eff is computed over the weights *including* the pseudo-units.
  - The pooled-mean fallback for an all-abstained stratum is new in this design.
  - When calling the oracle, pass `pseudo=0.5`; the prototype defaults to 1.0.

The full table, with the commands and URLs used, is kept in `wip/council2/d-factcheck.md`.

---

## Post-adoption factual corrections (2026-11-04)

These edits came from the spec-sheet doubter/judge pass ([reviews/review2-spec-sheet.md](../reviews/review2-spec-sheet.md)). They fix facts and declare one deviation. **The council's decisions are unchanged.**

| Where | Change | Why |
|---|---|---|
| §5.2 `nepal-good` cassette | "13 cloud-trap scenes" → "16" | The pinned STAC fixture has 16 post scenes that intersect the AOI at 71–94 % cloud (2026-08-27 to 09-09; 15 cover at least 60 % of the AOI). The P1 Nepal card pins all 16. "13" came from a bbox count in wip/council2/a-rs.md that could not be reproduced. |
| §5.2 Controls | Placebo reason now says "~63 % of the AOI covered by both (fixture footprints; RS measured ~51 %)" | Re-measured on the fixture footprints. §0 row 24 keeps RS's original figure as a record of what RS measured. |
| §2 `unreported_frame # W10`, §7 W10 | **Deviation from DD1, now declared** (SCOPE D74). Text unchanged | DD1 (Suhas) puts "claimed items + unreported places" in the MVP verifier sample. This design deferred the unreported-places frame to W10 with no [DEV] mark and no §10 entry. Until W10 the verifier samples claimed items and controls only, and the passport says "unreported places not sampled (W10)". Suhas to confirm. |
| Golden Nepal scene list (P4 acceptance) | No text change. Note only: an AOI search returns the **23** intersecting scenes (2 pre, 21 post), not the 33-item catalog | Matches the card's pinned ids. |
