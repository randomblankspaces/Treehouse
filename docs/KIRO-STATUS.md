# Kiro build status

Live log of what Kiro ran against the Workshop AWS account, with artifacts and blockers. Account IDs/ARNs
are redacted to role/resource names. One section per task.

Region: us-east-1. Identity: `WSParticipantRole` (assumed-role session).

---

## Task 0 — Environment and AWS foundation

**Status:** done (one non-blocking blocker recorded).

### Environment
- `uv sync --locked --all-extras` — ok (added CDK/FastAPI extras).
- `uv run pytest` baseline — **green**, 3 skipped, 0 failed (on `origin/main` @ `56e9182`). The failures
  listed in `probe-report.json` were against a stale local `main`; the current `main` is clean.
- `ui/`: `npm ci && npm run build` — ok (vite build, 288 kB JS bundle).
- `uv run treehouse budget status` — ok, ledger `$0.1053`, under $350 alarm.

### AWS foundation (CDK)
- `cdk bootstrap aws://<redacted>/us-east-1` — ok (CDKToolkit stack created; account was not bootstrapped,
  per probe).
- `cdk deploy --all -c retention_days=1 -c lock_mode=compliance` — ok after the OnlineEval fix below.
- Stacks deployed and verified live:
  - **TreehouseRunStore** (`CREATE_COMPLETE`): sealed run store S3 bucket with **Object Lock COMPLIANCE,
    1-day default retention** + versioning (both verified via `get-object-lock-configuration` /
    `get-bucket-versioning`); KMS-encrypted key bucket with an explicit Deny for the worker role; worker +
    grader IAM roles.
  - **TreehouseEval** (`CREATE_COMPLETE`): two code-based evaluator Lambdas
    (`treehouse.aws.lambda_evaluator.handler`) and their AgentCore Evaluator registrations.
    `list_evaluators` confirms `treehouse_rules` and `treehouse_guard` are **ACTIVE**; both Lambda
    functions exist.
- Outputs committed (account redacted): `infra/cdk-outputs.json`.

### CloudWatch Transaction Search (AgentCore Observability prerequisite)
- Created CloudWatch Logs resource policy `TransactionSearchAccess` granting `xray.amazonaws.com`
  `PutLogEvents`/`CreateLogStream` on `aws/spans` and `/aws/application-signals/data` (scoped by
  `aws:SourceAccount` / `aws:SourceArn`).
- `UpdateTraceSegmentDestination(Destination=CloudWatchLogs)` and
  `UpdateIndexingRule(Default, Probabilistic 100%)` applied. Destination reports `CloudWatchLogs` /
  status `PENDING`; activation completes asynchronously (minutes). Re-check with
  `aws xray get-trace-segment-destination`.

### Blocker (non-blocking, worked around)
- **AgentCore `OnlineEvaluationConfig` create fails** with `ValidationException: One or more specified log
  groups do not exist`. The config references a hosted-agent log group
  (`/aws/bedrock-agentcore/runtimes/treehouse-DEFAULT`) that does not exist because no AgentCore Runtime is
  hosted yet (that is KA3 / a "Could"-tier step). The control plane validates the log group at create time
  even though the config ships `DISABLED`.
  - **Workaround:** gated the `OnlineEvaluationConfig` behind `-c online=true` in `infra/app.py` /
    `EvalStack(..., with_online=...)`, default off. The two evaluators + Lambdas (the Must-tier pieces)
    deploy without a runtime. Enable online eval later once a runtime log group exists.

### Artifacts
- `infra/cdk-outputs.json` (redacted), `infra/treehouse_infra.py` + `infra/app.py` (online-eval gate).
- `aws-foundation.json` (deployed resource ids, redacted; repo root, like `aws-capabilities.json`).
