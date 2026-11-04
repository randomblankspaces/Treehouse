# Continuation context — confirmed minimal sandbox

Latest instruction: Suhas confirmed an evaluation sandbox that observes why/how an agent uses
foundation models and other workflow components to build a geospatial database. Strands is part
of the workflow under evaluation, not a fixed Treehouse architecture. Natural-language target/AOI,
embeddings, classification and red prediction markers form a representative workflow, with
inspectable reasons/confidence/evidence/time/cost and independent process/output assessment. He requested Kiro prompts. The previous
implementation is merged in PR #8; separate PR #9 sets Compliance-mode Object Lock as the default.
Read [LGND-REPORT-CONTEXT.md](LGND-REPORT-CONTEXT.md) and then use
[KIRO-NEXT-PROMPTS.md](KIRO-NEXT-PROMPTS.md). The broader benchmark remains source context, not a
commitment to every report task. This Codex change adds documentation, not a live implementation.

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

## New benchmark context to preserve

The closest product match is Section 5.8's agentic evaluation layered over workflow benchmarks.
Observe decisions, adaptations, evidence and limits, and independently score the database. Fix the
reference, asset/cell/site units, matching, metrics, labeling effort and transfer protocol before
results. Do not compare our point-distance fixture grades directly with their 160 m cell/asset
any-touch or detector-IoU results. Table 9 is a set of workflow alternatives, not a required call
order. Imagery permissions are in Table 17; report licenses/access/results are not independently
verified. The first task/region remains open; USPVDB is still an evaluator fixture, not the supplied
warehouse benchmark. Preserve independent test authorship before feature implementation.

## What Kiro needs for the confirmed minimal integration

Clone only `https://github.com/randomblankspaces/Treehouse.git`, inspect clean git status and current
main, and incorporate Suhas's additional context before extending it. Never modify the upstream
VishalPatil18 repository or force push. Use a new `kiro/...` branch for integration checkpoints.

Read [LGND-REPORT-CONTEXT.md](LGND-REPORT-CONTEXT.md), [OUTLINE.md](OUTLINE.md),
[PLAN.md](PLAN.md), [INVESTIGATION.md](INVESTIGATION.md),
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

Next action: Kiro follows KIRO-NEXT-PROMPTS.md, establishes the current baseline, freezes independent
acceptance checks and integrates the confirmed minimal pipeline. Keep AWS work in the authorized
Workshop environment. Report actual outcomes and blockers; broader report work needs separate scope.
