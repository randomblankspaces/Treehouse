# ADV round (b): attacks, concessions, revised position

## 1. Attacks

**A1. Four of five plans put the demo after the end of the night. This is the decisive conflict.** Totals from each I7 table:

| Plan | Total | Where the demo sits |
|---|---|---|
| STAT (a-stat I7) | about 20 h | its replay package is P6, but the report is P11 |
| OBS (a-obs I7) | about 20 h | `demo` is in P10; its stated "minimum handoff" is P0–P7, which has **no scorer and no report** |
| RS (a-rs I7) | P0–P14 sum to 20 h | `demo synth` is P13 |
| AWS (a-aws I7) | about 21.5 h | demo is P12 |

The overnight agent has about 6–8 h. Under any of those orders, on Wednesday morning the repo has a gateway and adapters but nothing a judge or Suhas can open. That fails DoD rows 1 and 12 and J8. A vertical slice (trace, seal, minimal score, minimal HTML) must merge by about H4; later packages deepen a working demo (SYSTEM-DESIGN A12: "one thin vertical slice beats broad half-built layers").

**A2. Virginia keyed grading tonight is not feasible.** RS measured that USGS/USPVDB is blocked and NAIP returns 403 (a-rs §0.3, §5.3: `key.status: pending_fetch`). OBS P8 ("Virginia fixture grade") and AWS P8 assume a Virginia key that cannot exist before Suhas's Mac fetch. Tonight's only keyed calibration is the synthetic world.

**A3. CDK, moto and the OTLP mirror are not tonight's work.** AWS P7 is 2.5 h and appears in its never-cut list, and it adds a node toolchain to CI. AWS's own synth check shows it works offline (a-aws "What I checked"), so it is cheap to do **on Wednesday**, by the same agent, while Suhas runs K1–K2 (the probe and the vision smoke test). Neither K1 nor K2 needs CDK or S3Store. Night hours on it buy nothing visible at 08:00.

**A4. Real COG reads tonight are a time sink and a licence hazard.** RS measured 367 requests and 25 s for one Vantor window without a block cache (a-rs §0.2). Decoded Vantor pixels are CC-BY-NC, and their hashes are unstable across libjpeg builds (a-rs caveat). RS's ETag-pinned `rangeio` belongs on Wednesday behind `@network`, outside the default test and demo paths.

**A5. STAT's complexity beyond the fix.** The pooled-rectifier and pseudo-disagreement variance fix is justified by STAT's own evidence: the naive bootstrap gives 0.60 coverage with a perfect verifier and 0.76 with a strong one (a-stat §0). Without it, our high-sensitivity fake verifier would print a falsely narrow interval. But three items cannot fire tonight:
cross-fitted λ (needs n_gold ≥ 50), DerSimonian-Laird τ (needs ≥ 2 keyed regimes) and the `estimators.lock` test (wait until code settles).

**A6. OBS's MEASURED tier is right but needs a fence**, or it becomes a back door for untyped accuracy claims: a validator allows it only on trace-exact panels (1, 2, 5), never on output or trust estimands.

**A7. RS's synth-crossings is better than my synthetic-sites, but its cost is understated.** Accuracy comes from a real detector on returned pixels, not a dialled constant, and its cloud trap is KEYED. Its cost (synthworld 1.5 h + COG path 2 h) is understated; the demo needs no COG files.

## 2. Concessions (positions I change)

1. **I adopt RS's `synth-crossings` world and detector-driven policies.** They replace my dialled planted traces. I keep my extra policies: looper, overconfident, budget-stop, and the 0/10/20/40% corruption series. The world is seeded numpy arrays served directly by `imagery_window`; one separate test round-trips a tiny DEFLATE GeoTIFF through rasterio.
2. **Strands is no longer a risk to replay.** OBS showed that `TreehouseStrandsModel` wraps our provider and that a FakeModel drives a real Strands Agent offline (a-obs §I3). Cassettes replay under Strands too; my risk #2 is withdrawn.
3. **AWS is right that Kiro should only run code.** I move the **Bedrock adapter (Stubber) and the Strands adapter** into the overnight set, merged before 08:00, so that K3/K4 live runs can start on waking. S3Store (moto) and CDK come next, on Wednesday morning, by the agent.
4. **I accept the MEASURED tier with the A6 fence.** Chip: "Measured from trace"; replayed numbers carry a `replayed` flag (a-obs I9.7).
5. **I accept STAT's variance fix**, plus the classical gold-only interval and the width ratio printed next to the PPI interval (a-stat finding 2).
6. **I adopt RS's facts:**
   `pan_gsd` not `gsd`; Nepal test-retest pair E5610/E5810 with **no pre/pre placebo**; India on Sentinel-2, ABSTAINING from trust transfer.
7. **From AWS:** P0 env scrub (`AWS_ACCESS_KEY_ID=proxy-injected`) and the spend-ledger hard stop.
8. My 7.2 h was optimistic; re-planned to about 8 h.

## 3. Revised position

Overnight order, one PR per package, all offline:

| # | Package | h |
|---|---|---|
| P0 | scaffold, offline guard, env scrub, CI | 0.4 |
| P1 | schemas (TypedNumber with MEASURED and its fence) and 3 cards | 0.8 |
| P2 | store, per-trial chained tracer, seal, verify | 0.6 |
| P3 | gateway and in-process MCP tools on synthworld arrays and committed Vantor STAC JSON; budget guard with spend ledger | 1.2 |
| P4 | Fake and Replay providers, plain loop, `run` | 0.7 |
| **P5** | **demo skeleton**: `treehouse demo` replays both tasks and writes minimal HTML; README quickstart; clean-clone offline CI job (**gate: by about H4**) | 0.5 |
| P6 | Bedrock (Stubber) and Strands (FakeModel) adapters; J3 swaps | 1.0 |
| P7 | rules, keyed grader, Panels 1/2/3/5 | 1.0 |
| P8 | sampling, recorded verifier, synthetic gold, PPI with STAT's variance fix, B0/B1/B2, abstain, passport, method tests | 1.3 |
| P9 | five-panel report, chips, summary lint, synthetic banner | 0.7 |
| | **Overnight total** | **about 8.2** |

**Wednesday agent queue:** Rogan-Gladen, compare/stats (J5/J6), MCP server, S3Store (moto), CDK synth, `rangeio` Vantor reads, FastAPI (J9), `synth/study.py`.

**Cut order** if the night slips: P9 polish, then the summary lint, then the P6 Strands half (Bedrock stays), then P8's B1/B2 (B0 and PPI stay).

**Decisions I insist on:**

| # | Decision | Blocking |
|---|---|---|
| D1 | A demo skeleton (P5) is merged before any trust maths. A clean-clone `uv sync && uv run treehouse demo` passes offline in CI. | **BLOCKING** |
| D2 | The demo **re-runs the pipeline** from sealed cassettes (replay, seal, check, score, trust, report). It never renders pre-computed JSON. | **BLOCKING** |
| D3 | Every synthetic artefact carries `synthetic: true`. The manifest flag drives the report banner. Gold is labelled "SYNTHETIC GOLD, not human labels" and verdicts "recorded fake verifier". | **BLOCKING** |
| D4 | Bedrock and Strands adapters are merged before 08:00. Kiro runs code; it does not write it. | **BLOCKING** |
| D5 | Not tonight: CDK, moto, real COG/HTTP reads, OTLP, cross-fitted λ, τ, LORO, Dawid-Skene, conformal, act layer, UI. Virginia ships as `pending_fetch`. | **BLOCKING** |
| D6 | No bare floats. MEASURED is allowed only on trace-exact panels. The chip-invariant HTML test exists. | **BLOCKING** |
| D7 | STAT variance fix + classical interval; RS synth world as arrays; plain loop in Must-0 as reference harness; J10–J15 for S14–S19 | non-blocking |
