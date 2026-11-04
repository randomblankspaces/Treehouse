# Future Work

> **For agents — what this file is:** The record of post-build features we didn't implement but would if we had more time (SCOPE D21). It ships in the repo so Clay, judges, and future contributors can see where the project goes next. **Keep it current:** whenever a feature is cut or deferred during the build, add a row to "Cut during the build" with what it is, why it was cut, and how we'd do it. Nothing in this file is promised in the MVP. The cut line that put items here is SCOPE D66, from [design/SYSTEM-DESIGN.md](design/SYSTEM-DESIGN.md) A12 (**SD**) and [design/IMPLEMENTATION-DESIGN.md](design/IMPLEMENTATION-DESIGN.md) §7 (**ID**).

## Cut during the build

Fill this in as the build goes. Add a row the moment something is dropped, including any Should item below that doesn't get built.

| Feature | Why it was cut | How we would build it | Effort guess |
|---|---|---|---|
| | | | |

## Deferred by the cut line (built only if time remains before the deadline)

These are Should and Could items. They are planned, not promised. If one is not built by the T-6h freeze, move it to "Cut during the build".

| Feature | Tier | What it adds | Source |
|---|---|---|---|
| Leave-one-regime-out (LORO) validation table | Should, **only once a 2nd real keyed regime exists** | Tests whether trust transfers across regimes and whether the engine beats B2. Until then the passport says "not computable: 1 keyed regime". Synthetic tasks never count | SD A7, A12 Should 8; SCOPE D48 |
| Rogan–Gladen transfer (CALIBRATED-TRANSFER tier) | Should (W4) | Verifier-only estimate corrected by measured sensitivity and specificity, existence only, never damage; needs a same-family existence key such as an OSM bridge snapshot | SD A13 U2; ID W4 |
| Process-signal trust model (U3) and cross-trial vote fraction (U5) | Should (W11) | Replaces the wide B2 interval for MODEL-ESTIMATED numbers once a process feature is shown to predict keyed accuracy | SD A13 U3, U5; ID W11 |
| Predictive-validity strip (Panel 1b) | Should | Shows which process sub-scores predict keyed accuracy ("style, not signal" otherwise) | SD A6, A12 Should 4 |
| Unreported-places frame and miss rate | Should (W10) | Estimates what the agent missed, inside a defined corridor frame | SD A5; ID W10 |
| Cross-fitted λ for PPI | Should (above n_gold 50) | Narrower intervals once more gold exists | SD A7; ID §3 |
| Physical-plausibility rules (V1b) | Should | Rejects impossible claims (a "bridge" on a hillside); needs a non-key hydrography and road source | SD A13 V1b |
| Adjudication-queue export (V11) and leak canaries | Should | A CSV of worker–verifier disagreements; canary decoys in hosted key copies | SD A13 V6, V11 |
| CloudWatch / OTLP second tracer, Bedrock invocation-log witness | Should (W9) | Provider-side check that token and call counts reconcile with our trace | SD A4, A10; ID W9 |
| Lambda `imagery_window`; hosted report via CloudFront/OAC or presigned URL | Should | Window reads next to the data; a shareable report without public S3 | SD A9, A10 |
| FastAPI service | Should (W12) | The same service layer over HTTP for the UI | SD A9; ID W12 |
| Model-phrased plain summary (`phrase.py`) | W14 | Prose filled from fact slots, with the numbers lint | ID W14 |
| India run (beyond validate-only) | Could | Shows the same card running in a third region | SD A12 Could |
| Inspection-priority list (act-layer stub) | Could | Visible formula over the Certified Dataset; "needs field check" rows; a person approves; no real-world action | SD A11 |
| Masked-block OSM keying | Could | OSM stays a normal tool while a spatial block is withheld as the key | SD A2 |
| Agreement-on-the-line (U6), metamorphic tests (V7), cross-source triangulation (V8), capture–recapture bound (V9) | Could | More label-free checks; each needs extra runs or sources | SD A13 |
| Athena with DuckDB parity, AgentCore Evaluations column, Bedrock batch, Step Functions, AgentCore Runtime, KMS signing, CloudTrail data events | Could | Deeper AWS integration once the Must items are done | SD A10 |
| OpenAI-compatible provider adapter | Could | Ollama, vLLM or OpenRouter for the plain loop (Strands already covers them) | SD A3 |
| `start_eval` write tool on the MCP server | Could | Launch runs from an MCP client, with an explicit budget argument | SD A9 |

## Planned stretch (would implement next, roughly in this order)

Order per the review-1 judge (C13): Clay's stretch goals first; the simulation is a downstream consumer of the agent-built dataset, not part of the eval product. Hindcasting is the first stretch among truth sources (DD1, SCOPE D43); placing it right after Clay's goals is an interpretation for Suhas to confirm (D71).

| # | Feature | What it adds | Source |
|---|---|---|---|
| 1 | Sensitivity analysis | Re-run tasks while varying inputs and prompts (beyond the required model/harness/tooling comparisons, D3), and measure how stable both the agent and the eval are | Clay vision doc, Journey 2 (stretch) |
| 2 | Multi-agent traces | Planner / executor / checker agents, each traced, scored, and summarized | Clay stretch goal |
| 3 | Dynamic MCP tool discovery | The agent chooses tools from Clay's ~99-server catalog instead of a fixed tool set | Clay stretch goal |
| 4 | Richer trace-summary dashboard | Full UI on top of the parameter-complete API (UI deferred, D11) | Clay stretch goal · D11 |
| 5 | Temporal hindcast run (V10) | Freeze claims with `as_of`, then grade them when truth arrives. The only route to the L4 rung. The MVP builds only the hooks (`as_of` at the gateway, the frozen claim table). Needs an event with later public truth; the Nepal event has none yet | DD1; SD A11, A13 V10 |
| 6 | Dawid–Skene latent-class model (U7) | Per-source reliability with no key; needs at least 3 conditionally independent sources including a non-LLM one | SD A7, A13 U7 |
| 7 | Weighted conformal intervals | Coverage under covariate shift; report measured coverage until then | SD A7 |
| 8 | Agent-written verification code | The agent writes code that computes a dataset statistic, and the sandbox runs it to check the agent's claim | Team discussion (round 1, Q1 option b) |
| 9 | Batch trials on AWS | Large N-trial evals in parallel (Step Functions distributed map, Lambda or ECS) | OQ9; SD A10 |
| 10 | Second Clay task: caption generation | Five-criterion caption rubric, fixed/change tasks, retrieval answer keys. Full reference in [03-out-of-scope.md](03-out-of-scope.md) | Clay vision doc, task 2 |
| 11 | Flood and bridge-failure simulation | **Downstream consumer**, outside the eval product and the demo. First a Simulation Card spec only: editable inputs, user-selected place and click, "scenario, not prediction", human-verified, consuming only claims above the trust gate and stamped with the dataset's tier. Then the full version: after the agent returns the bridge dataset, the user selects a location and clicks to simulate. Treehouse builds a rough 3D layer from elevation, flood records, soil, pre/post-flood imagery and bridge type, size and condition, then shows a realistic (not over-engineered) failure simulation with every input number visible so it can be recreated. A person verifies each result. Validated against the August 2026 Nepal flood. Candidate data: Copernicus DEM, SoilGrids, Global Flood Database, Copernicus EMS, BIPAD (all unchecked) | Suhas, SCOPE D41; SD A11; SCOPE D71 |
| 12 | Third Clay task | The vision doc mentions three tasks but defines only two. Build it once Clay defines it | Clay vision doc |

## Beyond the hackathon (outside our 2-day mandate, natural next steps for Clay)

| Feature | Why it's not MVP |
|---|---|
| Hosted partner login (Fargate + Cognito), multi-user auth | Cut by SD A9/A10: a self-contained HTML report is enough for the demo |
| S3 Vectors for embeddings | numpy cosine over an AOI subset is enough at hackathon scale (SD A10 Stretch) |
| EventBridge re-check when new event imagery lands | Needs a running service; stretch in SD A10 |
| Amazon A2I human review | A CSV or static labelling page covers the MVP's 60–90 min block (SD A10 Stretch) |
| Full act-on-the-world layer | The core never mutates the world; ADB would replace the stub (SD A1, A11) |
| Run Clay's wider eval backlog through the sandbox | The MVP proves the loop on one task family |
| Partner-account deployment (e.g. ADB's own account) | Single sandbox account only |
| Production observability and warehouse (Snowflake/Iceberg/Athena, Managed Grafana) | A lightweight trace store is enough to prove the loop |
| Continental-scale builds | Too big for a 2-day sandbox |
