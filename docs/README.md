# Treehouse documentation index

## Current product context — November 4, 2026

**Latest reading:** [LGND-REPORT-CONTEXT.md](LGND-REPORT-CONTEXT.md) preserves the supplied ADB/LGND
report, corrected table map, benchmark/data constraints, result caveats and current gaps. It is an
source-grounded reading. Suhas confirmed an agent-evaluation sandbox; the Strands/embedding/
classification/marker sequence is a representative workflow, not a required universal strategy. [KIRO-NEXT-PROMPTS.md](KIRO-NEXT-PROMPTS.md) contains the
requested continuation prompts; broad report experiments are not implicitly approved.

Then read [OUTLINE.md](OUTLINE.md), [PLAN.md](PLAN.md), [PRODUCT-STATUS.md](PRODUCT-STATUS.md),
[INVESTIGATION.md](INVESTIGATION.md), [UI.md](UI.md), and [KIRO-HANDOFF.md](KIRO-HANDOFF.md).
The current product evaluates an agent's strategy, exploration, decisions and resulting geospatial
database. It is task/zone configurable; warehouses in Bangladesh are an example. MCP calls support
the evidence trail but do not by themselves grade reasoning. Reported confidence, independent
accuracy and optional model-estimated process review remain separate.

The reviewed investigation implementation is merged. Next is Kiro clone/AWS integration and live
testing of the confirmed minimal pipeline, then refinement. Independent acceptance tests use different
agent context from implementation. [FUTURE-WORK.md](FUTURE-WORK.md) is the current roadmap.
The earlier event notes and package order below are historical context, not the current build queue.


> **For agents — what this file is:** Entry point and index for the whole folder. Read this first. It holds the scope note, event logistics and judging, the build order, the file list, and the stretch order. Reading order for a new agent: README → SCOPE → design/SYSTEM-DESIGN → design/IMPLEMENTATION-DESIGN → OPEN-QUESTIONS → 01 → 02 → 04 → 05 → 06 → 03 → EXTERNAL-DEPENDENCIES → FUTURE-WORK.

Source: Clay's vision doc and the AWS event guide, narrowed to our team's scope. The PDFs aren't in the repo; ask the team for a copy. The team's own scope and decisions are in [SCOPE.md](SCOPE.md), and terms are defined in its [glossary](SCOPE.md#glossary).

**Our scope:** the **ADB agentic eval only**. The caption-generation task is a later stretch, attempted only after the ADB stretch goals (see the end of this file). Any caption-specific line in the vision doc (five-criterion caption rubric, VLM GPU-cost comparison, fixed/change caption tasks) is **not MVP** for us.

**Loop under test:** task card → harness (Bedrock) → tool gateway and MCP tools → trace capture → seal → check (rules, key, blind verifier) → score → trust passport → summary and report.

**Event deadlines (AWS Breaking Barriers DC):** official build time ends **Wed Nov 4, 5:30 pm**, but the team can build outside those hours (SCOPE D18). Prelim presentations run **Thu Nov 5, 10:00 am–12:00 pm**. The public GitHub repo must be up before judging.

## Event logistics and judging (AWS Breaking Barriers DC)

| | |
|---|---|
| Days 1–2 (Nov 3–4) | **WAS16, 1770 Crystal Drive, Arlington VA 22202**. Enter from 18th St (main) or Crystal Dr. Reception is on the 2nd floor. Garage costs about $24/day, first come first served, using the "1770" elevator bay |
| Day 3 (Nov 5) | **WAS17, 510 14th Street South, Arlington VA**. Reception is on the 2nd floor. Park at the Costco lot on S Fern St (about a 3 min walk) |
| Bring | **Government-issued photo ID**, a laptop and charger, and optionally a water bottle |
| Day 1 | 9:00 check-in · 10:00 kickoff (rules and **point system**) · 11:00 keynote · **1:00–5:30 build** |
| Day 2 | 8:30 doors · **9:30–12:30 and 1:00–5:30 build** (build ends Wed 5:30 pm) |
| Day 3 | 8:00 arrival · 10:00–12:00 **prelim presentations** · 2:10–2:50 DC finals · 3:30 prizes |
| Sandbox | AWS Workshop Studio. **$500 cap**, wiped after the event. Use infrastructure as code where it applies. Publish as open source in a **public GitHub repo before judging** |
| Judging | Four **equally weighted** criteria: **Technological Implementation** (execution and AWS service integration) · **Design** (UX, interface, architecture) · **Potential Impact** · **Quality of Idea** (innovation, creativity, feasibility). The top 3 per location go to finals, judged by new judges on the same criteria. The winning beneficiary gets $50K in AWS credits |
| Support | AWS SMEs onsite, AWS Builder Center online, breaking-barriers-us-2026@amazon.com |

## Historical overnight build order

**Clay's Day-1 guidance (from the source):** harness on Bedrock + RODA MCP + 1–2 shortlist servers → **one trace captured end to end before adding any scoring** → prove observe → summarize → score on one synthetic task before adding swaps, comparisons and statistics.

**How we apply it** (SCOPE D66; [IMPLEMENTATION-DESIGN.md](design/IMPLEMENTATION-DESIGN.md) §7). One branch and PR per package, tests first, merged when CI is green and a doubter→judge review finds nothing blocking.
1. **Overnight, offline, no AWS:** P0b offline guard → P1 schemas and task cards → P2 trace and sealed store → P3 providers and plain loop → P4 gateway and tools → **P5 demo skeleton** (`uv run treehouse demo`; checkpoint C1 at H4.5) → **P6 Bedrock adapter, capability probe and spend ledger** (merged by 08:00 for Kiro) → P7 checks and panels → P8 trust core. The demo skeleton comes before any trust maths.
2. **Wednesday queue:** W0 summary and report layout → W1 real COG reader → W2 Strands and the agent verifier → W3 blind labelling tool → W3b cassette export and key fetch scripts → W4–W15 (Rogan–Gladen, S3 store, CDK, MCP server, compare, tracer mirror, unreported frame, U3/U5, API, `estimators.lock`, model phrasing, README). In parallel, Kiro runs K0 locus → K1 probe → K2a prices → K3 live synthetic run → K2b vision smoke → K4 live Nepal run → K5–K9, plus the 60–90 min human labelling block.
3. **Freeze at T-6h** (non-negotiable). The demo is recorded from replayed traces regardless.

**Deviations from Suhas's own decisions in this cut line:** DD1's unreported places (W10, SCOPE D74), D3's comparison (Should, W8), D8's CloudWatch tracer (Should, W9) and D23's UI (Should). They and every other open confirmation are listed in [SCOPE: Decisions Suhas must confirm](SCOPE.md#decisions-suhas-must-confirm).

## Files

- [Team Scope](SCOPE.md): the team's own problem, constraints, solution requirements (S1–S29) and decisions (D1–D75)
- [System Design](design/SYSTEM-DESIGN.md): adopted system design (council 1), including the cut line (A12) and the unkeyed-methods comparison (A13)
- [Implementation Design](design/IMPLEMENTATION-DESIGN.md): adopted implementation design (council 2): modules, schemas, interfaces, test strategy, package plan, Kiro prompts
- [Council 1 log](design/council-1-log.md) and [Council 2 log](design/council-2-log.md): how each design was argued, voted and fact-checked
- [Council brief](design/council-brief.md) and [Design decisions after review 1](design/design-decisions.md) (DD1)
- Review 1 ([judge](reviews/review1-judge.md), [doubter](reviews/review1-doubter.md), [defender](reviews/review1-defender.md), [verifier](reviews/review1-verifier.md)): the review that set the must-fix list
- [Review 2: spec-sheet judge](reviews/review2-spec-sheet.md): rulings on the 41 spec-sheet doubts and the code-side fixes they need
- [Future Work](FUTURE-WORK.md): post-build features we'd implement with more time (kept current during the build)
- [Build Design Decisions](OPEN-QUESTIONS.md): build-time design questions, all decided (SCOPE D25), several superseded in round 6
- [MVP Features in Scope](01-features-in-scope.md)
- [MVP Success Criteria](02-success-criteria.md)
- [MVP Features Explicitly Out of Scope](03-out-of-scope.md)
- [MVP User Journeys as Tests](04-user-journeys-tests.md)
- [MVP Definition of Done](05-definition-of-done.md)
- [MVP Risks and Dependencies](06-risks-and-dependencies.md)
- [External Dependencies](EXTERNAL-DEPENDENCIES.md)

---

## Historical stretch order (see current FUTURE-WORK.md)

Full list, plus everything the cut line deferred and anything cut during the build: [FUTURE-WORK.md](FUTURE-WORK.md). Order: **the temporal hindcast first**, per DD1 ("Hindcasting = first stretch") and SD A12's Stretch list; then Clay's stretch goals. The simulation is a downstream consumer of the agent-built dataset, outside the eval product and the demo, and stays last (RJ C13, SCOPE D71). *(If DD1 meant first among truth sources only, the hindcast moves after Clay's goals; Suhas to confirm.)*

1. Temporal hindcast (DD1: first stretch).
2. Sensitivity analysis: vary the inputs, prompts, tool selection, and model, then compare traces and scores across the variants to see how stable both the workflow and the eval are.
3. Multi-agent traces (planner, executor, and checker).
4. Dynamic MCP tool discovery across Clay's catalog.
5. A richer trace-summary dashboard.
6. Further trust methods: Dawid–Skene and weighted conformal. (LORO is a conditional Should, not a stretch: it runs as soon as a second real keyed regime exists; see FUTURE-WORK.)
7. **Then** a second task: caption generation, using the five-criterion caption rubric. The caption sections of the vision doc apply only at this point.
8. The flood and bridge-failure simulation (SCOPE D41), starting with the Simulation Card spec, as a consumer of the certified bridge dataset.
