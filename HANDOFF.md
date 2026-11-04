# HANDOFF — overnight job (for whichever agent picks this up)

> If you are a new agent: read this file, then `TODO.md`, then `docs/OVERNIGHT-REPORT.md` (if present). Continue from **Current state**. Keep this file current, push often (WIP included), and merge into the fork's `main` only when tests are green.

## The job, as Suhas gave it (2026-11-04, ~00:00 EST)

Treehouse ("Clay agent-eval sandbox") is built for the AWS Breaking Barriers Challenge 2026 (DC). The beneficiary is Clay (Earth Dataset Foundry), with partner ADB. The public repo is due **Thu Nov 5 2026, 10:00 EST**. Suhas works solo. He is asleep and hands-off, and has given permission to run multi-agent councils, update docs, and merge into the fork's main.

### Hard rules
- **Push only to `origin`** = `randomblankspaces/team-43-renaissance-philanthropy-clay` (Suhas's fork). **Never** push or open PRs against upstream `VishalPatil18/…`. With `gh pr create`, always pass `--repo randomblankspaces/team-43-renaissance-philanthropy-clay --base main`.
- Work on branches. Merging into the fork's `main` is allowed once tests are green.
- License Apache-2.0. Open source, and reproducible on other computers, other inputs and other model providers. Bedrock is the default.
- "AWS-native, not AWS-locked": every AWS piece has a local stand-in.
- Data licenses:
  - LGND embeddings: CC BY 4.0.
  - Vantor: CC-BY-NC-4.0.
  - OSM: ODbL.
  - Commit scene IDs and window coordinates, **never imagery pixels**.
- **No AWS credentials** in the build container. Skip any step that needs AWS (Bedrock calls, CDK deploy) and write a ready-to-paste **Kiro prompt** for it in `TODO.md` → "Needs Suhas / Kiro". Never stop on an AWS roadblock.
- Commit messages end with `Co-Authored-By: Claude <noreply@anthropic.com>`.
- Suhas's later instructions:
  - (a) For every produced artifact (docs and code), run a **doubter subagent**, then a **judge subagent** that decides which doubts are valid, and apply the valid fixes.
  - (b) Don't prompt Suhas.
  - (c) Before credits run out, push everything, WIP included.
  - (d) When done, end with a note that this agent is done for the night.

### Read first
`docs/README.md`, `docs/SCOPE.md`, `docs/reviews/review1-judge.md`, `docs/reviews/review1-verifier.md`, `docs/design/council-brief.md` (Suhas's vision, trust engine, AWS map, top priority), `docs/design/design-decisions.md`, `docs/design/SYSTEM-DESIGN.md`.

### Top priority
**Most datasets are UNKEYED.** Keyed tasks exist to calibrate. Compare several methods for:
1. eval scores on unkeyed output;
2. testing and verification on unkeyed datasets.

For each method, give what it catches, what it misses, its cost, and how the method is validated on keyed data. (Now in SYSTEM-DESIGN.md §A13.) DD1: MVP truth sources are answer keys plus a blind, sampled verifier agent. Hindcasting is the first stretch.

### Steps
1. **System-design council.** Five agents (statistician, remote-sensing, agent-eval/observability, AWS architect, Clay/ADB/judging advocate). Rounds: propose, debate, moderator merge, then votes until all five accept (at most 6 rounds; if round 1 is unanimous, force a devil's-advocate round first), then a fact-check. Log to `docs/design/council-1-log.md`; output `docs/design/SYSTEM-DESIGN.md`.
2. **Implementation council.** Same process, deciding how to implement the design: module layout, interfaces (provider, harness, tracer, evaluator, verifier, trust engine), trace and task schemas, storage, API/MCP, test strategy (including how each unkeyed method is tested), and an ordered package plan. Log to `docs/design/council-2-log.md`; output `docs/design/IMPLEMENTATION-DESIGN.md`.
3. **Spec sheet.** Update `docs/` to match both designs:
   - Map S14–S19 and new items to F/SC/J/DoD rows in 01/02/04/05.
   - Update 06 risks, EXTERNAL-DEPENDENCIES (Vantor license, LGND tag), FUTURE-WORK and the README stretch order.
   - Log D43+ in SCOPE.md.
   - Branch → PR → merge.
4. **Build the basic form.** Python 3.12+, `uv`, `pytest`. Follow the package order in IMPLEMENTATION-DESIGN, with tests first. Bedrock is the default adapter but can't be called here, so test through a fake provider with recorded fixtures plus a replay path; write the Bedrock adapter and unit-test it against stubs. Use small offline fixtures. One branch and PR per package; merge when green **and** a fresh reviewer (doubter → judge) finds no blocking issue. Keep a README quickstart that runs end to end locally in replay mode.
5. **Morning report.** `docs/OVERNIGHT-REPORT.md`: what was decided (and whether each council was genuinely unanimous), what was built and merged (with test output), what is blocked, the Kiro prompts, and the decisions Suhas should confirm or override. Keep `TODO.md` current.

### Clay's values (paraphrased from Clay's private vision doc; never commit it verbatim)
- The product is an observability + evaluation sandbox for agentic geospatial dataset builds: a harness calls geospatial tools over MCP, the activity is captured as traces, and traces plus output are summarized and scored against a rubric or reference.
- Clay's bottleneck is knowing whether to trust an agent, not running one. Partners such as ADB need custom evals against their own tasks and rubrics.
- Users:
  - Clay's model and data team, who want to evaluate without hand-checking.
  - Partners, who want a reusable harness.
  - Harness developers, who want observable traces and clear scores.
  - Domain experts, who want summaries scored against a rubric.
- Constraints: open and reproducible (Apache-2.0); trust and provenance first-class (every scored run keeps its traces, inputs and rubric/reference); public or synthetic data only; model and tracer swappable.
- Principles: evaluating the agent is the product; known task + known input + reference; record traces and replay them for the demo; Bedrock behind an abstraction; greenfield but migration-aware.

## Environment facts (checked 2026-11-04)
- Python 3.13 and uv 0.11 are available. PyPI works. **mcp is 2.3.0**: `from mcp.server.mcpserver import MCPServer`; `from mcp.client.client import Client`; `Client(server)` connects in-process.
- strands-agents 1.63 (custom `strands.models.model.Model` ABC), rasterio 1.5.2 wheel, boto3, fastapi, numpy, scipy and pydantic all install.
- Network: Vantor bucket HTTPS **works**; data.source.coop and overpass-api.de are **blocked**; arxiv.org is blocked for fetch.
- Vantor Nepal event: 33 scenes, **4 pre + 29 post** (STAC `phase`). Items carry `eo:cloud_cover`, `pan_gsd`, `view:off_nadir`, `view:sun_*`. There is no cloud mask.

## Current state (update this as you go) — checkpoint 1, ~00:45 EST Wed Nov 4
- [x] Step 1: SYSTEM-DESIGN.md (an earlier session's council, unanimous in round 2) is on main (`22f0400`). Branch `docs/system-design-factcheck` has: fact-check pass 2; scene count corrected to 4 pre + 29 post; §A13 unkeyed-methods comparison; council-1 log addendum. A doubter raised 36 doubts (`wip/doubt-sd.md`). A **judge agent** is applying the valid ones on that branch. When its commit lands, merge the branch to main.
- [ ] Step 2: implementation council. Rounds (a) and (b) are done (`wip/council2/`). A neutral moderator is merging into `c-design-r1.md`. Next: all 5 seats vote with blocking objections; revise until unanimous; fact-check library/API claims; write `docs/design/IMPLEMENTATION-DESIGN.md` and `docs/design/council-2-log.md` (from `log-draft.md`).
  - Consensus after round (b):
    - The demo skeleton comes before the trust maths, with a 04:30 checkpoint. The plain tool loop is Must-0 and is the demo engine.
    - A MEASURED tier for exact trace-derived numbers.
    - One synthetic world: RS's `synth-crossings` structure plus ADV's planted policies, rendered as numpy arrays, with a synthetic flag on every number.
    - moto for S3 and Stubber for Bedrock. No CDK tonight.
    - The Bedrock adapter, probe script and model registry are merged before 08:00 for Kiro.
    - Strands runs via our ModelProvider with `SequentialToolExecutor` (Wednesday).
    - STAT's PPI variance fix, with the gold-only interval printed beside it.
- [ ] Step 3: spec sheet.
- [~] Step 4: build. **P0 scaffold** is on branch `pkg/p0-scaffold`: uv project, `canon.py`, typer CLI, offline test guard (blocks non-loopback sockets, clears `AWS_*`), CI workflow; 6 tests pass. It is not yet reviewed or merged.
- [ ] Morning report (`docs/OVERNIGHT-REPORT.md`).
