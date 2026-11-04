# Kiro continuation prompts — agent evaluation MVP

> **Superseded for the MVP build by [KIRO-MVP-PROMPT.md](KIRO-MVP-PROMPT.md) and [MVP-PLAN.md](MVP-PLAN.md)** (2026-11-04). Kept for history and for its independent-acceptance guidance.

Suhas confirmed this scope after the report reading: **Treehouse evaluates the agent building a
geospatial database**. Strands belongs to the workflow under evaluation, alongside foundation
models, retrieval and classification. It is not the product or a mandatory architecture for every
agent. The goal is to inspect and assess why/how the agent uses these components and whether its
final database is accurate. Red prediction markers link the result back to the decision/evidence.

The existing code is a local synthetic/replay MVP with plugin seams. No real model/imagery accuracy
or deployed AWS pipeline is established. The source brief is [LGND-REPORT-CONTEXT.md](LGND-REPORT-CONTEXT.md);
current code limits are in [PRODUCT-STATUS.md](PRODUCT-STATUS.md) and [INVESTIGATION.md](INVESTIGATION.md).

Planning estimate: roughly **2–4 hours for one narrow live T1 inventory/evaluation MVP** if AWS
permissions and usable imagery/labels are available. This is an estimate, not a measured runtime or
promise. Data access and model availability are the main unknowns. Full report reproduction,
cross-region studies, T2–T4, active-learning studies and production hosting are separately scoped.

Paste the prompts in order into Kiro. Preserve its findings/checkpoints between them.

## Prompt 1 — inspect the baseline and independently specify acceptance

```text
Continue randomblankspaces/Treehouse in the authorized Kiro Workshop environment. Clone
https://github.com/randomblankspaces/Treehouse.git if no checkout exists; otherwise inspect clean
git status before fetching current main. Preserve uncommitted work. Only this fork is a write
target; never modify or open PRs against VishalPatil18 upstream. Work on a kiro/... branch.

Read README.md, HANDOFF.md's latest context, docs/LGND-REPORT-CONTEXT.md, docs/OUTLINE.md,
docs/PRODUCT-STATUS.md, docs/INVESTIGATION.md, docs/KIRO-HANDOFF.md and this prompts file.
Earlier overnight queues are historical. Preserve merged work and existing fixture hashes.

Product: evaluate the agent's decision-making while it creates a geospatial object database.
Strands is one component/harness in the agent's workflow; keep agents/models/harnesses swappable.
Observe why it selects a foundation model, inputs/resolution/examples/query/classifier, which
alternatives it considers, what evidence it sees, how it changes course and why it stops. Check
the resulting database independently. Explanations/confidence are agent self-reports; judge
them against actions/evidence/outcomes, not as verified hidden internal thought.

Establish actual baseline: uv sync --locked --all-extras; uv run ruff check .; uv run pytest;
npm --prefix ui ci; npm --prefix ui run typecheck; npm --prefix ui run build. Record exact results
and pre-existing failures. Inspect .github/workflows/ci.yml for existing browser/demo commands.
Do not count skipped live tests as passes.

Inspect current AWS account/region/model permissions, probe reports, actual billing, price tables
and .spend/spend.jsonl without printing credentials. Preserve existing budget guards. Choose one
small feasible T1 target/AOI with eligible public imagery and labeled reference data; document why,
version/date/coverage/completeness and terms. Keep target text and zone configurable. USPVDB is an
incomplete evaluator fixture, not proof of imagery detection. Report license claims need checking
for the selected version/use. Use a labeled complete test block if available; otherwise explicitly
limit metrics to the audited reference scope. Do not buy imagery or enlarge budget authority.

Before feature code, give a separate test-author agent/session a requirements-only brief: the
confirmed product, public interfaces and evaluation contract, not the planned implementation or
feature diff. Freeze its acceptance assertions/rubric/fixture hashes and show meaningful baseline
failures. Feature builders must not rewrite them to fit code. If Kiro cannot provide a separate
context, hand off this test-authoring step to a fresh session rather than claiming independence.

Acceptance must cover actual observation-dependent choices, evidence available at decision time,
revisions/alternatives/stopping, distinct candidate/asset units, no held-out leakage, truthful
confidence/cost, model failures/budget partial runs, exact claim-to-map coordinates and multiple
valid strategies. Include wrong-class lookalikes, unsupported high confidence, incomplete coverage,
revisited regions, duplicated candidates and a model failure. A tool-count checklist is insufficient.

Record the smallest implementation package and a checkpoint in the repo. Proceed to Prompt 2
only after the independent acceptance contract is frozen. Do not deploy resources just to inspect
the baseline, run paid experiments without existing valid caps, or execute old TODO prompts blindly.
```

## Prompt 2 — connect one real agent workflow and its evaluation

```text
Continue from Prompt 1's checkpoint and frozen independent acceptance contract. Build the smallest
real example that demonstrates the evaluation sandbox. Reuse the existing ModelProvider, gateway,
budget, decision-binding, seal, investigation evaluator/export and UI paths. Inspect current SDK
interfaces and official documentation as needed; do not assume old plans are implemented APIs.

Instrument one Strands-based agent workflow as the initial example, keeping the harness swappable.
The agent receives a natural-language object request and AOI, chooses among available permitted
model/retrieval/classification actions, uses actual GeoFM embeddings or a verifiable precomputed
index, and builds a georeferenced claim database. Embeddings must retain cell footprint/CRS,
imagery date/source/license and model/index version. An LLM describing an image is not a GeoFM
embedding; similarity is not an object probability. Document any unavailable model capability.

Connect real permitted imagery windows and a genuine classifier/model path where needed to test
candidate objects. Strands coordinates calls; the foundation/vision models and classifier perform
inference. No synthetic fallback presented as live, no coordinates copied from held-out answers,
and no catalog lookup disguised as image-based classification. Do not force a single supposedly
correct search sequence: the object of evaluation is the agent's choices and adaptation.

Capture concise decision explanations, alternatives, selected model/settings, confidence and
evidence refs before actions; bind them to actual calls/results and parent/revision links. Keep
failed paths, unresolved regions and reasons for stopping. Reuse record_decision's existing
action-id/tool/argument binding. Handle agent, classifier, source and budget failures with honest
sealed partial output. All live calls go through actual price/spend guards; unknown costs/bytes
remain unknown, and measured model cost is not a complete AWS bill.

After sealing, independently assess the resulting database against the declared reference scope.
Keep prompting/fitting examples separate from holdouts. Pin class definitions, unit, matching,
thresholds and denominators before results. Current point-distance scoring is not LGND any-touch
cell/asset or detector-IoU scoring; implement a separately tested/versioned adapter only if the
selected comparison needs it. Otherwise label the different protocol and make no reproduction claim.

Assess strategy/evidence/adaptation/uncertainty/stopping separately from output accuracy. Use the
existing distinct-model fresh-context process review where available, with versioned rubric and
valid evidence citations; label its findings MODEL-ESTIMATED. Trace diagnostics are not semantic
decision quality. Do not issue a validated trust/Rely passport from the existing stub/unsafe core.

In the existing UI let a user supply object text and an explicit AOI, start the bounded configured
workflow, inspect the agent's pathway and model choices, and see the sealed database. Show the AOI
and actual red prediction markers linked to claim, decision and evidence; candidates and verified
reference labels must be distinguishable. Markers represent predictions, not certified objects.
Show reported confidence, independent output results, process-review status, time and cost
separately. Keep a keyboard-accessible table and clear partial/failed/unavailable states. Do not
fabricate live events, image previews, confidence calibration or exploration coverage.

Use restricted Kiro previews and server-owned configuration/credentials. Keep held-out data and
audit aliases outside agent access; trusted local Python plugins are not hostile-code isolation.
Preserve raw pixels/credentials/private documents outside commits. Defer 3D, simulation, production
hosting, optional AWS challenge panels and full benchmark studies. Keep a useful checkpoint, run
the frozen acceptance cases and continue to Prompt 3. After two failed repairs, reassess the cause.
```

## Prompt 3 — independent review, bounded live proof and handoff

```text
Validate the implementation from Prompt 2 without weakening the frozen independent contract.
Run the relevant acceptance checks, full offline pytest/Ruff, TypeScript/build and actual browser
flows at desktop/mobile with keyboard navigation. Follow .github/workflows/ci.yml to prepare a
fresh disposable store and launch the existing product/start/investigation browser tests; preserve
existing sealed artifacts. Add independently authored coverage for new behavior rather than
silently treating replay browser tests as live integration proof.

Use a fresh reviewer context, distinct from the implementer, to inspect the diff, requirements,
source/evaluator boundaries and actual evidence. Review both process assessment and output
accuracy: a fluent rationale with unsupported choices must not earn a semantic success claim.
Repair verified blockers within the two-attempt bound, rerun affected checks and obtain review.
Do not label roles in one shared context as independent agents.

In authorized Kiro AWS only, run one small paid T1 investigation under verified existing caps.
Record actual account/region/resource and model IDs safely, source/image/index versions, decisions,
call results, independent grades, stop status, token/cost/latency accounting and remaining unknowns.
Verify in the UI that red markers/table equal the sealed claims and link to the model-selection
decisions and actual evidence. Export SQLite/GeoJSON and the report. Show unresolved areas and
reference completeness. If a model/service/data permission is unavailable, preserve the partial
run and report the blocker; a mock or READY status cannot close the live gate.

Commit and push only to randomblankspaces/Treehouse. Merge only after relevant checks and fresh
independent review pass; preserve concurrent work and never force-push. Update README, product
status, plan, future work and handoff with actual commands/results, exact commit, selected task/data,
UI preview steps and evidence limits. End with a short judge walkthrough: request/AOI → agent's
model choice and explanation → actual retrieval/classification evidence → prediction database/red
markers → separate process, output, confidence, time and cost. Report what still needs refinement.
Stop at this bounded MVP; do not claim full report reproduction or production readiness.
```
