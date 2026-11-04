# Review 2 — spec-sheet judge rulings (docs/spec-sheet, 2026-11-04)

> **For agents — what this file is:** The judge's rulings on the doubter's 41 doubts against the first spec-sheet update (commit 180c8e9), and what was changed. The live list of decisions for Suhas is in [SCOPE.md](../SCOPE.md#decisions-suhas-must-confirm); where this file and SCOPE differ, SCOPE wins.

Input: doubt-spec.md (41 doubts: 1 blocking, 16 major, 24 minor) against the spec sheet at 180c8e9.
Rule applied: only D1–D42 and DD1 are Suhas's own decisions. Where council/agent text changed or deferred one, it is marked **DEVIATION, Suhas to confirm**. Tiers follow SD A12 and ID §7; where the first spec sheet invented a tier, it is reverted and the tension flagged.
Fixture claims (#4, #18, #19) were re-measured independently on `wip/fixtures/nepal-flooding-aug-2026.stac.json` (point-in-polygon grid, 28,560 points): 23 AOI scenes (2 pre / 21 post); 16 trap scenes at 71–94 % cloud, 15 of them at ≥ 60 % AOI; F4F10 99 %; C86CED00 83 %; 364E8400 72 %; pre/pre both-cover 63 %; `pan_gsd` 0.31–0.77 (all) and 0.31–0.69 (AOI). All confirmed.

**Counts: 37 VALID, 4 PARTLY, 0 INVALID.**

| # | Sev | Ruling | Reason / what was applied |
|---|---|---|---|
| 1 | blocking | VALID | DD1 puts unreported places in the MVP; ID deferred them to W10 silently. New **D74** (DEVIATION, Suhas to confirm); S21, F16, FUTURE-WORK row, README cut-line note; new **SC27**, J13 step 8 and a DoD box test the frame when W10 lands; ID post-adoption note declares the deviation. |
| 2 | major | VALID | D43 now quotes DD1 verbatim; the council additions (calibrated, never the grade, recorded verdicts) are labelled as council's (RJ C10). Status split. |
| 3 | major | VALID | Following DD1 literally ("Hindcasting = first stretch", which SD A12's Stretch list also puts first): the hindcast is #1 in FUTURE-WORK and README; D71 records the judge's earlier ordering as the alternative for Suhas. |
| 4 | major | VALID | 16 trap scenes, 08-27 to 09-09; EF5910/2B2A10 row added; "13" fixed in SCOPE (3 places) and ID §5.2 (post-adoption note). P1 card still says "Thirteen" (code-side fix). |
| 5 | major | VALID | An AOI search returns 23, not 33. F14 pass check and J15 step 1 fixed. |
| 6 | major | VALID | SD A4/A10 make the versioned S3 store Must-0 (the AWS floor). F25 re-tiered; D66 note (b) says it is built W5/K8 and the local store shows tonight. |
| 7 | major | PARTLY | F6 and the DoD did depend on Should items (W2/W9) and D8 was demoted silently: both fixed (F6 split into Must-0/Should; DEVIATION from D8 in F6, D67 and FUTURE-WORK; J3 steps 2–3 marked Should; DoD box split). The proposed "second local tracer (OTLP-JSON or null tracer)" was not applied: ID has no such tracer tonight, so it would be invented. |
| 8 | major | VALID | API is Should (SD A9) / Could (SD A12). F12, SC11, J9 step 2 and DoD split into spec+CLI (Must-0) and API (Should, W12). Cutting it would deviate from D32/D34: flagged. |
| 9 | major | VALID | Unranked "Must" removed from the 01 key. F3 → Must-1 (SD Must-1 item 3; P9 is first in ID's cut order); F6, F10, F11, F12 re-tiered to designs; cut-order line added. F9 handled per #10. |
| 10 | major | VALID | Per instruction, F9 reverted to the designs' tier (Should, SD A12 Should 7, W8) and flagged as a **DEVIATION from D3**; D68 status, DoD and J5 marked. |
| 11 | major | VALID | "Should in practice" was the writer's call. F20, D64, J10 and DoD now follow SD: **Must-1, cut first on slip** (W7); RJ decision 10 left to Suhas; cutting it deviates from D34. MCP is not added to FUTURE-WORK, because it is not deferred by tier. |
| 12 | major | VALID | F8 marked **DEVIATION from D23**. D67 status now asks Suhas to confirm the hosted-login Stretch tier; SCOPE round-4 note changed from "Resolved" to "Proposed". |
| 13 | major | VALID | Added to SC19, J13 step 6 and a DoD box; F16 states it. Listed as a confirm item (only Virginia can supply it). |
| 14 | major | VALID | W2 also carries AgentVerifier. Fallback added to D60 and F16 ("verifier: recorded, not live"). |
| 15 | major | VALID | Strands goes through our provider (ID §0 row 14), so "Strands already covers them" is wrong. FUTURE-WORK row rewritten; D66 note (c) makes multi-provider Could, Suhas to confirm (it is a HANDOFF hard rule, not a D-decision). |
| 16 | major | VALID | D66 note (a) says SD's H10 checkpoint is superseded by C1–C3; D53 wording fixed; SD post-adoption note. |
| 17 | major | VALID | DoD boxes added for scene discovery/windows, the numbers lint (Must-1), blind labelling (Must-1) and S3/Object Lock/IAM/CDK; J1 step 3 lint check and J13 step 7 export/import added. |
| 18 | minor | VALID | F4F10 99 %, C86CED00 83 %, 364E8400 72 % (stops at 28.26 N), D56 and ID §5.2 placebo reason give both RS 51 % and the 63 % footprint figure. (The P1 card's placebo string still says 51 %.) |
| 19 | minor | VALID | `pan_gsd` made consistent (D38, data line, "why it tests", glossary) and fixed in SD A3 and Sources (post-adoption note). The unverified "0.34 m measured pixels" clause was not added. |
| 20 | minor | VALID | 04 header now says J16–J18 packages are inferred. |
| 21 | minor | VALID | FUTURE-WORK row: only OSM-key canaries are deferred; synthetic canaries are Must-0 (F15). |
| 22 | minor | PARTLY | Rows added for the UI (F8), the paired comparison (F9), the second harness, and the SD Should 1/9 items; Lincoln–Petersen added to the Could row. The MCP-server row was not added: it is Must-1 per the designs (#11), not a deferred Should. |
| 23 | minor | VALID | README item 6: LORO is a conditional Should, not a stretch. |
| 24 | minor | VALID | 03 and FUTURE-WORK say Athena is a Could; 03 gains the round-6 cuts (KB/Guardrails/SageMaker/DynamoDB, public S3 hosting, an LLM judge as the grade). |
| 25 | minor | VALID | Hosted login: "Stretch per SD A10 and D67 (SD A9 says cut)". |
| 26 | minor | VALID | OPEN-QUESTIONS header, the round-5 pending line, and a D25 note. |
| 27 | minor | VALID | OQ7: the per-run guard extension is credited to ID §2–§3 (F11), and the ledger to D65. |
| 28 | minor | VALID | K2b runs after W1 and K3 (about $15), before K4. |
| 29 | minor | VALID | C1/C2/C3 labels corrected in D66. |
| 30 | minor | PARTLY | Added as **D75** (D74 was taken by #1), including the TODO.md K0 step. P6 is confirmed not on origin/main, so "done before P6" stands. |
| 31 | minor | VALID | RODA and the shortlist are "Optional (F1)" in EXTERNAL-DEPENDENCIES and F1; D66 note (d) records the departure from Clay's Day-1 guidance (Clay's, not Suhas's). |
| 32 | minor | VALID | D69 notes it departs from RJ C11 (the judge, not Suhas); status set to Suhas to confirm. |
| 33 | minor | VALID | D62 status: Suhas to confirm the D38 recommendation. F2/D62 also say "marked absent" (#37). |
| 34 | minor | VALID | Glossary "Trust estimate" no longer settles RJ decision 1. |
| 35 | minor | PARTLY | K0–K9 in the glossary, D67, 06, EXTERNAL-DEPENDENCIES, README and 01; 06 repo row shows the rename. D27 (Suhas's decision text) was left unchanged. |
| 36 | minor | VALID | Prompt now says "$20 per run" to match the card; the card's `budget` is stated as normative. |
| 37 | minor | VALID | F2: reasoning is "marked `absent` when not" returned (RJ C12). |
| 38 | minor | VALID | DoD validate box names all four cards. |
| 39 | minor | VALID | EXTERNAL-DEPENDENCIES notes that the 2026-11-04 USPVDB link was not link-checked. |
| 40 | minor | VALID | D70 credits the no-pixels rule to HANDOFF's hard rules, not a D-decision. |
| 41 | minor | VALID | F4 From gains S16, F5 gains S13; F12 also gains S13 (same rule). |

## Decisions Suhas must confirm (final list; also in SCOPE.md)

Deviations from his own decisions:
1. D74: DD1's unreported places are deferred to W10 (Should).
2. D68/F9: D3's comparison is Should (W8).
3. F8: D23's "UI is essential" is Should.
4. D67/F6: D8's CloudWatch second tracer is Should (W9).
5. F12/F20: the API is Should (W12) and MCP is Must-1, cut first; cutting either deviates from D32/D34.
6. DD1's "own accuracy on keyed tasks" depends on Virginia (K6); until then the passport says synthetic only.
7. D71: hindcast first (literal DD1), or after Clay's goals.

Council choices flagged: D44, D45 (RJ decision 1), D47, D49, D50, D51, D52, D53, D54, D55, D56, D60, D61, D62, D64, D65, D66, D67 (hosted login), D69, D73, D75.

## Code-side fixes needed outside docs (not applied here)

1. `tasks/nepal-bhote-koshi-bridges.yaml` (origin/pkg/p1-schemas, also carried on p4): `known_limits` "Thirteen post-event scenes are 71-94 % cloud" → "Sixteen post-event scenes (2026-08-27 to 09-09) are 71-94 % cloud". Also the placebo string "about 51 % overlap" → "about 63 % of the AOI covered by both (fixture footprints)".
2. P4/P5 code: the golden Nepal `stac_search` test must expect the 23 AOI scenes (2 pre, 21 post), not 33. The `nepal-good` demo cassette (`make_demo_fixtures.py`, `synth/nepal`) must treat all 16 ids as the cloud trap.
