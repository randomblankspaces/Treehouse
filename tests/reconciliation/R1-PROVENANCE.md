# R1 independent regression freeze

Author: `/root/independent_score_repair_tests`, separate context from the feature writer.
Workspace baseline commit: `54a3d1c4824633ad445e6f6a412e6f104fb11280`.
This freeze targets the intentional post-MVP dirty source state recorded in R1-FROZEN-SHA256.json,
not the clean baseline commit. Source writer remained idle during authoring. Root's concurrent
README/docs changes are outside this test author's scope. No production code, original frozen test,
original manifest, historical fixture, dependency, or user TODO was changed by this author.

## Approved additive public contract

Lead approved before freeze: each evaluation section retains status/value/reason and adds `scores`,
an array of `{metric, value, unit, numerator, denominator, basis, status, reason}`. Unit is `percent`
or `raw`; status is available/unavailable/method_test_only. Missing scores can use an empty array
with an explicit section reason. Scores use metric names rules_pass_rate, precision, recall, ece,
and brier. Optional trial identifiers can disambiguate multiple trials. Percentages are numeric
values on 0..100 with named population/denominator. Rules use passed/(passed+failed), excluding
not applicable criteria. Precision/recall retain their actual protocol units. ECE is percent;
Brier is raw, never transformed into accuracy. Reviewer/AgentCore require a known recorded rubric
or scale for numeric scores; missing results are unavailable. Synthetic method restrictions remain.
Historical legacy HTTP fixtures need not be rewritten to inject additive fields.

`thinking_summary` is `{status: available|unavailable, basis: recorded_decisions, text, reason}`.
It describes recorded actions, rationale, model/harness, revisions, stopping and outcome only from
recorded evidence; missing records are explicit. It is deterministic local reporting, not hidden
reasoning and not a new model call. HTML/Markdown must render it and readable numeric scores;
a raw JSON inspector alone is insufficient.

## Final red commands and results

Commands from workspace root:

```sh
JSII_RUNTIME_PACKAGE_CACHE=disabled .venv/bin/python -m pytest tests/reconciliation/test_r1*.py -o addopts='' -q -ra
node --test ui/tests/reconciliation-r1-scores.mjs
.venv/bin/ruff check tests/reconciliation/test_r1*.py
```

Python: **28 collected; 22 failed, 6 passed in 2.00 s**.
Node: **4 tests; 4 failed, 0 passed** (127.096583 ms in final Node log).
Ruff: **All checks passed**.
Final raw outputs are temporarily `/tmp/r1-python-red.txt` and `/tmp/r1-node-red.txt`; lead should
preserve copies in its private evidence directory before cleanup. Their hashes are in the manifest.

Actual failures:

- HTTP sanitizer exposes AWS session token, punctuated equivalent keys, imageBase64 variants and
  Bearer token text. Investigation sanitizer already passes these five defense-in-depth checks.
- Snapshot/export/bundle/investigation forward arbitrary nested decision input; snapshot also
  forwards arbitrary nested provenance. Real local sealed fixture and HTTP boundary are exercised.
- Grader drops an overlapping heldout asset but leaves its other touched cell in the population:
  excluded cells 1 instead of 2. Calibration retains 2 claims instead of 1.
- Missing split grades all references; overlapping and unknown-ID splits yield numbers. Malformed
  JSON raises an uncontextualized parser error instead of a clear split/population refusal. A wrongly
  typed string heldout collection currently happens to abstain and passes that individual test.
- Changing only a mutable, unbound adjacent split changes a sealed run's protocol panels.
- Snapshot lacks named scores and recorded-rationale summary. The explicit independently supplied
  current-reference HTTP comparison does reach actual catalogue matching (one matched, one unmatched,
  two holdouts; raw precision/recall .5 and Brier .2), then fails because named score projection is
  absent. Thus a historical-score abstention cannot bypass the percentage-production requirement.
- Actual React report HTML and readable Markdown omit numeric metrics and the recorded summary.
  Missing-summary explanation is absent too. Structured export preservation itself is exercised.

## Test evidence and limits

New files only: three test_r1 Python modules, one reconciliation-r1 Node module, this provenance,
and R1 manifest. Existing frozen helpers are reused unchanged as allowed harness code. Tests use
real locally generated seals and public API calls, with process-wide offline guard. Invalid split
tests relocate exact reference bytes into temporary directories and stub only unrelated git metadata
and classifier-comparison reporting; grading/population logic is not mocked. Calibration test feeds
controlled geometry to the actual analysis panel. Nested provenance is poisoned in an in-memory
loaded-run projection, leaving sealed bytes untouched. The historical-binding test exercises the
same pure protocol helper consumed by snapshots.

Node uses installed Vite transformWithOxc plus ReactDOMServer to render the actual report component;
no new dependencies/server or cloud access. During harness development, the installed TypeScript 7
package exposed version metadata rather than transpileModule; the final harness uses existing Vite
and fails on missing display behavior, not a loader error. Temporary-root unrelated analysis paths
were isolated before final run, so no fixture FileNotFoundError/git error remains.

This is offline regression evidence, not browser pixel/layout verification, real geospatial accuracy,
AWS availability, physical hardware measurements, or an operational/live score. No commits, pushes,
deployment or cloud calls. Original frozen assertions and original manifest are preserved.
