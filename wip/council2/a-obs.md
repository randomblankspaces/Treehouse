# Council 2, round (a): OBS (agent-eval / observability) implementation proposal

Scope: I1–I9 in full. Most of the detail is on the seams that every other package depends on: provider, harness, gateway, trace, seal/verify, the scorers, the summary lint and the offline guarantee. I implement SYSTEM-DESIGN.md as written. Where I depart from it, the departure is marked **[DEVIATION]** so it can be voted on.

**Checked tonight in the build container** (scripts are in `scratchpad/obs/`, pinned versions are those in context.md):
- A `strands.models.model.Model` subclass with a scripted `stream()` drives a real `strands.Agent` through a tool call and final answer **with `socket.connect` patched to raise** (`fake_strands.py`). An **async** `PythonAgentTool` fn calling an in-process MCP `Client` works under `agent.invoke_async` (`t3.py`): Strands → our gateway → MCP runs offline.
- `botocore.stub.Stubber` on `bedrock-runtime.converse` checks the request shape, including an `image` block with `source.bytes` and `toolConfig` (`t2.py`).
- **Gotcha:** an MCP 2.3 tool annotated `-> dict` returns `structured_content=None`, with only a JSON text block. Annotated `-> PydanticModel`, it returns the structured dict. Rule: **every tool returns a Pydantic model** (`t4.py`). Bad arguments come back as `is_error=True`, not as an exception.
- The GenAI semconv now lives at https://github.com/open-telemetry/semantic-conventions-genai (status "Development"). Span names: `invoke_agent {gen_ai.agent.name}`, `chat {model}`, `execute_tool {gen_ai.tool.name}`. Every `gen_ai.*` attribute used below (incl. `gen_ai.provider.name=aws.bedrock`, `gen_ai.usage.image.input_tokens`, `gen_ai.input.messages_ref`) appears in the current spec text. Installed package: `opentelemetry-semantic-conventions 0.66b2`.
- Strands custom provider docs: https://strandsagents.com/docs/user-guide/concepts/model-providers/custom_model_provider/ (not re-fetched; the signatures below come from the installed 1.63 source).

---

## I1. Repo and module layout

```
pyproject.toml   # uv, hatchling; requires-python>=3.12; ruff; pytest; hypothesis
                 # core deps: pydantic, pyyaml, numpy, scipy, typer, mcp==2.3.*, httpx
                 # extras: aws=[boto3], strands=[strands-agents==1.63.*], geo=[rasterio], otlp=[opentelemetry-sdk, -exporter-otlp]
src/treehouse/
  canon.py            # canonical JSON (sorted keys, no NaN, UTF-8, floats repr) + sha256 helpers
  clock.py            # Clock protocol; WallClock; LogicalClock (replay/golden)
  schemas/            # task.py config.py trace.py claims.py numbers.py checks.py scorecard.py manifest.py passport.py
  providers/          # base.py fake.py cassette.py bedrock.py openai_compat.py registry.py prices/2026-11.yaml
  harness/            # base.py loop.py strands_adapter.py prompts/{worker,verifier,summarizer}.md
  gateway/            # gateway.py policy.py budget.py meter.py
  tools/              # stac_server.py imagery_server.py clay_server.py claims_server.py cog_reader.py
  trace/              # chain.py tracer.py otlp_mirror.py
  store/              # base.py local.py s3.py layout.py seal.py verify.py
  checks/             # rules.py keyed.py sampling.py verifier.py gold.py leak.py ledger.py
  score/              # process.py understanding.py output.py cost.py  (pure)
  trust/              # ppi.py baselines.py rogan_gladen.py abstain.py passport.py  (pure)
  summary/            # facts.py phrase.py lint.py
  report/             # bundle.py html.py
  service.py          # the single code path the CLI, MCP and API all call
  cli.py  mcp_server.py  api.py(Could)
tests/  unit/ method/ golden/ e2e/ live/(marked aws, skipped)  conftest.py
fixtures/  tasks/ stac/ clay_synth.npz cogs/(generated at test time, not committed) cassettes/demo/ gold/
keys/      # answer keys; separate root, never mounted into the worker's tool servers
```

Import-boundary rule, enforced by a 20-line AST test: `score/`, `trust/`, `summary/lint.py` and `report/` may not import `providers`, `gateway`, `harness`, `boto3`, `httpx` or `strands`. This makes "pure function of sealed records" checkable rather than aspirational.

## I2. Core schemas (Pydantic v2, `model_config = frozen, extra="forbid"`)

```python
class Tier(StrEnum):
    KEYED="KEYED"; GOLD_ANCHORED="GOLD_ANCHORED"; CALIBRATED_TRANSFER="CALIBRATED_TRANSFER"
    MODEL_ESTIMATED="MODEL_ESTIMATED"; ABSTAINED="ABSTAINED"
    MEASURED="MEASURED"   # [DEVIATION] exact function of the sealed trace (Panels 1, 2, 5)

class Interval(BaseModel): lo: float; hi: float; level: float = 0.90; method: str  # "stratified-bootstrap", "clopper-pearson", ...
class TypedNumber(BaseModel):
    value: float | None; type: Literal["proportion","count","usd","ms","bytes","tokens","ratio"]
    tier: Tier; n: int | None; interval: Interval | None
    estimator_version: str; manifest_ref: str            # "sha256:…" of the sealed run manifest
    reason: str | None = None                            # required iff ABSTAINED
    detail: dict[str, float | int | str] = {}            # n_gold, n_verified, abstention_rate, key_version, reference_quality
    # validators: ABSTAINED => value is None and reason set; KEYED => detail.key_version;
    # GOLD_ANCHORED => n_gold and abstention_rate; any estimate tier => interval set
```

Why `MEASURED`: every number must carry a tier (commitment 2). "$1.84 for this run" is neither KEYED nor an estimate. Without a fifth label, the overnight agent will either invent one ad hoc or leave cost numbers untyped. The chip renders as a plain "measured from trace".

```python
TaskCard      # A2 fields; must_notice: list[NoticeItem{id, kind: mentions_any|plans_tool|declares_limit, terms|tool, weight}]; hash = canon.sha256(card - hash)
RunConfig     # task_ref, worker/verifier/summarizer: RoleConfig{provider, model_id, family, params, tools}, harness: loop|strands,
              # trials, seed, budget, backends{store: local|s3, mirror: none|otlp}, mode: fake|replay|live|record
              # validators: same-family verifier needs allow_same_family; needs_vision rejects non-vision models
Claim         # claim_id, trial_id, geometry, cls, status, confidence, evidence_refs, reason, grounded, unresolved_refs, contaminated, span_id
CheckResult   # layer: rules|key|verifier|overlap|human, verdict, detail, version, record_ref
CheckLedger   # claim_id, results[], resolved, resolved_by   (pure: rule fail > human > key > verifier > unchecked)
VerifierVerdict  # unit_id, unit_kind (hidden from verifier), verdict incl. cannot_assess, span_ref, pi, stratum
GoldLabel     # unit_id, label, labeller, ts, protocol_hash, sealed_ref, is_relabel
TrustPassport # estimand, headline, estimates[], baselines{B0,B1,B2}, shift, gate, disagreement, loro="not computable: 1 keyed regime"
Scorecard     # process / understanding / output / cost: dict[str, TypedNumber] + version; trust_ref. No field sums panels.
```

## I3. Interfaces and implementations

### Normalized model shape (Converse-shaped, because Bedrock is the default and Strands messages are already Converse-shaped)

```python
Block = TextBlock(text) | ImageBlock(format, sha256, bytes_ | None) | ToolUseBlock(id, name, input)
      | ToolResultBlock(tool_use_id, status, content: list[TextBlock|JsonBlock|ImageBlock]) | ReasoningBlock(text, signature)
class Message(BaseModel): role: Literal["user","assistant"]; content: list[Block]
class ToolSpec(BaseModel): name: str; description: str; input_schema: dict
class InferenceParams(BaseModel): max_tokens: int; temperature: float | None; top_p: float | None; seed: int | None
class ModelRequest(BaseModel): model_id: str; system: str; messages: list[Message]; tools: list[ToolSpec]; params: InferenceParams
    def key(self) -> str: ...    # sha256 of canon(request) with every ImageBlock replaced by its sha256
class Usage(BaseModel): input_tokens: int; output_tokens: int; cache_read_input_tokens: int = 0
    cache_write_input_tokens: int = 0; image_input_tokens: int | None = None
StopReason = Literal["end_turn","tool_use","max_tokens","stop_sequence","content_filtered","guardrail"]
class ModelResponse(BaseModel): message: Message; stop_reason: StopReason; usage: Usage
    latency_ms: int; response_model_id: str; request_id: str | None

class ModelProvider(Protocol):
    provider_name: str                      # -> gen_ai.provider.name ("aws.bedrock", "treehouse.fake", "treehouse.replay")
    async def complete(self, req: ModelRequest) -> ModelResponse
```

Only `ModelRequest.key()` touches image *bytes*, and it reduces them to a hash. That is what lets a committed cassette replay a vision run on a fresh machine with **no Vantor pixels anywhere** (A4 licence rule). The replay provider never needs the image, only the key.

The implementations:
- **`FakeProvider(script: list[FakeTurn] | Callable[[ModelRequest], ModelResponse])`**. YAML fixtures `fixtures/scripts/*.yaml`; each turn has an optional `expect` (e.g. `last_tool_result.contains: "r-0002"`) and a `respond` (text or tool_use); a failed `expect` raises `ScriptDivergence`, so a broken gateway fails loudly. It drives the planted-error and forbidden-source tests (a worker that claims exactly what we choose, hits the key bucket, cites unfetched windows).
- **`RecordingProvider(inner, cassette)`** and **`ReplayProvider(cassette, miss="fail"|"live", live=None)`**. The cassette is `cassette/model.jsonl` of `{key, response, recorded_at, provider, model_id}`. Must: `miss="fail"` raises `CassetteMiss(key, first_divergent_message_index)`. Should: fall through to live and emit a span event `treehouse.cassette=miss`. There is a matching `ToolCassette` keyed on `(server, tool, canon(args))`. Image results are stored as `ImageBlock(sha256, bytes_=None)` plus a pointer into the private pixel cache.
- **`BedrockConverseProvider(client=None, region, max_attempts=6, concurrency=4, price_table)`**. It maps to and from `client.converse(modelId, system=[{"text"}], messages, toolConfig={"tools":[{"toolSpec":{name,description,inputSchema:{"json":…}}}]}, inferenceConfig)`. Images map to `{"image":{"format":"png","source":{"bytes":…}}}`, both in user turns and inside `toolResult.content`. Usage maps from `usage.inputTokens/outputTokens/cacheReadInputTokens/cacheWriteInputTokens`. `reasoningContent` becomes a `ReasoningBlock`, which is stored and never scored. Calls run via `asyncio.to_thread` behind an `asyncio.Semaphore`. Backoff: jittered exponential on `ThrottlingException`, `ServiceUnavailableException` and `ModelNotReadyException`. Each retry is a span event `treehouse.retry {attempt, error_code, sleep_ms}`. Stubber tests: request shape incl. image block; throttle-twice-then-succeed; usage/stop-reason mapping; `ValidationException` → typed error; cost = usage × dated price. A live test (`@pytest.mark.aws`) is skipped unless `TREEHOUSE_LIVE_AWS=1`.
- **`OpenAICompatProvider(base_url, api_key_env)`** (Could). Uses httpx `/v1/chat/completions` with tools and `image_url` data URIs. Tested with `httpx.MockTransport`.
- **Registry**: `models.yaml` rows `{id, provider, family, vision, tool_use, reasoning, price_ref, region}`. The price table is versioned by date and its version goes into the manifest.

### Harness

```python
class Harness(Protocol):
    name: str; version: str
    async def run(self, *, system: str, user: list[Block], provider: ModelProvider, gateway: ToolGateway,
                  tracer: TrialTracer, budget: BudgetGuard, max_turns: int) -> HarnessResult
class HarnessResult(BaseModel): final_text: str; stop: Literal["completed","max_turns","budget","error"]; turns: int
```

The harness **does not return claims**. Claims exist only in the gateway's `ClaimLedger`, filled by `record_claim`. A harness therefore cannot route around the evidence rule.

- **`LoopHarness`** (about 80 lines). It calls `provider.complete` inside a `chat` span. It appends the assistant message. If `stop_reason == "tool_use"`, it awaits `gateway.call` for each `ToolUseBlock` and appends one user message of `ToolResultBlock`s. It stops on `end_turn`, `max_turns` or `BudgetExceeded`. **[DEVIATION]** I put this loop in **Must-0**. It is the reference harness for every offline test and the e2e demo, and it is the fallback if Strands breaks. The harness *comparison axis* stays Should, as A3/A8 say.
- **`StrandsHarness`**. It builds `strands.Agent(model=TreehouseStrandsModel(provider, tracer, budget), tools=gateway.as_strands_tools(), system_prompt=system, callback_handler=None)` and calls `await agent.invoke_async(user)`.
  - `TreehouseStrandsModel(Model)` implements `update_config`, `get_config`, `structured_output` (raises `NotImplementedError`; we do not use it) and `stream(messages, tool_specs, system_prompt, **kw)`. `stream` converts Strands Messages and ToolSpecs into a `ModelRequest`, which is a near-identity map since both are Converse-shaped. It awaits our provider inside **our** `chat` span, then re-emits the response as Strands `StreamEvent`s (`messageStart`, `contentBlockStart/Delta/Stop`, `messageStop{stopReason}`, `metadata{usage, metrics}`), as checked tonight.
  - So fake, replay and Bedrock all work under Strands with one trace schema and working cassettes. Strands' own OTel stays off (no global TracerProvider), avoiding double spans; the manifest records `harness: strands@1.63.x, model calls via treehouse provider`.
  - The verifier is a second `StrandsHarness` instance with `tools=[imagery_window, stac_search]`.

### ToolGateway

```python
class ToolGateway:
    def __init__(self, servers: Mapping[str, MCPServer], policy: GatewayPolicy, tracer: TrialTracer,
                 budget: BudgetGuard, meter: Meter, tool_cassette: ToolCassette | None, as_of: datetime)
    async def __aenter__(self) -> Self      # opens one in-process mcp Client per server; builds catalog from list_tools()
    def specs(self) -> list[ToolSpec]       # allow-listed tools only, schema from tool.input_schema
    async def call(self, name: str, args: dict, *, call_id: str) -> ToolOutcome
    def as_strands_tools(self) -> list[PythonAgentTool]   # async fn -> self.call
    claims: ClaimLedger; limitations: list[Limitation]; understanding: UnderstandingStatement | None
class ToolOutcome(BaseModel): result_id: str; status: Literal["success","error","blocked"]
    content: list[Block]; bytes_read: int; pixels: int; latency_ms: int; block_reason: str | None
```

`call`, in order: open an `execute_tool {name}` span; apply policy (not allow-listed → `not_allowlisted`; any URL, s3 URI, dataset id or bucket prefix in the args matching `forbidden_sources` → `forbidden_source`, tagged `treehouse.key_access_attempt=true`; dates after `as_of` → `as_of`); pre-call budget check; cassette lookup or `client.call_tool`; re-check every result `href` against the deny-list (tools also get a `SourceGuard` to call before any fetch); meter bytes, pixels and latency and write the payload to a blob; put a deterministic `result_id = f"r-{seq:04d}"` **into the result the model sees** so it can be cited; close the span. A blocked call returns an `is_error` result reading "blocked by policy: <reason>". It never raises, so the agent's reaction is observable.

`record_claim(geometry, cls, status, confidence, evidence_refs, reason)`, `note_limitation(text, scope)` and `submit_understanding(...)` live on a `claims` MCP server. The gateway intercepts them to resolve `evidence_refs` against this trial's `result_id` log. A claim with unresolved refs is sealed as `grounded=false`. A claim whose evidence touched a blocked or forbidden call is sealed as `contaminated=true`.

**Tools** (MCP 2.3 `MCPServer`, every return a Pydantic model):
- `stac_search` and `scene_info` read committed STAC item JSON in `fixtures/stac/` tonight, or the Vantor HTTPS bucket in live mode.
- `imagery_window` uses `cog_reader.py`, a rasterio windowed read over a range-counting file or HTTP opener, so `bytes_read` is *measured*, not estimated. It returns `ImageContent` (PNG) plus metadata `{scene_id, bbox, gsd, datetime, scene_cloud_pct, pixel_sha256, obscuration_heuristic}`. Tests run on a synthetic COG generated in a fixture.
- `clay_search` does numpy cosine search over `fixtures/clay_synth.npz`. The real loader is tested on a tiny generated GeoParquet. Every response includes the coverage report.

`BudgetGuard(limit_usd, limit_tool_calls, limit_bytes, limit_wall_s)` has `reserve(estimate)` and `commit(actual)`, raises `BudgetExceeded`, and emits a `treehouse.budget` event at 50/80/100%.

### Tracer

```python
class SpanRecord(BaseModel):
    trace_id: str; span_id: str; parent_span_id: str | None
    name: str                 # "invoke_agent worker" | "chat us.amazon.nova-pro-v1:0" | "execute_tool imagery_window"
    start_ns: int; end_ns: int; status: Literal["ok","error"]; error_type: str | None
    attributes: dict[str, str | int | float | bool | list[str]]
    events: list[SpanEvent]   # {name, ts_ns, attributes}
class TrialTracer:
    def __init__(self, writer: ChainedJsonlWriter, *, trace_id: str, clock: Clock, base_attrs: dict)
    def span(self, name: str, op: str, **attrs) -> ContextManager[SpanHandle]   # set(k,v), event(name,**a), error(exc)
class ChainedJsonlWriter:
    def __init__(self, path: Path, genesis: str)   # genesis = sha256("treehouse/trial/" + trial_id)
    def append(self, rec: BaseModel) -> str        # writes {"seq","prev","rec","h"}; h = sha256(prev + canon(rec))
    def close(self) -> ChainHead                   # {head, n_lines, file_sha256}
```

Each span is written as one line when it **ends**, so a child can appear before its parent and the reader reorders by id. Every span gets IDs from a seeded counter under `LogicalClock`, so a replay produces a byte-identical trace. The golden tests rely on this.

Mandatory `treehouse.*` attributes: `task.id`, `task.hash`, `run.id`, `trial.id`, `trial.index`, `role` (worker/verifier/summarizer), `config.hash`, `cost.usd`, `price_table.version`, `cassette` (hit/miss/live), `tool.args_hash`, `tool.result_ref`, `tool.result_id`, `tool.bytes_read`, `tool.pixels`, `tool.blocked`, `tool.block_reason`, `key_access_attempt`, `image.sha256`, `scene.id`, `license.spdx`, `claim.id`, `evidence.refs`, `budget.remaining_usd`. Message bodies are never inlined. `gen_ai.input.messages_ref` and `gen_ai.output.messages_ref` point to blobs.

`OtlpMirror` (Should) reads **sealed** span records and exports them through the OTel SDK with explicit ids and times. Because it never sits on the write path, a CloudWatch outage cannot corrupt the canonical record. A count or token mismatch between mirror and source becomes a `provenance_warning`. The CI semconv test re-scores the frozen trace in `fixtures/golden/` after any semconv or package bump.

## I4. Storage layout

```
$TREEHOUSE_STORE (default ./.treehouse)/
  ledger.jsonl                         # chained: {seq, prev, manifest_hash, run_id}
  blobs/sha256/ab/<hex>                # JSON payloads, message bodies, tool results; <hex>.meta.json {license, media_type}
  runs/<run_id>/
    task.yaml  config.json  manifest.json  SEALED
    trials/<trial_id>.trace.jsonl  trials/<trial_id>.claims.jsonl  trials/<trial_id>.understanding.json
    cassette/model.jsonl  cassette/tool.jsonl
  evals/<run_id>/<kind>/<record_hash>.json   # kind: rules|key|sample|verifier|gold|score|trust|summary
  evals/index.jsonl                          # chained, each row names its run manifest hash and input versions
  bundles/<run_id>/bundle.json  report.html
~/.cache/treehouse/pixels/sha256/…           # private pixel cache, never committed, never in bundles
$TREEHOUSE_KEYS (default ./keys, outside the tool servers' root)
```

`Manifest = {schema: "treehouse.manifest/1", run_id, created_at, task{id,version,hash}, config_hash, config, mode, backends_ran, software{treehouse, git_sha, uv_lock_sha256, python, container_digest?}, semconv{repo_ref, pkg: "0.66b2"}, trials[{trial_id, role, trace_file, head, n_lines, file_sha256, claims_sha256, stop}], cassettes{model_sha, tool_sha}, data_pointers[{scene_id, href, etag, bbox, datetime, license}], key_isolation: "local convention, not IAM-enforced"|"IAM-enforced", license_floor, price_table_version, prev_manifest_hash, manifest_hash}`.

`seal(run_dir)`: close writers, hash files, write the manifest last (chained to the ledger head), atomic rename from `runs/.tmp-<id>`, `chmod -R a-w`, write `SEALED`, append to the ledger.

`S3Store` (Must-0 in Kiro, written and Stubber-tested tonight) writes the same keys with `If-None-Match: *` conditional PUT (https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html) on a versioned bucket, plus optional Object Lock headers.

`treehouse verify [RUN|--store]` checks offline every line's `prev`/`h`, file shas and heads against the manifest, the manifest hash, the ledger chain, that every blob ref exists and re-hashes, and that every eval record names a sealed manifest. It reports the first broken path and seq, exit code 1.

## I5. CLI / MCP / API surface

Typer, everything through `service.py`:
- `treehouse task init|validate CARD`
- `run CARD -c CONFIG --mode fake|replay|live|record [--trials K]` (seals automatically)
- `check RUN [--layers rules,key,sample,verifier]`
- `label export|import RUN` (blind CSV and static page; shuffled; hides worker and verifier fields)
- `score RUN`, `trust RUN`, `summarize RUN`, `report RUN [--out]`
- `verify [RUN|--store]`, `replay RUN --rescore|--rerun`, `compare RUN_A RUN_B`
- `cassette diff RUN` (first divergent request)
- `mcp serve [--store]`
- `probe` (writes `aws-capabilities.json`)
- `demo` (the fresh-machine path, I7)

The **MCP server** (`MCPServer("treehouse")`) is read-only over `bundles/*/bundle.json`. Its tools are `list_runs`, `get_scorecard`, `get_trust_passport`, `explain_trust(item)`, `get_plain_summary`, `get_claim`, `compare_configs` and `get_trace_span`, plus the resource `treehouse://runs/{id}/report`. Every numeric field is returned as a `TypedNumber`, so the chip travels with the number. The test opens it with an in-process `Client`, asserts that the tool-name set equals exactly that list (no write tool exists), and walks every response checking that each float sits inside a `TypedNumber`.

The API (FastAPI) is Could and returns the same bundle models.

## Scorers (Panels 1, 2, 5) as pure functions

```python
SealedRun  # frozen view: manifest, spans by trial (parent-ordered), claims, understanding; loaded via store.read_only()
def score_process(run: SealedRun, task: TaskCard, *, version="process-v1") -> ProcessPanel
def score_understanding(run: SealedRun, task: TaskCard, *, version="understanding-v1") -> UnderstandingPanel
def score_cost(run: SealedRun, prices: PriceTable, *, version="cost-v1") -> CostPanel
```

Panel 1, each value a `TypedNumber(tier=MEASURED, n=denominator)`, defined in `docs/scoring-v1.md` before any real run:
- `grounding_rate` = grounded / claims.
- `evidence_sufficiency` = status claims citing a window whose bbox **contains** the geometry at GSD ≤ the card threshold, over status claims.
- `tool_validity`; `error_recovery` (error followed within 3 calls by a successful same-tool call with new args).
- `coarse_to_fine` (first window preceded by `stac_search`/`clay_search`); `redundancy` (duplicate `(tool, args_hash)`); `max_loop`.
- `abstention_appropriateness` (`cannot_assess` citing cloud ≥ threshold or the heuristic flag); `forbidden_attempts`; `budget_adherence`.

Panel 2: weighted `must_notice` coverage by declared `kind`; plan-vs-action tool Jaccard.

Panel 5: per-role USD from `treehouse.cost.usd`, wall time from the root span, p50/p95 chat latency, tokens (cache, image), calls, windows, `bytes_read`, `cost_per_correct` only when Panel 3 is KEYED. Replayed runs show "recorded cost" (`detail.replayed=1`). Verifier cost is shown as "price of trust".

Purity test: run each scorer twice, with sockets blocked and a patched clock. Results must be equal and must equal the golden JSON.

## Plain summary and numbers lint

`facts.build(scorecard, passport) -> FactTable`, a list of `{slot, display_str, typed_number, span_ids}`.

`phrase(facts, provider)` asks the summarizer model for prose that uses only `{{slot}}` placeholders and ends each sentence with `[span:…]`. The slots are filled deterministically.

`lint(text, facts, span_index) -> list[LintError]`:
- Regex `-?\d+(?:[.,]\d+)?%?` over the text after slot fill. Every match must equal some fact's `display_str` (allowing dates and ids from a whitelist pattern).
- Every sentence must cite at least one span id that exists in the sealed trace.
- Words "verified" and "accurate" are disallowed next to a non-KEYED number.

If lint fails, the deterministic template prose is used and the failure is stored. Tests cover a planted hallucinated number, a missing citation, a nonexistent span id and a correct paraphrase. The FakeProvider supplies all four. The output is labelled "narrative, not scored".

## Static HTML report

`report.html.render(bundle) -> str`: one file, inline CSS, no JS dependency, `html.escape` everywhere. The passport and plain summary are in the first viewport, followed by five panels with chips (`<span class="chip" data-tier="KEYED">`), the claim table (worker | verifier | key | ledger resolution), the trace timeline from spans, the licence floor, the NC notice and "what would change this interval". There are **no image bytes ever**, only pixel hashes and scene ids.

Test: parse with `html.parser`. Every text node containing a digit (minus the whitelist of ids and dates) must have an ancestor carrying `data-tier`. That keeps commitment 2 true in the UI.

## Verifier, trust engine (signatures; detail belongs to the statistics seat)

```python
def build_frame(run, task) -> Frame                           # claimed + unreported corridor cells + controls
def draw_sample(frame, plan: SamplingPlan, seed: int) -> Sample   # units with pi_i, stratum; sealed before the verifier runs
async def run_verifier(sample, harness, gateway_factory) -> list[VerifierVerdict]  # blind: gets location, object def, scene ids only
def draw_gold(sample, n: int, seed_commit: str) -> list[UnitId]   # from ALL sampled units incl. abstentions
def ppi_estimate(sample, verdicts, gold, *, lam=1.0, n_boot=2000, seed) -> TypedNumber
def rogan_gladen(p_obs, se, sp, *, ci_inputs, spread) -> TypedNumber   # ABSTAINED if se+sp-1 < 0.1
def baselines(history, task) -> dict[str, TypedNumber]        # B0 pooled beta-binomial, B1 stated confidence, B2 intercept-only
def passport(estimates, baselines, shift, task) -> TrustPassport  # headline = highest tier; disagreement flag; gate
```

Blindness is enforced **structurally**. The verifier's prompt is built by `verifier.build_unit_prompt(unit)` from a `BlindUnit` Pydantic model with exactly the fields location, object definition and scene ids. Its gateway has its own allow-list and its own forbidden list. A unit test asserts that no worker field name or value appears in any verifier `ModelRequest`, by serialising the requests and grepping for claim ids, worker labels and confidences.

## I6. Test strategy

**Offline guarantee.** In `conftest.py`, an autouse fixture monkeypatches `socket.socket.connect`, `socket.create_connection` and `socket.getaddrinfo` to raise `NetworkBlocked`. It also sets `AWS_ACCESS_KEY_ID=testing`, `AWS_EC2_METADATA_DISABLED=true` and `TREEHOUSE_STORE=tmp_path`. `@pytest.mark.network` and `@pytest.mark.aws` lift it, and both are skipped unless an env flag is set. In-process MCP uses memory streams, so it keeps working (checked).

**Unit and property tests** (hypothesis):
- canonical JSON is stable under key order;
- the chain detects any single-byte flip, line deletion, reorder or truncation at exactly the right seq;
- `ModelRequest.key()` ignores image bytes but changes with any text change;
- the ledger resolution order;
- `TypedNumber` validators.

**Golden and replay tests:**
- `fixtures/cassettes/demo` replays to a byte-identical trace head and a golden scorecard;
- `replay --rescore` equals the original scores;
- a cassette miss raises with the divergent index.

**Method tests** (`tests/method/`, each a pass/fail assertion):
- *Evidence-in-trace*: scripted citations of an unfetched id / an overlapping-not-containing window / a valid window → fabrication, fabrication, pass.
- *Forbidden source*: scripted `imagery_window(href=s3://treehouse-keys/…)` and `stac_search(collection=<key id>)` → blocked spans, `forbidden_attempts=2`, later claim `contaminated` and excluded from keyed grading. *as_of*: post-`as_of` scene refused.
- *HT / design sampling*: unequal π, mean HT error over 2,000 seeds ≤ 0.01; empirical inclusion frequencies match stored π; FPC applied.
- *PPI*: simulated population with a known biased verifier, 90% coverage over 500 sims in [0.85, 0.95]; never wider than gold-only when the verifier is good; useless verifier still covered; λ=1 when n_gold < 50.
- *Abstention category*: where abstention correlates with error, the naive drop-abstentions estimator is biased and the full-table one stays covered.
- *Planted error*: corrupt k ∈ {0,2,5,10} of 40 keyed claims → estimate monotone, KEYED value moves by exactly k/40.
- *Shuffled labels*: width ≥ 0.9 × B2 width and covers the B2 point. *Placebo*: scripted 30% false-damage verifier on pre/pre recovers 0.3 within its CI. *Test-retest*: kappa on fixed tables.
- *Rogan-Gladen*: recovers known prevalence; ABSTAINED when se+sp ≤ 1.1; widens with regime spread. *Baselines*: hand-computed B0/B1/B2; "not computable: 1 keyed regime".
- *Leak / canary*: in-tolerance claim with no imagery span flagged; decoy → `INVALID_FOR_ACCURACY`, removed from trust training input.
- *Blindness* (grep test above); *gold-before-verdict*: the gold draw's ledger seq precedes every verifier record, else `draw_gold` refuses.

**E2E:** `treehouse demo` in a clean tmp dir with sockets blocked produces `report.html`, and `verify` exits 0.

## I7. Ordered package plan (one branch and PR each, tests first, merge on green)

| # | Package | Size | Acceptance |
|---|---|---|---|
| P0 | scaffold, ruff, offline fixture, `canon`, `clock`, import-boundary test | 0.5 h | `pytest` green with network blocked |
| P1 | schemas + `task validate` + Virginia, Nepal and India cards | 1.5 h | invalid cards rejected with field paths; hashes stable |
| P2 | chain writer, TrialTracer, `verify` (file level) | 1 h | tamper property tests |
| P3 | provider base, Fake, Recording/Replay cassette, price table | 1.5 h | scripted divergence; miss raises; image-hash key |
| P4 | gateway, policy, budget, meter; MCP servers on fixtures (stac, synthetic COG window, clay_synth, claims) | 2.5 h | forbidden/as_of/allow-list tests; bytes_read measured; result_id citations |
| P5 | LoopHarness, orchestrator, local store, seal, manifest and ledger, `run --mode fake` | 2 h | e2e fake run seals; `verify --store` passes; golden head |
| P6 | Bedrock provider (Stubber) + S3Store (Stubber) | 1.5 h | request shape incl. image; backoff; conditional PUT |
| P7 | Strands adapter (TreehouseStrandsModel, `as_strands_tools`) | 1 h | same scripted run under both harnesses gives equal claim tables |
| P8 | rules, keyed grader (one-to-one match, cluster bootstrap), Panels 1/2/5, scorecard | 2 h | evidence-in-trace and planted-error KEYED tests; purity test |
| P9 | sampling, blind verifier, gold draw, label export/import, PPI, baselines, RG, abstain, passport | 3 h | method tests above |
| P10 | facts, summary, lint; bundle; HTML report; `demo` command + committed synthetic demo cassette | 2 h | lint tests; chip-ancestor test; clean-clone demo |
| P11 | read-only MCP server | 1 h | exact tool set; typed numbers |
| P12 | OTLP mirror; cassette miss fall-through; OpenAI-compatible | Should/Could | — |

Total Must work is about 20 agent-hours, so the overnight agent will not finish all of it. **Cut from the bottom.** By Wednesday morning the minimum handoff is P0–P7: Suhas can then record real cassettes in Kiro immediately. P8–P10 continue in the daytime. The `demo` path tonight uses a **synthetic** cassette recorded from the FakeProvider on synthetic fixtures, stamped `SYNTHETIC DEMO` in the manifest and report. It is replaced by a Bedrock-recorded cassette (pixel hashes only) after K4.

## I8. Kiro prompts (AWS, morning)

- **K1** `treehouse probe` → `aws-capabilities.json` (locus, models, one vision call cost, quotas, S3 versioning/Object Lock, CloudWatch).
- **K2** `TREEHOUSE_LIVE_AWS=1 pytest -m aws tests/live/` (text, image and tool call per candidate model).
- **K3** vision smoke test on 10 real Vantor windows → worker/verifier families in `models.yaml`.
- **K4** `treehouse run fixtures/tasks/virginia.yaml --mode record --trials 3`, then Nepal, then `check/score/trust`; commit cassettes (pre-commit hook rejects image bytes).
- **K5** versioned bucket (CDK or CLI), `--store s3://…`, show `list-object-versions`; try Object Lock and key-bucket Deny, record result in manifest.
- **K6** (Should) OTLP mirror to CloudWatch; invocation logging text/metadata only; reconciliation test.

## I9. Risks

1. **Strands/MCP API churn** → pin `strands-agents==1.63.*`, `mcp==2.3.*`; contract tests (FakeModel drives an Agent; in-process Client lists tools). Strands may call `structured_output` on some path: we raise, and the contract test pins the paths we use.
2. **MCP structured-output gotcha** → Pydantic returns plus a test that `structured_content` is non-null for every tool.
3. **Cassette brittleness** (any prompt edit invalidates keys) → `cassette diff`, prompt hash in manifest, freeze prompts before recording.
4. **Pixel leakage** via cassettes/bundles/traces → image-hash keys, private cache, magic-byte lint on committed files.
5. **Double tracing** if Strands OTel is switched on → documented off; mirror is read-only. **Semconv "Development"** → pinned ref + frozen-trace test.
6. **Overnight agent builds trust maths before the spine** → this order; P5 e2e green before P8 starts.
7. **Replayed cost read as live cost** → `replayed` flag on the chip.
