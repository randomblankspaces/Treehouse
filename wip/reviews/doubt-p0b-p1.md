# Code doubter: Treehouse P0b + P1 (pkg/p1-schemas on pkg/p0b-guard)

Checkout: `scratchpad/wt-review` at 8940b71 (diff against 5bde133). Spec: origin/main `docs/design/IMPLEMENTATION-DESIGN.md` (§1, §2, §6, §7 P0b/P1, Fact-check F1–F11).
Baseline: `uv run --frozen pytest` passes 122 tests; `ruff check .` is clean; `uv lock --check` is clean; the boto3 canary is not skipped (boto3 1.43.123).
Probe scripts are in `scratchpad/doubt-p1/` (`probe_schemas.py`, `probe_cards.py`, `probe_paths.py`, `probe_misc.py`, `guardprobe/`). They write nothing to the checkout. The only side effect is the `.venv` that `uv run` created there.

Counts: **blocking 2 · major 12 · minor 26** (40 items).

---

## Blocking

**1. `src/treehouse/schemas/passport.py:33-50`: TrustPassport lacks `n_gold_cannot_assess` and `narrowing_note`.**
- Doubt: §2 lists both fields explicitly. They come from STAT-B1, a blocking objection, and from STAT NB2. P8's acceptance tests them ("estimand named `verified_precision` when any gold label is `cannot_assess`"; "`narrowing_note` set when ratio ≥ 1"). Because the model is `extra="forbid"`, P8 cannot attach them without changing the schema and the golden `passport.json`/`bundle.json`. No validator ties `estimand.kind` to the cannot_assess count either.
- Evidence: `probe_misc.py` prints `passport fields missing: ['n_gold_cannot_assess', 'narrowing_note']`, and `grep -rn narrowing src/` finds nothing.
- Fix:
  - Add `n_gold_cannot_assess: int` (≥ 0) and `narrowing_note: str | None = None`.
  - Add a validator: when `estimand.kind == "precision"`, require `n_gold_cannot_assess == 0`. When it is > 0 and the headline is GOLD-ANCHORED, require kind `verified_precision`. When `detail.width_ratio_vs_classical >= 1`, require `narrowing_note`.
  - Regenerate the goldens.

**2. `src/treehouse/schemas/tools.py:34-63`: WindowResult has no `detail` field.**
- Doubt: §2 specifies `detail: {bytes_model: "synthetic-overview-block-v1" | "measured", …}`, and §0 row 6 / RS-B1 (blocking) requires results to carry `detail.bytes_model`. With `extra="forbid"`, P4's synthetic reader has nowhere to say the bytes are modelled. The "modelled bytes" chip (item 3) has no source either.
- Evidence: `probe_misc.py` prints `WindowResult has detail: False`.
- Fix: add `detail: dict[str, str | int | float | bool]` with `bytes_model` required, as `Literal["synthetic-overview-block-v1", "measured"]`. Add validators: `reader == "synthetic-v1"` ⇒ `bytes_model == "synthetic-overview-block-v1"`, and `synthetic` must be True when the reader is synthetic. Regenerate `window-result.json`.

## Major

**3. `src/treehouse/schemas/numbers.py:115-121`: `chip()` never adds "modelled bytes" and has no hover text.**
- Doubt: §2 says a `bytes_read` from the synthetic block model reads "Measured from trace · SYNTHETIC · modelled bytes", with hover "declared overview-block model, not measured" (RS-B1). The docstring mentions `bytes_model`, but the code ignores it.
- Evidence: `probe_schemas.py` #7 shows MEASURED bytes with `detail.bytes_model="synthetic-overview-block-v1"` → `'Measured from trace · SYNTHETIC'`. `test_chip_labels` only checks the constant dict and two KEYED chips.
- Fix:
  - Append "modelled bytes" when `detail.get("bytes_model") == "synthetic-overview-block-v1"`.
  - Add a `chip_hover()` method, or a constant, for the hover text.
  - Test `chip()` for every tier, and for the modelled-bytes case.

**4. `src/treehouse/schemas/scorecard.py:11-27`, `passport.py:33-60`: the MEASURED fence holds only on the panel label a number declares for itself.**
- Doubt: the fence checks `TypedNumber.panel`, but no container checks that its numbers belong to it.
  - A MEASURED number labelled `panel="process"` is accepted inside `Panel(name="output")`.
  - A TrustPassport accepts a MEASURED, process-panel headline with gate "Rely".
  - `Panel.name` is not checked against its slot in the Scorecard, so `Scorecard.output` can hold a Panel named "cost".
  - "Never output or trust" is therefore not enforced where it matters.
- Evidence: `probe_schemas.py` #1 prints `MEASURED number accepted inside output Panel` and #1b prints `passport with MEASURED headline on panel process, gate Rely: accepted`.
- Fix:
  - `Panel` validator: every number has `panel == self.name`.
  - `Scorecard` validator: each slot's `Panel.name` equals the slot name.
  - `TrustPassport` validator: `headline`, every entry in `alternatives` and `truth_reveal` have `panel == "trust"` and tier ≠ MEASURED. The `controls` numbers have `panel == "controls"`.
  - Add these to the fence test.

**5. `src/treehouse/schemas/model_io.py:100`: `ModelResponse.stop_reason` lacks the values F3 requires.**
- Doubt: F3 (normative) says to also map `malformed_model_output`, `malformed_tool_use`, `model_context_window_exceeded` and `guardrail_intervened`, and P6's test loops over botocore's stopReason enum. The current Literal has no target for the malformed or context-window cases. P6 will have to change a schema that P2/P3 cassettes already serialise.
- Evidence: `probe_misc.py` prints `('end_turn','tool_use','max_tokens','stop_sequence','content_filtered','guardrail')`.
- Fix: add `malformed_model_output`, `malformed_tool_use` and `model_context_window_exceeded` now, or a generic `error` plus a raw `provider_stop_reason: str | None`. Document `guardrail_intervened → guardrail`.

**6. `src/treehouse/schemas/sampling.py:19-28`: SampleDesign does not record the numpy version.**
- Doubt: F8 (normative) says to "record `numpy.__version__` in every SampleDesign". Without it, a design drawn under another numpy cannot be recognised as such, which was the point of risk 5. P8 would need a schema change.
- Evidence: `probe_misc.py` field list: `design_id, seed, rng, algorithm, frame_hash, N_h, n_h, units, created_seq`.
- Fix: add `numpy_version: str` (required). Optionally add `bitgen_api: Literal["random_raw"]` to pin the F8 selection method.

**7. `tests/unit/test_import_boundary.py:27-33, 103-122`: the AST boundary test misses `from treehouse import <subpkg>`.**
- Doubt: `ImportFrom` with `module="treehouse"` and level 0 is recorded as the bare name `treehouse`, so `inner` is None.
  - In PURE packages, `from treehouse import gateway, providers` therefore passes, although it is the most natural way to write the import.
  - The same path gives a false positive in `schemas/`: `from treehouse import canon` is flagged, though §1 allows canon.
  - Dynamic `importlib.import_module("boto3")` is also invisible to the test.
- Evidence: `probe_cards.py` A plants `trust/x.py: from treehouse import gateway, providers`, `score/x.py: importlib.import_module('boto3')` and `checks/x.py: import urllib.request, http.client, requests`. The result is `['report/x.py: imports treehouse.tools', 'schemas/x.py: imports treehouse']`. None of the trust, score or checks plants is caught, and the schemas finding is the false positive.
- Fix:
  - For absolute `ImportFrom`, expand to `f"{node.module}.{alias.name}"`, as the relative branch already does.
  - Flag `importlib.import_module` / `__import__` calls with a constant argument.
  - Consider adding `urllib`, `http.client`, `requests`, `urllib3` and `ssl` to IO_EXTERNAL for PURE.
  - Add these plants to `test_planted_violations_are_caught`.

**8. `tests/conftest.py:56-95`: the offline guard is function-scoped, so session- and module-scoped fixtures, collection-time code and subprocesses all escape it.**
- Doubt: §6 says "no test can reach the network". The guard is installed only around each test function's own setup.
  - A `scope="session"` or `scope="module"` fixture runs before the guard, with real sockets and the real `AWS_*` and proxy environment. This is exactly where P5 will build the demo once ("demo under the guard in under 60 s").
  - Module-level code in test files runs at collection, also unguarded.
  - Subprocesses (`test_lazy_imports`, a future J8 `uv run treehouse demo`) get real sockets. They inherit only the environment changes.
- Evidence (`guardprobe/test_holes.py`, run with the repo conftest):
  - A session fixture's `getaddrinfo("example.com")` raised the sandbox resolver's `gaierror`, not `NetworkBlocked`. The call reached the real resolver.
  - A subprocess `getaddrinfo` likewise reached the real resolver.
  - In both cases nothing was recorded on the guard.
- Fix:
  - Install the socket patches process-wide in `pytest_configure` or `pytest_sessionstart`, and scrub the environment there too. Keep the per-test fixture only to flip loopback on for `allow_loopback` and to collect attempts.
  - For subprocesses, put a `sitecustomize.py` on a `PYTHONPATH` the guard sets, so child Pythons install the same block. Alternatively, have `treehouse` honour `TREEHOUSE_OFFLINE=1` at import.

**9. `src/treehouse/cards.py:66, 72-77`: `task validate` does not do the footprint check, and its fixture check is shallow.**
- Doubt:
  - §2's first rule, "the AOI … intersects a pinned footprint", is replaced by an unconditional TODO warning. This deviation is not in the builder's list. No later package's acceptance (P4) picks the check up, so it is likely to be lost.
  - It is the only check that would catch a lat/lon swap.
  - "Every pinned item has a fixture" is checked only as "the `fixture_path` directory exists". Item files are never checked, and the card's ETags are never compared with `etags.json`.
- Evidence: `probe_cards.py` E swaps lon/lat on every Nepal AOI vertex and gets `errors: []`. `test_shipped_cards_validate` asserts that the TODO warning is present.
- Fix:
  - Implement the check now for pinned sources: read `items/<id>.json` footprints and use the existing `geom` helpers (vertex-in-polygon or edge crossing). Error when no pinned footprint intersects the AOI.
  - Check each `items/<id>.json` exists and that its ETag matches `etags.json`.
  - Move the TODO into P4's acceptance list if the check stays deferred.

**10. `src/treehouse/cards.py:69-79`: `data_allowlist.fixture_path` is never checked against `keys/` or the tool roots.**
- Doubt: §2 checks that `key_path` is not under a tool root, but nothing stops a card from declaring `keys/` as a data source, or a `fixture_path` that escapes the repo. That reverses the key isolation.
- Evidence: `probe_cards.py` C gives `fixture_path: keys/synth/synth-crossings-v1.key.json` → errors `[]`, and `fixture_path: ../../etc` → errors `[]`.
- Fix: in `validate_card`, error unless `is_under(root/fixture_path, tool_root)` for some tool root and not `is_under(..., keys_root())`. Include the `event.footprint_ref` and `gold_plan.seed_file` paths.

**11. `src/treehouse/cards.py:16-45`; `tests/unit/test_cards.py:190, 198`: the licence floor is a lossy total order.**
- Doubt: licences are not totally ordered. The floor keeps only the highest-rank id and drops every other obligation.
  - For Nepal (CC-BY-NC-4.0 Vantor, CC-BY-4.0 LGND, ODbL-1.0 OSM key), the reported floor is just `CC-BY-NC-4.0`. The CC-BY attribution and the ODbL attribution / share-alike notice disappear.
  - The test enshrines this: `license_floor(["ODbL-1.0","CC-BY-NC-4.0","MIT"]) == "CC-BY-NC-4.0"`.
  - The Manifest's `license_floor`/`nc_notice` will inherit the loss.
- Evidence: `test_cli_task_validate` asserts `"license floor: CC-BY-NC-4.0"` for Nepal.
- Fix: compute obligation flags (`attribution`, `share_alike`, `non_commercial`) over all inputs. Report the most restrictive id plus an `attributions: [ids]` list, or the full set of non-public-domain ids. Update the tests.

**12. `src/treehouse/paths.py:47-55`: the key-path deny check can be bypassed on case-insensitive macOS.**
- Doubt: `Path.resolve()` does not case-fold. On the default APFS volume, `<repo>/KEYS/synth/x.key.json` (or `fixtures/../Keys/...`) opens the key file, yet `is_relative_to(<repo>/keys)` is False, so `assert_not_key_path` passes. The demo targets a clean clone on macOS. Unicode NFD/NFC differences are the same class of problem.
- Evidence: this is reasoning, not a run (the probe host is Linux). `os.path.realpath` and `Path.resolve` do not canonicalise case on macOS.
- Fix:
  - Compare by identity: walk the resolved path's ancestors and test `os.path.samefile(ancestor, keys_root())`.
  - Better still, make the gateway rely on an allow-list (`is_under(tool_root)`, which fails safe under case variation). Keep the deny check as a second layer.
  - Add a test that monkeypatches a case-insensitive comparison.

**13. `src/treehouse/schemas/bundle.py:21-35`: ReportBundle has no evidence rows, and its summaries smuggle untyped numbers.**
- Doubt:
  - §6 I5 and RS NB1 require every Nepal WindowResult evidence row in the report to carry a SYNTHETIC chip. The bundle has no `window_results` or evidence rows, and no understanding statement, so the report cannot render the claim-and-evidence table from the bundle.
  - `manifest_summary` and `card_summary` are `dict[str, str]`. Numbers placed there as strings, such as bytes or costs, pass the no-bare-float walker but violate the I6 chip invariant.
  - The builder's refs-plus-summaries deviation also drops the card's `known_limits`, `must_notice` and steps, which the report shows.
- Evidence: field list in `bundle.py`. The walker in `test_schemas.py:237-255` only looks for the `float` type.
- Fix:
  - Add `evidence: list[WindowResult]` (each already carries `synthetic`) and `understanding: list[UnderstandingStatement]`.
  - Type the summaries as small Frozen models with str fields only, and put any number they need into `facts: dict[str, TypedNumber]`.
  - Or keep the full `TaskCard`, as §2 says.

**14. `src/treehouse/schemas/passport.py:50`, `manifest.py:59-98`, `numbers.py:82`: golden hashes cannot be stable (a forward risk the schema locks in).**
- Doubt:
  - Every TypedNumber carries `manifest_ref`, and every passport carries `code_sha`.
  - If `manifest_ref` is the manifest hash, then `versions.git_sha`, `versions.python` and the wall-clock `created_at` all feed it.
  - So the "golden passport hash" (P8) and the scorecard JSON golden would change on every commit and every Python version.
  - Committing a golden that contains the commit's own git sha is a fixed point that cannot be satisfied.
- Evidence: `Manifest.compute_hash` excludes only `manifest_hash`.
- Fix: decide in P1/P2 and document it:
  - `manifest_ref` = run_id, or the hash of the deterministic subset of the manifest (excluding `created_at`, `git_sha`, `python` and `uv_lock_sha256`).
  - `code_sha` excluded from the golden passport hash, or defined as the hash of `src/` content.
  - `created_at` taken from the run Clock (LogicalClock in replay).

## Minor

**15. `src/treehouse/schemas/model_io.py:19-27`, `tools.py:55`: the pixel-hash rule (OBS-B1/B2) has no single implementation.**
- `Image.sha256` and `WindowResult.pixel_sha256` are free strings, and the exact byte layout is unspecified: shape-string format, its order relative to the data, separator, and `sha256:` prefix or not. P3 and P4 will each invent one, yet the gateway needs the two to be equal.
- Fix: add `canon.pixel_sha256(data: bytes, shape: tuple[int, ...]) -> str` (stdlib only), plus a pattern constraint `^sha256:[0-9a-f]{64}$` on both fields.

**16. `src/treehouse/schemas/base.py:47-48`: NaN and ±Inf are accepted everywhere and fail only later, in `canonical_json`.**
- Evidence: `probe_schemas.py` #2 accepts `value=nan` (count), `value=inf` (usd) and an Interval with `lo=nan`. `canonical_json` then raises.
- Fix: `ConfigDict(..., allow_inf_nan=False)` on `Frozen`.

**17. `src/treehouse/schemas/numbers.py:83, 86` (and every `list`/`dict` field): the freeze is shallow.**
- After validation, `tn.detail.pop("key_version")` leaves a KEYED number with no key version. The models are also unhashable.
- Evidence: `probe_schemas.py` #3.
- Fix: use `tuple[...]` for lists and a frozen mapping for dicts, or re-validate on seal (`model_validate(model_dump())`) in P2.

**18. `src/treehouse/schemas/numbers.py:91-97`: ABSTAINED may carry a value.**
- `value=0.93, tier=ABSTAINED` renders as "Not issued · SYNTHETIC" next to 0.93.
- Evidence: `probe_schemas.py` #4.
- Fix: require `value is None` when the tier is ABSTAINED.

**19. `src/treehouse/schemas/numbers.py:111` and elsewhere: there are no range checks beyond `proportion`.**
- Accepted today: `abstention_rate=7.0`, an Interval of [−0.5, 1.7] on a proportion, a value outside its own interval, `kappa=5`, `flag=0.4`, `count=-3.5`. Also unbounded: `Claim.confidence` and the `*_coverage_fraction` fields.
- Evidence: `probe_schemas.py` #6 and #8.
- Fix: bound the proportion-like fields, kappa to [−1, 1], flag to {0, 1}, and count to ≥ 0 and integral. Require the interval to lie within [0, 1] for proportions.

**20. `numbers.py:86`, `trace.py:122` (`str|int|float|bool` unions): int and float give equal models but different canonical bytes.**
- `detail={"x": 1}` and `{"x": 1.0}` compare equal, but their sha256 differs. Golden heads will flip if one code path produces `float(1)`.
- Evidence: `probe_schemas.py` #5.
- Fix: normalise numerics in `canonical_json` (for example, integral floats → int) or forbid ints in these unions.

**21. `src/treehouse/schemas/task.py:178-179`: `card_hash()` depends on schema defaults and the timezone offset, not just the card's content.**
- Adding a defaulted field to any nested card model changes every card hash and every recorded `task_ref`, even with `schema_version` unchanged.
- The same `as_of` instant written as `+05:45` hashes differently.
- Evidence: `probe_cards.py` H (defaults such as `census_if_N_le=60` and `must_notice=[]` are hashed) and I (`hash equal? False`).
- Fix: normalise `as_of` to UTC. Bump `schema_version` on any field change (add a test that the golden schema and `schema_version` change together), or hash `exclude_defaults=True`.

**22. `src/treehouse/schemas/task.py:166-176`, `cards.py`: the card has semantic holes.**
- None of these is caught:
  - `statuses_allowed` inconsistent with `question_id` (exists → `["destroyed"]`);
  - `match_rule.tolerance_m` keys that are not in `classes`;
  - `as_of` outside `time_window`;
  - `smoke_aoi` outside `aoi`;
  - duplicate `strata_keys`;
  - negative `n_gold`, `n_total` or `max_out_px`;
  - `partly_keyed` without a `completeness_caveat`;
  - an unkeyed step with no `gold_plan`;
  - a `present` key that is missing on disk (only a warning).
- Note: the shipped Nepal `smoke_aoi` [85.33, 28.14, 85.37, 28.18] itself extends below the AOI's southern edge (28.150) and past its western edge at 28.18 N. This is inherited from the spec, but R2 "inside AOI" will flag smoke-run claims there.
- Evidence: `probe_cards.py` F gives `errors: []` for all of these at once. D: present-but-missing key → warnings only. G: Nepal without `gold_plan` → `[]`.
- Fix: add the validators. Make a `present` key missing on disk an error.

**23. `src/treehouse/schemas/task.py:166-176`: model-level errors carry no field path.**
- These errors report `card: Value error, …` with an empty loc: forbidden_sources, synthetic_notice, duplicate step ids, time_window. P1's acceptance says "bad cards rejected with field paths", and only the unknown-field test checks a path.
- Evidence: `probe_paths.py`.
- Fix: use field validators, or raise `PydanticCustomError` with the loc. Assert the path in each bad-card test.

**24. `src/treehouse/cards.py:43-45`: `license_floor([])` raises.**
- A card with an empty allowlist and only unkeyed steps makes `validate_card` raise `ValueError: max() iterable argument is empty`. The CLI prints a traceback instead of an error.
- Evidence: `probe_cards.py` B.
- Fix: return `None` with an error such as "no licences declared".

**25. `tasks/nepal-bhote-koshi-bridges.yaml:136`: `known_limits` miscounts the cloud trap and names the answer.**
- It says "Thirteen post-event scenes are 71-94 % cloud", but the card's own item comments list 16 such scenes (the cloud values are 71,71,71,72,73,78,78,78,79,79,81,84,85,93,94,94). The 13 is inherited from a-rs "13 scenes … 71–94".
- The same line names E5610/E5810 as the clear scenes. If any prompt builder renders `known_limits` or `must_notice` to the worker, the cloud-trap test is given away. No schema marker separates worker-visible fields from hidden ones.
- Fix: correct the count, or say "16". Document, and later test in P3/P5, that the worker prompt is built from `goal` only.

**26. All 4 cards set `synthetic: true`, which conflates "synthetic task" with "synthetic data".**
- Virginia and Nepal cards use real imagery and keys. If `TypedNumber.synthetic` is derived from `card.synthetic`, real live runs (K4, a Virginia run) will be chipped SYNTHETIC.
- Fix: rename the field to `synthetic_task` (keep the required notice), and derive the per-number flag from the data sources (`access == "synthetic"`, `labeller_kind`, and `synthetic` on the WindowResults). Document the derivation.

**27. `tasks/synth-crossings-v1.yaml:67`: the synth key is mislabelled `pending_fetch`.**
- This builder deviation produces the warning "keyed scores unavailable until it is fetched" for a key that is generated, not fetched.
- Fix: acceptable until P5, but word the warning by `key_source`, or add a `pending_generation` status.

**28. `tests/conftest.py:76-84`: name-lookup and UDP calls other than `getaddrinfo` are not blocked.**
- `gethostbyname`, `gethostbyname_ex`, `gethostbyaddr` and UDP `sendto` / `sendmsg` all bypass the guard.
- Evidence: `guardprobe` — `gethostbyname("example.com")` reached the real resolver and recorded nothing. `sendto(b"x", ("8.8.8.8", 53))` returned `sent 1`.
- Fix: patch those functions and `socket.socket.sendto` / `sendmsg` for non-loopback destinations.

**29. `tests/unit/test_guard.py:56-61`: the guard tests leave behaviour unchecked, and the canary can be skipped.**
- The `allow_loopback` marker's behaviour is never tested: nothing shows loopback blocked without the marker or allowed with it. A guard that always allowed or always blocked loopback would pass.
- The canary uses `importorskip("boto3")`, so it is skipped silently if boto3 is missing, even though boto3 is a pinned dev dependency.
- Otherwise the canary is sound. It asserts that `amazonaws.com` appears in a recorded `getaddrinfo` attempt, so a connect-only guard would fail it.
- Fix: add a loopback server test with and without the marker. Use a hard `import boto3`.

**30. `tests/unit/test_licence_scan.py:169-177`: the licence scan has holes.**
- It misses:
  - GIF (`GIF8`), WebP (`RIFF....WEBP`), JPEG 2000 and BigTIFF (`II+\0` / `MM\0+`) magic. Bedrock accepts gif and webp (F4).
  - Images inside zip/npz/gz containers. `fixtures/embeddings/*.npz` lands in P4.
  - Raw `.npy` uint8 pixel arrays.
- Only `fixtures/`, `tasks/` and `docs/` are scanned, so `tests/` (goldens), `keys/` and `out/` are not.
- Fix: add the magics. Open `.npz`/`.zip`/`.gz` and scan their members. Reject `.npy` arrays with uint8 dtype and ≥ 2 dimensions in `fixtures/`. Add `tests/` and `keys/` to the scanned roots.

**31. `tests/unit/test_import_boundary.py:18, 150-160`: the lazy-import test omits `botocore` and has no planted failure.**
- A top-level `import botocore.config` in `providers/bedrock.py` would pass here, because botocore is installed with dev, and then break a no-`aws` install.
- Fix: add `botocore` to LAZY. Add a planted test showing a module with top-level `import boto3` fails the subprocess check.

**32. `tests/unit/test_schemas.py:221-255`: the no-bare-float walker treats `Any` as safe and ignores bare ints.**
- So `dict[str, Any]` fields, or a bare-int count such as `n_gold_cannot_assess`, slip through.
- The exempted `CheckResult.detail` floats (distances) will reach the report as untyped digits, against I6.
- Fix: treat `Any` as a violation unless the field is exempt. Decide whether ints count as numbers too. Note in I6 that exempt floats must be rendered inside a `data-tier` ancestor.

**33. `tests/unit/test_schemas.py`, `tests/unit/test_cards.py:106`: several validators have no tests.**
- Untested: the TrustPassport validators (`truth_reveal` only when synthetic; GOLD-ANCHORED needs `width_ratio_vs_classical`), the Keying rules, and the TaskCard rules (synthetic notice, time window, unique steps).
- Round-trip is tested only for TypedNumber, Image and TaskCard, not for every registry schema.
- The second assertion in `test_card_hashes_are_stable` compares one call with itself, so it is vacuous.
- Fix: add one example per registry schema (round-trip plus frozen) and a validator table per model.

**34. `src/treehouse/schemas/verdicts.py:26-27`: GoldLabel has no synthetic consistency check, and its docstring names the wrong estimand.**
- There is no rule that `labeller_kind == "synthetic"` ⇒ `synthetic`.
- The docstring says y=0 counts "for precision". The estimand is `verified_precision`, and `precision` is reserved for the case with zero cannot_assess labels.
- Fix: add the validator and fix the wording.

**35. `src/treehouse/schemas/checks.py:18`, `manifest.py:76-98`: a spec-required field is optional, and the Manifest has no consistency checks.**
- `CheckResult.record_ref` is optional, but §2 makes it required.
- The Manifest has no validators for:
  - `config_hash == sha256_json(config)`;
  - `mode == config.mode`;
  - a non-commercial floor ⇒ `nc_notice`;
  - all five `backends_resolved` slots being present;
  - `manifest_hash == compute_hash()`.
- Fix: add them, or record them as P2 acceptance items.

**36. `.github/workflows/ci.yml:13`, `pyproject.toml:19`: CI does not enforce the lockfile, and the strands floor is below spec.**
- `uv sync --all-extras` without `--locked` re-locks silently instead of failing on drift.
- The strands floor is `>=1.60` against the spec's `>=1.63`. The lock resolves to 1.63.0, so this matters only outside the lock.
- Fix: use `uv sync --locked --all-extras` and `strands-agents>=1.63,<2`.

**37. `tests/conftest.py:104`: any `-m` expression turns off the default slow deselection.**
- For example, `pytest -m "not live"` runs the slow tests.
- Fix: deselect slow tests unless the `-m` expression mentions `slow`.

**38. `src/treehouse/schemas/tools.py:15-25`: SceneSummary has no `synthetic` flag.**
- SYN-* scene rows in the report cannot carry the SYNTHETIC chip.
- Fix: add `synthetic: bool`, required.

**39. `tests/unit/test_prereg_and_literals.py:44-47`: the region-constant scan has gaps.**
- It misses coordinates inside strings (`"85.33"`), 1-decimal floats (85.3) and integers (85).
- The place-name list is short.
- Fix: also regex-scan string constants for `\d{2,3}\.\d{2,}`.

**40. `src/treehouse/schemas/config.py:105`: the RunConfig `needs_vision` registry validator is deferred to P6.**
- The docstring documents the deferral, but it is missing from the builder's deviation list.
- Fix: add it to P6's acceptance list.

---

### Checked and found sound
- Proxy stripping is the right call: a loopback proxy would tunnel past the guard.
- `getaddrinfo` patching does cover `socket.create_connection`, urllib3 and asyncio. `SSLSocket.connect` goes through the patched `connect`.
- The canary proves DNS-level blocking.
- `IdSource` and `LogicalClock` are deterministic and machine-independent.
- Canonical JSON uses shortest-repr floats, so it is stable across IEEE-754 machines.
- YAML line-break normalisation makes the card hash immune to CRLF checkouts.
- `os.devnull` resolves correctly on macOS.
- Virginia's AOI lies in MGRS 18STH: a hand-computed UTM zone 18 easting of about 241–264 km and northing of about 4.21–4.23 Mm gives T/H.
- India's AOI stays at or below 26.22 N, matching a-rs's "46RCP verified to reach 26.22 N". Its exact placement is still UNVERIFIED.
- The Nepal notice says "synthetic task … not from ADB", and the goal repeats it.
- `prereg/trust-config.yaml` equals the TrustConfig defaults.
- The ETag count (23) matches a-rs "All 23 intersecting item ids".
- Over-engineering is modest. The region-constant scan and the self-intersection check go beyond the spec, are cheap and are tested.
