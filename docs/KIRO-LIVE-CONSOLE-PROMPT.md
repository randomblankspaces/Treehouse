# Kiro prompt: enable the dev-view live console in the workshop account (us-east-1)

Paste everything below the line into Kiro (Workshop Studio, authorized AWS terminal). Repo: `/workshop/Treehouse`.

---

You are Kiro in the Treehouse workshop account. The dev-view **live console** (`uv run treehouse ui serve --live`) needs AWS access that only you can grant or verify. Do the steps in order, claim only what you ran, and stop on the stop conditions at the end. Region is **us-east-1** for everything; an ambient `AWS_REGION=us-west-2` must not redirect anything (`export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1`).

## Rules (same as `docs/KIRO-FINAL-PUSH.md`)
- Read `AGENTS.md`, `.kiro/steering/*.md`, `docs/ARCHITECTURE.md`, `docs/JUDGE-DEPLOY.md` first.
- Never commit credentials, account numbers, ARNs with account ids, imagery pixels or base64 payloads. Redact account ids as `<ACCOUNT_ID>` in every receipt. Scan before commit:
  `grep -rnE 'AKIA[0-9A-Z]{16}|arn:aws:[a-z-]+:[a-z0-9-]*:[0-9]{12}|[0-9]{12}|base64' fixtures/live/receipts`
- Do not edit `.spend/spend.jsonl` by hand; never delete or truncate it.
- Do not change code. The only repo edit allowed is `config/models.yaml` (set `verified: true` and the probe date on a row only where the probe proved it; fix an `inference_profile` only where the probe proved a different one) and new files under `fixtures/live/receipts/`.
- Branch from `main`, run `uv run pytest -q` and `uv run ruff check .` before any PR; do not push to `main` directly.

## 0. Preflight (no paid calls)
```sh
uv sync --locked --extra aws --extra strands --extra api
uv run treehouse budget status          # stop if exit code >= 2
aws sts get-caller-identity --query Arn --output text   # record the ROLE NAME only, redact the account id
```
Budget for this task: **$10 estimated incremental**; the account policy stays **$350 warning / $450 hard stop** (existing guard, `treehouse budget`). Reconcile with `uv run treehouse budget reconcile` after step (a) and after step (c).

## (a) Bedrock model access, verified with one tiny Converse tool-use call each
Enable model access (Bedrock console > Model access, or the equivalent API) for each inference profile, in us-east-1:

| registry key (`config/models.yaml`) | inference profile |
|---|---|
| nova-lite | `us.amazon.nova-lite-v1:0` |
| nova-pro | `us.amazon.nova-pro-v1:0` |
| claude-sonnet-4-6 | `us.anthropic.claude-sonnet-4-6` |
| claude-sonnet-4-5 | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| llama-3-3-70b (check the key in the yaml) | `us.meta.llama3-3-70b-instruct-v1:0` |
| claude-haiku-5-5 | `us.anthropic.claude-haiku-5-5` |
| claude-sonnet-5-5 | `us.anthropic.claude-sonnet-5-5` (alt: `global.anthropic.claude-sonnet-5-5`) |

For each, make **one** Converse call with a single trivial tool (for example `ping` with no arguments), `maxTokens` 64, temperature 0, prompt "Call the ping tool." Do not send images. Use the repo's probe so the ledger records it:
```sh
uv run python scripts/aws_probe.py --help     # read the flags first; use its Converse + tool-use probe per key
```
If the probe cannot target a single key, call Converse via `scripts/aws_probe.py`'s helper or boto3 in a scratch script outside the repo, and still record each call with `treehouse budget` tooling if it offers a record command; otherwise note "not in the ledger" in the receipt.

Record per model: `key`, `inference_profile`, `ok|AccessDenied|Throttled|ValidationError`, whether a `toolUse` block came back, `stopReason`, input/output tokens, latency ms, the error text if any. If a bare id fails on-demand, retry via the `alt_profiles` entry and record both. Write `fixtures/live/receipts/bedrock-model-access-<YYYYMMDD>.json` (account id redacted). Then update `verified:` in `config/models.yaml` only for rows that passed.

## (b) Amazon Polly neural synthesis for the console role
The role that runs `treehouse ui serve --live` (the Workshop role from `get-caller-identity`, or the instance/task role if the console runs elsewhere) needs `polly:SynthesizeSpeech` (and `polly:DescribeVoices`) in us-east-1.
1. Check first: `aws polly describe-voices --engine neural --language-code en-US --region us-east-1 --query 'Voices[?Id==\`Joanna\`].Id'`
2. If AccessDenied, attach an inline policy allowing only those two actions on `*` (Polly has no resource-level ARNs for synthesis). Do not widen anything else.
3. Verify with the repo script on an existing run (neural engine, <=2,900-char chunks):
```sh
uv run python scripts/narrate_polly.py --store out/live/store --run live-t1-nagoya-warehouses-nova-pro-101943 --out ui/public/narration/
```
Confirm `<run>.mp3` and `<run>.json` (voice, engine `neural`, text sha256) exist. Do not commit the mp3 unless `docs/KIRO-FINAL-PUSH.md` task 3 says to; commit the sidecar JSON hash summary in the receipt instead. Write `fixtures/live/receipts/polly-neural-<YYYYMMDD>.json` (voice, engine, characters synthesised, role name, redacted).

## (c) Amazon Bedrock AgentCore
1. **Evaluations on the live runs.** The evaluator Lambdas are in the CDK app in `infra/` (`treehouse_rules`, `treehouse_guard`; ids in `infra/cdk-outputs.json` as `RulesEvaluatorId` and `GuardEvaluatorId`). If `infra/cdk-outputs.json` does not match what exists in the account, run `cd infra && uv run cdk diff` and report before deploying anything. For each sealed run in `out/live/store/runs/` (`live-t1-nagoya-warehouses-nova-lite-1105-102717`, `live-t1-nagoya-warehouses-nova-pro-101943`, `nagoya-nova-lite-1`):
```sh
uv run python scripts/agentcore_eval.py --run out/live/store/runs/<run_id> \
  --evaluators Builtin.TrajectoryInOrderMatch,Builtin.ToolSelectionAccuracy,Builtin.ToolParameterAccuracy,Builtin.GoalSuccessRate,<RulesEvaluatorId>,<GuardEvaluatorId>
```
It verifies the sealed run, writes append-only results to `<store>/comparisons/agentcore/<run_id>/<sha256>.json`, and exits 1 if any evaluator errored. Built-in LLM-judged evaluators bill Bedrock tokens that are NOT in the Treehouse ledger: do the first run alone, note the cost, then continue only if it is under $2 per run. Copy each result file to `fixtures/live/agentcore/<run_id>.agentcore.json` (same shape as the existing `t1-nagoya-sonnet-strands-3.agentcore.json`), account ids redacted. A run that errors on a built-in evaluator (for example runs with no tool spans) is recorded as an error, not retried more than once.
2. **Judge path, only if everything above is done and time remains.** Follow `docs/JUDGE-DEPLOY.md` exactly (Runtime + Gateway + Lambda + KB):
```sh
uv run python scripts/judge_deploy.py                       # plan only, zero AWS calls; read it
uv run python deploy/judge_runtime/build.py --output "$PWD/outputs/judge/runtime-arm64.zip"
uv run python scripts/judge_deploy.py --apply --acknowledge-spend 25 --runtime-zip "$PWD/outputs/judge/runtime-arm64.zip"
uv run python scripts/judge_smoke.py                        # one smoke question; check --help for flags
```
The `--acknowledge-spend 25` flag acknowledges the $25 stop threshold for that path; it is not a billing cap. Check current pricing and account headroom before `--apply`; stop if headroom is unclear. Keep calls to a handful. Export the deployment receipt per `docs/JUDGE-DEPLOY.md` (state in `outputs/judge/deploy-state.json`, which must not be committed unredacted) to `fixtures/live/receipts/judge-deploy-<YYYYMMDD>.json`.

## (d) Spend and receipts
- Run `uv run treehouse budget status` before (a), before (c)(1), before (c)(2); stop on exit >= 2. After each step run `uv run treehouse budget reconcile` and put the ledger total and the AWS-reported total in the receipt.
- All receipts under `fixtures/live/receipts/`, JSON, account id replaced by `<ACCOUNT_ID>`, no ARNs with account ids, no secrets, no response bodies beyond the fields listed. Include for each: UTC timestamp, step, command run, result, estimated and observed cost.
- Finally test the console itself: `uv run treehouse ui serve --live --store out/live/store` (check `uv run treehouse ui serve --help` for exact flags), open the dev view, confirm `GET /api/live/options` lists the models you verified, and launch **one** cheapest run (a `nova-lite` run on the Nagoya card). Record the run id and cost. Do not start more than one live run.

## (e) Stop conditions
Stop and report (do not work around) if any of these happen:
- `treehouse budget status` exits >= 2, or estimated incremental spend reaches **$10**, or AWS-reported spend exceeds the ledger by a large margin.
- AccessDenied you cannot fix with the narrow permissions above (do not create broad admin policies, do not touch the Workshop role's trust policy, do not run `extend`/`unpause`-style budget overrides).
- A model needs a marketplace subscription or EULA you were not told to accept; report it.
- CDK/judge deploy plan shows deletions or replacement of existing resources.
- Any scan hit for credentials, account numbers or base64 in a file you are about to commit.
- Anything that would require code changes: write it into `docs/KIRO-STATUS.md` and stop that item.

## Report back (append a dated section to `docs/KIRO-STATUS.md`, and reply with it)
1. Table of the 7 inference profiles: access enabled?, Converse tool-use result, latency, tokens, error text, `verified` changed in `config/models.yaml`?
2. Polly: voice, engine, role, one run synthesised (run id, characters), permission added (exact action list).
3. AgentCore Evaluations: per run id, evaluator, label/value, errors, cost; paths of the files under `fixtures/live/agentcore/`.
4. Judge deploy: done / skipped, why, resources created (names, no account ids), smoke result, estimated vs observed cost.
5. Spend: ledger total, AWS-reported total, budget status exit code at the end.
6. The one live console run id, model, cost; anything the console showed wrongly (for example capabilities still saying `not_configured`).
7. Open items and blockers.
