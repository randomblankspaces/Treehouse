# Clay Agent-Eval Sandbox — team 43

An observability and evaluation sandbox for agentic geospatial workflows, built for [Clay](https://madewithclay.org) (Earth Dataset Foundry) at the AWS Breaking Barriers Challenge 2026 (DC). An LLM agent on Amazon Bedrock calls geospatial tools over MCP. Every run is traced, summarized, and scored on how the agent worked and what it produced, and agents are compared statistically.

**Start here:** [docs/README.md](docs/README.md) has the scope, MVP features, tests and definition of done. The team's decisions are in [docs/SCOPE.md](docs/SCOPE.md).

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
- **Checks:** R1 (schema and class), R2 (point inside the AOI) and R4 (evidence in trace: fabrication and
  ungrounded). Keyed match and R3/R5–R9 are not built yet.
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
