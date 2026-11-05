"""R1 public-boundary regression tests, authored independently before repair."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from helpers import ORIGIN, claim, planned, run_case

from treehouse import service
from treehouse.investigation.public import public_value as report_public_value
from treehouse.store.local import LocalStore
from treehouse.ui import create_app
from treehouse.ui.web import public_value as http_public_value


@pytest.mark.parametrize("project", [http_public_value, report_public_value], ids=["http", "report"])
@pytest.mark.parametrize("key", ["aws_session_token", "AWS.Session-Token", "imageBase64", "Image_Base_64"])
def test_r1_normalized_sensitive_keys_are_redacted(project, key):
    projected = project({"nested": [{key: "R1-PRIVATE-VALUE", "result_id": "r-safe"}]})
    assert "R1-PRIVATE-VALUE" not in json.dumps(projected)
    assert "r-safe" in json.dumps(projected), "safe evidence identifiers must survive"


@pytest.mark.parametrize("project", [http_public_value, report_public_value], ids=["http", "report"])
def test_r1_bearer_credentials_inside_notes_are_redacted(project):
    safe = project({"note": "Recorded failure; Bearer eyJ0oken.secret.sig", "decision_id": "d-safe"})
    assert "eyJ0oken.secret.sig" not in json.dumps(safe)
    assert "d-safe" in json.dumps(safe)


@pytest.fixture(scope="module")
def private_run(tmp_path_factory):
    store = LocalStore(tmp_path_factory.mktemp("r1-public") / "store")
    args = {"source_id": "aef-10m-annual", "cell_size_m": 160, "year": 2024,
            "innocent_bundle": {"description": "R1-ARBITRARY-RAW-PAYLOAD", "values": [1, 2, 3]},
            "aws_session_token": "R1-AWS-SECRET", "imageBase64": "R1-PIXEL-SECRET"}
    # An invalid tool request still has a real recorded contemporaneous decision and failure.
    run_case(store, "private", planned("index", "build_index", args) + claim("safe", [136.85, 35.08]))
    service.evaluate(store, "private")
    return store


@pytest.mark.parametrize("suffix", ["snapshot", "export", "bundle", "investigation"])
def test_r1_public_surfaces_do_not_forward_arbitrary_decision_parameters(private_run, suffix):
    with TestClient(create_app(private_run.root), base_url=ORIGIN) as api:
        response = api.get(f"/api/runs/private/{suffix}")
    assert response.status_code == 200, response.text
    for raw in ("R1-ARBITRARY-RAW-PAYLOAD", "R1-AWS-SECRET", "R1-PIXEL-SECRET"):
        assert raw not in response.text, f"{suffix} forwarded raw nested input"
    assert "claim_id" in response.text and "decision" in response.text


def test_r1_snapshot_tool_provenance_is_an_allowlisted_summary(private_run, monkeypatch):
    # Exercise nested tool metadata at the public boundary without modifying sealed evidence.
    from dataclasses import replace

    from treehouse.ui.web import Controller

    run = service.load_sealed(private_run, "private")
    trial = run.trials[0]
    call = next(c for c in trial.calls if c.name == "build_index")
    poisoned = replace(call, payload={"provenance": {"source": "synthetic-aef-v1", "synthetic": True,
        "access": "fixture", "innocent_bundle": {"description": "R1-RAW-PROVENANCE"}}, "year": 2024})
    projected_run = replace(run, trials=[replace(trial, calls=[poisoned if c == call else c for c in trial.calls])])
    monkeypatch.setattr(Controller, "sealed", lambda self, rid: projected_run)
    with TestClient(create_app(private_run.root), base_url=ORIGIN) as api:
        response = api.get("/api/runs/private/snapshot")
    assert response.status_code == 200, response.text
    assert "R1-RAW-PROVENANCE" not in response.text
    assert "fixture" in response.text, "safe provenance must remain inspectable"
