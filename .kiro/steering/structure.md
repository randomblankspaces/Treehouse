---
inclusion: always
---
# Structure

- `src/treehouse/` — library and CLI (`cli.py`).
  - `investigation/` — decision-bound agent runs (`record_decision`), classifier plugin seam
    (`VisionClassifier`), post-seal evaluation, process review, public projection. Read `docs/INVESTIGATION.md`.
  - `harness/` — `plain_loop.py`, `strands_harness.py` (`harness: strands`), `baseline.py` (no-tool).
  - `providers/` — fake/record/replay/Bedrock providers, `strands_model.py`, spend ledger, prices.
  - `verifier/` — `ConverseVerifier`, `StrandsVerifier` (blind; never see worker fields).
  - `tools/` — in-process MCP tool servers (Clay search, imagery, STAC, claims) and `search_agent.py`.
  - `gateway/` — Tool Gateway: allow-list, forbidden sources, metering, budget. Every tool call goes through it.
  - `checks/`, `score/`, `stats/`, `sampling/`, `trust/` — pure evaluation layers; they receive a `SealedRun`
    and never import providers/harness/gateway/tools/store/boto3/network (enforced by
    `tests/unit/test_import_boundary.py`).
  - `trace/`, `store/` — hash-chained traces, sealed store, `verify`.
  - `aws/` — AgentCore Evaluations client (`agentcore.py`) and Lambda code-based evaluator.
  - `ui/`, `judge/`, `report/` — HTTP API, judge workbench, HTML report.
- `infra/` — CDK app (run store, key bucket, Lambda evaluators, AgentCore evaluator registration).
- `tasks/` — task cards (YAML); `keys/` — grading references (never given to the agent); `fixtures/` — recorded demo runs.
- `config/` — model registry, prices. `scripts/` — probes, fixture builders, data fetchers.
- `docs/` — `MVP-PLAN.md` (start here), `REPORT-TABLES.md`, `LGND-REPORT-CONTEXT.md`, `INVESTIGATION.md`,
  `design/` (system/implementation design, defense book, AWS blueprint, Strands notes).
- `.kiro/specs/treehouse-mvp/` — requirements, design, tasks for the MVP; tick tasks as they land.

**Conventions:** one concern per file; reuse existing helpers; new evaluators are versioned and append-only
(re-scoring writes a new record); keep new modules inside the existing layers above.
