# Pitch page (`/pitch`)

A scrolling presentation that ends in the live product. Each section is one slide; content appears as it scrolls in.

| # | Slide | Point to land |
|---|---|---|
| 1 | Problem | Agents are building the maps that decide disaster money; nobody can see how. |
| 2 | Why it is real | Four ADB decisions (risk finance, PDNA, Risk Analytics Explorer, project teams) need asset lists they can trust. |
| 3 | Working backwards | Customer → their question → what earns trust → what we must capture → what we built. |
| 4 | How we fix it | Observe, Seal, Score separately. |
| 5 | Architecture | AWS diagram (AWS Architecture Center conventions), numbered steps 1–5. |
| 6 | Demo | Three modes; the recorded run scrolls through 1 investigate → 2 capture → 3 score. |
| 7 | By the numbers | Cost and speed (measured), what the evaluation caught (live agent, synthetic key), benchmark projection. |
| 8 | Impact | Before vs after; honest when blind; under $1 a run. |
| 9 | Future & scale | Now → Next (ADB pilot) → Scale (AgentCore Runtime, Step Functions, S3 Vectors); CDK into any account. |

Keys: **↓ / ↑ / Space / PageDown** next/previous slide (inside the demo they step through its stages first),
**T** light/dark theme (use light on washed-out projectors), **D** cycle demo mode. URL options: `?theme=light`,
`?demo=recorded|embedded|live`.

## Run it

```sh
uv sync --locked --extra api
uv run python scripts/replay_live.py exp-nagoya-sonnet-1 --store out/pitch/store   # the run the demo opens
npm --prefix ui ci && npm --prefix ui run build
uv run --extra api treehouse ui serve --store out/pitch/store
# open http://127.0.0.1:8765/pitch
```

`npm --prefix ui run dev` also serves `/pitch` (recorded mode works without the Python server).

## The three demo modes (pick one, strip the others)

| Mode | What it shows | Needs | Risk |
|---|---|---|---|
| **Recorded run** (`recorded`) | The live Bedrock run `exp-nagoya-sonnet-1`, replayed from its recording, as 3 scroll stages | Nothing (data bundled) | None; works offline |
| **Treehouse app** (`embedded`) | The real story / dev view of any stored run, inside the slide | `treehouse ui serve` with the run in its store | Server must be up |
| **Live on Bedrock** (`live`) | A new Strands + Bedrock run started from the slide, then opened when sealed | AWS credentials, `uv sync --extra aws --extra strands`, spend guard OK, `TREEHOUSE_PITCH_LIVE=1` | Costs ~$0.5–1; minutes; can fail live |

To strip a mode, delete its file and its line in `ui/src/pitch/demo/modes.ts`:

- recorded: `ui/src/pitch/demo/recorded.tsx` (+ `ui/src/pitch/data/recorded-run.json`, `scripts/build_pitch_demo.py`)
- embedded: `ui/src/pitch/demo/embedded.tsx`
- live: `ui/src/pitch/demo/live.tsx`, `src/treehouse/ui/pitch_live.py`, the `pitch_live.register` lines in
  `src/treehouse/ui/web.py`, and `tests/unit/test_pitch_live.py`

If you strip both `embedded` and `live`, also set `frame-ancestors` back to `'none'` in `src/treehouse/ui/web.py`
(it is `'self'` only so the pitch page can embed the app).

### Live mode safety

`POST /api/pitch/live` is refused (403) unless the server process has `TREEHOUSE_PITCH_LIVE=1`, the `boto3` and
`strands` extras are installed, and the repo spend guard is initialised and below the alarm. It takes no parameters:
the task (`tasks/t1-nagoya-warehouses.yaml`), config (`fixtures/live/configs/t1-nagoya-sonnet-strands.json`) and
model are pinned on the server. One run at a time. Bedrock responses are recorded to
`out/pitch-live/<run>.model.jsonl` (override with `TREEHOUSE_PITCH_CASSETTES`) so the run can be replayed.
Page loads never start a run.

## Data and honesty

- `ui/src/pitch/data/recorded-run.json`: built by `uv run python scripts/build_pitch_demo.py` from the same snapshot
  the UI API serves. It keeps the provenance labels.
- `ui/src/pitch/data/stats.json`: built by `uv run python scripts/build_pitch_stats.py` from `.spend/spend.jsonl`
  (read only) and `fixtures/live/experiments/metrics.json`. Every block is labelled **measured**, **live agent ·
  synthetic answer key**, or **projection**.
- The experiment matrix uses synthetic embeddings and answer keys (see `docs/KIRO-STATUS.md`): its recall numbers
  show the pipeline catching an under-performing agent, not real-world accuracy. Say so when presenting.
- The projection is arithmetic: measured mean cost and wall time per run × the ADB benchmark scope in the inception
  report (7 places × 5 asset classes × 3 models × 5 seeds). It is not a quote or an AWS bill.

Re-run both scripts whenever the run, the ledger or the snapshot contract changes.

## Architecture diagram

The slide follows AWS Architecture Center conventions: AWS Cloud and Region group boxes, AWS category colours
(AI/ML teal, compute orange, storage green, security red, management pink), orthogonal connectors and numbered
black callouts with a legend. The editable source is `docs/architecture/treehouse-aws.drawio`, built with draw.io's
AWS 4 shape library (open it at app.diagrams.net). Keep it and `ui/src/pitch/architecture.tsx` in sync.
