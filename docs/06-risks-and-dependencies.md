# MVP Risks and Dependencies

> **LGND/ADB context — minimal agent-evaluation scope confirmed:** read [the report brief](LGND-REPORT-CONTEXT.md).
> New source risks include incomplete references, class-definition mismatch, cell/asset metric confusion, transfer degradation and imagery-use restrictions.
> Suhas confirmed an agent-evaluation sandbox; Strands is part of the workflow being assessed.
> See the report brief and Kiro prompts for that scope; broader benchmark studies remain future work.

> **For agents — what this file is:** Known risks with their mitigations, the things we depend on (and their status), and the questions to ask Clay. Check it at the start of each work session. Risks come from the review-1 judge (**RJ**), SYSTEM-DESIGN A12 "Risks said out loud" (**SD**) and IMPLEMENTATION-DESIGN §9 (**ID**). Updated 2026-11-04.

> Scope: **ADB agentic eval only**. Captions are a stretch after the ADB stretch goals. Index: [README.md](README.md)

### Risks

**Trust and evidence**

| Risk | Likelihood | Impact | Mitigation | Source |
|---|---|---|---|---|
| Too few keyed regimes: with one real keyed regime (Virginia), leave-one-regime-out can't run, so the trust method can't be validated across regimes | Certain | High | The MVP claims only PPI plus tiers plus the abstain rule, validated by planted-error, placebo and coverage tests. The passport says "not computable: 1 keyed regime". Synthetic tasks never count as a regime (SCOPE D48, D53) | SD A12 risk 1 |
| About 20–25 human labels give wide intervals | Certain | Medium | Show the width, n_gold and the gold-only interval beside the headline; print "the verifier did not narrow the interval" when it didn't | SD risk 2 |
| The gold labeller is the builder | Certain | Medium | Blind protocol (worker and verifier outputs hidden, shuffled, sealed before reveal), test-retest on 5 items reported as anecdotal; labels are called "builder-checked human reference", not truth | SD risk 3 |
| No keyed calibration exists for bridge damage; nothing transfers from solar | Certain | High | The damage step is GOLD-ANCHORED from in-area gold, or MODEL-ESTIMATED and wide. The card says "nothing is borrowed from solar" | SD risk 4 |
| Worker and verifier read the same pixels, so their errors are partly shared | Certain | Medium | Different model families, own windows and crops. Under random-gold PPI this affects interval width, not validity | SD risk 7 |
| The July 2025 flood broke the "no change" baseline in the upper corridor | Certain | Medium | Grade post-event state; test-retest controls only; placebo marked unavailable; attribute change to Aug 2026 only where a post-2025-07 pre scene covers the bridge | SD risk 11 |
| No available model can see a footbridge at 0.5 m | Medium | High | Vision smoke test (K2b, after W1 and the K3 live synthetic run, about $15 spent by then) before the Nepal run (K4); if so, `cannot_assess` dominates and that is reported as the finding | SD risk 10; ID risk 9 |
| Model memory of OSM or USPVDB can't be excluded by blocking tools | Certain | Medium | Printed as an honest limit on every report; prefer the post-cutoff Aug 2026 event | SD risk 9 |
| OSM is incomplete for rural footbridges, so the inventory key undercounts | Likely | Medium | Partly keyed step: unmatched claims go "to adjudicate", not "wrong"; completeness caveat on precision | RJ C5; SD A2 |
| Few tasks and trials make comparisons inconclusive (F9, F10) | Likely | Medium | Every comparison labelled exploratory; many small spaced keyed tiles instead of a few big tasks; report the minimum detectable difference and "inconclusive at N=k"; at least 5 per arm | SD A8 |
| The agent or a future edit simplifies the estimator | Medium | High | Mutation tests M2 and M5, the reference oracle, and `estimators.lock` before K4 | ID risk 4 |
| Synthetic numbers get quoted as real | Medium | High | Required `synthetic` field, row chips, banner, and "SYNTHETIC GOLD, not human labels" | ID risk 7 |

**Schedule and build**

| Risk | Likelihood | Impact | Mitigation | Source |
|---|---|---|---|---|
| Hour estimates are optimistic (solo build, deadline Thu 10:00) | Likely | High | Checkpoints C1 (P5 by H4.5) and C2 (P6 by 08:00), the cut order, and the T-6h freeze. The demo is recorded from replays regardless | ID risk 1; SD A12 |
| Doubter/judge review passes cost about 1.5 h | Certain | Medium | One pass per PR, run concurrently | ID risk 2 |
| The spec-sheet step eats night hours | Certain | Low | Run after P6 or in parallel | ID risk 3 |
| mcp 2.3 or Strands APIs churn | Medium | Medium | Pinned versions, contract tests, one wrapper module, the image side channel | ID risk 6 |
| numpy drift breaks golden hashes | Low | Medium | `uv.lock` pins numpy; each sample design records its RNG, algorithm and numpy version | ID risk 5 |
| JPEG pixel hashes depend on the environment | Medium | Low | Compared only within one environment; synthetic array hashes are stable everywhere | ID risk 10 |
| The demo depends on an editable install (`fixtures/` at the repo root) | Low | Medium | uv installs editable by default; `paths.py` errors clearly otherwise | ID risk 12 |
| Live agent is flaky during the build or the demo | Medium | High | Planted-trace replay built early; demo recorded from replayed traces (J2) | baseline; SD A12 |
| Scope creep into captions, the simulation or the act layer | Medium | Medium | Cut line (SCOPE D66); simulation and act layer stay downstream (D71) | baseline; RJ C13 |

**AWS and data**

| Risk | Likelihood | Impact | Mitigation | Source |
|---|---|---|---|---|
| Real vision cost and Bedrock quotas are unmeasured; vision tokens can eat the $500 cap | Likely | High | Measure one real run (K3) first, size N from p90 cost; spend ledger at $250/$350/$450; probe capped at $3; backoff and concurrency 2 | SD risk 6; RJ C9 |
| Workshop Studio denies services or forces the Kiro-terminal locus | Medium | Medium | Capability probe first (K1); every seam degrades to a local stand-in, and the manifest says so | SD risk 5 |
| The Workshop role is not the worker role, so the IAM key Deny can't be shown | Medium | Low | Manifest says "local convention, not IAM-enforced" unless the canary denial is observed | ID risk 11 |
| A Kiro session reset silently zeroes the spend ledger | Medium | High | Ledger kept at `$REPO/.spend/spend.jsonl` and pushed after every K step | ID §0 AWS NB1 |
| The Nepal AOI corners come from memory | Certain | Medium | The fixture builder checks footprint intersection; Suhas checks visually at K2b | ID risk 8 |
| Vantor imagery is CC-BY-NC-4.0 and could leak into the repo or recording | Medium | High | Commit ids, windows and pixel hashes only; licence scan; NC notice on every Vantor-derived view | SD risk 8; RJ C14 |
| USPVDB key and NAIP imagery dates don't line up (V4.0 April 2026 vs NAIP about 2010–2023) | Likely | Medium | Filter the key by install year; check the gap before relying on Virginia numbers; fall back to a smaller AOI or the OSM masked-block key | SD A12 demo task 1 |
| No ADB inputs are coming (D13), and an ADB rubric is unconfirmed | Certain | High | Synthetic task cards with keys from public data; the synthetic notice sits inside the prompt; ask Clay to review the cards | baseline; RJ C15 |
| Data licences need attribution: LGND CC BY 4.0, OSM ODbL, Vantor CC-BY-NC-4.0, NAIP and USPVDB public domain (attribution requested) | Certain | Low | Licence per source in provenance and a licence floor on every report; credits in the README | baseline; SD A4 |
| Sandbox wiped after the event | Certain | Medium | Everything that matters goes in the public repo: infrastructure as code, pixel-free cassettes, sample runs and reports | baseline |

### Dependencies

| Dependency | From | Status (2026-11-04) |
|---|---|---|
| AWS sandbox (Workshop Studio) with Bedrock access | AWS team lead | Provisioned, $500 cap. Bedrock access confirmed (D40). **Reached only through the browser via Kiro; no AWS credentials in the build container** |
| Bedrock model ids | AWS | **UNVERIFIED until K1.** Defaults: worker `anthropic.claude-sonnet-5-5` through a `us.`/`eu.`/`global.` inference profile; verifier `amazon.nova-pro-v1:0`. Whether Sonnet 5.5 accepts an image inside a tool result is unverified, so it ships with `image_delivery: user_turn` |
| Bedrock prices | AWS | Price table is null until K2a. Live calls are refused while a price is null |
| Vantor open data (Nepal event) | Vantor via RODA | **Reachable** from the build container over anonymous HTTPS. STAC fixture (33 items, metadata only) built 2026-11-04 |
| LGND / Clay embeddings | Clay / source.coop | **Blocked from the build container** (data.source.coop). The demo uses a synthetic npz; real embeddings need the Mac or Kiro |
| USGS USPVDB (Virginia key) | USGS | Public domain, V4.0 (2026-04-15). **Blocked from the build container**; `fetch_uspvdb.py` runs on Suhas's Mac (K6). Card ships `pending_fetch` |
| NAIP imagery (Virginia) | USDA via RODA | Public domain, **Requester Pays** in us-west-2: needs AWS credentials and `RequestPayer=requester`; egress outside us-west-2 costs money. Kiro only |
| OSM bridge snapshot (Nepal inventory key) | OpenStreetMap | ODbL. Overpass is **blocked from the build container**; fetched via Kiro or the Mac (K6), snapshot date pinned |
| Kiro web IDE | AWS Workshop Studio | Runs K0–K9 from prompts in `TODO.md` |
| Harnesses under test (2, for comparison) | Suhas | Plain Converse loop (Must-0, P3) and Strands via our provider (W2) |
| Free/priority MCP shortlist | Clay | Catalog saved at [reference/geomcp-catalog.csv](reference/geomcp-catalog.csv). Shortlist still unconfirmed; OSM/Overture servers are forbidden where they are the key |
| LGND Geo MCP whitelist | Clay/LGND | Commercial tool. Access still unconfirmed |
| Open-source repo | Team | Public fork [randomblankspaces/Treehouse](https://github.com/randomblankspaces/Treehouse) (renamed from team-43-renaissance-philanthropy-clay; the old URL redirects), Apache-2.0 (D27, D28) |
| Data and tool links | — | See [EXTERNAL-DEPENDENCIES.md](EXTERNAL-DEPENDENCIES.md) |

### Ask Clay

1. **The kickoff confirmation list is missing.** The doc's intro says "a short list of items to confirm with Clay at kickoff is at the end", but the doc ends with Stretch Goals and has no such list. Ask Clay for it.
2. **The third task is undefined.** "The Three Tasks" defines only two: the ADB agentic eval and caption generation. Ask what the third one is.
3. **What a concrete ADB task looks like:** the actual "how to use AI / build datasets" prompt or brief, and what a good output is.
4. Ask Clay to review our task cards (Nepal, Virginia, India stub), and whether an ADB rubric exists (we get no ADB inputs, D13).
5. Which servers in the geoMCP catalog are on the free/priority shortlist.
6. Whether our team is whitelisted for LGND Geo MCP, and what it can find.
