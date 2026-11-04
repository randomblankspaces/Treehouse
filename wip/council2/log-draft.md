# Council 2 log (implementation design)

Topic: how to implement docs/design/SYSTEM-DESIGN.md. It covers module layout, interfaces, schemas, storage, the API/MCP surface, the test strategy (including how each unkeyed-verification method is tested) and an ordered package plan.

Seats:
- **STAT**: statistician
- **RS**: remote-sensing scientist
- **OBS**: agent-eval / observability engineer
- **AWS**: AWS architect
- **ADV**: Clay/ADB/judging advocate and scope hawk

The orchestrating agent ran the process and took no seat. Each seat's full round texts were kept in the session scratchpad. This log records positions, changes, votes and objections.

## Round (a): proposals

| Seat | Key positions |
|---|---|
| STAT | Prototyped PPI in numpy. The plain rescaled bootstrap **under-covers** when the verifier is good: nominal 90 % gave 0.76 coverage with a strong verifier and 0.60 with a perfect one, at n_gold = 20. Fix for n_gold < 50: pool the human-minus-verifier correction across strata, and add two half-weight pseudo-disagreements to the variance only. With both, coverage was at least 0.897 in 6 scenarios. With λ = 1 and 20 labels, PPI does not narrow the interval with a moderate verifier and widens it with a useless one, so the passport always shows the exact human-only interval and the width ratio. Rogan-Gladen with 15 + 15 controls gives about ±0.24 and abstains for weak verifiers. Gave exact signatures for `stats`, `sampling` and `trust`, plus about 17 seeded method tests and mutation tests that check the coverage test catches simplified estimators. 14 packages, about 20 h. Never cut stats, sampling, trust or the mutation tests. |
| RS | Measured tonight: the Vantor COGs are EPSG:4326, 3-band JPEG, 512 px tiles, about 0.34 m pixels. The resolution field is `pan_gsd`. `imagery_window` uses rasterio with a 16 KB block cache, which makes "bytes read" exact: one window took 5 requests and 81,920 bytes instead of 367 requests. Reads are pinned to ETags. No shapely or pyproj at runtime (about 120 lines of geometry); one-to-one matching via `linear_sum_assignment`. Rules R1–R9 read evidence from what the gateway recorded. Nepal AOI is the Syabrubesi–Timure corridor, where E5610 and E5810 form a same-pass test-retest pair and 13 cloudy scenes form the cloud trap. Pre-event overlap is only about 51 %, so controls use post/post only. Virginia card is `pending_fetch` (USPVDB blocked here). India stub uses Sentinel-2 and a different family. Synthetic keyed world `synth-crossings`: scripted policies run a real detector on generated pixels, giving 200-seed method studies. 16 packages. |
| OBS | Verified by running code: a scripted Strands `Model` subclass drives a real Strands Agent offline; an MCP 2.3 in-process `Client` works inside Strands tools; botocore Stubber validates a Converse request that carries an image block. **MCP 2.3 tools typed `-> dict` return `structured_content=None`**, so every tool returns a Pydantic model. `ModelProvider.complete(ModelRequest) -> ModelResponse` with image bytes replaced by their sha256 in cassette keys, so cassettes replay with no pixels. Harness never returns claims; only `record_claim` makes them. Deterministic `result_id` in each tool result. Import-boundary AST test keeps score and trust pure. Proposed: **plain loop in Must-0** as the offline reference harness, and a **MEASURED tier** for exact trace-derived numbers. P0–P11, about 20 h; the minimum morning handoff is P0–P7. |
| AWS | `backends:` seam per component; the manifest's `backends_resolved` is filled from read-backs and live denial checks, never from config. "IAM-enforced" requires the worker role plus a canary denial. S3 store tested with **moto** (verified offline: versioning, Object Lock, `IfNoneMatch`/`IfMatch`, denied version delete). Bedrock adapter tested with Stubber, adaptive retries, concurrency 2. Model ids live in a registry file: Claude worker, Amazon Nova Pro verifier, ids UNVERIFIED until the probe. Prices table null until measured, which **blocks live calls**. Spend ledger with worst-case reservation ($250 planned / $350 alarm / $450 stop). CDK in `infra/` as an optional extra; `cdk synth` with `Template` assertions passes offline in about 6.5 s. Kiro prompts K1–K8, about $56. Flagged that `AWS_ACCESS_KEY_ID=proxy-injected` exists in the container, so tests must clear `AWS_*`. |
| ADV | By Wed 08:00, `uv sync && uv run treehouse demo` re-runs the pipeline from sealed cassettes on a fresh clone with no network. P0–P8 (about 7.2 agent-hours) are the overnight commitment; P9–P13 move to Wednesday. Checkpoint: if P5 (demo skeleton) is not merged by 04:30, stop widening and finish P6–P8. Synthetic `synthetic-sites-v1` has 40 planted sites, 6 planted traces and a corruption series. The Nepal demo uses real STAC metadata, synthetic crossing points, recorded verifier verdicts and synthetic gold (n = 24). Plain-English chips; a report test fails if any number sits outside a chip. J1–J9 plus new J10–J15 for S14–S19. Explicit "not tonight" list: UI, CDK, Object Lock, Lambda, CloudWatch, LORO, Dawid-Skene, act layer and others. |

## Round (b): debate (attacks, concessions, blocking items)

Every seat attacked the plan sizes. Four of the five round-(a) plans needed about 19–21 h for a 6–8 h night and put the demo near the bottom, so "cut from the bottom" would have cut the demo first.

| Seat | Main attacks (with evidence) | Position changes / concessions | Blocking items after round (b) |
|---|---|---|---|
| STAT | Ran `b_check.py`: with shuffled verifier verdicts the correct PPI interval is 0.34 wide vs B2's 0.51 and excludes B2's point. So ADV's and OBS's "shuffled → baseline-equivalent" test would push the agent to break a correct estimator; the reference must be the gold-only interval. A naive bootstrap passes ADV/OBS coverage tests at an 85/80 verifier (0.853) and fails only with strong verifiers (0.58). RS's upper coverage bound of 0.95 would reject the corrected interval. A 200-seed full-pipeline study will not fit in 10 s. | Skeleton before statistics; ADV's ~7.5 h budget and 04:30 checkpoint; MEASURED with a validator; ADV's world tonight; plain loop as replay engine; Strands on Wednesday; moto/Stubber; ADV tree with `stats/` as a leaf | S1 pseudo-disagreement variance fix + pooled correction (n_gold < 50), λ = 1, gold-only interval shown beside it; S2 method tests with strong/perfect verifiers, a mutation test, shuffled check vs gold-only, one-sided coverage ≥ 0.86, < 6 s; S3 gold drawn from all sampled units, committed before the first verdict; S4 trust core built overnight after the checkpoint (1.8 h) |
| RS | `pan_gsd`, not `gsd`. Evidence sufficiency must use effective resolution: a 1 km window at 512 px is about 2 m. Without a block cache, "bytes read" is meaningless (367 requests / 25 s vs 5 requests / 0.64 s). ADV's outcomes are dialled constants. ADV's synthetic points at real Bhote Koshi coordinates could pass for a real inventory. The cloud trap cannot be keyed on Nepal (`mask: false`); only a synthetic `visible_in` key can grade `cannot_assess`. | Dropped the 16-package plan. rasterio becomes a `[geo]` extra (its 1.5.2 macOS wheels need macOS 15). Demo replays recorded tool results with no rasterio. Adopted OBS module names, PlainLoop in Must-0, one merged synthetic world | Effective resolution in R5 and Panel 1; measured `bytes_read`; rule evidence only from gateway-recorded results, with "contains"; a real Vantor STAC fixture with ETags tonight; keyed `visible_in` in the synthetic key |
| OBS | `scratchpad/obs/t5.py`: Strands' default executor ran two tool calls as [b, a]; `SequentialToolExecutor` fixes [a, b]. AWS's Strands-on-`BedrockModel` breaks record/replay and gives two Bedrock code paths. Adaptive botocore retries hide throttles from the trace. Other tier lists leave cost/process numbers with no valid tier. Golden traces need an injected clock and seeded ids. | Cassette key adopted from AWS (role, trial, turn, request hash) because OBS's collided across trials. Adopted moto, the `AWS_*` scrub, STAT's TypedNumber fields, and AWS's per-model image-delivery mode. Strands and S3 on Wednesday; no CDK tonight | Strands through our ModelProvider with sequential tools; plain loop Must-0 and the demo engine; an explicit non-estimate tier (MEASURED); demo re-runs cassettes through loop + gateway + MCP, then seals and passes `verify` offline with no rasterio; claims only via `record_claim`; import-boundary purity test |
| AWS | Two fake-model Strands runs gave identical request hashes, so Strands is deterministic apart from tool order. ADV's "no Kiro code tonight" leaves Kiro idle at 08:00. Stubber-only S3 tests cannot show put-once or denied deletes hold. Other offline guards leave the `proxy-injected` credentials in place. No other proposal has a cross-run dollar guard. Replay must take tool results from the cassette, because Vantor JPEG pixel hashes vary across builds. | Adopted ADV's order (P5 skeleton, 04:30 checkpoint, P0–P8 overnight). CDK, CloudWatch tracer code and Object Lock to Wednesday. Adopted MEASURED, the plain loop, the synthetic world, and the OBS layout plus `stats/`, `sampling/`, `geo/`, `synth/` | Cumulative spend ledger with worst-case reservation, $250 / $350 / $450; a 1 h AWS package tonight (Bedrock adapter, probe, registry, null price table) merged before 08:00; `backends_resolved` from read-backs only; offline guard with a canary test |
| ADV | STAT, OBS, RS and AWS plans leave nothing to open at 08:00 (fails DoD 1, DoD 12 and J8). OBS's minimum handoff has no scorer or report. Virginia cannot be graded tonight. AWS's 2.5 h CDK/moto/OTLP package, RS's real COG reads (25 s per window, CC-BY-NC pixels) and STAT's cross-fitted λ, DL τ and lock test cannot pay off tonight. | Adopted RS's world (as numpy arrays), MEASURED with a fence, STAT's variance fix shown beside the classical interval, RS's Nepal facts, the env scrub, the spend hard stop. Withdrew the Strands risk after OBS's evidence | D1 demo skeleton before trust maths, plus a clean-clone offline CI job; D2 demo re-runs the pipeline from cassettes, never pre-rendered JSON; D3 synthetic labelling with "SYNTHETIC GOLD, not human labels"; D4 adapters merged by 08:00; D5 the not-tonight list, with Virginia as `pending_fetch`; D6 no bare floats, plus a chip-invariant HTML test |

## Round (c): neutral merge, revision 1

A moderator who held no seat merged the ten round texts into `c-design-r1.md`, about 6.4k words of prose plus code blocks. It resolved 30 issues. Four were conflicts between blocking items:
- **Row 2:** Strands moved to Wednesday, against ADV's D4.
- **Row 3:** the trust core sized at 1.8 h, against ADV's estimate.
- **Row 6:** the real COG reader moved to W1, against RS's B2.
- **Row 16:** probe tests use Stubber only tonight, against AWS's moto request.

It also proposed three new rulings that no seat had argued, so each went to the vote:
- **Row 26:** a human `cannot_assess` gold label counts as y = 0 for precision.
- **Row 27:** the test-retest kappa is MEASURED.
- **Row 21:** images travel through an in-process PixelCache side channel.

## Vote round 1 (on r1)

| Seat | Vote | Blocking objections |
|---|---|---|
| ADV | **ACCEPT** | None. Non-blocking: move C1 to H4.5; say at 08:00 what actually merged; mark synthetic bytes in hover text; don't claim Strands if W2 slips; keep W0 (plain summary) first on Wednesday |
| AWS | REJECT | B1: K1 probe makes live calls while every price is null, so the ledger either refuses them or the probe bypasses the $450 guard. Fix: a per-call `unpriced_cap_usd` reservation, `max_tokens` ≤ 32, a $3 probe cap, an estimated ceiling at commit, and Stubber tests |
| OBS | REJECT | B1: replay would attach a text placeholder where the live request had an image, so the request key changes and real recorded runs can never replay. Fix: the same `Image(sha256, bytes_=None)` in both; live providers refuse a byte-less image; a test that the live key equals the replay key. B2: hashing the encoded PNG makes keys and golden heads depend on the zlib build. Fix: hash the decoded uint8 array plus its shape |
| STAT | REJECT | B1: with a human `cannot_assess` counted as y = 0, the headline must be `verified_precision` (a lower bound), with `n_gold_cannot_assess` and a y = 1 upper-bound alternative. B2: the M5 mutation threshold sits on a knife edge (reproduced: \|bias\| 0.041 vs 0.04, and 0.039 with larger strata). Fix: P(abstain) of 0.6 if y = 0 and 0.1 if y = 1, which gives mutation bias 0.057–0.063 with coverage held at 0.893 |
| RS | REJECT | B1: the synthetic bytes model picks no overview level, so skimmer would show about 35× good's bytes. Measured on E5610, the real gap is about 1.2× (98,304 B vs 114,688 B), and the number is chipped MEASURED. Fix: overview selection, a block count at that level, a header cost and a declared block size, tagged `bytes_model`; I3 order checks; a W1 calibration test |

Result: 1/5 accept, so not unanimous. All blocking objections were sent to the moderator with the seats' replacement text, for r2.

## Revision 2 (moderator)

r2 applies every round-1 blocking fix verbatim, plus the cheap non-blocking ones, in 16 rows of a "Round-1 objections and resolutions" table:
- **AWS-B1:** probe reservations ($0.25/call cap, `max_tokens` ≤ 32, $3 probe cap, estimated ceiling prices).
- **OBS-B1:** a byte-less `Image` in replay, an identical key, live refusal (`MissingPixels`).
- **OBS-B2:** array-plus-shape hashing.
- **STAT-B1:** `verified_precision`, plus `n_gold_cannot_assess` and an upper-bound alternative.
- **STAT-B2:** the new M5 scenario.
- **RS-B1:** an overview-aware block model with a "modelled bytes" chip.
- **Non-blocking:** C1 moves to H4.5; the 08:00 report must say what merged; no Strands claims if W2 slips; mcp 2.3's `CallToolResult` image + structured content is verified (OBS t6.py); W3b for cassette export and the fetch scripts; the spend ledger committed in-repo during Kiro sessions; a `narrowing_note`; hypergeom only for full census; per-row SYNTHETIC on Nepal WindowResults.

Not applied (non-blocking, not requested): STAT's M2 margin, an AWS Budgets alert, OBS's semconv names, RS's check-etags and three-GSD smoke, RS's POST-C footprint in the key. They are carried to the Wednesday queue and the overnight report.

## Vote round 2 (on r2)

| Seat | Vote | Notes |
|---|---|---|
| ADV | ACCEPT | Hours: P4 and P8 grew without re-estimate; this is a schedule risk covered by the cut order. Suggests `bytes_model: flat-v0` if C1 fires |
| STAT | ACCEPT | Both round-1 items resolved, reproduction confirms M5 (bias 0.057–0.063, coverage 0.893). Non-blocking: the disagreement check should compare like with like (KEYED precision vs `verified_precision`); M14 should get a case with `n_gold_cannot_assess > 0` |
| OBS | ACCEPT | Both items resolved in the body text, not only in the table. Non-blocking: risk 10 should name the GDAL/libjpeg dependency; `narrowing_note` should be a fact slot |
| AWS | ACCEPT | Item resolved. Non-blocking: list `config/prices/probe-ceiling.yaml`; keep `.spend/` tracked and exclude it from the pixel scan |
| RS | **REJECT** | Erratum to its own round-1 text: the "≤ 2×" and "≥ 8×" order checks fail for a correct implementation of the block model now specified. Worst cases over 2,000 window centres are 4.0 and 4.0; centre counts are 1, 4 and 25. Replacement: ≤ 4×, ≥ 4×, exact centre counts 1/4/25 |

Result: 4/5, not unanimous.

## Revision 3 (orchestrator applied RS's replacement text verbatim; no other change)

## Vote round 3 (on r3)

| Seat | Vote | Notes |
|---|---|---|
| ADV | ACCEPT | Diffed r2 to r3: only the I3 erratum changed; scope, hours, demo and claims unchanged |
| STAT | ACCEPT | Checked the new bounds at the scene centre (4 ≤ 4; 25 ≥ 16); only a MEASURED Panel 5 number is constrained |
| OBS | ACCEPT | Test-only change; cassette keys, golden heads and image hashing unaffected |
| AWS | ACCEPT | No AWS-side effect |
| RS | ACCEPT | Its replacement text is applied verbatim; the bounds hold on the design's 2400 px world |

**Result: unanimous (5/5) at round 3.** Rounds 1 and 2 had blocking objections, so the forced devil's-advocate rule did not apply. Unanimity is genuine: every seat's blocking items were resolved in the text, and each seat checked the resolution against the body text, not just the summary table.

## Fact-check (round d)

See the section "Fact-check of r3" at the end of IMPLEMENTATION-DESIGN.md.
