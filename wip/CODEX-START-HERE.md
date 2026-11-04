# Codex (or any agent): start here

Claude ran the overnight job until it stopped. This folder holds **work in progress** that was not finished enough for `docs/` or `src/`. Read in this order:

1. [`../HANDOFF.md`](../HANDOFF.md): the job exactly as Suhas gave it (hard rules, steps 1–5, Clay's values paraphrased), environment facts, and the current-state checklist.
2. [`../TODO.md`](../TODO.md): open items and the **Kiro prompts** for AWS-only steps.
3. `docs/design/SYSTEM-DESIGN.md` on `main`: the adopted system design. Branch `docs/system-design-factcheck` holds the fact-check pass 2 and A13 edits, plus a judge pass applying valid doubts. Merge it if it is not on `main` yet.
4. This folder:
   - `council-context.md`: shared brief given to all council agents. Its Clay values are paraphrased; never commit Clay's vision doc verbatim.
   - `council2/`: implementation council (Step 2).
     - `context.md`: the brief.
     - `a-*.md`: round-(a) proposals.
     - `b-*.md`: round-(b) debate with each seat's BLOCKING items.
     - `log-draft.md`: the council-2 log so far.
     - `c-design-r1.md`: the moderator's merge, if present.
     - `proto/`: the statistician's PPI and Rogan-Gladen prototypes.
   - `a13-draft.md`: first draft of SYSTEM-DESIGN §A13 (unkeyed methods compared).
   - `doubt-sd.md`: the doubter's 36 doubts on it.
   - `fc-keep.md`: fact-check pass 2 table.
   - `fixtures/nepal-flooding-aug-2026.stac.json`: real Vantor STAC metadata for the Nepal event. 33 scenes (4 pre, 29 post), ETags, simplified footprints. **No pixels.** CC-BY-NC-4.0 attribution included.

## Process rules Suhas set
- For every artifact (docs and code), run a doubter subagent, then a judge subagent that rules on each doubt, then apply the valid fixes.
- Councils have five seats (statistician, remote-sensing, agent-eval/observability, AWS architect, Clay/ADB/judging advocate). They go through propose → debate → neutral merge → vote until all five accept (at most 6 rounds; if round 1 is unanimous, force a devil's-advocate round first) → fact-check. Log every round.
- Push only to `origin` (the fork). Branch per package and merge to the fork's `main` when green. **Never** touch upstream `VishalPatil18/…`.
- No AWS credentials here. The container has a dummy `AWS_ACCESS_KEY_ID=proxy-injected`; do not use it. AWS steps become Kiro prompts in `TODO.md`.
- Before you run out of budget, push everything to this `wip/` folder and update `HANDOFF.md` → Current state.

## Where Step 2 stood when Claude last updated this file
See `HANDOFF.md` → Current state (updated at each checkpoint).
