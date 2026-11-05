"""Current-reference public scores abstain when positive predictions leave known scope."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from helpers import ORIGIN, claim, hashes, planned, run_case

from treehouse import service
from treehouse.store.local import LocalStore
from treehouse.ui import create_app


@pytest.mark.parametrize("outside", [(136.90, 35.08), (136.95, 35.08)],
                         ids=["outside-reference-coverage", "outside-task-aoi"])
def test_r2_current_reference_scores_withhold_unknown_out_of_scope_correctness(tmp_path, outside):
    store = LocalStore(tmp_path / "store")
    actions = planned("index", "build_index", {"source_id": "aef-10m-annual", "cell_size_m": 160, "year": 2024})
    actions += claim("inside", [136.85, 35.08], confidence=.8)
    actions += claim("outside", list(outside), confidence=.6)
    run_case(store, "partial-coverage", actions)
    sealed = service.load_sealed(store, "partial-coverage")
    assert len(sealed.trials[0].claims) == 2, "scope regression needs both actual recorded predictions"
    assert all(c.status == "present" for c in sealed.trials[0].claims)
    # Isolate each boundary: the outside-AOI claim remains inside reference coverage.
    coverage_east = 136.87 if outside[0] < 136.92 else 136.99
    reference = {
        "schema_version": "treehouse.reference/1", "quality": "complete",
        "source": {"dataset": "Independent synthetic partial coverage", "version": "r2-scope",
                   "url": "https://example.invalid/r2", "license": "CC0-1.0",
                   "attribution": "Synthetic method test; complete only within explicit coverage"},
        "coverage": {"type": "Polygon", "coordinates": [[[136.82, 35.05], [coverage_east, 35.05],
                      [coverage_east, 35.10], [136.82, 35.10], [136.82, 35.05]]]},
        "features": [{"id": "inside-positive", "lon": 136.85, "lat": 35.08,
                      "cls": "warehouse", "split": "holdout"}],
    }
    path = tmp_path / "partial-reference.json"
    path.write_text(json.dumps(reference))
    before = hashes(store.root)
    with TestClient(create_app(store.root, server_reference=path), base_url=ORIGIN) as api:
        for suffix in ("snapshot", "export"):
            response = api.get(f"/api/runs/partial-coverage/{suffix}")
            assert response.status_code == 200, response.text
            payload = response.json()
            snapshot = payload if suffix == "snapshot" else payload["snapshot"]
            assert len(snapshot["markers"]) == 2, "withholding numeric scores must preserve recorded predictions"
            for name in ("output", "calibration"):
                section = snapshot["evaluation"][name]
                assert section["status"] == "unavailable", f"{name} assigned correctness outside known comparison scope"
                assert section["value"] is None
                assert section["reason"] and any(word in section["reason"].lower()
                    for word in ("scope", "coverage", "aoi")), "withholding must explain the unknown comparison scope"
                assert isinstance(section["scores"], list)
                assert all(s["value"] is None and s["status"] == "unavailable" and s["reason"]
                           for s in section["scores"]), "unknown scope must not turn into a numeric zero"
    assert hashes(store.root) == before
