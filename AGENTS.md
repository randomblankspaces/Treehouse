# Treehouse — agent notes

Python 3.12 (uv) in `src/treehouse/`, TypeScript/Vite UI in `ui/`, CDK in `infra/`. Product rules, commands and
module map: `.kiro/steering/{product,tech,structure}.md` — read them first. Plan: `docs/MVP-PLAN.md`.

- Tests: `uv run pytest -q` (offline; live tests are `@live`, skipped). Lint: `uv run ruff check .`.
  UI: `cd ui && npm run typecheck && npm run build`.
- Never commit credentials, AWS account IDs/ARNs, imagery pixels or Bedrock image payloads.
- Never use Maxar/Vantor imagery. Never let a grading reference reach the agent.
- Class-agnostic: no asset-class-specific code; classes live in `config/asset-classes.yaml`.
- Claim only what ran; label synthetic/replay/designed clearly.
- Never touch `.spend/spend.jsonl` except through the spend guard.
