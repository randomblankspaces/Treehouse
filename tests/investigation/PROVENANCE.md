# Independent acceptance test provenance

The tests and rubric were authored independently before the corresponding feature or review helper, and copied from the sibling `independent-investigation-tests` directory. The source directory retains the original freeze hashes, red logs and the documented portability and tamper-harness amendments. The vision-adapter red was recorded after the core implementation started; the browser script has not been run against a seeded app. Red logs were not reproduced during this copy.

Only import organization and removal of one unused `json` import were applied to copied Python files. The shared `context` fixture imports were moved into this directory's `conftest.py` so Ruff does not remove pytest fixture registration. AST comparison with import nodes removed verified every test file retains the same non-import code and assertions. Documents and browser script were copied byte-for-byte. No tests ran during this transfer because implementation files were being edited concurrently.

| Source file | Source SHA-256 | Integrated SHA-256 |
|---|---|---|
| `test_adaptive_budget.py` | `68efc360faeef8ab47c8138d805b337a939db7fb550f2675ea854485191f75e3` | `953c6d2da085f767a19820b1f05a35caf367b2c83164d609bf8fee6e92da6e13` |
| `test_api_red.py` | `409611264a8ba298ff09a857c7863cd71b6dc5994d2a53c0496ca7fd86d9e4ba` | `409611264a8ba298ff09a857c7863cd71b6dc5994d2a53c0496ca7fd86d9e4ba` |
| `test_classifier_boundary.py` | `d55a5e4b05b00eae07d2ea7d93f0f2dec31d12cc24650803ffa943787fe687f4` | `19b1697e7b95336f036b4cec4ee67c29e345376e501d653f77097ecc9eca1a0d` |
| `test_investigation_acceptance.py` | `e46cc675f64c1dea54d8e89aa510679293a3bcf236ef8c6763a56b6d891d0f3d` | `6e4c2ef20a915f70f1db36d8799dbbde5e586c6a9b397b21b397bbc818f8d3f6` |
| `test_investigation_http.py` | `24d7931f554b2bfb3faec74b599c8e97d266b603071847f4dbf41490496aaab8` | `f6285e29ffbcdab72f64bf06fd9130db94e83a9fe70209b83b27b4badaaad65e` |
| `test_process_review.py` | `c92c9781d73a137a45fbe2bcbba0875a89bd63cd8340e8da88e9b69ebedb800c` | `f050b5b6a939972511b92d6c247985adc2437bd15bebf2b4fc090460c3d6ee16` |
| `test_strategy_quality.py` | `976284d550c3fef831613d6f01f87241980dc2e18a75c0e4a9cb0fc69d1606d1` | `bbf58b6a1673ba275f426f1e7e23dc8baafba794620ac6765584dfd2337b8a1b` |
| `test_vision_adapter.py` | `015b5ad6244def7c0960866da364ba95f60136c8fa91960245ad34178e422a4d` | `8f38f6c19f6e5901e184d319c52e1499f40f81c30325eaf53f8e4f815d0271a4` |
| `RUBRIC-v1.md` | `66900d40d18f47dc80a845648c1eac56a4934f8098ceb31d7e4a883f6870f38f` | `66900d40d18f47dc80a845648c1eac56a4934f8098ceb31d7e4a883f6870f38f` |
| `EXPECTED-BEHAVIOR.md` | `536404ce746c8ae31413e99a183187d9ff3ad801cc2a716da0b82f6c190feea0` | `536404ce746c8ae31413e99a183187d9ff3ad801cc2a716da0b82f6c190feea0` |
| `investigation-browser.cjs` | `22c49e604b187cee9c0a637821bf94755810929fd944657aa13013c304265a57` | `22c49e604b187cee9c0a637821bf94755810929fd944657aa13013c304265a57` |

`conftest.py` (integration fixture wiring): `d7a2b177a11d701b94259695f1d3993c75b4a4334bb2e5880e4853edacca93e3`.

## Earlier frozen hashes

The two tamper test sources were later amended only to chmod disposable read-only files before mutation; the acceptance source also received repository-relative locator corrections. Those amended source hashes appear above.

| File | Earlier frozen SHA-256 | Source hash record |
|---|---|---|
| `EXPECTED-BEHAVIOR.md` | `536404ce746c8ae31413e99a183187d9ff3ad801cc2a716da0b82f6c190feea0` | `SHA256SUMS.txt` |
| `test_api_red.py` | `409611264a8ba298ff09a857c7863cd71b6dc5994d2a53c0496ca7fd86d9e4ba` | `SHA256SUMS.txt` |
| `test_investigation_acceptance.py` | `7716f2c59e6ce9be771fdfb31c70e751effb0af99d70cdb4eef3460642c7d39a` | `SHA256SUMS.txt` |
| `test_investigation_http.py` | `3c7071e6a3673aba527dc3421b6f6bb91d9481a9fd73936f5c3335e133ebbefd` | `HTTP-UI-SHA256.txt` |
| `investigation-browser.cjs` | `22c49e604b187cee9c0a637821bf94755810929fd944657aa13013c304265a57` | `HTTP-UI-SHA256.txt` |
| `test_adaptive_budget.py` | `68efc360faeef8ab47c8138d805b337a939db7fb550f2675ea854485191f75e3` | `SUPPLEMENT-SHA256.txt` |
| `test_strategy_quality.py` | `976284d550c3fef831613d6f01f87241980dc2e18a75c0e4a9cb0fc69d1606d1` | `STRATEGY-SHA256.txt` |
| `test_classifier_boundary.py` | `d55a5e4b05b00eae07d2ea7d93f0f2dec31d12cc24650803ffa943787fe687f4` | `CLASSIFIER-SHA256.txt` |
| `test_vision_adapter.py` | `015b5ad6244def7c0960866da364ba95f60136c8fa91960245ad34178e422a4d` | `VISION-SHA256.txt` |
| `RUBRIC-v1.md` | `66900d40d18f47dc80a845648c1eac56a4934f8098ceb31d7e4a883f6870f38f` | `REVIEW-SHA256.txt` |
| `test_process_review.py` | `c92c9781d73a137a45fbe2bcbba0875a89bd63cd8340e8da88e9b69ebedb800c` | `REVIEW-SHA256.txt` |

## Browser executable override

The integrated browser harness accepts optional `PLAYWRIGHT_CHROMIUM_EXECUTABLE` because the bundled Chromium executable is unavailable. Assertions are unchanged. Earlier browser SHA-256: `22c49e604b187cee9c0a637821bf94755810929fd944657aa13013c304265a57`; updated SHA-256: `2709f10abfe9282cebb68b02defcda2be6849b12c49c19b468542e53a33003d1`.

## Held-out isolation and classifier accounting regressions

`test_holdout_isolation.py` and `test_classifier_accounting_validation.py` were independently authored before the repair. Byte-identical copies and the frozen hashes are in the sibling independent test directory; `RED-HOLDOUT-ACCOUNTING.txt` records the pre-repair run. The recorded failures expose reference-example contamination, ambiguous reference/holdout matching, and boolean cost treated as a real charge. Other malformed accounting cases either were rejected or failed closed. No earlier test assertions were modified.
