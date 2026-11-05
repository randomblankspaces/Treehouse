# Kiro final push — 2026-11-05, 07:30 → 09:40 EST (autonomous)

Suhas is commuting with no network; the Claude lead is offline. You (Kiro, in Workshop Studio) finish the build.
Repo: `/workshop/Treehouse` = github.com/randomblankspaces/Treehouse. Work only on this fork. **Repo is judged at 10:00.**

## Rules (read first)
- Read `AGENTS.md`, `.kiro/steering/*.md`, `docs/ARCHITECTURE.md`. Claim only what ran; label synthetic data.
- Never commit credentials, AWS account numbers/ARNs, imagery pixels or base64 image payloads. Scan before every commit
  (`grep -nE 'AKIA[0-9A-Z]{16}|arn:aws:[a-z-]+:[a-z0-9-]*:[0-9]{12}|base64'`).
- Never use Maxar/Vantor imagery. Never let a grading key reach the agent.
- Before any live AWS step: `uv run treehouse budget status` (stop on exit ≥ 2). **Bedrock budget for this push: $15.**
- Do not edit `.spend/spend.jsonl` by hand; never delete/truncate it.
- **Kiro credits:** stop development once the account shows **940 / 1000 used**; keep the rest for AWS checks.
- Every change: branch → `uv run pytest -q` + `uv run ruff check .` + `cd ui && npm run typecheck && npm run build`
  green → PR into `main` → merge. Pull `main` first; resolve conflicts in favour of main's tests.
- **Stop all work at 09:40** with `main` green.

## Tasks, in priority order

1. **Finish the two unmerged packages** (Codex is out until 10:35; WP-003 and WP-007 are already in `main`).
   - **`wp/WP-004` (on origin)** — model thinking capture + deliberation score. Its suite is green and the reviewer
     left two Blocking findings: (a) `src/treehouse/investigation/__init__.py` `_ObservedProvider` stores responses by
     `trial_index` only, so a non-worker call with `trial_index=0` overwrites the worker turn's thinking; key by
     (role, trial_index) and record worker turns only; a positional `trial_index` must not raise KeyError.
     (b) `src/treehouse/investigation/runtime.py` ~179: attach thinking from the worker turn that produced the
     `record_decision` call, and make `thinking_ref` the sha256 of the thinking/Reasoning text only. Add a test for each.
     Also drop temperature only for Claude models when thinking is on (`providers/bedrock.py` ~270), so Nova runs keep
     it. Merge `main` in first: it conflicts on `tests/golden/schema/manifest.json` and `runconfig.json`; regenerate
     the goldens the way the tests say. Then PR and merge.
   - **WP-010 (not started; branch from `main`)** — small WP-002 follow-ups: derive the LGND month from the card's
     `time_window` instead of the hardcoded `month=4` in `tools/retrieval.py` and record it in provenance; accept
     `RunConfig.servers` import paths only under `treehouse.providers.factories:`; one shared helper so every
     `run_investigation` call without a server factory uses `cfg.servers`. Do this only if task 2 and 3 are done.
   Keep every model-visible string identical to main (recorded cassettes replay byte-exact).
2. **Simple thinking view (the essence of the demo)** — spec in `docs/FUTURE-FEATURES.md` §F2 and §F3. In the run
   report/story UI (`ui/src/shell/story.tsx`, `report.tsx`): (a) a pinned **scale card** for the cell/chip-size and
   foundation-model decision (chosen vs rejected options, the object's size from `config/asset-classes.yaml`, the agent's
   one-sentence why); (b) one card per decision with a one-sentence "Chose X over Y because Z", a confidence bar, a
   verdict chip from the RV rules (✓/⚠/✗) and an evidence badge; (c) clicking a red site shows the decision chain that
   produced it; (d) a short "How confidence is gauged" panel (stated vs calibration vs earned) using the text in §F3,
   with the deliberation numbers if WP-004 merged. Build from data already in the snapshot API; no new backend unless
   needed. Check at 1440 px and 390 px.
3. **Narrator + colour themes (accessibility).** `scripts/narrate_polly.py --store <store> --run <id> --out ui/public/narration/`
   (Amazon Polly neural, ≤2,900-char chunks, writes `<run>.mp3` + `<run>.json` with text sha256, voice, engine).
   The UI already has `useNarration` in `ui/src/shell/hooks.ts` playing `audio_url`: play the MP3 only when its sha
   matches the shown summary, else browser speech; label "Voice: Amazon Polly". Colour-safe theme options (Okabe–Ito
   red–green safe, blue–yellow safe, monochrome) and status by marker shape (present = filled circle, cannot_assess =
   hollow diamond, absent = ×). Generate MP3s live for the committed demo runs.
4. **Live runs (≤ $15):** use `probe/live1.sh` from branch `lead/k1-probe` (`git show origin/lead/k1-probe:probe/live1.sh`)
   or the same commands: card `tasks/t1-nagoya-warehouses-real.yaml` (real LGND Clay), Sonnet with `thinking` on × 2,
   Haiku × 1, Nova Pro × 1; if WP-007 merged, one run of a card with `user_examples` so the agent reaches the vision
   sub-agent; if WP-003 merged, Chattogram fuel tanks × 1. Env for vision: `TREEHOUSE_VISION_MODE=record`,
   `TREEHOUSE_VISION_CASSETTE`, `TREEHOUSE_GSI_LOG`, `TREEHOUSE_CASSETTE_OUT`. Commit evidence under
   `fixtures/live/real/` exactly like PR #31 (scan first), then run AgentCore Evaluations on one new run
   (`src/treehouse/aws/` helpers) and commit the result JSON (account id redacted).
5. **Docs and numbers:** update `docs/ARCHITECTURE.md` status rows and README "what ran live" with what actually ran
   (run ids, $ spent, decisions the agent made, deliberation numbers); append a final section to `docs/KIRO-STATUS.md`.

Anything you cannot finish goes into `docs/FUTURE-FEATURES.md` with what is left.

If something is blocked, record it in `docs/KIRO-STATUS.md` and move to the next task. Do not ask questions; there is
nobody to answer before 10:00.
