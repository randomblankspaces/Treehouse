# Treehouse shell UI — design direction and plan

Agreed with Suhas on 2026-11-04 (design interview, then "execute … make our better decision, I trust you").
Scope: the UI shell only. Backend, model logic and AWS integration are built separately; every
data-dependent spot goes through one typed seam (`ui/src/shell/contract.ts`).

## What Treehouse tracks
The **input** (task, area, time window, allowed tools and data), the **context** the model was given,
its **thinking**, and the **trace** (OpenTelemetry GenAI spans: `invoke_agent` → `chat` → `execute_tool`).
We evaluate the **model**, not the framework: **Strands is a tool the model may choose** — a labelling
sub-agent it calls to tag image chips and build the claims database. A Strands call is a key decision
in the trace, and its own sub-agent spans nest under it so a developer can drill in.
Output grading is not tracked in the shell. Cost and elapsed time are shown because they are cheap and
first-class. The same contract serves both interfaces and can be exposed through the Treehouse MCP.

## Two interfaces, one contract
| | Storybook (`/`, intuitive) | Dev (`/dev`, technical) |
|---|---|---|
| Who | partners, judges | developers, technical reviewers |
| Look | pixel art drawn in code, from the logo (purple / yellow / black) | plain, dense, terminal-like; no scene graphics |
| Flow | night/day treehouse → one continuous zoom → book (input) → boy takes binoculars → window → live map → summary → export → back to book | run picker → input / context / narrator → trace tree + inspector |
| Must show | key decisions (foundation-model use, data access) with reasoning, live and in the summary | everything, drillable down to raw span attributes |

**Key decisions** are highlighted in both: a decision is key when its tool uses a foundation model
(`list_embedding_sources`, `build_index`, `retrieve`, `classify`, `strands_label`) or reads data
(`get_examples`, `imagery_window`). Mapping lives in one table in `contract.ts`.

## Demo data
Nagoya Port warehouses (T1 retrieval, keyed), the worked example of the LGND/ADB inception report
(`tasks/t1-nagoya-warehouses.yaml`). The mock run is scripted from that task card's AOI, tools and
data allowlist. It is labelled MOCK in the UI at all times.

## Seams (typed, swappable)
- `TreehouseClient` — `listRuns()`, `snapshot(runId)`. Live runs are polled (~1 s) until
  `status` is terminal. `http.ts` adapts today's endpoints (`/api/runs`, `/bundle`, `/investigation`);
  `mock.ts` replays a scripted Nagoya run in real time.
  - Backend ask: serve a partial snapshot while a run is in flight (today `/bundle` is 409 until sealed),
    and record model **thinking** text on `chat` spans (today only hashes are kept).
- `Narrator` — `line(step, snapshot) → {text, audio_url}`. Mock writes captions from templates.
  AWS plan: Bedrock writes the line, Polly speaks it (`audio_url`). Captions are always on screen and in
  an `aria-live` region, so audio is never the only channel.
- Client choice is build-time: `npm run dev` uses the mock unless `VITE_TREEHOUSE_API=http`; a
  production build uses HTTP unless `VITE_TREEHOUSE_API=mock`.

## Visual system
- **Palette** from the logo. Dark (default): ink `#0d0b12`, panel `#16131d`, text `#ece8f4`,
  purple `#b59cff`, key-decision yellow `#f6c945`, error `#ff8a80`, ok `#6fd39a`. Light and high-contrast
  themes; a colour-blind-safe set (Okabe–Ito blue/orange). Status is never colour alone: every state has
  a text label or glyph.
- **Type**: system UI sans for labels, system monospace for data (no web-font downloads).
- **Motion** (storybook): one camera, nested scenes handed off at whole-number pixel scales; ease-out
  only; reduced motion turns the zoom into a cut. Dev UI motion is limited to new-row fade and the live bar.

## Accessibility settings (both interfaces, shared storage key)
Theme (dark / light / high contrast), text size (100 / 125 / 150 %), reduce motion (follows the system
by default), colour-blind-safe palette, narrator captions, skip intro (storybook). AA contrast, 44 px
targets, full keyboard use (arrow keys in the trace), visible focus.

## Build order (Q2 = A)
1. Dev UI + contract + mock + http adapter + narrator seam. **(this PR)**
2. Storybook: pixel scenes in code, zoom, book input, window/map, summary drawer, export
   (File System Access API folder save, zip/JSON download fallback for Safari/Firefox).
3. Backend asks above (Kiro), Polly/Bedrock narrator.

## Run it
```sh
npm --prefix ui ci
npm --prefix ui run dev        # open http://127.0.0.1:5173/dev (mock data)
VITE_TREEHOUSE_API=http npm --prefix ui run dev   # against `treehouse ui serve` on :8765
```
