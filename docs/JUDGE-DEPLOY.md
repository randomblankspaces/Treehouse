# Kiro handoff: three live AWS challenge gates

This path is implemented locally and tested offline. No deployment or paid AWS
invocation has been performed on the Mac. The three live challenge gates remain
**pending Kiro** until the exported receipt contains actual service evidence.
Existing geospatial benchmark and T1 trust wiring are outside this path.

The approved architecture is: judge UI → IAM InvokeAgentRuntime → standalone
Strands agent → SigV4 MCP Gateway → Lambda search tool → Bedrock KB RAG. Two more
Lambda tools list task cards and explain public rules. The KB ingests only
`docs/judge-knowledge/treehouse-public.md`, our owned public demonstration note.
Its distinctive fact is **Cedar Lantern 47**. This is project demonstration data,
not scientific field data. Do not upload private imagery or answer keys.

## Prepare in Kiro, without paid calls

Use the merged reviewed checkout in the authorized Kiro AWS terminal. Commands
below run from the repository root. AWS region is explicitly `us-east-1`; an
ambient `AWS_REGION=us-west-2` must not redirect these resources.

```sh
uv sync --locked --extra aws --extra strands --extra api
uv run python scripts/judge_deploy.py
uv run python deploy/judge_runtime/build.py --output "$PWD/outputs/judge/runtime-arm64.zip"
```

The first command resolves the reviewed project lock. The deployment plan makes
zero AWS calls and does not construct a credential provider. Packaging downloads
public Python wheels, not AWS resources, and checks every native library is an
ELF AArch64 binary. The zip has `main.py` plus the dependencies at its root, uses
644 file modes, omits bytecode, and fits the 250 MB compressed / 750 MB unpacked
limits. Do not zip the Mac `.venv`. Direct requirements pin Strands 1.63.0 and
boto3 1.43.123; transitive wheels resolve at package time. Retain the resulting
artifact SHA-256 in deployment state as the reproducible artifact identity.

Local outputs on a Mac must stay under `/Users/suhas/Codex`; the default repository
already meets that requirement. In Kiro, use its checkout-local `outputs/judge`.
No AgentCore CLI bootstrap or Transaction Search enablement is needed.

## Spend decision before applying

Working budget for these three challenges is **$15**, stop threshold **$25**.
First inspect the existing Workshop/account spend and keep its **$350 warning /
$450 hard stop** policy. Stop this path if remaining account headroom is unclear.
The apply flag explicitly acknowledges the $25 threshold; it is **not an AWS
billing hard cap**. Billing is delayed. Existing Treehouse model ledger does not
meter this separate Runtime/KB path, ingestion, Lambda, S3 Vectors, log retention,
or idle session compute. Check current official service pricing and account
billing in Kiro before proceeding; record estimated and observed costs there.

Each request caps Strands at four model turns × 900 output tokens and five
Gateway tool attempts. Each KB generation caps output at 600 tokens and retrieves
three chunks. Runtime sessions idle out after 60 seconds with a 300-second maximum
lifetime. Calls are sequential, per-hop timeouts are bounded, and there are no
background paid calls or automatic model retries. The 100-second tool/model
budget is checked between operations; an in-flight service call can extend it.
Only submit a handful of judge questions; these technical bounds do not establish
a measured dollar maximum. Stop new calls at $15 estimated incremental spend,
and do not exceed $25. IAM explicitly denies Bedrock batch-job creation on all
four new roles. No expensive OpenSearch fallback is created if S3 Vectors fails.

## Apply in Kiro only

Applying needs IAM create/pass-role and scoped policy rights, private S3 bucket
creation, S3 Vectors, Bedrock KB/data source/ingestion, Lambda, and AgentCore
Gateway/Runtime control-plane permissions. Model access is required for Titan
Text Embeddings V2 and Amazon Nova Lite. Account SCPs or workshop policies may
deny these; report the exact denial and stop rather than weaken policies or
claim success. The Runtime and Gateway use IAM authorization, never browser keys.

```sh
uv run python scripts/judge_deploy.py --apply --kiro --acknowledge-spend 25 \
  --runtime-zip "$PWD/outputs/judge/runtime-arm64.zip" \
  --state "$PWD/outputs/judge/deploy-state.json"
```

The script refuses apply on macOS. It persists identifiers after resource stages,
persists one cryptographically random source/code bucket name before first creation,
looks up the other deterministic resource names, uses client tokens for KB/ingestion, waits at most
10 minutes per stage, and validates every SDK request against installed botocore.
Re-run the **same command and artifact** after a transient IAM propagation or
pending-state timeout. It reuses resources and skips completed document ingestion.
It does not delete resources or silently update deployed Lambda/Runtime code.
Ownership tags, role, embedding/vector storage, source bucket/prefix/chunking,
Gateway IAM/target credentials and Runtime artifact/network/lifecycle are read
back and compared before adoption. A KB with unexpected extra data sources is
refused. Existing vector bucket policy is compared with the expected policy: an
identical policy is left alone; an absent policy on the owned bucket is created;
a different policy stops deployment without replacing any grants.
If code/artifact/config differs, stop and review a targeted update; do not choose
a new prefix merely to bypass a failure and duplicate costs. Failed ingestion observations and failure history are persisted in state. An
ordinary rerun observes the same job and stops without starting another one. After
diagnosing and correcting the actual cause, authorize one new bounded attempt:

```sh
uv run python scripts/judge_deploy.py --apply --kiro --acknowledge-spend 25 \
  --runtime-zip "$PWD/outputs/judge/runtime-arm64.zip" \
  --state "$PWD/outputs/judge/deploy-state.json" --retry-failed-ingestion
```

That flag creates at most one new attempt per invocation, with a maximum of three
persisted attempts for a document/source context. A new token is saved before the
StartIngestionJob call, so an interruption reuses that attempt instead of spawning
a second job. Successful unchanged ingestion is read back and remains idempotent.
A COMPLETE job with failed documents is treated as failure. Changing state by hand
does not establish recovery or reset the authorized budget.

S3 bucket recovery uses current ownership tags, never a previous acknowledgement.
The deployment persists a cryptographic 12-hex nonce and the complete bucket name
before its first CreateBucket call. At the maximum prefix length, the name is 61
characters (within S3's 63-character bound). Reruns retain that exact name; there
is no automatic new-name retry or prefix change that creates resource sprawl.
Legacy state naming an existing deterministic bucket may reuse it only when its
current expected ownership tags verify; a missing legacy bucket needs an explicit
recovery decision rather than another deterministic CreateBucket.

For a new randomized name, the script tags the bucket immediately after creation,
then reads the tags before any encryption/public-access configuration or other
resource provisioning. The create response is retained only as diagnostic history
and marked after ownership tag readback. In us-east-1, a successful CreateBucket
can return 200 for an already-owned bucket and reset its ACLs; 200 is not proof of
a new bucket incarnation. Random naming reduces the concurrent-name collision
risk; it is not an AWS transaction or ownership attestation.

Every existing untagged or unexpectedly tagged bucket is refused, even if state
contains a successful old create receipt. This also prevents a stale receipt from
a deleted bucket authorizing adoption of its untagged replacement. An interruption
between create and tagging therefore safely **stops on rerun**; it does not recover
automatically. Preserve state and perform read-only Kiro inspection of caller
identity, owner/region, CloudTrail CreateBucket event/request ID, current tags and
any intervening deletion/recreation. Present that concrete evidence for a manual
operator proof/tag decision. Do not delete state, change prefix, add tags or edit
receipts merely because the bucket name looks right. Existing-name collisions,
unexpected role trust, mismatched target schema or resource readbacks stop the
script.

The KB uses S3 Vectors with a 1024-dimension float32 cosine index. Reserved
`AMAZON_BEDROCK_TEXT` and `AMAZON_BEDROCK_METADATA` are nonfilterable. S3 source and
code objects are private/encrypted. Nothing adds Object Lock or irreversible
retention. The final `judge-config.json` is written only after KB ingestion and
Gateway/target/Runtime ready-state readbacks. This is deployment readiness,
**not** proof that a live answer works.

## One paid smoke, then show the judge UI

```sh
uv run python scripts/judge_smoke.py \
  --config "$PWD/outputs/judge/judge-config.json" \
  --output "$PWD/outputs/judge/proof.json"
uv run python scripts/judge_smoke.py --invoke --kiro \
  --config "$PWD/outputs/judge/judge-config.json" \
  --output "$PWD/outputs/judge/proof.json"
```

The first command prints a no-call plan. The second makes exactly one Runtime
invocation with a fresh UUID session, saves actual JSON before checking gates,
and attempts to stop the session. A failure exits nonzero. Retain the receipt,
state, config, deployment zip checksum and any actual AWS denial/request IDs.
Never hand-edit successful proof or replace missing citations with expected text.

The receipt must show a nonempty answer and AWS Runtime request ID; at least three
actual catalog names; an actual successful Gateway call with request ID; and an
actual S3 source citation with nonempty retrieved quote. The question asks about
Cedar Lantern 47, so inspect whether the answer and source quote support that
fact. A nonsensical answer can pass transport checks and still fail the challenge.
Gateway tool results carry the Lambda/KB request IDs too. Session and configured
resource identifiers are checked by the server adapter. Missing facts remain
missing; no status flag from the model can assert success.

Launch the UI as documented in `docs/JUDGE-UI.md`:

```sh
uv run --extra api --extra aws treehouse judge serve \
  --config "$PWD/outputs/judge/judge-config.json" --host 0.0.0.0 \
  --origin https://YOUR-EXACT-PREVIEW-HOST
```

Use the exact preview origin without a trailing slash. Open the Kiro port
preview, ask the marker question, expand tool/runtime evidence and export its
`proof.json`. Browser code never receives IAM credentials. Recorded proof imports
are labeled recorded; offline fixtures remain unverified. A live submit is an
explicit paid invocation. Slow cold calls can outlast the UI request window; wait
for local status recovery instead of clicking submit repeatedly.

## Recovery and end of demo

On `AccessDenied`, preserve the service operation, request ID and error, then
report the missing permission. On KB citation failure, inspect ingestion status
and actual retrieval; do not fabricate a quote. On catalog/tool mismatch, inspect
Gateway target status and Lambda context name `project___search_project_docs`.
On Runtime errors inspect its ready state, execution role, environment and ARM64
archive. Resource state is useful diagnosis, not successful challenge proof.

At the end, stop any known Runtime sessions (smoke does this automatically) and
stop submitting paid questions. Review the IDs in deployment state for teardown:
Runtime, Gateway target then Gateway, Lambda, KB data source then KB, vector index
then vector bucket, source/code objects then S3 bucket, and four project roles.
Deletion is deliberately not automated: retain proof first and ask for approval
before destructive cleanup. Charges can continue for stored resources/logs until
removed; record any resources intentionally left running. This challenge path
adds no immutable retention.

## Verified sources and local evidence

Official AWS docs read for this implementation on 2026-11-04:

- [Direct Python CodeZip deployment](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-code-deploy-python.html): ARM64 wheels, S3 CodeZip, entry point and HTTP endpoints.
- [Lambda Gateway targets](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-add-target-lambda.html): inline tool schemas and exact `context.client_context.custom` tool name.
- [IAM Gateway inbound authorization](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-inbound-auth.html): AWS_IAM and resource-scoped InvokeGateway.
- [S3 Vectors KB prerequisites](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-setup.html): reserved metadata and mutually exclusive index reference forms.
- [S3 Vectors KB integration](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-bedrock-kb.html).
- [S3 CreateBucket API](https://docs.aws.amazon.com/AmazonS3/latest/API/API_CreateBucket.html): us-east-1 legacy 200/ACL-reset behavior; acknowledgements are diagnostic only.
- [Runtime execution role](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html).

`tests/test_judge_aws.py` runs offline: botocore streaming Stubber, real installed
Strands loop with scripted model/fake Gateway, Lambda citation parsing, SigV4/SSE,
request shape validation across provisioning and idempotent rerun, actual loopback
HTTP envelope and redirect rejection. The optional AgentCore Python SDK is not
installed locally; this Runtime uses the documented HTTP contract directly. These tests do
not measure AWS latency, actual access, model behavior, ingestion compatibility or
physical hardware. Kiro live gates remain required.
