# R2 independent scope regression freeze

Author: `/root/independent_score_repair_tests`, separate context from feature writer.
Baseline commit is `54a3d1c4824633ad445e6f6a412e6f104fb11280`; target is the intentional dirty,
post-R1 repaired source state recorded in R2-FROZEN-SHA256.json, before the R2 source repair.

Only three new files owned: test_r2_reference_scope.py, this provenance, R2-FROZEN-SHA256.json.
No source, R1/original frozen assertions, manifests, dependencies or historical fixtures changed.

## Requirement and scope

The actual current server-reference comparison must not present unscoped positive predictions as
known false positives/calibration outcomes while labeling its denominator scoped predictions.
Lead approved the smallest repair at snapshot comparison only: withhold output and calibration,
with null numeric values and an explicit scope/coverage/AOI explanation whenever a positive claim
lies outside task AOI or supplied reference coverage. Preserve recorded database predictions and
legacy core comparator semantics. This suite freezes that fail-closed option; a population-filtering
alternative would require explicit review before replacing this contract.

Two actual-HTTP cases use fresh seals and complete synthetic reference documents:

- One correct positive inside coverage plus a positive outside reference coverage but inside AOI.
- One correct positive plus a positive outside AOI but inside the supplied reference coverage, so
  AOI and reference boundaries are independently tested.

Snapshot and export must preserve two recorded predictions, set output/calibration unavailable,
withhold their raw result/value and numeric scores, and explain the unknown scope. Missing scores
cannot silently become numeric zero. Existing frozen R1 all-inside current-reference case is run
unchanged as the positive control, retaining 50% precision/recall and raw Brier .2.

## Final red evidence

```sh
JSII_RUNTIME_PACKAGE_CACHE=disabled .venv/bin/python -m pytest tests/reconciliation/test_r2_reference_scope.py tests/reconciliation/test_r1_scores.py::test_r1_explicit_current_reference_comparison_produces_numeric_percentages -o addopts='' -q -ra
.venv/bin/ruff check tests/reconciliation/test_r2_reference_scope.py
```

Result: **2 failed, 1 passed in 2.97 s**. Both new cases fail because HTTP output evaluation is
method_test_only instead of unavailable; the all-inside frozen R1 control passes. Ruff passes.
There are no fixture, import or loader failures. Temporary full log: `/tmp/r2-python-red.txt`;
lead should preserve it in its private evidence directory. Its hash is recorded in the manifest.

Local in-process HTTP and real seals are used; hashes assert successful GET inspection remains
read-only. The existing process-wide offline guard applies. A red assertion stops before later
calibration/export checks, so those remain acceptance requirements rather than already-observed
baseline failures. No full suite, AWS, commits, pushes, deployment or browser visual checks run.
No evidence about real geospatial accuracy or physical hardware is established.
