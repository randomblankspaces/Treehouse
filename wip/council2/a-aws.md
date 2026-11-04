# Council 2, round (a): AWS architect implementation proposal

Seat: AWS architect. This proposal covers I1–I9. My focus is the AWS seams: `backends:`, the S3 store, the Bedrock Converse adapter, prices, exporters, CDK, the probe, the Kiro prompts and the cost guard. The statistics seats own the method details.

## What I checked tonight

I built a scratch venv: Python 3.13, botocore 1.43.123, moto 5.2.5, aws-cdk-lib 2.275.0, node 22.23. Sockets were patched to raise.

**What works offline:**
- **moto S3.** Versioning and Object Lock GOVERNANCE default retention both work.
  - A simple DELETE adds a delete marker. A version-id DELETE returns `AccessDenied`.
  - `PutObject(IfNoneMatch="*")` on an existing key returns `PreconditionFailed`.
  - `PutObject(IfMatch=<stale ETag>)` returns `PreconditionFailed`.
- **`botocore.stub.Stubber` on `bedrock-runtime.converse`.** It validates requests against the real service model, including image blocks (`format` is png, jpeg, gif or webp; `source.bytes`). It can inject `ThrottlingException`.
  - The service model's `ToolResultContentBlock` accepts `image`.
  - `TokenUsage` includes cache read and write tokens.
  - `CountTokens` exists.
- **CDK synth.** A stack with a versioned Object Lock bucket, a KMS key bucket with an explicit Deny, and a log group synthesizes. It passes `aws_cdk.assertions.Template` checks in about 6.5 s, with no credentials.

**What I could not check:**
- **AWS docs.** `docs.aws.amazon.com` is outside this session's allowed network. The AWS URLs below are cited without a fresh fetch. API facts were checked against botocore and moto instead.
- **Model ids.** They are UNVERIFIED; the probe resolves them.

**One finding needs action:** the build container exports `AWS_ACCESS_KEY_ID=proxy-injected`. An unscrubbed boto3 call in a test could send real signed requests through the proxy. The fixture in I6 must scrub these variables.

## I1. Repo and module layout

**Dependencies (`pyproject.toml`).** uv, `requires-python >=3.12`, ruff, pytest. Extras:
- `aws` = boto3
- `strands` = strands-agents
- `otel` = opentelemetry-sdk + otlp-proto-http exporter
- `infra` = aws-cdk-lib>=2.275,<3 + constructs

Dev group: pytest, hypothesis, moto[s3]>=5.2, ruff.

```
src/treehouse/{schemas,config,store,trace,providers,harness,gateway,tools,checks,verifier,trust,score,report,budget}/  cli.py  mcp_readonly.py
data/models/registry.yaml   data/prices/bedrock-us-east-1.2026-11-04.yaml   data/prices/fixture.yaml
tasks/{virginia-solar,nepal-bridges,india-stub}.yaml
infra/app.py  infra/stacks/{store,keys,obs,roles}.py      # the only place aws_cdk is imported
scripts/aws_probe.py
tests/{unit,property,golden,methods,aws_offline,infra}/
fixtures/{cassettes (pixel-free),stac,cog (synthetic),embeddings (synthetic npz/parquet),smoke}/
```

`boto3` is imported lazily, only inside `store/s3.py`, `providers/bedrock.py` and the exporters. A test imports every module with `sys.modules["boto3"]=None`. A clone without the `aws` extra therefore still runs the replay demo.

## I2. Core schemas

All schemas are frozen Pydantic v2 models with `schema_version`. Their JSON Schema export is golden-diffed.

**Task and config**
- `TaskCard`: as in SYSTEM-DESIGN A2.
- `RunConfig`: worker, verifier and summarizer `ModelRef`; harness; tools; K; seed; `backends`; budget.
- `EvalSpec`: scorer, key and estimator versions; seed.

**Run records**
- `Manifest` holds:
  - task `id@hash`, config hash, git SHA, lock hash
  - semconv pin, price-table id and hash
  - `backends_resolved`
  - per-trial trace heads, claim-table hash, cassette hash
  - license floor, key-isolation statement
  - `prev_manifest_hash` and `manifest_hash`
- `Span`: GenAI-style `invoke_agent`, `chat` and `execute_tool` spans, with `treehouse.*` attributes, `seq`, `prev_hash` and `hash`.
- `Claim`.
- `CheckLedger`: an append-only list of `CheckResult{layer, version, verdict, evidence}`.
- `VerifierVerdict`: a status or `cannot_assess`, plus `unit_id`, `inclusion_prob` and `is_control`.
- `GoldLabel`: blind-protocol fields.

**Typed outputs**
- `TypedNumber`: `value`, `type`, `tier`, `n`, `interval{lo,hi,level,method}`, `estimator_version`, `manifest_ref`, `abstain_reason`.
- `TrustPassport`.
- `Scorecard`: five panels of `TypedNumber`. There is no composite field.
- `CostRecord`: `usd` is a `TypedNumber` and may be typed `UNPRICED`.

**The `backends:` seam.** The config asks for a backend per seam:

```yaml
backends:
  model: {worker: bedrock, verifier: bedrock, summarizer: bedrock}  # fake|replay|bedrock|openai_compat
  store: s3                     # local|s3
  tracer: [jsonl, cwlogs]       # jsonl always; +cwlogs|otlp
  key_isolation: iam            # local|iam
  tool_locus: inproc            # inproc|lambda
  budget_alarm: [inapp, aws_budgets]
  allow_degrade: true
```

The manifest records what actually ran, with evidence:

```json
"backends_resolved": {
  "store": {"requested":"s3","ran":"s3","versioning":"Enabled","object_lock":"GOVERNANCE/1d",
            "evidence":"GetBucketVersioning+GetObjectLockConfiguration @2026-11-04T14:02Z"},
  "key_isolation": {"requested":"iam","ran":"local","degraded_from":"iam",
            "reason":"caller ARN != worker role; canary GetObject allowed",
            "statement":"key isolation: local convention, not IAM-enforced"}}
```

**Rule: `ran` comes from a read-back or a live denial test at preflight, never from the config.**
- **`object_lock`** comes from `GetObjectLockConfiguration`.
- **`key_isolation: iam`** needs two things:
  - `sts:GetCallerIdentity` returns the worker role.
  - A canary `GetObject` on the key bucket returns `AccessDenied`.

  This matters because in Workshop Studio the process may run as the participant role, which the Deny does not name.
- **`allow_degrade: false`** makes a run fail instead of degrading.

## I3. Interfaces and implementations

### Model providers

`ModelProvider.converse(messages, tools, system, params) -> ModelTurn` returns content, tool calls, stop reason, usage (in, out, cache_read, cache_write), latency, the model id that was sent, and the request id. There are four implementations:
- **`fake`**: a scripted policy.
- **`replay`**: a cassette keyed on (role, trial, turn, request hash). In the Must a cache miss is an error; a `cassette_miss` fall-through is a Should.
- **`bedrock`**.
- **`openai_compat`**: Could.

### Bedrock adapter

It uses `bedrock-runtime.converse`, not `InvokeModel`, so both model families share one message shape (https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html).
- **Retries and concurrency.** `Config(retries={"mode":"adaptive","max_attempts":8}, read_timeout=300)`, plus the gateway's semaphore (default 2). Every throttle becomes a span event, so throughput is measured.
- **Images.** `imagery_window` returns a PNG, downsampled to the registry's `max_image_px` (1024 by default). The registry sets `image_delivery` per model:
  - `tool_result`: the image goes inside `toolResult.content`. botocore allows this; per-model support is UNVERIFIED.
  - `user_turn`: the tool result says "attached" and the image goes in the next user message.

  The probe and the vision smoke test pick the mode.
- **Recorded per call.** The `modelId` sent (inference profile), region, `inferenceConfig`, prompt hash, `RequestId`, usage, `metrics.latencyMs` and stop reason.
- **Reasoning.** `reasoningContent` is stored and never scored.
- **Preflight token count.** `CountTokens` is used when the model supports it (UNVERIFIED), else a chars/4 estimate.
- **Strands.** The Strands worker uses `strands.models.bedrock.BedrockModel(model_id=<profile>)`. The gateway tools are wrapped as Strands tools, and a hook emits our spans. **Both harnesses read the same registry entry.**

### Model registry

`data/models/registry.yaml` is config, not code. All ids are UNVERIFIED. The probe fills `available` and `inference_profile` from `ListFoundationModels` (keeping models with IMAGE input) and from `ListInferenceProfiles`.

| key | family | candidate id | role |
|---|---|---|---|
| claude-sonnet-5-5 | anthropic | `anthropic.claude-sonnet-5-5` (profile `us.`/`global.` prefix) | worker default |
| claude-opus-5-5 | anthropic | `anthropic.claude-opus-5-5` | worker alt |
| nova-pro | amazon | `amazon.nova-pro-v1:0` / `us.amazon.nova-pro-v1:0` | verifier default |
| nova-2-lite | amazon | `amazon.nova-2-lite-v1:0` | verifier cheap alt |
| llama4-maverick / pixtral-large | meta / mistral | `us.meta.llama4-maverick-…` / `us.mistral.pixtral-large-…` | third-family fallback |

Each entry has these fields: `family`, `model_id`, `inference_profile`, `region`, `vision`, `tool_use`, `image_delivery`, `max_image_px`, `price_ref`, `quota_note`.

Validation:
- A non-vision model is rejected when the task sets `needs_vision`.
- A worker and verifier from the same family are rejected unless `allow_same_family` is set. That flag stamps the run "self-verified".

Why Nova as the verifier default: it is a different family, it is first-party, and it is likely cheap, which serves A8's rule that the verifier costs at most about 20% of the worker. **The K2 smoke test can overturn all of this.**

### Price table

A dated data file:

```yaml
table_id: bedrock-us-east-1.2026-11-04
source: https://aws.amazon.com/bedrock/pricing/
retrieved_at: null     # Kiro fills in K2
retrieved_by: null
unit: usd_per_1k_tokens
rows:
  - {model_key: claude-sonnet-5-5, tier: on_demand, input: null, output: null, cache_read: null, cache_write: null}
  - {model_key: nova-pro, tier: on_demand, input: null, output: null}
```

- Its hash goes into every manifest.
- **A null price gives `UNPRICED`. No price is ever invented.**
- Tests use `fixture.yaml` with synthetic prices.
- Cost Explorer is used only to reconcile, never as the cost of record.

### Harness and tracer

- **Harness:** `plain_loop` is about 100 lines over `ModelProvider` and is almost free to test with `fake`. `strands_adapter` drives a real `strands.Agent` through a `FakeModel(Model)` subclass in tests.
- **Tracer:** one JSONL file per trial. Each line carries `prev_hash` and `hash` (sha256 of the canonical JSON). `close()` returns the head.
- **Exporters are observers only.** If an exporter fails, the run records `exporter_error` and continues.
  - `cwlogs` uses boto3 `PutLogEvents` to `/treehouse/spans`. It needs no extra dependency and is the cheap second tracer.
  - `otlp` (the `otel` extra) sends OTLP/HTTP with SigV4 to `https://xray.<region>.amazonaws.com/v1/traces`. It needs Transaction Search (https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-OTLPEndpoint.html, UNVERIFIED this pass), or it can target an ADOT collector.
- **Reconciler:** compares span counts and token totals between JSONL and the exporter, and raises a provenance warning on any mismatch.

### Store

```python
class Store(Protocol):
    def put_blob(self, data: bytes, *, media_type: str, license: str) -> BlobRef  # CAS, idempotent
    def put_once(self, key: str, data: bytes) -> PutResult                         # raises AlreadyExists
    def get(self, key_or_ref) -> bytes
    def advance_head(self, new_hash: str, expected_prev: str | None) -> None       # compare-and-swap
    def versions(self, key: str) -> list[VersionInfo]
    def capabilities(self) -> StoreCaps   # versioning, object_lock, enforced_by
```

**Local store**
- Blobs are written with `os.open(O_CREAT|O_EXCL)` and then `chmod 0444`.
- HEAD is moved by atomic rename, and every move is appended to `HEAD.log`.

**S3 store**
- `put_blob` calls `PutObject(IfNoneMatch="*", ChecksumAlgorithm="SHA256", Metadata={sha256, license})`.
  - If it gets `PreconditionFailed`, it HEADs the object and compares the sha256. A match counts as success, so the call is idempotent.
  - `put_once` raises instead.
- `advance_head` calls `PutObject(Key="chain/HEAD", IfMatch=<etag>)`, which stops two writers forking the chain. With versioning on, HEAD's version list is the seal history that the demo shows.
- With default Object Lock retention on the bucket, every object inherits GOVERNANCE mode, so no lock parameters are passed per call.
- Sources: https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html and https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html.

**Seal order:** blobs, then traces, then claims, then cassette, then the manifest (put-once), then HEAD. `treehouse verify` runs on either store.

### Gateway and pure functions

- **ToolGateway.** Wraps the in-process MCP server (mcp 2.3.0 `MCPServer`; tests use `Client(srv)`). It enforces the allow-list, forbidden sources and `as_of`. It meters bytes, dollars and time, applies backoff, and caps concurrency. A blocked call becomes a `key_access_attempt` span.
- **Scorers, verifier, trust engine and summarizer** are pure functions over sealed records. The verifier is a second harness run with only `imagery_window` and `stac_search`, built from a blinded prompt.

## I4. Storage layout

The same keys apply under `~/.treehouse/store/` and `s3://treehouse-runs-<acct>-<region>/`:

```
objects/sha256/<2>/<62>                       # CAS blobs
runs/<run_id>/manifest.json                   # put-once
runs/<run_id>/trials/<k>.trace.jsonl          # put-once
runs/<run_id>/{claims.jsonl,cassette.jsonl}
evals/<run_hash>/<scorer_v>/<key_v>/<verifier_cfg>/<est_v>/<seed>.json   # append-only
labels/<gold_plan>/<labeller>/<ts>.jsonl
spend/ledger.jsonl                            # budget ledger mirror
chain/HEAD                                    # the only mutable object; versioned
```

- **Answer keys** never live here. They go in `treehouse-keys-<acct>`, which is KMS-encrypted and has the Deny, or locally in `~/.treehouse/keys`, outside the worker's working directory.
- **Committed cassettes are pixel-free.** Each image payload is replaced by `{"redacted":"vantor-cc-by-nc","sha256":…,"bytes":…}`. The crops themselves stay in a gitignored `~/.treehouse/cache/`.

## I5. CLI, API and MCP surface

- **CLI:** the A9 commands, plus:
  - `store push --to s3://…`: put-once upload, then chain verify, then HEAD advance.
  - `store versions`, `prices check`, `budget status|plan`, `probe import|verify-infra`, `smoke vision`, `cassette export --pixel-free`, `trace reconcile`.
- **MCP:** read-only, as in A9.
- **FastAPI:** Could.

## I6. Test strategy

### Offline guarantee

An autouse fixture in `conftest.py`:
- Patches `socket.connect` and `create_connection` to raise. Loopback is allowed only for tests marked `localnet`.
- **Scrubs every `AWS_*` variable**, then sets:
  - `AWS_ACCESS_KEY_ID=testing` and `AWS_SECRET_ACCESS_KEY=testing`
  - `AWS_DEFAULT_REGION=us-east-1`
  - `AWS_CONFIG_FILE=/dev/null` and `AWS_SHARED_CREDENTIALS_FILE=/dev/null`
  - `AWS_EC2_METADATA_DISABLED=true`

A canary test asserts that an unstubbed boto3 call raises `NetworkBlocked`.

### AWS seams: moto for S3, Stubber for Bedrock

**S3 is tested with moto.** The store's value is S3 behaviour, and moto reproduces versioning, Object Lock, both preconditions and the version-delete denial. I checked all of this tonight. The tests:
- `put_once` twice raises.
- `put_blob` twice is idempotent.
- A stale HEAD compare-and-swap raises.
- Seal followed by `verify` passes.
- Tampering with a new version makes `verify` fail.
- `capabilities()` reads back the lock mode.
- Deleting a sealed version is denied.

**Bedrock, CloudWatch Logs and Budgets are tested with Stubber.** moto has no useful Converse, and Stubber catches malformed request dicts against the real service model. The tests:
- text turn, tool-use turn
- both image-delivery modes
- cost from cache-aware usage
- `UNPRICED` when the price is null
- throttle, then a backoff span
- the same-family rule and the vision rule

**Probe.** moto plus Stubber produce a golden `aws-capabilities.json`, which is schema-checked.

### CDK

`tests/infra/test_synth.py` begins with `importorskip("aws_cdk")` and skips when `which("node")` finds nothing. It asserts:
- The runs bucket has versioning `Enabled`, and `ObjectLockEnabled` under the context `object_lock=governance`.
- BlockPublicAccess is fully on for every bucket.
- The key-bucket policy has `Deny s3:*` for the worker role.
- No role grants `s3:BypassGovernanceRetention`.
- The log group exists, with retention set.

CI runs `uv sync --group dev --extra infra`. **Tests never need the CDK CLI or credentials.**

### Method tests

The statistics seats own these. They cover PPI coverage simulation, λ=1 below n_gold 50, Horvitz-Thompson unbiasedness, placebo and test-retest, Rogan-Gladen abstention, B0–B2, the abstain rule, planted errors, shuffled labels, evidence-in-trace, forbidden sources and canary decoys.

### Golden tests

- The planted-trace replay produces a byte-identical scorecard.
- A license scan fails on any PNG, JPEG or TIFF magic bytes or base64 image prefix in `fixtures/`, `tasks/` or `docs/`.

## I7. Ordered package plan

Each package is one branch and one PR, tests first, merged when green. **The AWS pack (P7) is built offline overnight and merged by about H7, so in the morning Kiro only runs code and never writes it.**

| # | Package | Size | Acceptance | AWS |
|---|---|---|---|---|
| P0 | scaffold, offline guard + env scrub, ruff, CI | 0.5h | canary network test | no |
| P1 | schemas, JSON Schema, 3 cards, `validate` | 1.5h | golden diff; India stub validates | no |
| P2 | local store, chain, manifest, `verify`, backends resolver | 1.5h | tamper test | no |
| P3 | per-trial JSONL tracer, semconv pin | 1h | chain + frozen-trace test | no |
| P4 | fake + replay providers, registry, prices, **budget guard + ledger** | 1.5h | guard property tests | no |
| P5 | gateway + MCP tools on synthetic fixtures | 2h | forbidden, as_of and evidence-ref tests | no |
| P6 | plain loop + Strands adapter (FakeModel) | 1.5h | same script gives same claims in both | no |
| **P7** | **Bedrock adapter (Stubber), S3 store (moto), probe, cwlogs/otlp, `infra/` + synth tests, `store push`** | 2.5h | `aws_offline` + `infra` green | built offline; **runs in K1–K8** |
| P8 | rules, keyed grader, cluster bootstrap | 1.5h | Virginia fixture grade | no |
| P9 | verifier sampling, controls, blinding | 2h | inclusion-probability + blindness tests | no |
| P10 | PPI, Rogan-Gladen, B0–B2, abstain, passport | 2h | method tests | no |
| P11 | panels, summary lint, HTML report, CLI | 2h | golden report | no |
| P12 | planted-trace demo, `make demo` | 1h | fresh-clone CI job | no |
| P13 | read-only MCP | 1h | in-process Client test | no |

- **Cut order:** P13, then OTLP (keep cwlogs), then the Object Lock CDK context (keep versioning), then the Strands adapter (keep the plain loop).
- **Never cut:** P0–P5, the Bedrock, S3 and probe parts of P7, and P12.
- **Offline demo:** `uv sync && uv run treehouse replay fixtures/runs/planted && uv run treehouse report …`.

**Budget guard (P4).** The control of record is a cumulative ledger in `~/.treehouse/spend.jsonl`, mirrored to `s3://…/spend/` after every trial so it survives a Kiro session reset. The thresholds are `planned=250`, `alarm=350` and `hard_stop=450`.
- **Before every live call**, the guard reserves the worst-case cost: the input estimate × the input price, plus `max_tokens` × the output price.
- **Spent plus reserved above $450** raises `BudgetHardStop`. From then on only replay is allowed.
- **Above $350**, a run needs `--allow-over-alarm` and a logged reason.
- **Above $250**, the guard warns.
- **A model with a null price** is refused for live calls unless `--unpriced-cap-usd` is given.
- **The $50 gap below the $500 cap** absorbs billing lag and non-Bedrock spend: KMS (about $1 per month), S3 and Logs.
- **AWS Budgets is secondary**, used if the account allows it: a $350 budget with ACTUAL notifications at 100% and FORECASTED notifications at 90%.
- **Property tests:** no random call sequence takes the ledger past the hard stop, and a replay costs $0.

## I8. Kiro prompts (paste in order)

**Preamble for every prompt:** "Repo <url>; `git pull`; `uv sync --extra aws --extra strands`. Never commit pixels, credentials or `~/.treehouse/cache`. Before any Bedrock call run `uv run treehouse budget status`, and stop and ask me if spend is over $350. Commit to the branch `kiro/<step>` and push."

**K1 Probe (15 min, under $1).** "Run `uv run python scripts/aws_probe.py --region us-east-1 --out aws-capabilities.json --cleanup`. Classify every check as ok, denied, unavailable or error, and never abort. Then show me the summary table, run `uv run treehouse probe import aws-capabilities.json`, and commit the JSON and the updated registry." The checks:
- **Locus:** STS identity; hostname, disk, CPU; whether node, cdk and docker are present; whether `aws configure export-credentials` works.
- **Bedrock:**
  - `ListFoundationModels` (image input) and `ListInferenceProfiles`.
  - Per candidate: a 20-token text Converse, and a 64×64 synthetic-PNG Converse in both image-delivery modes.
  - A 5-call burst to observe throttling.
  - `CountTokens` and `GetModelInvocationLoggingConfiguration`.
- **S3:** a versioned bucket; an Object Lock bucket; a put-once write; a version delete denied under a 5-minute governance RetainUntilDate.
- **Other services:**
  - KMS `CreateKey`, scheduled for deletion on cleanup.
  - Logs `PutLogEvents`, and one OTLP span POST.
  - Budgets `DescribeBudgets`.
  - Read-only list calls for Lambda, Athena, Step Functions and AgentCore.
  - Whether the `CDKToolkit` stack exists.

The output has this shape:

```
{schema:"treehouse.aws-capabilities/v1", probed_at, account_hash, region,
 locus:{mode:"local-creds"|"kiro-terminal", disk_gb, node, docker},
 checks:[{id, status, detail, latency_ms, est_usd}],
 bedrock:{models:[{model_id, profile, vision, image_delivery_ok, throttled}]},
 recommended_backends:{…}}
```

**K2 Vision smoke test and model choice (30 min, under $8).** "Steps:
1. From https://aws.amazon.com/bedrock/pricing/ or the console, fill `data/prices/bedrock-us-east-1.2026-11-04.yaml` for every available model, including `retrieved_at` and `retrieved_by`. Then run `treehouse prices check`.
2. Run `uv run treehouse smoke vision --task tasks/nepal-bridges.yaml --windows fixtures/smoke/windows.yaml --models all-available-vision --n 12`. That is 12 Vantor 0.5 m windows; crops go to the cache only.
3. Per model, report agreement with `fixtures/smoke/labels.sealed.json`, the `cannot_assess` rate, tokens per image, $ per call and p50 latency.
4. Pick the best vision model as the worker. Pick as verifier the best model from a different family that costs at most 20% of the worker; if none qualifies, take the cheapest acceptable one and flag it.
5. Write `docs/decisions/model-choice.md` with the numbers and commit."

**K3 First live keyed run (30 min, under $15).** "Run `uv run treehouse run tasks/virginia-solar.yaml --config configs/live-keyed.yaml --trials 1 --record`, then `check`, `score` and `report`. Confirm the manifest shows `backends_resolved.model.worker.ran=bedrock` and that no cost is `UNPRICED`. Paste the p90 cost per run. Run `treehouse budget plan`, which computes N_total = floor(budget / p90), and commit `docs/decisions/n-plan.md`."

**K4 First Nepal run (45 min, under $30).** "First commit `gold-seed.txt` by running `treehouse gold draw --seed-file gold-seed.txt`, and push it before you show me any verifier output. Then run `uv run treehouse run tasks/nepal-bridges.yaml --config configs/live-nepal.yaml --trials 3 --record`, then `check --verifier` (blind, sampled, controls on). Confirm the verifier is from a different family. Report whether there were zero `key_access_attempt` spans, or list them. Commit sealed metadata only."

**K5 Record cassettes (20 min, $0).** "For every sealed run, run `treehouse cassette export <run_id> --pixel-free --out fixtures/cassettes/`. Then, with `TREEHOUSE_OFFLINE=1`, run `treehouse replay <cassette>` and `uv run pytest tests/golden -k replay`. Confirm the scorecards are byte-identical. Run the license scan, then commit."

**K6 CDK deploy (30 min).** "In `infra/`, run `npx aws-cdk@2 synth -c object_lock=governance:1 -c worker_principal=<arn from aws-capabilities.json>`.
- If the `CDKToolkit` stack is missing, try `cdk bootstrap`. If that is denied, synth with `-c synth=bootstrapless` (we ship no assets) and run `aws cloudformation deploy --template-file cdk.out/TreehouseStore.template.json --stack-name TreehouseStore --capabilities CAPABILITY_NAMED_IAM`. Do the same for Keys and Obs.
- Then run `treehouse probe verify-infra`. It reads back versioning and Object Lock, does a canary key `GetObject` as the worker role, and does a version delete as the worker role. Both must be AccessDenied.
- Commit `infra/outputs.json`. Record any denials; the manifest reports them automatically."

**K7 Push sealed runs to S3 (10 min).** "For each run, `treehouse store push <run_id> --to s3://<runs bucket>`.
- **Do not use `aws s3 sync`.** It overwrites objects and has no put-once.
- Then run `treehouse verify --store s3://<runs bucket>` and `aws s3api list-object-versions --bucket <runs bucket> --prefix chain/HEAD`. Screenshot the version list.
- Try a version delete as the worker role **through the CLI**, and capture the AccessDenied. Do not use the console: it sends the governance-bypass header by default."

**K8 CloudWatch tracer check (15 min, under $2).** "Set `backends.tracer: [jsonl, cwlogs]`, adding `otlp` if K1's OTLP check passed. Replay one sealed run with `--reexport-traces`; this makes no model calls. Then run `treehouse trace reconcile <run_id> --cloudwatch`. Paste the comparison of span counts and token totals. If Transaction Search cannot be enabled, keep `cwlogs` only and note it."

## I9. Risks (AWS-centred)

1. **Kiro-terminal locus and session timeouts.** Each trial is sealed on its own so runs can resume, the ledger is mirrored after every trial, and K stays small.
2. **The participant role is not the worker role**, so the Deny may not bind our own process. The live canary decides what the manifest says.
3. **Images inside tool results may be unsupported for some models.** `user_turn` is the fallback.
4. **Model ids drift, and prices are unfilled tonight.** Ids live only in the registry, which the probe rewrites. Costs show `UNPRICED` and live calls are refused without a cap.
5. **Billing lags.** The in-app guard is primary, with a $50 margin.
6. **CDK bootstrap may be denied.** Fall back to bootstrapless synth plus `cloudformation deploy`.
7. **Leaky offline tests from the proxy-injected credentials.** Handled by the env scrub, the socket guard and the canary test.
8. **moto fidelity gaps.** K6 `verify-infra` is the real check.
9. **Throttling caps N.** Size N from the observed throughput, not only from dollars.
10. **Unfetched AWS doc details** (the OTLP endpoint and Transaction Search). K1 and K8 test them live.
