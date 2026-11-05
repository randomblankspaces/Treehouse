"""Current-reference HTTP reports share snapshot scope withholding."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from helpers import ORIGIN, claim, hashes, run_case

from treehouse.investigation import evaluate_investigation
from treehouse.store.local import LocalStore
from treehouse.ui import create_app


@pytest.mark.parametrize(("outside", "coverage_east"), [
    ([136.90, 35.08], 136.87),  # Outside reference coverage, inside task AOI.
    ([136.95, 35.08], 136.99),  # Outside task AOI, inside reference coverage.
    ([136.90, 35.08], None),
])
def test_investigation_and_snapshot_withhold_same_scope_without_changing_history(
    tmp_path, outside, coverage_east,
):
    store = LocalStore(tmp_path / "store")
    run_case(store, "mixed-scope", claim("inside", [136.85, 35.08], confidence=.8)
             + claim("outside", outside, confidence=.6), synthetic=True)
    reference = {
        "schema_version": "treehouse.reference/1", "quality": "complete",
        "source": {"dataset": "Synthetic scope fixture", "version": "scope-1",
                   "url": "https://example.invalid/scope", "license": "CC0-1.0",
                   "attribution": "Synthetic method test; no physical measurement"},
        "coverage": {"type": "Polygon", "coordinates": [[[136.82, 35.05], [coverage_east, 35.05],
                     [coverage_east, 35.12], [136.82, 35.12], [136.82, 35.05]]]} if coverage_east else None,
        "features": [{"id": "heldout", "lon": 136.85, "lat": 35.08,
                      "cls": "warehouse", "split": "holdout"}],
    }
    path = tmp_path / "reference.json"
    path.write_text(json.dumps(reference))
    historical = evaluate_investigation(store, "mixed-scope", reference=reference)
    before = hashes(store.root)
    with TestClient(create_app(store.root, server_reference=path), base_url=ORIGIN) as api:
        response = api.get("/api/runs/mixed-scope/investigation")
        assert response.status_code == 200, response.text
        report = response.json()
        snapshot = api.get("/api/runs/mixed-scope/snapshot").json()
        database = api.get("/api/runs/mixed-scope/database").json()
    assert len(report["claims"]) == len(snapshot["markers"]) == len(database["features"]) == 2
    for name, panel in (("output", "output"), ("calibration", "confidence")):
        section = snapshot["evaluation"][name]
        assert section["status"] == "unavailable" and section["value"] is None
        assert report[panel]["no_grade_reason"] == section["reason"]
        for number in report[panel]["numbers"].values():
            assert number["value"] is None and number["tier"] == "ABSTAINED"
            assert number["reasons"] == [section["reason"]]
    assert hashes(store.root) == before
    assert evaluate_investigation(store, "mixed-scope", reference=reference) == historical
    if coverage_east:
        assert historical["output"]["numbers"]["catalog_precision"]["value"] == .5
        assert historical["confidence"]["numbers"]["brier"]["value"] == pytest.approx(.2)
