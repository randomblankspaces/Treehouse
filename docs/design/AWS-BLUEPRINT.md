# Treehouse on AWS: blueprint, routing rule and Kiro prompts (T3)

Status: prototype, 2026-11-04. Code: `infra/` (CDK, Python), `src/treehouse/aws/` (AgentCore adapter and
Lambda evaluator), `scripts/agentcore_eval.py`. Everything here is tested offline (botocore Stubber, CDK
assertions); nothing has been deployed yet. KA0-KA3 below are the live steps, run by Suhas through Kiro in
Workshop Studio, region **us-east-1**. Principle from A10: AWS-native, not AWS-locked; every AWS piece has a
local stand-in and the manifest records which ran.

## 1. What runs where

| Job | AWS service | Code | Local stand-in | State |
|---|---|---|---|---|
| Worker and verifier models | Bedrock Converse (Strands) | `providers/bedrock.py` | Ollama / fake provider | existing |
| Sealed run store | S3, versioned, **Object Lock GOVERNANCE with default retention** (1 day; `-c retention_days=N`) | `RunStoreStack.run_store` | content-addressed dir + hash chain + `treehouse verify` | CDK, synth-tested |
| Key isolation | Separate S3 key bucket, KMS CMK (rotation on), **explicit Deny for the worker role** in both the bucket policy and the key policy | `RunStoreStack.key_bucket`, `.key_kms` | key dir outside the worker volume | CDK, synth-tested |
| Roles | Worker (Bedrock invoke, run-store read + put + `PutObjectRetention`; no delete, no `BypassGovernanceRetention`), grader (read runs and keys) | `RunStoreStack.worker_role`, `.grader_role` | none | CDK, synth-tested |
| Treehouse checks inside AWS | Lambda, Python 3.12, `treehouse.aws.lambda_evaluator.handler`, bundle = `src/treehouse` + pydantic (8 MB) | `EvalStack.functions` | in-process `checks.rules` | CDK + unit-tested handler |
| Evaluator registration | AgentCore Evaluations code-based evaluators `treehouse_rules` (TRACE: R1, R2, R4 per trial) and `treehouse_guard` (SESSION: forbidden-source access, cost / tool-call / byte limits) | `EvalStack.rules`, `.guard` (L2 `aws_bedrockagentcore.Evaluator`) | `lambda_evaluator.handler` called directly | CDK, synth-tested |
| Comparison column | AgentCore `Evaluate` (on demand) with built-ins `Builtin.TrajectoryInOrderMatch` / `ExactOrderMatch` / `AnyOrderMatch`, `Builtin.GoalSuccessRate`, `Builtin.Correctness` and the two Treehouse evaluators | `aws/agentcore.py`, `scripts/agentcore_eval.py` | none (Strands evals, if ever) | Stubber-tested |
| Online monitoring | AgentCore `OnlineEvaluationConfig` over a CloudWatch log group (stack parameters `AgentLogGroup`, `AgentServiceName`), sampling 10 %, **DISABLED** at deploy | `EvalStack.online` | none | CDK, synth-tested |
| Logs | CloudWatch log groups, 7-day retention | `EvalStack` | JSONL | CDK |

**Keyed vs unkeyed maps onto on-demand vs online.** AgentCore refuses ground-truth evaluators in online
configs. Treehouse's keyed work (trajectory, assertions from `must_notice` / `known_limits`, and an expected
response for keyed steps only) goes through on-demand `Evaluate` with `evaluationReferenceInputs`; the
reference-free Treehouse evaluators are the only ones wired into the online config.

**Comparison, never a panel input.** `record_results` writes the raw AgentCore JSON append-only (write-once,
content-addressed, read-only file) to `<store>/comparisons/agentcore/<run_id>/<sha256>.json`, keyed by the
run's manifest hash. It lives outside `runs/` and `evals/`, so `treehouse verify` and the scorecard never
read it. (It is not in the store ledger yet: that needs `"agentcore"` added to `store.base.EVAL_KINDS`,
which is outside T3's files.)

**How a run reaches AgentCore.** One sealed run = one AgentCore session (`session.id` = run id), one trial =
one trace. Spans keep every `gen_ai.*` and `treehouse.*` attribute and are reshaped into the OTel span-log
record that `aws/spans` holds (`traceId`, `spanId`, `parentSpanId`, `name`, `kind`, `*UnixNano`,
`attributes`, `status`, `resource`, `scope`). Each trial's root span also carries the card
(`treehouse.card`) and the trial's claims (`treehouse.claims`); each tool span carries its recorded result
(`treehouse.tool.payload`, `treehouse.tool.status`). The Lambda checks that `treehouse.task.hash` matches
the card it was handed and returns `VALIDATION_FAILED` otherwise. Spans over 6 MB are refused rather than
silently truncated by AgentCore.

## 2. Large-workload routing rule

Small stays local, because local is free, deterministic and replayable; AWS takes over only where a local
run would be too slow, too costly in egress, or impossible. The thresholds are starting points chosen from
the Workshop Studio budget ($450 guard), the Mac (M-series, 16 GB), and the service limits noted.

| Workload | Stay local while | Route to AWS when | AWS path | Why this number |
|---|---|---|---|---|
| Trials | ≤ 50 trials and ≤ 1 h estimated serial wall time, ≤ 8 in flight | either is exceeded | **Step Functions Distributed Map**, one child execution per trial; the agent loop runs on **AgentCore Runtime** (Strands), not in Lambda | Bedrock on-demand quotas, not CPU, cap concurrency at about 8 in our probe budget; Lambda's 15-minute ceiling is shorter than a long agent loop, so the map item starts a Runtime session instead |
| Verifier sweeps | < 1,000 verifier items, or the result is needed within the hour | ≥ 1,000 items and an overnight answer is fine | **Bedrock batch inference** (JSONL in S3) | batch jobs have a minimum record count (100, known record) and run asynchronously; below about 1,000 items the discount does not pay for the job set-up and the wait. Coverage of our model families is UNVERIFIED (A10): KA0 must list it |
| Imagery windows / rules near the data | ≤ 200 MB read per run (the synthetic card's byte budget) and the data is in the Mac's reach | > 200 MB per run, or > 500 windows, or data in another region | **Lambda in the data's region** (Vantor us-east-1; Clay / NAIP us-west-2) returning windows and hashes, never pixels to the repo | 200 MB is the existing card budget; above it, pulling over residential bandwidth dominates trial time and cross-region reads add egress |
| Embedding search over big areas | ≤ 1 M vectors (≈ 1.5 GB at 768-d float16) | > 1 M vectors, or the area spans many tiles | Parquet on S3 queried by **Athena** for filters and aggregates (DuckDB locally, same SQL); **S3 Vectors** for nearest-neighbour search | 1 M × 768-d fits comfortably in 16 GB RAM for numpy brute force; past that, a laptop scan stops being interactive. S3 Vectors index limits: check in KA0, not assumed |
| Hosted agent and online eval | the agent runs in the harness | a partner wants a hosted agent or continuous monitoring | **Strands on AgentCore Runtime** + `treehouse_online` enabled (KA3) | online eval reads the Runtime's spans from CloudWatch; it needs Transaction Search on once |

Every routed step writes the same chained JSONL and manifest as a local run; the manifest's `backends` block
records which path ran, so the same report and the same `treehouse verify` work for both.

## 3. Handoff: how Clay or ADB deploy this in their own account

1. Prerequisites: an AWS account with Bedrock model access in us-east-1, AgentCore Evaluations available
   (KA0 checks), `uv`, `node` (for the CDK CLI) and either `uv` or docker for bundling the Lambda.
2. `git clone` the repo, `uv sync --extra aws --extra infra`.
3. `cd infra && npx -y aws-cdk@2 bootstrap && npx -y aws-cdk@2 deploy --all --outputs-file cdk-outputs.json`.
   Stacks: `TreehouseRunStore` (buckets, KMS key, roles) and `TreehouseEval` (two Lambdas, two evaluators,
   one disabled online config). Options: `-c retention_days=30` for a longer lock, `-c agentcore=false` where
   AgentCore is unavailable (Lambdas still deploy), `-c bootstrapless=true` for the run store alone when
   bootstrap is not allowed (then `aws cloudformation deploy --template-file
   cdk.out/TreehouseRunStore.template.json --stack-name TreehouseRunStore --capabilities CAPABILITY_IAM`).
4. Point Treehouse at it: run-store bucket and role ARNs come from `cdk-outputs.json`.
5. Evaluate any sealed run: `uv run python scripts/agentcore_eval.py --run <store>/runs/<id> --evaluators ...`.
6. Retention is the one irreversible choice: Object Lock cannot be turned off on the bucket, and GOVERNANCE
   objects can only be removed early by a principal with `s3:BypassGovernanceRetention`. Both buckets and the
   KMS key are `RETAIN` on stack delete, so tearing down the stack never deletes evidence.
7. Cost at rest: one KMS key (about $1 a month), S3 storage for runs (cents), Lambdas and log groups idle at $0.
   Evaluators and a disabled online config cost nothing until called.

## 4. Kiro prompts

Each prompt starts with the **Shared preamble** from `TODO.md` (paste it in place of `<preamble>`). KA1
supersedes the CDK part of K7 for these stacks (there is no `infra/README.md`; this file is the reference).
AgentCore's LLM-judged evaluators bill model tokens to the account; those are **not** in the Treehouse spend
ledger, so each prompt below states its own stop rule.

### KA0. AgentCore availability and Transaction Search status (5 min, $0, read-only)

```
<preamble>
Read-only: do not create, enable or change anything.
1. aws sts get-caller-identity
2. aws bedrock-agentcore-control list-evaluators --region us-east-1 --max-results 50
3. aws bedrock-agentcore-control list-online-evaluation-configs --region us-east-1
4. aws cloudformation describe-type --type RESOURCE --type-name AWS::BedrockAgentCore::Evaluator --region us-east-1 --query '{arn:Arn,visibility:Visibility}'
5. aws xray get-trace-segment-destination --region us-east-1      # Transaction Search: want Destination=CloudWatchLogs, Status=ACTIVE
6. aws bedrock list-model-invocation-jobs --region us-east-1 --max-results 1   # batch inference reachable (AccessDenied is an answer too)
7. uv run python -c "import botocore.session as s; m=s.get_session().get_service_model('bedrock-agentcore'); print('Evaluate' in m.operation_names)"
Write agentcore-capabilities.json at the repo root:
  {identity_arn, list_evaluators: ok|denied|error + the Builtin.* ids seen, online_configs: ok|denied|error,
   cfn_evaluator_type: ok|missing, transaction_search: {destination, status}, batch_inference: ok|denied,
   boto3_has_evaluate: bool}
Commit it on kiro/ka0-agentcore and push.
```

Expected: `list-evaluators` returns the `Builtin.*` evaluators (including `Builtin.GoalSuccessRate` and the
three `Builtin.Trajectory*Match`), the CloudFormation type exists, `boto3_has_evaluate` is true.
Transaction Search may be off (`Destination: XRay`); that only blocks KA3. If `list-evaluators` is denied, KA2
and KA3 are skipped and KA1 deploys with `-c agentcore=false`.

### KA1. CDK bootstrap and deploy (20 min, about $0; stop if CloudFormation shows any resource outside the two stacks)

```
<preamble>
uv sync --extra aws --extra infra
cd infra
npx -y aws-cdk@2 synth --quiet                      # must print "Successfully synthesized"
npx -y aws-cdk@2 bootstrap aws://$(aws sts get-caller-identity --query Account --output text)/us-east-1
npx -y aws-cdk@2 deploy --all --require-approval never --outputs-file cdk-outputs.json
If KA0 said AgentCore is unavailable, add: -c agentcore=false
If bootstrap is denied:
  npx -y aws-cdk@2 synth -c bootstrapless=true --quiet
  aws cloudformation deploy --template-file cdk.out/TreehouseRunStore.template.json --stack-name TreehouseRunStore --capabilities CAPABILITY_IAM --region us-east-1
  (the evaluator stack needs a bootstrapped account for its Lambda asset; report that it was skipped)
Verify (read-only):
  B=$(jq -r .TreehouseRunStore.RunStoreBucketName cdk-outputs.json)
  aws s3api get-bucket-versioning --bucket $B
  aws s3api get-object-lock-configuration --bucket $B
  aws s3api get-bucket-policy --bucket $(jq -r .TreehouseRunStore.KeyBucketName cdk-outputs.json) --query Policy --output text | jq '.Statement[] | select(.Sid=="DenyWorker")'
  aws bedrock-agentcore-control get-evaluator --evaluator-id $(jq -r .TreehouseEval.RulesEvaluatorId cdk-outputs.json) --region us-east-1 --query '{name:evaluatorName,level:level,status:status}'
  aws bedrock-agentcore-control get-online-evaluation-config --online-evaluation-config-id $(jq -r .TreehouseEval.OnlineEvalConfigId cdk-outputs.json) --region us-east-1 --query '{status:status,execution:executionStatus}'
Commit infra/cdk-outputs.json and the verify output (ka1-verify.txt) on kiro/ka1-cdk and push.
```

Expected: versioning `Enabled`; Object Lock `Enabled` with `DefaultRetention: {Mode: GOVERNANCE, Days: 1}`; a
`DenyWorker` statement naming the worker role; `treehouse_rules` at level `TRACE`; the online config with
execution `DISABLED`. Cost: the KMS key is about $1 a month prorated; everything else is idle at $0.

### KA2. On-demand AgentCore evals on a recorded demo run (15 min, under $2; stop at $5 in Cost Explorer)

```
<preamble>
uv run treehouse demo --out out/ka2          # replays the 9 recorded demo runs offline; no Bedrock calls
R=$(jq -r .TreehouseEval.RulesEvaluatorId infra/cdk-outputs.json)
G=$(jq -r .TreehouseEval.GuardEvaluatorId infra/cdk-outputs.json)
for run in synth-good synth-fabricator synth-key-peeker; do
  uv run python scripts/agentcore_eval.py --run out/ka2/store/runs/$run \
    --evaluators Builtin.TrajectoryInOrderMatch,Builtin.GoalSuccessRate,$R,$G
done
Copy each "wrote .../comparisons/agentcore/<run>/<sha>.json" file to results/agentcore/<run>.json
(they hold labels and explanations only, no pixels). Commit results/agentcore/ on kiro/ka2-agentcore and push.
If an evaluator returns errorCode, keep the file and report the code and message verbatim.
```

Expected, per run: `Builtin.TrajectoryInOrderMatch` Pass (all three runs call `imagery_window`, the card's
expected trajectory); `treehouse_rules` PASS for synth-good and FAIL for synth-fabricator (explanation names
`R4:fabrication`); `treehouse_guard` PASS for synth-good and FAIL for synth-key-peeker
(`forbidden-source accesses=2`). These match Treehouse's own R1/R2/R4 and blocked-call counts; any mismatch is
the finding. `Builtin.GoalSuccessRate` is the true unknown: our spans carry message references, not message
text, so it may score low or return an error. Cost: trajectory and Treehouse evaluators make no LLM calls
(Lambda cost ≈ $0); GoalSuccessRate is LLM-judged, 3 sessions, well under $2 at Bedrock token prices.

### KA3. Online eval on a hosted agent (optional, 30 min, under $5; disable before you stop)

Needs: a Strands agent hosted on AgentCore Runtime with observability on, and KA0 showing Transaction Search
`ACTIVE` (or permission to turn it on). Skip if either is missing.

```
<preamble>
If KA0 showed Transaction Search not ACTIVE, ask Suhas before running:
  aws xray update-trace-segment-destination --destination CloudWatchLogs --region us-east-1
Find the agent's span log group and service name (Runtime console, Observability tab), then redeploy the eval
stack with them:
  cd infra && npx -y aws-cdk@2 deploy TreehouseEval --require-approval never \
    --parameters AgentLogGroup=<log group> --parameters AgentServiceName=<service.name>
Enable, invoke the agent 3 times, wait 10 minutes, read results, then DISABLE:
  ID=$(jq -r .TreehouseEval.OnlineEvalConfigId cdk-outputs.json)
  aws bedrock-agentcore-control update-online-evaluation-config --online-evaluation-config-id $ID --execution-status ENABLED --region us-east-1
  ... invoke the agent ...
  aws logs describe-log-groups --log-group-name-prefix /aws/bedrock-agentcore/evaluations --region us-east-1
  (read the newest results there; save them to results/agentcore/online.json)
  aws bedrock-agentcore-control update-online-evaluation-config --online-evaluation-config-id $ID --execution-status DISABLED --region us-east-1
Commit results/agentcore/online.json on kiro/ka3-online and push. Report whether the config is DISABLED at the end.
```

Expected: sampled sessions show `treehouse_guard` results. A hosted agent that does not emit
`treehouse.card` and `treehouse.claims` gets `VALIDATION_FAILED` from both Treehouse evaluators; that is the
honest result until the hosted agent writes Treehouse spans. Note the AWS docs: while an online config is
enabled, its code-based evaluators are locked (cannot be updated or deleted), so disable it before changing
the Lambda. Cost: 10 % sampling of 3 sessions with programmatic evaluators is cents; the agent's own Bedrock
calls dominate. The results log-group prefix above is an assumption; take the real one from the console.

## 5. Verified vs assumed

- Verified against the installed packages (aws-cdk-lib 2.275.0, botocore 1.43.123): L2
  `aws_bedrockagentcore.Evaluator`, `EvaluatorConfig.code_based`, `EvaluationLevel`, `OnlineEvaluationConfig`,
  `DataSourceConfig.from_cloud_watch_logs`, `EvaluatorSelector.custom`, `ExecutionStatus.DISABLED`; CFN types
  `AWS::BedrockAgentCore::Evaluator` / `OnlineEvaluationConfig`; botocore `Evaluate` request/response shapes
  (`evaluationReferenceInputs`, `ignoredReferenceInputFields`); the `aws:cdk:bundling-stacks` context key.
- Verified in AWS docs (code-based-evaluators, ground-truth-evaluations, read 2026-11-04): Lambda input/output
  contract, 300 s / 6 MB limits, online lock-in of code-based evaluators, ground-truth fields and levels.
- Found by synth: one Lambda cannot back two L2 Evaluators (each adds a fixed-id invoke permission), so the
  same asset ships as two functions.
- Assumed, check in KA2: the exact span-log shape AgentCore expects in `sessionSpans` (docs show only that spans
  have `traceId`, `name`, `attributes`); whether replay runs' logical-clock timestamps (near 1970) are accepted.
- Assumed, check in KA0 / KA3: Bedrock batch coverage and minimum record count, S3 Vectors limits, the online
  results log-group name, AgentCore pricing.
