# HANDOFF — overnight job (for whichever agent picks this up)

> Current handoff: read [docs/KIRO-HANDOFF.md](docs/KIRO-HANDOFF.md),
> [docs/OUTLINE.md](docs/OUTLINE.md) and [docs/PLAN.md](docs/PLAN.md) first. The product now includes
> an opt-in decision/evidence investigation sandbox and observatory UI. Local checks do not prove
> live model/imagery accuracy. Suhas will provide further context after the reviewed main merge;
> Kiro then handles AWS integration/live testing, followed by refinement. The overnight narrative
> below is retained as history and must not be executed blindly.


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

## Current state: checkpoint 4, ~04:00 EST Wed Nov 4
- [x] **Steps 1, 2 and 3** are on main. The design docs and spec sheet each went through a doubter and a judge.
- [~] **Step 4 (build).** **Main is at 7eebedf: P0, P0b, P1, P2, P3, P4 and P6, each with its judged review fixes. 507 tests pass, 2 live tests are skipped and 1 is deselected; ruff is clean.** P6 (Bedrock adapter, spend ledger, probe) is on main, so the Kiro steps K0–K2a can run now.
  - **P5 (demo skeleton)** is on `pkg/p5-demo-skeleton` (57a84a8). `treehouse demo` works offline in about 8 s; 385 tests at that commit. **It is not on main yet.** A doubter is running. After that, a judge must merge main into P5, re-record the demo cassettes and goldens (`uv run python scripts/make_demo_fixtures.py`), apply the fixes, and then merge.
  - **P7 (checks and panels)** is being built on `pkg/p7-checks-panels`, stacked on P5.
  - **P8a (pure trust engine: sampling, PPI, baselines, tiers, gate, passport, M1–M17)** is being built on `pkg/p8a-trust-core` from main. **P8b** wires it into the demo after P5 and P7 land.
  - The merge log with test outputs is in `wip/merge-log.txt` (copied at each checkpoint).
- [x] TODO.md holds the Kiro prompts K0–K9 and H. The P6 judge updated them: the ledger must exist (`budget init`), prices are per model and profile, and `budget reconcile` runs against the AWS bill.
