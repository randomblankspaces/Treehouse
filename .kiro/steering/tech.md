---
inclusion: always
---
# Tech

- **Python 3.12+, `uv`** (`uv sync --locked --all-extras`), `pytest`, `ruff`. TypeScript/Vite UI in `ui/`
  (`npm ci && npm run build`). Licence Apache-2.0.
- **Commands:** `uv run pytest` (must stay green), `uv run ruff check .`, `uv run treehouse --help`,
  `uv run treehouse demo` (offline replay), `uv run treehouse verify --store <store>`,
  `uv run --extra api treehouse sandbox run|evaluate|export ...`, `uv run --extra api treehouse ui serve --store <store>`,
  `uv run treehouse budget status|init|plan`, `uv run treehouse prices check`.
- **AWS region:** us-east-1 (data buckets: source.coop and Sentinel-2 COGs in us-west-2; GSI tiles are HTTPS).
- **AWS services used:** Bedrock Converse (worker, vision sub-agent, reviewer), Strands Agents, AgentCore
  Evaluations (built-in + Lambda code-based), AgentCore Observability (needs CloudWatch Transaction Search),
  S3 with Object Lock **Compliance** + KMS key bucket, Lambda, CDK (`infra/`, `npx -y aws-cdk@2`).
  Should: SageMaker/EC2 GPU for Clay embeddings, Step Functions Distributed Map. **Bedrock batch inference is
  denied in this account — never use it.**
- **Models:** default worker `us.anthropic.claude-sonnet-5-5`; alternative `us.amazon.nova-pro-v1:0`. Both
  accept images in user turns and tool results (probe). Prices in `config/prices/`.
- **Spend guard (mandatory):** `uv run treehouse budget status` before any live step; stop and report if it
  exits 2/3 (spent + reserved > $350) or reports a wrong/empty ledger. Never delete, move, truncate or
  re-create `.spend/spend.jsonl`. Hard ceiling: $450 of the $500 Workshop budget.
- **Offline guard:** the test suite blocks network; live tests are marked `@live` and skipped by default.
- **Git:** work on branches named `kiro/<task>`; PR into `main` of `randomblankspaces/Treehouse`
  (`gh pr create --repo randomblankspaces/Treehouse --base main`); merge only when `uv run pytest` is green.
  Never push to `VishalPatil18/...`. Commit messages end with `Co-Authored-By: Kiro`.
- **Never commit:** credentials, account IDs/ARNs (redact to role names), imagery pixels (PNG/JPEG/TIFF
  crops), Bedrock image payloads. Commit scene/tile IDs, cell coordinates, hashes and JSON results.
