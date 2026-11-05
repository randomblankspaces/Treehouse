# Independent reconciliation acceptance freeze

Author: `/root/independent_mvp_acceptance`, a separate Codex context from implementation.
Scope: new `tests/reconciliation/**` and `ui/tests/reconciliation-contract.test.mjs` only.
No source, existing assertions, committed fixtures, dependency files or user TODOs changed.
Raw baseline logs were moved to the private evidence directory at the lead's explicit request. No commits,
cloud calls, network requests, purchases or deployment. The existing test-wide offline guard is active.

Baseline: `54a3d1c4824633ad445e6f6a412e6f104fb11280`.
Tracked source remained unchanged (`git diff --quiet` passed) when the final red runs completed.
Root separately recorded the pre-existing full suite baseline: 923 passed, 3 skipped, 1 deselected.
That full-suite log is outside this author's ownership at `work/mvp-document-review/baseline-pytest.txt`.

Requirements read before writing assertions: `work/treehouse-pr/MVP-ACCEPTANCE-BRIEF.md`,
`MVP-RECONCILE-BRIEF.md`, `docs/design/SHELL.md`; existing public API contracts, scorer schemas,
fixture metadata, test harnesses and service entry points were inspected. Assertions were not copied
from existing tests and this suite imports no existing test modules.

## Interface approved before feature implementation

Lead explicitly approved `GET /api/runs/{rid}/snapshot` as the read-only bridge, producing the shell
RunSnapshot. The additional fields are:

- `mode`: `live | replay | fake | mock | unknown`.
- `provenance`: `embeddings` (`synthetic_reference_derived | synthetic | real | unknown`),
  `reference` (`synthetic | real | none | unknown`), `vision` (`used | not_used | unknown`), and
  `limitations: string[]`.
- `evaluation`: `reasoning_rules`, `reviewer`, `agentcore`, `output`, `calibration`,
  `predicted_accuracy`; each has `status` (`available | unavailable | method_test_only`), `value`
  (JSON or null), and `reason` (string or null). Missing and method-only results require explanations.
- Map markers retain actual recorded claim status, `claim_id`, `trial_id`, `evidence_refs`,
  `decision_id`. Positive-only `/database` may remain positive-only. Tests permit the snapshot to omit
  negative map markers but never relabel presence as confirmed truth.
- Pending snapshots have empty recorded steps/markers and null unavailable elapsed/cost values.

The new endpoint tests deliberately fail because the route does not yet exist. Those failures are
contract red tests, not evidence of successful end-to-end integration. The Node tests additionally
exercise the old routes with well-formed data, reproducing concrete current adaptation failures.

## Final frozen baseline commands and outcomes

Run from `/Users/suhas/Codex/2026-11-04/alr/work/treehouse-continuation`:

```sh
JSII_RUNTIME_PACKAGE_CACHE=disabled .venv/bin/python -m pytest tests/reconciliation -o addopts='' -q -ra
node --test ui/tests/reconciliation-contract.test.mjs
.venv/bin/ruff check tests/reconciliation
```

- Python: **17 collected; 13 failed, 4 passed in 4.70 s**. Full final baseline output:
  `/Users/suhas/Codex/2026-11-04/alr/work/mvp-document-review/reconciliation-baseline-python.txt`.
- Node: **10 tests; 9 failed, 1 passed**. Full final baseline output:
  `/Users/suhas/Codex/2026-11-04/alr/work/mvp-document-review/reconciliation-baseline-node.txt`.
- Ruff: **All checks passed**.

Observed red behavior:

- Snapshot missing (404) for sealed, unevaluated, pending and corrupted runs; new-route privacy/no-write
  assertions cannot proceed until that route exists.
- Compatible recorded `exp-nagoya-sonnet-1` replay itself passes verification and reproduces all ten
  source claims. The CLI does not score/report it: `/bundle` returns 409. Historical source run and
  cassette bytes are checked unchanged at fixture teardown.
- Unsupported AEF years 2023 and 2025 incorrectly replace actual 2024 dates.
- Adding one nonoverlapping correct training-example prediction changes heldout precision 1.0 to
  0.5, calibration count 1 to 2, and ranking retains all 2,793 cells rather than excluding the 16 known
  training-positive cells. Evaluated population description is absent.
- Predicted-accuracy object lacks its own synthetic/method demonstration restriction. Constructed
  fixture estimates may remain as method-only values; the tests do not demand regenerating vectors.
- Current HTTP adapter emits `confirmed`, loses claim identity/support, drops execution provenance
  and evaluation sections, fabricates missing cost as 0, and silently launches an unchanged preset
  when the caller edited its goal.
- Readable export crashes with null cost; GeoJSON with known cost loses claim IDs/evidence/decision
  links; summary does not distinguish absent/cannot-assess predictions.

Passing safeguards: valid 2024 deterministic/synthetic AEF behavior, exact offline recorded-source
replay, no-heldout/overlapping-reference abstention, unchanged pinned preset launch.

## Evidence and limits

`helpers.py` constructs deterministic offline scripted claims with contemporaneous decisions using
public run/provider contracts. The experiment test invokes the public `analyze(store)` result for
real fresh sealed stores, selects train/holdout points from the committed synthetic reference split,
and computes excluded cell coordinates independently. It does not mock the scorer. Overlap/empty
population tests use explicitly synthetic reference documents. The Node HTTP fixtures are contract
fixtures; they do not prove backend JSON or rendered browser behavior. Backend tests use FastAPI's
in-process HTTP client and real sealed stores. No visual browser interaction, physical measurements,
real geospatial accuracy, AWS availability, live execution or live vision was validated.

Root should inspect this freeze before commissioning repairs. Feature writers must not weaken these
assertions. Preserve baseline logs. `FROZEN-SHA256.json` records exact source-test/private-log hashes plus the
baseline source/evidence inputs. New successful verification logs should use different filenames.
