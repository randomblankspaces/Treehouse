# Master Kiro prompt — build the Treehouse MVP

Paste the block below into Kiro (Workshop Studio, us-east-1). It is self-contained.

```
You are building the Treehouse MVP in this AWS account. Work autonomously until the MVP acceptance
checklist in docs/MVP-PLAN.md §8 passes, or until a hard blocker or the spend guard stops you.

SETUP
  git clone https://github.com/randomblankspaces/Treehouse.git || (cd Treehouse && git pull)
  cd Treehouse
  export PATH="$HOME/.local/bin:$PATH"; command -v uv || curl -LsSf https://astral.sh/uv/install.sh | sh
  uv sync --locked --all-extras
  (cd ui && npm ci && npm run build)
  export TREEHOUSE_SPEND_LEDGER=$PWD/.spend/spend.jsonl
  uv run treehouse budget status

READ FIRST (in this order), then follow them as your contract:
  .kiro/steering/product.md, tech.md, structure.md   (loaded automatically; re-read if unsure)
  docs/MVP-PLAN.md          — the goal, decisions DM1–DM10, panels, rules RV1–RV10, acceptance checklist
  docs/REPORT-TABLES.md     — the ADB/LGND report: imagery licences, tasks, protocol, taxonomy, workflows, metrics, models
  .kiro/specs/treehouse-mvp/requirements.md, design.md, tasks.md   — the executable spec
  docs/INVESTIGATION.md, docs/design/STRANDS.md, docs/design/AWS-BLUEPRINT.md, docs/design/DEFENSE-BOOK.md
  probe-report.json         — what this account allows (Bedrock vision OK; AgentCore allowed; Bedrock batch DENIED; CDK not bootstrapped)

WHAT YOU ARE BUILDING (one paragraph)
  An ADB analyst asks "where are all the warehouses in this city?" (T1 retrieval). A Strands agent on
  Bedrock answers it by choosing foundation-model resources (AEF 10 m, LGND Clay precomputed, optionally
  Clay computed on 160 m chips, a Bedrock vision model on GSI aerial chips), a cell size, a retrieval
  method, a classifier (linear probe / linear SVM / Strands vision sub-agent) and a threshold, then plots
  red predicted sites. Treehouse records a decision with a "why" before every action and judges the
  thinking: (a) reasoning validity, (b) confidence calibration, (c) predicted accuracy from reasoning —
  three separate scores — plus output accuracy under the report's protocol and cost/time/data. Scenarios:
  Nagoya (keyed, PLATEAU) → Gifu (transfer) → a Bangladesh city (unkeyed, OSM precision only).

HOW TO WORK
  1. Do .kiro/specs/treehouse-mvp/tasks.md in order. One task = one branch kiro/<n>-<slug> = one PR into
     main of randomblankspaces/Treehouse (gh pr create --repo randomblankspaces/Treehouse --base main).
     Write tests first. Merge only when `uv run pytest` and `uv run ruff check .` are green. Tick the task
     box in tasks.md in the same PR. Never push to VishalPatil18/....
  2. Before every live AWS or Bedrock step: `uv run treehouse budget status`. Exit 2/3 (spent+reserved >
     $350) or a wrong/empty ledger after K1 → STOP and report. Never delete, move, truncate or re-create
     .spend/spend.jsonl. Size trial counts from the measured cost of the first live run.
  3. Live tests stay marked @live and skipped by default; record pixel-free cassettes of every live run so
     the offline demo can replay it.
  4. Never commit credentials, account IDs/ARNs (redact to role names), imagery pixels or Bedrock image
     payloads. Never use Maxar/Vantor imagery. Never let a grading reference (keys/) reach the agent.
  5. Verify every AWS API, CDK construct and Strands API against installed packages or official docs before
     using it. Do not invent names. Bedrock batch inference is denied here — do not use it.
  6. If something is blocked (a service denied, a dataset unreachable, AEF access unavailable): write the
     exact error and your workaround to docs/KIRO-STATUS.md, then continue with the next task that does not
     depend on it. Do not stop the whole build for one blocker.
  7. Claim only what ran. Every live claim in README/demo must point to a committed artifact
     (cdk-outputs.json, AgentCore results JSON, sealed-run manifests, metrics JSON).

REPORT BACK after each task, and at the end, in this format (keep it short):
  === TREEHOUSE KIRO STATUS ===
  task: <n> <name> | branch | PR url | merged yes/no
  tests: <passed/failed/skipped> | ruff: ok/fail
  live AWS run: <what ran, model ids, $ spent this task, ledger total>
  artifacts committed: <paths>
  blockers: <one line each, with workaround>
  acceptance checklist (MVP-PLAN §8): <ticked items> / 11
  next: <next task>
  === END ===

Start with task 0 now.
```

## Notes for Suhas
- Kiro picks up `.kiro/steering/*.md` automatically; the spec lives in `.kiro/specs/treehouse-mvp/`.
- The Workshop credentials expire (the probe saw a ~6 h expiry). If Kiro reports auth errors, refresh the
  session in Workshop Studio and tell Kiro "continue from the last unticked task in tasks.md".
- Paste Kiro's status blocks back to Claude for review whenever you want a second check.
