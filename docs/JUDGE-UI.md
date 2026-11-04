# Judge evidence workbench

The workbench asks one bounded question through the server's AgentCore Runtime adapter. It does not deploy resources or call AWS on startup, page refresh, or receipt download. The existing trust implementation is separate and is not displayed as challenge evidence.

From the repository, install the locked API extra and start an empty preview:

```sh
uv sync --locked --extra api
uv run --extra api treehouse judge serve
```

Open http://127.0.0.1:8765. For live questions, run in Kiro/AWS with the AWS extra and a server-owned configuration produced by provisioning:

```sh
uv sync --locked --extra api --extra aws
uv run --extra api --extra aws treehouse judge serve --config /absolute/path/judge-config.json
```

Only pressing **Ask agent** starts a Runtime invocation, which may call Bedrock and tools. Runtime, KB and storage charges are not covered by the existing model-dollar ledger. IAM credentials stay on the server. Do not include secrets in questions; questions go to the configured AWS Runtime. The UI makes one request at a time, caps questions at 2,000 characters, imposes a five-second cooldown and a 130-second application timeout (aligned with the adapter’s 120-second SDK read timeout and Runtime’s 100-second work guard), and retains the busy slot until a timed-out backend exits. A timeout does not guarantee that AWS processing or billing stopped. Local status polling runs every 1.5 seconds while busy; a late valid answer is retained and appears without another paid call or page reload. The Runtime adapter must also bound SDK/network timeouts and the deployed agent's work.

For a Kiro port preview, bind deliberately and specify its exact browser origin (scheme and hostname, no trailing slash):

```sh
uv run --extra api --extra aws treehouse judge serve --config /absolute/path/judge-config.json --host 0.0.0.0 --origin https://YOUR-EXACT-PREVIEW-HOST
```

Keep the preview private. This small operator workbench is not an authenticated multi-user service. Exact Host/Origin checks reject alternate hosts and cross-origin submission; no wildcard CORS, browser-supplied resource overrides, uploads, or filesystem paths are accepted. A reverse proxy must preserve the configured public Host. For a different local address use `--origin http://localhost:8765` and browse that exact address.

## Configuration and recorded evidence

Configuration schema `treehouse.judge-config/1` requires `region`, `runtime_arn`, `gateway_url` (HTTPS), `gateway_id`, `knowledge_base_id`, and `model_id`. `evidence_dir` is an optional server setting, not exposed to the browser. Invalid configurations and mismatched receipt resource IDs stop startup. Configuration contains resource identifiers, never access keys.

The receipt schema `treehouse.judge-invocation/1` follows the shared judge Runtime contract. It contains answer, citations, tool calls, Gateway catalog, resource IDs, session, Runtime request ID, timezone-bearing capture timestamp, and source. Unknown fields (including arbitrary success booleans), malformed citations, future timestamps, and receipts larger than 1 MB are rejected. Tool arguments/results and answers are rendered as text, never executable HTML. Before status or export, the server recursively redacts credential-bearing keys and known AWS access key, bearer, authorization and private-key strings in answers, citations and nested traces. Arbitrary prose cannot be perfectly classified as secret; use owned public project documents and never put secrets in questions or source documents. Credential-bearing source URLs, including signed query parameters, are rejected. HTTP(S) citations require a host and open separately; S3 sources require a bucket and nonempty object key and remain visible text. Tool names reject whitespace variants; catalog proof counts distinct validated identifiers.

Inspect an operator-supplied exported receipt without making an AWS call:

```sh
uv run --extra api treehouse judge serve --recorded /absolute/path/receipt.json
```

Use `--config` as well to enforce receipt resource matches against the deployment. Imported receipts are always **Recorded AWS receipt**, even if JSON claims live; `source: sample` remains **Sample · unverified**. Recorded means operator-supplied historical observations, not independently authenticated AWS provenance. Receipts older than 24 hours are flagged. Download exports only validated receipt fields and preserves recorded/sample provenance. It does not export the prompt or server credentials. The latest receipt lives in memory; restart clears it unless `--recorded` is supplied.

## Evidence checks

- **Know Your Stuff:** a nonempty answer plus a citation with a nonempty URI and source quote; resource identity must match configured KB. A citation without a quote is displayed but cannot meet this check.
- **Gateway Builder:** at least three distinct nonempty catalog names and a non-error call to a catalog tool with a nonempty result.
- **Ship It:** a nonempty Runtime answer and request ID from the invocation adapter.

These are observations from a returned receipt, not cryptographically signed AWS attestations or guarantees that a challenge submission will be accepted. Live requires a fresh server backend response; recorded rows remain recorded; sample rows never become observed. Backend failures preserve the previous receipt and the error explicitly identifies it as previous evidence. There is no false trust/Rely status.

## Verification

```sh
uv run --extra api pytest tests/unit/test_judge_ui.py tests/unit/test_import_boundary.py
uv run ruff check src/treehouse/judge src/treehouse/cli.py tests/unit/test_judge_ui.py
```

All test backends are explicitly synthetic and make no AWS calls. API tests cover malformed/oversized/cross-origin inputs, resource mismatch, recorded/sample provenance, age, missing evidence, tool errors, redacted failures, busy and timeout handling, and receipt export. Browser evidence is recorded separately in the integration handoff; a local render cannot establish deployed Runtime, Gateway, KB, IAM, or billing behavior.
