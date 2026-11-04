# Council 2, round (b): OBS debate

New evidence (`scratchpad/obs/t5.py`): Strands' default `ConcurrentToolExecutor` finishes two same-turn tool calls as **[b, a]**; `SequentialToolExecutor()` gives **[a, b]**.

## 1. Attacks

**A1. The package plans do not fit the night.** Four of the five plans (STAT I7, AWS I7, RS I7, and mine) total about 19–20 h. Only ADV I7 commits to an overnight block (7.2 h for P0–P8), with 0.4–1.3 h per package where others estimate 1–2.5 h. Realistically, 8–10 green PR cycles fit overnight. So we need **one merged plan** with an explicit overnight block, a 04:00 checkpoint, and a Wednesday block that the agent builds while Suhas runs Kiro (§3).

**A2. AWS: Strands on `strands.models.bedrock.BedrockModel` with "a hook to emit our spans"** (AWS I3, Bedrock adapter) breaks three things.
- **Record/replay**: BedrockModel calls boto3 itself; the cassette never sees the request.
- **One code path per number** (A9): usage, cost and stop reasons would be parsed twice.
- **Testing**: double the Bedrock surface.

STAT I3 already specifies the alternative: a `Model` subclass that wraps our provider. I showed tonight that this drives a real Agent offline.

**A3. AWS: botocore `retries={"mode":"adaptive"}`** hides throttles inside botocore, so "every throttle becomes a span event" would need event hooks. Simpler: botocore `max_attempts=1` plus our own retry loop, one span event per attempt.

**A4. Tier enum gap, in every other seat.**
- STAT I2 types `cost_usd`, `seconds`, `bytes` but allows only the five trust tiers, so a cost would have to claim KEYED or MODEL-ESTIMATED.
- ADV I2 forbids floats outside TypedNumber, yet gives Panel 5 (J14) no tier.
- AWS I2 invents `UNPRICED` (tier or type?).

Commitment 2 needs a tier on every number; each seat improvised one. `MEASURED` names it once. `UNPRICED` then becomes `value=None, tier=MEASURED, reason="unpriced"`.

**A5. STAT I1 puts `mcp` in the extras**, but the gateway *is* in-process MCP on the demo's core path: it must be core. **A6. RS I1 makes rasterio core** and renders synthworld as COGs; the fresh-machine demo should not need a GDAL wheel (ADV I9 risk 5). RS's COG and rangeio tests stay, behind `[geo]`.

**A7. ADV I9 risk 2: "Strands' loop is not replay-deterministic."** Only half true. With our model wrapper plus `SequentialToolExecutor`, the order is fixed (t5.py). I agree the plain loop is the demo engine. I do not agree that Strands can only be smoke-tested. A contract test "same script → same claim table under both harnesses" is cheap.

**A8. What the replay demo runs.**
- AWS and STAT (`replay fixtures/runs/…`) are ambiguous: re-score sealed runs, or re-run cassettes?
- ADV I7 P5 has it right: the demo must re-run the worker from cassettes **through the real loop, gateway and MCP tool servers**, seal into a fresh store, then check, score, trust, report and `verify`.
- Nobody else specifies how "byte-identical trace hashes" (ADV I6, AWS golden) can hold given wall-clock timestamps and random span ids. They need my injected `Clock` and `LogicalClock` plus seeded ids. Without that, those golden tests cannot pass.

**A9. Synthetic world: ADV `synthetic-sites-v1` vs RS `synth-crossings`.**
- RS's world matches the flagship family (crossings, cloud trap). Its key carries `visible_in[scene]`, so `cannot_assess` is **KEYED-gradable** and it has a real test-retest scene pair. ADV's rectangles demonstrate nothing about bridges.
- But it costs 3.5 h (RS P4 + P5) and needs rasterio.
- Merge: RS's world semantics (river, 40 crossings, distractors, post_a / post_b cloudy / post_c shifted) rendered **directly in numpy** by a `SyntheticImagerySource` behind the same `imagery_window` contract, plus a 20-line PNG encoder (zlib + struct). The planted policies come from ADV's roster, mapped to RS's names: good = careful, fabricator, key-peeker = leaker, looper, overconfident = guesser, plus skimmer and budget-stop.
- RS's "detector on pixels" policies are a Should. FakeProvider already accepts a callable policy.

**A10. ADV's Nepal demo** puts synthetic crossing points on a real event polygon, with fake verdicts and synthetic gold. A banner is not enough, because MCP quotes numbers out of context: `synthetic: true` must travel in every `TypedNumber.detail` and the chip text.

## 2. Concessions

1. **My cassette key had a bug.** Keying on the request hash alone collides across K trials: trial 2's first request equals trial 1's, but Bedrock answered differently. I adopt AWS's key `(role, trial_index, turn, request_hash)`, with the request hash used to detect divergence.
2. **moto for S3** (AWS I6). It reproduces versioning, Object Lock and `IfNoneMatch`/`IfMatch` preconditions offline; AWS ran this. Stubber stays for Bedrock, Logs and Budgets. I also adopt AWS's **`AWS_*` env scrub**, since the container injects `AWS_ACCESS_KEY_ID=proxy-injected`.
3. **TypedNumber fields.** I adopt STAT's explicit `rung`, `n_gold`, `n_verified`, `abstention_rate` and `reasons` instead of my free `detail`; `detail` stays for extras such as `synthetic` and `replayed`. Tier *values* use the design's hyphenated strings (`"GOLD-ANCHORED"`).
4. **Image delivery mode** (AWS I3). The registry's `image_delivery: tool_result | user_turn` is applied inside the provider adapter, *after* the request is normalized and the key computed. The trace and cassette stay mode-independent.
5. **Timing.** The Strands adapter and the S3 store move out of the guaranteed-by-morning block to the start of Wednesday. Real Vantor imagery reads (RS rangeio) come first Wednesday, because K4 needs them. No CDK tonight (ADV).
6. ADV's checkpoint rule; STAT's pure leaf packages `stats/` and `sampling/`; RS's `geo/` and `synth/`.

## 3. Revised position (**B** = blocking for me)

1. **B: Strands goes through our `ModelProvider`** via `TreehouseStrandsModel(Model)`, with `SequentialToolExecutor`. Bedrock is reached by exactly one adapter, `BedrockConverseProvider`.
2. **B: The plain loop is Must-0 and is the demo and replay engine.** The harness comparison axis stays Should.
3. **B: There is an explicit non-estimate tier** (`MEASURED`; the name is negotiable). Every Panel 1, 2 and 5 number carries it.
4. **B: `treehouse demo` re-runs cassettes through loop, gateway and in-process MCP**, seals to a fresh store, runs check, score, trust and report, and passes `verify`. It needs no network, no AWS and no rasterio, and its trace heads equal the golden heads (injected `Clock`).
5. **B: Claims exist only through gateway `record_claim`**, citing deterministic `result_id`s. Harnesses never return claims.
6. **B: Scorers, trust and report are pure.** An AST import-boundary test enforces it.
7. **The canonical package map:** `schemas, canon, clock, geo, stats, sampling, providers, harness, gateway, tools, synth, trace, store, checks, verifier, trust, score, report, service, cli, mcp_server`. `mcp` is a core dependency; `rasterio`, `boto3` and `strands` are extras, with lazy imports and an import test.
8. **Merged plan.**

   Overnight, about 7.5 h, checkpoint at 04:00 after P5:
   - P0 scaffold, guard, env scrub, canon, clock
   - P1 schemas and cards
   - P2 trace, local store, seal, verify
   - P3 fake and cassette providers, plain loop
   - P4 gateway and MCP tools on the numpy synth world plus the real Vantor STAC metadata
   - **P5 `demo` skeleton with clean-clone CI**
   - P6 Bedrock with Stubber, `--mode record`, probe script
   - P7 rules, keyed grader, Panels 1/2/3/5
   - P8 sampling, scripted verifier, PPI, baselines, abstain, passport (stretch)

   Wednesday, the agent in parallel with Kiro:
   - P9 rasterio rangeio `imagery_window`
   - P10 Strands adapter
   - P11 report v2 with summary lint
   - P12 S3 store (moto) and CDK synth
   - P13 Rogan-Gladen and full controls
   - P14 read-only MCP server
   - P15 compare, and the cwlogs/OTLP exporter

   Cut from the bottom.
