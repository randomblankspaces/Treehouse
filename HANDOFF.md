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

## Current state: checkpoint 3, ~03:15 EST Wed Nov 4
- [x] **Step 1** and **Step 2** are on main. Build from `docs/design/IMPLEMENTATION-DESIGN.md`: §7 is the package plan and §6 the tests; its final fact-check section overrides the body.
- [~] **Step 3** (spec sheet) is on branch `docs/spec-sheet` (180c8e9). A doubter raised 41 doubts. A judge is applying the valid fixes, then the branch is merged.
- [~] **Step 4: build.**
  - **On main (02ac127): P0, P0b, P1 and the P1 review fixes.** 213 tests pass, 1 deselected; ruff is clean.
  - **Built but not merged:** P2 and P3 on `pkg/p2-trace-store` and `pkg/p3-providers-loop`. Their review fixes are in progress on `pkg/p3-fixes` (blocking: seal and verify ledger holes).
  - **P4** (gateway and tools) is on `pkg/p4-gateway-tools` (06cdc4a, 233 tests). Its doubter is running.
  - **P6** (Bedrock adapter, spend ledger, probe) is on `pkg/p6-aws-a` (8a8f232, 234 tests). It is stacked on P3, **not** on P4. Its doubter is running. **It must be on main by 08:00 EST for Kiro.**
  - **P5** (demo skeleton) is being built on `pkg/p5-demo-skeleton`, stacked on P4.
  - **Merge order:** p3-fixes (which contains P2 and P3) → P4 (+ fixes) → P6 (+ fixes) → P5 → P7 → P8. Expect conflicts in `schemas/model_io.py`, `harness/plain_loop.py` and the golden schema files; keep both sides, then regenerate the goldens.
- At about 03:10 EST every agent stopped at a usage limit and was then resumed. If this happens again, run `git status` in each worktree and push any WIP.
