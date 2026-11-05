# Running the Treehouse demo

Everything needed is in this repo. The demo replays recorded **live Amazon Bedrock runs** of the Nagoya port
warehouse task offline, so it needs no AWS account and no network after install.

## Quick start (fresh clone)

Needs `uv` and Node 20+.

```sh
scripts/demo.sh
```

The script installs dependencies, replays the two recorded runs into `out/demo/store`, verifies the sealed store,
builds the UI and serves it. Open **http://127.0.0.1:8790/**. Use `127.0.0.1`: the server rejects other host
names, including `localhost`. Set `STORE=` or `PORT=` to change either.

## What is in the demo

| Run | Worker | What it shows |
|---|---|---|
| `exp-nagoya-nova-1` | Amazon Nova Pro (Strands on Bedrock) | 10 warehouse sites at about 90 % stated confidence, none backed by evidence, so Treehouse marks them **unearned** |
| `exp-nagoya-sonnet-1` | Claude Sonnet 5.5 (Strands on Bedrock) | Picks 160 m AEF cells over 1,280 m Clay ("too coarse for buildings"); 10 low-confidence sites |

Both runs come from live Bedrock calls recorded on 2026-11-04 (`fixtures/live/cassettes/`). Their embeddings are a
**synthetic** fixture derived from the reference, and the UI labels them that way. Both have an Amazon Polly
narration (`ui/public/narration/`).

### Task and reference data
- Task cards: `tasks/t1-nagoya-warehouses.yaml` (keyed, synthetic embeddings) and
  `tasks/t1-nagoya-warehouses-real.yaml` (real LGND Clay v1.5 embeddings from AWS Open Data, incomplete OSM pool).
- Reference sets (grader-side only; the agent can never read `keys/`): `keys/plateau/nagoya-*.geojson`,
  `keys/osm/`.

### Real-data live runs (2026-11-05)
These read **real** LGND Clay v1.5 embeddings from source.coop on S3. Evidence is in `fixtures/live/real/`, and the
numbers are in `docs/KIRO-STATUS.md` (final-push section).

| Run | Notes |
|---|---|
| `nagoya-real-sonnet-thinking-2` | Sonnet with adaptive thinking (`display: summarized`): 4 thinking blocks with text, 5 of 9 decisions linked to their thinking |
| `nagoya-real-sonnet-thinking-1`, `nagoya-real-haiku-1`, `live-nagoya-real-sonnet-2` | Each declined to guess on coarse real cells and recorded one `cannot_assess` claim |

Open each run's self-contained report at `fixtures/live/real/store/bundles/<run>/report.html`. The raw model
exchange, including the thinking text, is in `fixtures/live/real/live-<run>.model.jsonl`. The committed real
store has no ledger, so the live UI will not open these runs. Re-running them needs AWS (see `probe/live1.sh` on
branch `lead/k1-probe`).

## A five-minute walk-through

1. Click the treehouse. The camera flies into the room and opens the book, styled as an agent console.
2. Under **Saved runs**, pick a Nagoya run and open it. The walk-to-the-window animation plays, and the binoculars
   show the GSI aerial map of Nagoya port with the agent's sites in red.
3. Click **Read the full summary**. It shows what was asked, the scale decision card (160 m vs 1,280 m), the
   decision tree, and a plain-language ending: *how confident, and was it earned*.
4. Open the **Dev view** and pick the Nova run. Read the **execution map**: lanes by kind of work, green or red
   decisions, red ✕ failed tool calls with counts, ◆ claims. Pick a site to see "Stated confidence 90 % —
   unearned" and the checks that lowered it.
5. Open **Settings**:
   - colour-vision-safe palettes (Okabe–Ito, blue–yellow, monochrome); status is also shown by shape
   - **Narrator voice**: plays the Amazon Polly MP3. Click something first, because browsers block audio
     without a click.

## For agents picking this up

- Start with `AGENTS.md`, `docs/ARCHITECTURE.md` (system and AWS services with live/built/designed status) and
  `docs/FUTURE-FEATURES.md` (what is next, in order of value).
- UI: `ui/src/shell/` (`story.tsx` storybook, `dev.tsx` dev view, `execmap.tsx` execution map, `tree.tsx`
  decision tree). Snapshot API: `src/treehouse/ui/`.
- Full check before any PR: `uv run pytest -q`, `uv run ruff check .`, and
  `cd ui && npm run typecheck && npm run build`.
- Recorded model requests replay byte-exact, so never change model-visible text for an existing card.
