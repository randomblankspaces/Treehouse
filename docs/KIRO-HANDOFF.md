# Continuation context — wait for Suhas

Latest instruction: finish the code, review the PR, merge to Treehouse main only if the code and
checks pass, then stop and wait for Suhas. This document records context; it does not authorize an
agent to start AWS integration, deployment or further feature work by reading it.

## Product understanding

Treehouse evaluates an agent's complete geospatial investigation and the accuracy of its resulting
database. The user specifies what to find and the target zone. The observatory records strategy,
foundation-model/tool/settings choices, alternatives, evidence, revisions, stopping behavior and
self-reported confidence. Actual predictions appear as red geographic markers linked to claims,
evidence and decisions. MCP calls are supporting records, not a sufficient reasoning-quality metric.

Warehouses in a Bangladesh city are an example, not the selected first production scenario.
Agents and model/source/classifier implementations remain swappable. Strands coordinates agents;
it is not the classifier. Recorded explanations are self-reports, not proof of all hidden internal
computation. Independent output accuracy, evidence quality, confidence and cost remain separate.

## Implemented local MVP

- Existing ModelProvider/runner/gateway/policy/budget/trace/seal path, with opt-in prior decision
  bindings and successful-evidence references. Default replay catalogs and nine golden heads preserved.
- Trusted provider/classifier/source plugins, VisionClassifier adapter over ModelProvider, and partial
  run preservation on errors or limits. The local plugin environment is not OS isolation.
- Verified post-seal process/output/confidence/cost reporting; held-out class-aware one-to-one matching;
  known reference examples excluded from held-out grades; ambiguous split neighborhoods abstain.
- Fresh-context distinct-model process-review interface and independently authored rubric. Its findings
  are model-estimated. No composite truth score or new Rely gate is issued.
- Exact SQLite/GeoJSON exports from sealed claims, plus the React Living Sky/Atlas/Investigation UI,
  read-only API, actual prediction markers/table and decision/evidence selection.
- Small official CC0 USPVDB test subset: 12 permitted examples and 12 held-out points with provenance.
  It is incomplete and validates reference/evaluation mechanics, not imagery detection accuracy.
- Optional Runtime/KB/Gateway proof code and workbench, tested offline. It is secondary to the actual
  agent-evaluation product and has not been deployed from the Mac.

Independent test authors used different context from feature implementers. See
[tests/investigation/PROVENANCE.md](../tests/investigation/PROVENANCE.md) for frozen assertions,
red timing, hashes, harness corrections and the regression cases. Feature builders did not change
assertions merely to make their implementation pass.

## Verified local commands

From a clean clone with Python3.12+ and Node22.12+:

```sh
uv sync --locked --all-extras
uv run ruff check .
uv run pytest
npm --prefix ui ci
npm --prefix ui run typecheck
npm --prefix ui run build
uv run --extra api treehouse sandbox demo --store out/investigation/store --run-id investigation-demo
uv run --extra api treehouse sandbox evaluate investigation-demo --store out/investigation/store
uv run --extra api treehouse sandbox export investigation-demo --store out/investigation/store --output out/investigation/export
uv run --extra api treehouse ui serve --store out/investigation/store
```

Use a fresh destination/run ID; preserve existing sealed outputs. Open http://127.0.0.1:8765 and
select the run's Investigation pane. This demonstration uses an explicitly labeled synthetic,
observation-driven heuristic, not a validated real foundation-model detector.

## What Kiro will need after the user supplies further instructions

Clone only `https://github.com/randomblankspaces/Treehouse.git`, inspect clean git status and current
main, and incorporate Suhas's additional context before extending it. Never modify the upstream
VishalPatil18 repository or force push. Use a new `kiro/...` branch for integration checkpoints.

Read [OUTLINE.md](OUTLINE.md), [PLAN.md](PLAN.md), [INVESTIGATION.md](INVESTIGATION.md),
[PRODUCT-STATUS.md](PRODUCT-STATUS.md), [UI.md](UI.md), and [FUTURE-WORK.md](FUTURE-WORK.md).
Older overnight TODO prompts contain commands/scope that can be stale; do not execute them blindly.

The intended next sequence is AWS/model/source integration in Kiro → independent live testing →
refinement. The default imagery reader is synthetic/recorded; actual permitted imagery/embedding
sources and genuine worker/classifier/reviewer factories still need connection. Unknown I/O or
prices must stay unknown/unpriced. No model accuracy, physical measurement, human superiority or
live AWS deployment is established by the local tests.

Preserve `.spend/spend.jsonl`, filled price tables, probe reports, task/data versions and cassettes.
The prior probe used us-east-1 despite an ambient us-west-2 setting; inspect current verified model
profiles rather than guess. Use existing reservation/account guards, check actual billing, and keep
first live calls small. The separate Runtime/KB/Gateway path has costs outside the model ledger;
its documented operator thresholds are not an AWS billing cap. Bedrock batch jobs were explicitly denied.

Keep held-out labels/audit rows and all aliases of their source outside worker access. Public label
availability and local file separation do not guarantee isolation from model memory or hostile code.
Retain source licenses; no restricted pixels, credentials or raw private messages in committed artifacts.
The current trust reporting path remains an unissued stub; repair the separate trust-core audit
cases before wiring a real passport. Manual Windows screen-reader checks and real source/model
accuracy measurements remain outstanding.

No further action is scheduled here. Await Suhas's next instruction.
