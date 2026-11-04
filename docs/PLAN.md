# Current implementation and continuation plan

Updated November 4, 2026. This plan incorporates the clarified agent-investigation product and takes
precedence over old overnight package schedules. It does not discard historical decisions or tests.

**Current scope:** Suhas confirmed the minimal agent-evaluation sandbox after the report
reading and requested Kiro prompts. Read [LGND-REPORT-CONTEXT.md](LGND-REPORT-CONTEXT.md) and
[KIRO-NEXT-PROMPTS.md](KIRO-NEXT-PROMPTS.md). This Codex update publishes documentation and the
handoff; Kiro continues real AWS/model/source integration. Broader report experiments remain unscoped.

| Stage | Scope | Completion evidence / next gate |
|---|---|---|
| 1. Independent acceptance first | Separate-context test author freezes behavior, rubric and assertions before implementation | tests/investigation/PROVENANCE.md records hashes, meaningful failures, later independently authored additions and harness-only corrections. |
| 2. Local investigation sandbox | ModelProvider plugins; opt-in causal decisions; Clay/source/classifier seams; budgets; sealed partial/final runs; SQLite/GeoJSON | Independent runtime, isolation, accounting, matching, export and reviewer tests; original nine replay heads preserved. |
| 3. Observatory UI | Book, Living Sky, Atlas/Investigation, actual prediction markers/table, decision/evidence links, Story/Developer modes | TypeScript build, read-only API contracts, independently authored browser flow, desktop/mobile/keyboard evidence. |
| 4. Reviewed repository handoff | Finish checks, independent review, push and tested merge to randomblankspaces/Treehouse main; update docs | Main must contain the reviewed code. No upstream writes or force pushes. User receives exact SHA and Kiro prompt. |
| 5. Confirm new report context | Reviewed PR #8 merged; report extracted and documented; Suhas confirmed the minimal agent-evaluation sandbox, with Strands as a workflow component | Complete for the minimal framing. Full report reproduction, T2–T4 and transfer studies are not implied. |
| 6. Kiro AWS integration | Clone reviewed main; connect actual worker and distinct reviewer, imagery source, embedding data and classifier under budget guards | One real bounded end-to-end investigation with resource/model IDs, actual evidence, prices/usage, source licenses and sealed artifacts. |
| 7. Live acceptance | Run independent software tests plus held-out geospatial evaluation; verify actual UI output | No substitution of canned predictions, catalog lookups, READY states or synthetic data for imagery/model performance. |
| 8. Refinement | Improve UI, task setup, strategy comparison, coverage and reviewer integration from observed failures | Prioritize measured weaknesses. Keep previous runs immutable and evaluation versions separate. |

## Initial bounded Kiro evidence

Use a public labeled dataset already listed in EXTERNAL-DEPENDENCIES. The initial USPVDB subset is
CC0 with disjoint examples/holdouts; it is incomplete and is not the existing Virginia task's complete
polygon key. Choose a narrowly bounded public imagery area and object definition, pin source dates
and model/index versions, then independently evaluate actual predictions. Warehouse extraction is
not mandatory for this first experiment.

That dataset preference predates the newly supplied report. It is not a selection of USPVDB to
reproduce the warehouse/tank benchmarks. Pin a suitable task/AOI and eligible data for the first run;
keep target text and zone configurable. A
report-comparable run must predeclare its reference completeness, evaluation unit, matching rule,
metrics, labeling/review effort and transfer protocol (Table 7). Current point-distance matching is
not equivalent to the report's cell/asset any-touch or detector IoU rules. Record departures rather
than relabeling existing scores as benchmark results.

Connect registered agent, classifier and source plugins to the existing run path. The default
imagery source is synthetic/recorded; a real COG reader with honest byte accounting is still needed.
Use the existing Bedrock price/spend path. Missing prices stay unpriced, and unknown bytes must not
be labeled measured. Keep held-out labels, audit rows and source lookup aliases outside agent access.

A live run should prove: the agent makes observation-dependent decisions; actual model/imagery calls
produce evidence; the final database comes from recorded claims; red markers match those coordinates;
reference grading uses only its declared held-out scope; and cost/latency evidence has an honest
measurement method. Record limitations and unmatched predictions for adjudication.

## Checks and safety boundaries

Run locked Python dependencies, full offline tests, Ruff, TypeScript/build, and independent browser
flows before merging code changes. Keep independent tests separate from feature implementation;
multiple valid strategies must pass. After two unsuccessful repairs on an issue, reassess its cause.

AWS deployment/live paid calls remain in Kiro's authorized Workshop environment. Preserve the spend
ledger and real price table; account guard thresholds are not a substitute for AWS billing checks.
The standalone Runtime/KB/Gateway proof path has costs outside the model ledger. Do not deploy a
public multi-user service from the local UI without authentication/authorization work.

No real-world accuracy, human superiority, production readiness, hidden-thought access or calibrated
trust claim follows merely from software tests. The current trust stub and optional model-estimated
process reviewer are labeled separately.
