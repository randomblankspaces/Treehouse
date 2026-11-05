# Treehouse — team 43

Treehouse evaluates how a geospatial agent investigates a target area and whether its resulting database is accurate. It records the agent’s strategy, foundation-model/tool choices, decision explanations, alternatives, evidence, revisions and reported confidence, then checks the sealed output independently. Warehouses, solar facilities and bridges are task examples; the sandbox is configured by object class and geographic zone.

**Run the demo:** `scripts/demo.sh`, offline, with no AWS needed ([walk-through](docs/DEMO.md)).

**Start here:** [architecture and AWS integration](docs/ARCHITECTURE.md) (presentation reference: what ran live, what is designed), [MVP plan](docs/MVP-PLAN.md), [ADB/LGND report digest](docs/REPORT-TABLES.md), [defence book](docs/design/DEFENSE-BOOK.md), [Kiro AWS log](docs/KIRO-STATUS.md).

**Live on AWS (2026-11-05):** Strands agents on Amazon Bedrock (Sonnet 5.5, Nova Pro, Haiku 5.5; Sonnet adaptive thinking), AgentCore Evaluations with Treehouse Lambda evaluators, S3 Object Lock COMPLIANCE run store (admin delete denied), KMS-isolated answer keys, CDK infrastructure, an **Amazon Polly** neural narrator for the web report, and the agent reading **real LGND Clay v1.5 embeddings** from AWS Open Data. The web UI presents a **decision tree** thinking view with colour-vision-safe themes.

## Warehouse MVP: what ran live (2026-11-05)

An ADB-style T1 task ("where are the warehouses in this AOI?") was run live by a **Strands agent on Amazon
Bedrock** (`us.anthropic.claude-sonnet-5-5`, plus `us.amazon.nova-pro-v1:0` as the comparison model) for
Nagoya (keyed), Gifu (transfer) and Chattogram (unkeyed). The agent recorded a decision before every tool
action. Treehouse sealed each run and scored it in separate panels. Every claim below points to a committed
artifact. **The embeddings and reference keys are synthetic fixtures**, because the real AEF and PLATEAU
sources could not be read from the workshop; see [docs/KIRO-STATUS.md](docs/KIRO-STATUS.md). The numbers show
the pipeline working, not real-world accuracy.

| What | Evidence |
|---|---|
| 17 live agent runs (Strands, Bedrock), pixel-free cassettes | `fixtures/live/cassettes/`, sealed manifests + decision ledgers in `fixtures/live/runs/`, `fixtures/live/experiments/runs/` |
| Experiment matrix (Sonnet × 3 cities × N=3, Nova Pro × Nagoya × N=3) with separate panels and bootstrap intervals | `fixtures/live/experiments/metrics.json` |
| Reasoning rules RV1–RV10 on live runs | `fixtures/live/rules/` |
| Reviewer model of a different family (Nova Pro) | `fixtures/live/review/` |
| AgentCore Evaluations: 4 built-ins + 2 Treehouse Lambda evaluators | `fixtures/live/agentcore/` |
| CDK deploy (Compliance Object Lock run store, KMS key bucket, Lambda evaluators, AgentCore evaluators) | `infra/cdk-outputs.json`, `aws-foundation.json` |
| Run sealed to S3 with COMPLIANCE retention; a delete of that version **denied** | `fixtures/live/receipts/` |
| Bedrock spend ledger ($11.49 after the WP-004 merge) | `.spend/spend.jsonl` |
| Thinking view: a **decision tree** (nodes linked by `parent_id`, branch-taken vs greyed alternatives, RV verdict chips, per-claim earned-confidence panel) in both the dev and story UIs, each ending with a plain-language run summary | `ui/src/shell/tree.tsx`, `src/treehouse/ui/decision_tree.py` |
| Accessibility: **Amazon Polly** neural narrator (sha-matched MP3 or browser-speech fallback), colour-vision-safe palettes (Okabe–Ito, blue–yellow, monochrome) and status by marker shape | `ui/public/narration/`, `scripts/narrate_polly.py`, `ui/src/shell/mapart.ts` |
| Real-data live run on `t1-nagoya-warehouses-real.yaml` (real LGND Clay v1.5, Sonnet adaptive thinking + Haiku) | `fixtures/live/real/` — see "Real-data live runs" below |

The decision-tree thinking view, the Amazon Polly narrator and colour-vision-safe themes landed in the final push (they supersede the earlier task10 UI omission). WP-004 (model thinking capture + deliberation score) is merged. Recorded vision-subagent attempts in the earlier matrix errored; no successful live geospatial vision result is established. The predicted-accuracy panel has insufficient validation (2 configs). Historical experiment tables have not been recomputed under the corrected held-out population rules.

### Real-data live runs (2026-11-05)

A reduced live matrix was run on `tasks/t1-nagoya-warehouses-real.yaml` against **real LGND Clay v1.5 embeddings** (source.coop on S3, CC BY 4.0):

| run id | worker | thinking | decisions | claims | Bedrock $ |
|---|---|---|---|---|---|
| `nagoya-real-sonnet-thinking-1` | Claude Sonnet 5.5 | adaptive ON | 11 | 1 × cannot_assess @ 0.9 | ~$0.52 |
| `nagoya-real-haiku-1` | Claude Haiku 5.5 | off | 12 | 1 × cannot_assess @ 0.9 | ~$0.74 |

Both agents read the real coarse Clay index (1.28–2.56 km cells, far larger than the 160 m scoring unit), had no usable fine imagery, and **declined to assert warehouses** — recording a single `cannot_assess` each rather than guessing. That is the honest behaviour for real coarse embeddings, not a measured accuracy number. Full numbers, deliberation metrics and manifests are in [docs/KIRO-STATUS.md](docs/KIRO-STATUS.md); sealed evidence (verified) is under `fixtures/live/real/`. AgentCore Evaluations on these runs and a wider matrix are listed in [docs/FUTURE-FEATURES.md](docs/FUTURE-FEATURES.md).

### Quickstart: replay a live run offline (fresh machine, no AWS)

```sh
uv sync --locked --all-extras
uv run python scripts/replay_live.py exp-nagoya-sonnet-1 --store out/replay/store   # seals, evaluates and prepares the report
uv run treehouse verify --store out/replay/store
npm --prefix ui ci
npm --prefix ui run build
uv run treehouse ui serve --store out/replay/store
# Open http://127.0.0.1:8765/?run=exp-nagoya-sonnet-1
```

### Run it live (needs AWS credentials and the spend guard)

```sh
uv run treehouse budget status    # stop if it exits 2/3
TREEHOUSE_SPEND_LEDGER=$PWD/.spend/spend.jsonl TREEHOUSE_CASSETTE_OUT=out/nagoya.model.jsonl \
uv run treehouse sandbox run --task tasks/t1-nagoya-warehouses.yaml \
  --config fixtures/live/configs/t1-nagoya-sonnet-strands.json \
  --provider treehouse.providers.factories:bedrock_recording --run-id nagoya-1 --store out/live/store
```

## Agent investigation MVP

```sh
uv sync --locked --extra api
npm --prefix ui ci
npm --prefix ui run build
uv run --extra api treehouse sandbox demo --store out/investigation/store --run-id investigation-demo
uv run --extra api treehouse ui serve --store out/investigation/store
# Open http://127.0.0.1:8765/?run=investigation-demo to inspect the saved run.
```

The offline example makes choices from observed scene metadata and synthetic image bytes, records a
parent-linked decision pathway, and produces an actual claim database. It uses an explicitly labeled
synthetic heuristic; it does not measure a foundation model’s real-world detection accuracy.
Choose a fresh store/run ID when repeating it.

The [sandbox guide](docs/INVESTIGATION.md) explains trusted agent/provider, classifier and tool-source
plugins, independent post-seal evaluation, and SQLite/GeoJSON exports. The separate review-model
interface uses a fresh context and independently written rubric; its judgments are model-estimated.
Reported confidence, evidence quality, empirical catalogue matching and cost remain separate.
A red marker means an agent prediction, with links back to the decision and evidence.

The small [USPVDB benchmark](keys/public-benchmark/README.md) has disjoint reference/holdout records
and source provenance. It is incomplete and tests reference/evaluator mechanics, not image accuracy.
Independent tests were authored in a different agent context before implementation; see
[test provenance](tests/investigation/PROVENANCE.md). AWS and real imagery/model integration are the
intended Kiro step for the confirmed minimal pipeline, followed by live testing and refinement.
Nothing on page load invokes AWS.

## Living Sky and Constellation Atlas

The product UI follows the [master UI specification](docs/TREEHOUSE_MASTER_UI_IMPLEMENTATION_SPEC.md).
It reads verified stored runs through the Python service: Clay search cells appear in a geographic sky,
and Atlas shows claims, imagery metadata, observable traces, separate score panels and provenance.
Story and Developer modes use the same records. Scene Builder and simulations remain planned.

```sh
uv sync --locked --extra api
npm --prefix ui ci
npm --prefix ui run build
uv run --extra api python scripts/offline.py treehouse demo --out out/demo
uv run --extra api treehouse ui serve --store out/demo/store
# Open http://127.0.0.1:8765
```

Use a fresh demo output if `out/demo` already exists. The Book starts pinned recorded presets;
custom live geospatial tasks are not enabled by this frontend. Page loads never invoke AWS.
The optional server-configured AWS evidence workbench is at `/judge/`. See
[product status](docs/PRODUCT-STATUS.md) for implemented features, evidence limits and Kiro checks.
No restricted imagery pixels or answer keys are served to the browser. This local app has no hosted
account system: use a restricted port preview, not a public production deployment.

## Quickstart (offline demo)

```sh
uv sync
uv run treehouse demo          # about 10 s, no network, no AWS
open out/demo/index.html       # or xdg-open
```

`treehouse demo` replays nine recorded runs (seven scripted agents on the synthetic `synth-crossings-v1` world,
two on the Nepal corridor task) through the plain loop, the tool gateway and live in-process MCP servers. Each
run is sealed into a fresh store at `out/demo/store`, the trace heads are checked against
`fixtures/golden/heads.json`, and then the demo checks, scores, reports and runs `treehouse verify`.
The demo refuses to run if its destination already contains `store` or `index.html`, preserving existing
outputs. Use a fresh destination for another run, for example `treehouse demo --out out/demo-2`. Record mode
also refuses existing model or trial cassette targets; choose a fresh `--cassette-out` directory or run id.
Concurrent recording writers to the same cassette destination are unsupported; run them one at a time.
The existence checks do not protect against simultaneous writers.

**Everything it shows is SYNTHETIC DEMO DATA.** The Nepal points are illustrative, not surveyed bridges.

What the merged demo shows today:
- **Checks:** R1–R9 are reached through the service's check runner. Applicable evidence and policy checks
  run; key-dependent checks can skip because the current service does not supply answer keys. Read each
  ledger's reasons rather than treating a skipped check as a pass.
- **Panels:** process basics and cost, speed and data (MEASURED, flagged as recorded; bytes are "modelled bytes"
  from the declared block model). Understanding and output panels: not built yet.
- **Trust passport:** a stub that reports *Not issued* ("trust engine not yet built").

Other commands:

```sh
uv run treehouse run fixtures/demo/configs/synth-good.json --mode fake     # re-run a scripted policy live
uv run treehouse run fixtures/demo/configs/synth-good.json --mode record   # record cassettes to out/cassettes
uv run treehouse verify --store out/demo/store
uv run python scripts/make_demo_fixtures.py   # rebuild every demo fixture (byte-identical)
```

## License

Code: [Apache-2.0](LICENSE).

Data used by this project keeps its own license:
- LGND embeddings: CC BY 4.0
- OpenStreetMap: ODbL
- Global Renewables Watch: MIT
- NAIP and USGS: public domain

See [docs/EXTERNAL-DEPENDENCIES.md](docs/EXTERNAL-DEPENDENCIES.md).
