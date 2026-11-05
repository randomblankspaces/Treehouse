"""HTTP reference-scope contracts for sealed investigation reports."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient
from helpers import ORIGIN, claim, run_case

from treehouse.store.local import LocalStore
from treehouse.ui import create_app


def reference(coverage_east):
    return {
        "schema_version": "treehouse.reference/1",
        "quality": "complete",
        "source": {
            "dataset": "Independent synthetic coverage fixture",
            "version": "http-scope-1",
            "url": "https://example.invalid/http-scope",
            "license": "CC0-1.0",
            "attribution": "Synthetic method test; no physical measurement",
        },
        "coverage": {
            "type": "Polygon",
            "coordinates": [[[136.82, 35.05], [coverage_east, 35.05],
                              [coverage_east, 35.12], [136.82, 35.12], [136.82, 35.05]]],
        },
        "features": [{"id": "heldout", "lon": 136.85, "lat": 35.08,
                      "cls": "warehouse", "split": "holdout"}],
    }


def number(report, panel, name):
    return report[panel]["numbers"][name]


def test_http_withholds_correctness_for_prediction_outside_reference_coverage(tmp_path):
    store = LocalStore(tmp_path / "store")
    # The claim is in the task AOI but outside the explicit reference coverage.
    run_case(store, "outside-coverage", claim("outside", [136.90, 35.08]), synthetic=True)
    path = tmp_path / "reference.json"
    path.write_text(json.dumps(reference(136.87)))

    with TestClient(create_app(store.root, server_reference=path), base_url=ORIGIN) as api:
        response = api.get("/api/runs/outside-coverage/investigation")

    assert response.status_code == 200, response.text
    report = response.json()
    for metric in ("catalog_tp", "catalog_fp", "catalog_precision", "brier"):
        score = number(report, "confidence" if metric == "brier" else "output", metric)
        assert score["value"] is None and score["tier"] == "ABSTAINED"
        assert score["reason"] and any(word in score["reason"].lower()
                                        for word in ("scope", "coverage", "aoi"))


def test_http_returns_numeric_scores_when_prediction_and_reference_are_inside_coverage(tmp_path):
    store = LocalStore(tmp_path / "store")
    run_case(store, "inside-coverage", claim("inside", [136.85, 35.08], confidence=.8), synthetic=True)
    path = tmp_path / "reference.json"
    path.write_text(json.dumps(reference(136.92)))

    with TestClient(create_app(store.root, server_reference=path), base_url=ORIGIN) as api:
        response = api.get("/api/runs/inside-coverage/investigation")

    assert response.status_code == 200, response.text
    report = response.json()
    assert number(report, "output", "catalog_tp")["value"] == 1
    assert number(report, "output", "catalog_fp")["value"] == 0
    assert number(report, "output", "catalog_precision")["value"] == 1.0
    assert number(report, "output", "catalog_recall")["value"] == 1.0
    assert number(report, "confidence", "brier")["value"] == .04
