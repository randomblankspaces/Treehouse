# ADV round (a): implementation proposal. Scope hawk, Clay/ADB/judging advocate

**Thesis.** By Wed 08:00 a fresh clone must pass `uv sync && uv run treehouse demo` with no network and no AWS, and it must open `out/demo/index.html`. That page links two run reports, and each report has typed chips, five panels, a Trust Passport and a plain summary. The demo has to **re-run the pipeline from sealed records**. It must not render pre-baked JSON. Otherwise the judges see a mock-up, not proof of "evaluating the agent IS the product". Every package below is one branch and one PR, tests first, merged only when CI is green. If the night goes badly, we cut from the bottom of the list. The demo command, typed numbers, seal-before-check, PPI with abstain, and the offline guard are never cut.

---

## I1. Repo and module layout

```
pyproject.toml (uv, requires-python>=3.12, ruff, pytest; extras: [aws]=boto3, [strands]=strands-agents, [api]=fastapi, [geo]=rasterio)
src/treehouse/
  schemas/      typed.py card.py config.py trace.py claim.py checks.py trust.py scorecard.py manifest.py
  store/        local.py (content-addressed dir + hash chain)  s3.py (stub, Kiro)
  tracing/      jsonl.py (hash-chained, per trial)  otlp.py (optional, in-memory exporter in tests)
  providers/    base.py fake.py replay.py bedrock.py (Stubber-tested) 
  harness/      base.py plain_loop.py strands_adapter.py
  tools/        gateway.py server.py (MCP in-process) stac.py imagery.py clay.py claims.py fixtures.py
  checks/       rules.py keyed.py leak.py
  verify/       sampling.py verifier.py (recorded|agent) gold.py
  trust/        ppi.py baselines.py rogan_gladen.py abstain.py passport.py
  score/        process.py understanding.py output.py cost.py stats.py compare.py
  report/       summary.py (fact table + slot-filled prose + lint) html.py templates/
  mcp_server.py api.py cli.py demo.py
examples/demo/  cards/ fixtures/ cassettes/ verdicts/ gold/   (every file carries synthetic:true)
tests/          unit/ method/ journeys/ golden/
```

There is one service layer, `treehouse.service`. CLI, MCP and API call only that layer, so every number has one code path (A9).

## I2. Core schemas (Pydantic v2, JSON Schema exported and committed)

- **TypedNumber**: `value, type (proportion|count|usd|seconds|bytes|ratio), tier (KEYED|GOLD_ANCHORED|CALIBRATED_TRANSFER|MODEL_ESTIMATED|ABSTAINED), n, interval (lo,hi,level,method), estimator_version, manifest_ref, reason?`. Scorecards and passports **cannot hold a bare float**. A schema test walks every model field and fails on any `float` outside TypedNumber.
- **TaskCard**: the A2 fields, a `synthetic` flag, and per-step `keying`. The hash is sha256 of canonical JSON.
- **RunConfig/EvalSpec**: task refs, worker and verifier `{provider, model, family}`, harness, tracer, tool set, scorer version, trials K, seed, budget `{steps, tokens, usd, seconds, enabled}`, backends. J9 is checked against this schema.
- **Manifest**: config hash, task hash, versions (code SHA, lock hash, scorer, estimator, semconv pin), trial file heads, previous-manifest hash, `key_isolation` ("local convention, not IAM-enforced"), license floor, and `synthetic_data: true`.
- **Span**: OTel-GenAI-shaped `{span_id, parent, kind: invoke_agent|chat|execute_tool|budget|error, name, attrs(treehouse.*), t0,t1, tokens, usd, bytes, error{source: agent|tool|infra|budget, type}, prev_hash, hash}`.
- **Claim**, **CheckLedger** (one append-only entry per layer, with resolution rule), **VerifierVerdict** (`present|absent|cannot_assess`, verifier config, request hash), **GoldLabel** (labeller, `blind_protocol_ref`, `synthetic`), **TrustPassport**, and **Scorecard** with five panels. Each panel is a list of TypedNumbers plus evidence span ids.

## I3. Interfaces and implementations

| Interface | Tonight (offline) | Morning (Kiro) |
|---|---|---|
| `ModelProvider.converse(messages, tools) -> ModelTurn` | `FakeProvider` (a scripted policy per planted trace), `ReplayProvider` (cassette, fails on miss) | `BedrockProvider`, Stubber-tested tonight and live in the morning; OpenAI-compatible is a Could |
| `Harness.run(task, config, tracer, gateway, budget) -> RunResult` | `PlainLoop` (~120 lines; the replay engine) and `StrandsHarness` (driven offline by a `FakeModel(strands.models.Model)`) | Strands on Bedrock |
| `Tracer` | `JsonlChainTracer` | `OtlpTracer` to CloudWatch |
| `ToolGateway.call(name, args, role)` | allow-list, forbidden-source deny with `key_access_attempt` span, `as_of`, metering, budget, error tagging; tools are served by an in-process `MCPServer` and reached through `mcp.client.Client` | same, with live Vantor HTTPS range reads |
| `Store.put/get/seal` | `LocalStore` | `S3Store` (versioned) |
| `Scorer(trace, claims, card) -> Panel` | process, understanding, keyed, cost, all pure functions | — |
| `Verifier.verify(request) -> Verdict` | `RecordedVerifier` (verdict file); `AgentVerifier` interface tested with FakeProvider | Strands verifier, different family, on Bedrock |
| `TrustEngine.passport(...)` | PPI, B0/B1/B2, Rogan-Gladen, abstain | — |
| `Summarizer` | `TemplateSummarizer` (deterministic) plus lint | Bedrock phrasing, linted |

## I4. Storage layout

```
.treehouse/
  blobs/sha256/ab/cd…           tool payloads, crops' hashes (never Vantor pixels in git)
  runs/<run_id>/manifest.json   written last; chains trial heads + prev manifest
  runs/<run_id>/trials/<k>/trace.jsonl   claims.json (sealed before any check)
  evals/<run_id>/<scorer_v>/scorecard.json
  checks/<run_id>/<layer>/<ver>/ledger.jsonl
  verify/<run_id>/<verifier_cfg_hash>/sample.json verdicts.jsonl
  gold/<run_id>/draw.json (seed, inclusion probs) labels.jsonl
  trust/<run_id>/<estimator_v>/passport.json
  reports/<run_id>/report.html bundle.json
keys/   (outside the worker tool root; the gateway denies the path; the manifest says "local convention")
```

Re-scoring only appends records. `treehouse verify <run>` recomputes the chain.

## I5. Surface

- **CLI**: `demo`, `task init|validate`, `run`, `check`, `score`, `trust`, `verify`, `replay`, `report`, `compare`, `schema`, `mcp`.
- **MCP** (read-only, stdio): `list_runs, get_scorecard, get_trust_passport, explain_trust, get_plain_summary, get_claim, compare_configs, get_trace_span`. Every result returns TypedNumbers, so the chip stays attached to the number.
- **API** (minimal FastAPI): `GET /schema/run-config`, `POST /runs`, `GET /runs/{id}/report`.

## I6. Test strategy

- **Offline guarantee.** An autouse conftest fixture patches `socket.socket.connect` and `getaddrinfo` to raise. Tests marked `network` or `aws` are skipped unless `TREEHOUSE_ONLINE=1`. CI also runs `treehouse demo` under `unshare -n` where the runner allows it.
- **Golden/replay.** For every committed cassette, re-running gives byte-identical trace hashes and identical scorecard JSON.
- **Unit.** Schema round-trips, the hash chain (a tampered line fails `verify`), and gateway policy.
- **Property** (hypothesis, 30-min cap). HT estimator invariance to permutation, ledger resolution order, and interval containment.
- **Method tests**, one file each in `tests/method/`:
  - *PPI*: a hand-computed 6-item example matches exactly. A simulation on a synthetic population of 200 claims (true precision 0.8, verifier with 85/80 sens/spec, n_gold=24, 400 reps, 90% interval) needs coverage ≥ 0.85. The PPI interval must be no wider than the human-only interval when the verifier is good. λ=1 is asserted when n_gold<50. FPC is applied: if the whole population is sampled, the width collapses to the bound.
  - *Design-based sampling*: inclusion probabilities sum to the expected n per stratum, the seed is deterministic, the HT mean is unbiased over 2,000 draws (within 2 SE), the unreported-places frame stratum is present, and gold is drawn from all sampled units **including abstentions**. A test asserts that an abstention can be drawn.
  - *Verifier controls*: the placebo pre/pre false-alarm rate is computed from planted pairs. Test-retest agreement and kappa are computed. Blindness: the `VerifierRequest` schema has no label, confidence, reasoning or window fields, and serialised requests for claimed items and controls have identical key sets.
  - *Rogan-Gladen*: with known sens/spec, the true prevalence is recovered within tolerance. sens+spec−1 < 0.2 gives ABSTAINED. Damage-state requests are refused (existence only).
  - *Baselines*: B0/B1/B2 match closed forms. The beat-baseline panel renders "not computable: 1 keyed regime(s)".
  - *Abstain rule*: a family mismatch, no calibration, or non-overlapping estimator intervals give ABSTAINED or "estimators disagree" with confidence capped at LOW.
  - *Planted errors*: corrupting 0/10/20/40% of good-trace claims makes the estimate strictly decrease (monotone), and the keyed precision tracks the truth.
  - *Shuffled labels*: shuffling gold against verdicts widens the interval to B2-equivalent width (within 20%).
  - *Evidence-in-trace*: a bbox that contains the claim passes, an overlapping-only bbox fails, and a window fetched only after the claim fails.
  - *Forbidden source*: the deny produces a span, the process score drops, and the touched item is marked contaminated and excluded from keyed grading.
  - *Leak detection* (simple): a claim that matches a key item with no imagery evidence span is flagged `probable_leak`. Canaries are cut.
- **Chip invariant.** Parse the report HTML. Every numeral sits inside an element with `data-tier`, apart from a whitelist of dates and ids. A "panel blend" test asserts that no Panel 5 value appears in Panels 1–4.

---

## I7. Ordered package plan (centre of gravity)

Hour estimates are for an autonomous coding agent, including writing the tests and fixing CI. The night is about 00:30 to 08:00, so 7.5 h. P0–P8 is the overnight commitment. P9–P13 continue on Wednesday, with the agent and Suhas working in parallel.

| # | Package (branch) | h | Acceptance tests (J / DoD / new) | Clay value proved |
|---|---|---|---|---|
| P0 | `scaffold`: uv project, ruff, pytest, offline guard, CI (lint+test+`treehouse --help`), Apache headers | 0.4 | CI green; the offline guard fails a test that opens a socket | open and reproducible |
| P1 | `schemas+cards`: all I2 models, JSON Schema export, `task validate`, three cards (synthetic-keyed, Nepal, India stub) | 0.8 | the India card validates unchanged (J15); a card with an empty forbidden list for a keyed step is rejected | "known task + known input + reference" |
| P2 | `store+tracer`: LocalStore, per-trial chained JSONL, manifest, seal, `verify` | 0.6 | a tampered byte fails verify; seal happens before the checks dir exists (ordering test) | provenance first-class |
| P3 | `gateway+tools`: in-process MCP server, `stac_search` (committed Vantor STAC JSON), `imagery_window` (synthetic deterministic raster; rasterio path tested on a generated 64×64 GeoTIFF), `clay_search` (synthetic npz, real loader on a tiny generated parquet/npz), `record_claim`, `note_limitation`, forbidden deny, `as_of`, budget, error tags | 1.0 | J4.1 (fault-injected tool), J7 (guard on stops with `budget_exceeded`; off completes), forbidden-source test | harness calls geospatial tools over MCP |
| P4 | `providers+plainloop`: FakeProvider, ReplayProvider, PlainLoop, `treehouse run`, `scripts/make_demo_fixtures.py` writes the cassettes | 0.8 | J1 offline (≥1 MCP call, every span has name/args/result/latency/cost); J4.2 (nonexistent tool, malformed args, loop, give-up each logged) | model swappable; recorded-trace fallback |
| **P5** | **`demo-skeleton`**: `treehouse demo` replays both tasks, seals, writes a minimal HTML (trace table, cost); README quickstart | 0.5 | **J2 + J8**: in a tmp dir under the socket block, demo exits 0 and the trace hashes equal the committed ones; a clean-clone CI job runs `uv sync --frozen && uv run treehouse demo` | replay for demo |
| P6 | `checks+panels`: rules (incl. evidence-in-trace), keyed grader (1:1 match, cluster bootstrap), Panels 1, 2, 3, 5 | 1.0 | J1.4; J4.3 (wrong output scores lower); J11 (S15: the agent that notes the cloud limit scores higher on understanding); J14 (S18: cost/speed separate, blend test) | score process and output against a reference |
| P7 | `trust`: sampling, RecordedVerifier, gold draw, PPI, B0/B1/B2, Rogan-Gladen, abstain, passport | 1.3 | every method test above; J13 (S17); J12 (S16: a rule-failed claim is "Do not rely" whatever the verifier says, and the passport lists process facts beside the interval) | trust without a key; "knowing whether to trust it" |
| P8 | `report-v2`: five-panel HTML with chips, passport and plain summary in the first viewport, lint, "what would change this interval", synthetic banner | 0.8 | J1.3, J1.5; chip invariant; summary lint rejects an invented number and a sentence without a span id; J15 (Nepal report shows cannot_assess rewarded) | domain experts read summarized traces + scores |
| — | *Overnight total* | **7.2** | | |
| P9 | `compare+stats`: Wilson, bootstrap, permutation, `compare` report, K trials | 0.7 | J5; J6 (planted good vs bad separated by more than the CI) | clear scores showing where workflows fail |
| P10 | `mcp-server`: read-only wrapper | 0.4 | J10 (S14): an in-process Client lists 8 tools; `get_trust_passport` returns tier, n and interval | partners consume evals from their agents |
| P11 | `strands+bedrock`: StrandsHarness with FakeModel, BedrockProvider with Stubber, OtlpTracer with in-memory exporter | 0.9 | J3.1–J3.4 offline (swap model, tracer, harness and evaluator by config; re-score with scorer v2 appends a record and leaves the old one alone) | model and tracer swappable |
| P12 | `api`: minimal FastAPI | 0.4 | J9 (OpenAPI RunConfig schema contains every option used in J1–J7; POST /runs via TestClient completes) | every parameter exposed |
| P13 | `docs`: README (live, replay, swap, compare, budget), card template, FUTURE-WORK of cuts, ADR | 0.4 | DoD doc rows; README commands are executed by a test that parses the fenced `bash` blocks | reproducible beyond its builders |

**Cut order**, first to go: P12 API (J9 falls back to `treehouse schema` plus a CLI launch, and the gap is stated) → OtlpTracer → Rogan-Gladen (the passport row reads "CALIBRATED-TRANSFER: not computed") → the permutation test (Wilson and bootstrap stay) → the P10 MCP server → StrandsHarness offline. **Never cut**: P0–P8, which together are the demo.

**Checkpoint rule.** If P5 is not merged by 04:30, the agent stops widening and finishes P6–P8 against the skeleton. It does not start P9.

### Demo data (all under `examples/demo/`; every file has `synthetic: true` and every report has a top banner)

1. **`synthetic-sites-v1` (keyed, calibration).** A 20×20 km invented AOI with 40 planted rectangular "sites" drawn by a seeded generator. `imagery_window` renders a deterministic tile from the seed, so there are no external pixels and no licence issue. 4 tiles are "cloudy" (a white overlay). The key is the planted list, stored under `keys/`. **Planted traces**, scripted for FakeProvider and committed as cassettes:
   - **good**: Clay narrows, then windows, then 34 TP, 2 FP and 4 `cannot_assess` on the cloudy tiles.
   - **fabricator**: claims with no fetched window, plus windows whose bbox does not contain the claim.
   - **key-peeker**: calls the forbidden key source, then claims exactly the key items.
   - **looper**: repeated identical calls, tool errors, then giving up.
   - **overconfident**: guesses on the cloudy tiles with confidence 0.95.
   - **budget-stop**: a variant of good with the guard tight.

   The 0/10/20/40% corruption series of `good` feeds the planted-error test.
2. **`nepal-bridges-demo` (unkeyed damage step).** The real event polygon and real Vantor STAC metadata (scene ids, bbox, date, GSD, cloud %) are committed as JSON, with no pixels. The candidate crossings are **synthetic points** along the Bhote Koshi corridor, labelled "illustrative, not surveyed bridges". The worker cassette is scripted: 30 claims, with the cloudy scenes marked `cannot_assess` (the cloud trap). Verifier verdicts are **recorded fake verdicts** from a seeded noisy oracle (sens 0.85, spec 0.80, 15% abstain), labelled "recorded fake verifier". Placebo and test-retest controls are included. **Synthetic gold**: n=24 drawn by the committed seed from all sampled units, including abstentions, labelled "SYNTHETIC GOLD, not human labels". The demo renders the passport twice: without gold it is MODEL-ESTIMATED and wide, with gold it is GOLD-ANCHORED and narrower. That is the A12 demo moment, which is honest because it is clearly synthetic. In the morning Suhas's blind labels replace the file, and the same command reprints the passport.

### How the report shows evaluated vs estimated to an ADB officer

The first viewport has a one-line verdict ("Spot-check before relying"), the plain summary, and the passport. Each number wears a chip with a plain-English hover and a printed legend:

| Chip | What it says |
|---|---|
| **Checked** (KEYED) | "compared to an answer key (v1, n=36)" |
| **Estimated from a random check** (GOLD-ANCHORED) | "24 items checked by a person at random; the checker abstained on 15%" |
| **Estimated from track record** (CALIBRATED-TRANSFER) | — |
| **Rough model guess** (MODEL-ESTIMATED, hatched, always shows its width) | — |
| **Not issued** (ABSTAINED) | gives the reason |

Panels 3 (output) and 4 (trust) sit side by side. Neither ever displays a combined number. "What would change this interval: about 20 more random checks would narrow it to ±0.10."

---

## Journeys become automated tests (`tests/journeys/`)

- **J1–J9.** As mapped in the table. J1 and J3 also have an `@aws` twin run by Kiro, so the live Bedrock run proves the same assertions.
- **J10 (S14, MCP).** In-process MCP client; tools listed; the passport has its tier; write tools are absent.
- **J11 (S15, understanding).** `must_notice` items are checked from the Understanding Statement and `note_limitation` spans.
- **J12 (S16, trust uses how).** The resolution rule puts hard-rule failure above everything else. The passport shows grounding rate and evidence sufficiency next to P(correct).
- **J13 (S17, keyless trust).** The P7 method suite plus "not computable: 1 keyed regime".
- **J14 (S18, cost/speed first-class).** Panel 5 has a TypedNumber for $, s, tokens and bytes, and the blend test passes.
- **J15 (S19, Nepal specialization + generality).** The Nepal card produces the cloud-trap reward. The India card validates. No region constant appears in `src/` (a grep test for lat/lon literals and place names).

## What MUST NOT be built tonight

These are out of scope tonight:

- A JS UI (F8 is static HTML only).
- CDK, Object Lock, IAM Deny, Lambda, CloudWatch, AgentCore, Athena, Step Functions, Bedrock batch.
- The LORO table, agreement-on-the-line, Dawid-Skene, conformal, Lincoln-Petersen.
- The act layer or inspection list, simulation, hindcast.
- OSM masked-block keying, canaries.
- An LLM trajectory judge.
- The OpenAI-compatible adapter.
- The labelling web page (a CSV template is enough until morning).
- Live Vantor pixel fetch in the default test path (one `@network` test only).
- Real LGND parquet download, Docker, auth, hosting.
- Any Kiro-dependent code beyond stubs.

An agent that starts any of these before P8 is merged is off-plan.

## I8. Kiro prompts (Wed, AWS)

1. **K1** Capability probe: write `aws-capabilities.json` covering locus, models, quotas and S3 versioning/Object Lock.
2. **K2** Vision smoke test on 5 real Vantor 0.5 m windows to pick worker and verifier families.
3. **K3** Live `synthetic-sites-v1` run on Bedrock (Strands), K=3, then commit the cassettes. This passes J1 live.
4. **K4** Live Nepal run on the clearest scenes, plus the cross-family verifier. Commit traces and verdicts with no pixels.
5. **K5** S3 versioned bucket via CDK; run `S3Store` tests; show version history.
6. **K6** Object Lock and key-bucket Deny (manual check); the manifest flips to IAM-enforced only if they run.
7. **K7** OTLP to CloudWatch, with a span-count reconciliation.
8. **Human block** (Suhas, 60–90 min): blind labels replace the synthetic gold, then a re-run of `treehouse trust`.

## I9. Risks

1. The agent over-builds P3/P7 and misses P5. *Mitigation*: the 04:30 checkpoint rule.
2. Strands' internal loop is not replay-deterministic. *Mitigation*: the demo uses PlainLoop, and Strands is tested with FakeModel, not with byte-equal replay.
3. The `mcp` 2.3 API drifts between versions. *Mitigation*: pin it in the lockfile and wrap it in one module.
4. Judges read synthetic gold as real. *Mitigation*: the banner, the chip text, and the `synthetic` flag in the manifest that drives the banner.
5. rasterio wheels fail on a judge's Mac. *Mitigation*: it is an extra (`[geo]`); the demo uses the synthetic raster path without rasterio.
6. The live morning runs show nothing works at 0.5 m. *Mitigation*: that is the finding, and the replay demo still stands.
7. Time. *Mitigation*: the cut order above is pre-committed.
