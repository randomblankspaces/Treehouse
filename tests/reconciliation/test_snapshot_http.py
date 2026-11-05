"""Independent read-only HTTP bridge acceptance (interface approved by lead before repairs)."""
from __future__ import annotations

import json
import runpy

import pytest
from fastapi.testclient import TestClient
from helpers import ORIGIN, ROOT, claim, hashes, planned, run_case

from treehouse import service
from treehouse.store.local import LocalStore
from treehouse.store.verify import verify
from treehouse.ui import create_app

SECTIONS = {"reasoning_rules", "reviewer", "agentcore", "output", "calibration", "predicted_accuracy"}


def client(root):
    return TestClient(create_app(root), base_url=ORIGIN, headers={"Origin": ORIGIN})


def assert_evaluation(evaluation):
    assert SECTIONS <= evaluation.keys()
    for name in SECTIONS:
        section = evaluation[name]
        assert section["status"] in {"available", "unavailable", "method_test_only"}
        if section["status"] == "unavailable":
            assert section["value"] is None and section["reason"], f"{name} must explain missing evaluation"
        elif section["status"] == "method_test_only":
            assert section["reason"], f"{name} method demonstration must explain its limits"
        else:
            assert section["value"] is not None, f"{name} cannot be available without evidence"


@pytest.fixture(scope="module")
def sealed_store(tmp_path_factory):
    store = LocalStore(tmp_path_factory.mktemp("reconciliation-http") / "store")
    actions = planned("index", "build_index", {"source_id": "aef-10m-annual", "cell_size_m": 160, "year": 2024})
    actions += claim("present", [136.85, 35.08])
    actions += claim("absent", [136.86, 35.08], status="absent")
    actions += claim("unknown", [136.87, 35.08], status="cannot_assess")
    run_case(store, "sealed-method", actions)
    service.evaluate(store, "sealed-method")
    run_case(store, "sealed-unevaluated", claim("unevaluated", [136.85, 35.08]))
    return store


def test_sealed_run_snapshot_preserves_actual_status_ids_and_decision_support(sealed_store):
    run = service.load_sealed(sealed_store, "sealed-method")
    claims = {c.claim_id: c for t in run.trials for c in t.claims}
    assert len(claims) == 3, "fixture must really contain all three claim statuses"
    with client(sealed_store.root) as api:
        response = api.get("/api/runs/sealed-method/snapshot")
        assert response.status_code == 200, response.text
        snapshot = response.json()
        assert snapshot["run_id"] == "sealed-method" and snapshot["status"] == "complete"
        assert snapshot["mode"] == "fake"
        assert snapshot["markers"], "actual positive claim must remain viewable"
        for marker in snapshot["markers"]:
            source = claims[marker["claim_id"]]
            assert marker["status"] == source.status, "agent presence is not confirmed ground truth"
            assert marker["trial_id"] == source.trial_id
            assert marker["evidence_refs"] == [r.model_dump(mode="json") for r in source.evidence_refs]
            assert marker["decision_id"], "this fixture has a valid contemporaneous claim decision"
            assert [marker["lon"], marker["lat"]] == list(source.geometry.coordinates)
        assert any(m["status"] == "present" for m in snapshot["markers"])


def test_snapshot_and_export_retain_method_only_evaluation_and_source_provenance(sealed_store):
    with client(sealed_store.root) as api:
        response = api.get("/api/runs/sealed-method/snapshot")
        assert response.status_code == 200, response.text
        snapshot = response.json()
        provenance = snapshot["provenance"]
        assert provenance["embeddings"] == "synthetic_reference_derived"
        assert provenance["reference"] == "synthetic"
        assert provenance["vision"] == "not_used"
        assert provenance["limitations"]
        assert_evaluation(snapshot["evaluation"])
        for name in ("output", "calibration", "predicted_accuracy"):
            assert snapshot["evaluation"][name]["status"] != "available", "fixture results cannot validate operational accuracy"
        assert snapshot["evaluation"]["reasoning_rules"]["status"] != "unavailable"
        assert snapshot["evaluation"]["reviewer"]["status"] == "unavailable"
        assert snapshot["evaluation"]["agentcore"]["status"] == "unavailable"
        exported = api.get("/api/runs/sealed-method/export")
        assert exported.status_code == 200
        # Export may wrap the snapshot or retain a bundle; the approved semantic content must survive.
        text = json.dumps(exported.json(), sort_keys=True)
        for required in ("synthetic_reference_derived", "not_used", "reasoning_rules", "predicted_accuracy"):
            assert required in text, f"export lost {required}"


def test_unevaluated_sealed_run_remains_openable_with_missing_reasons(sealed_store):
    with client(sealed_store.root) as api:
        response = api.get("/api/runs/sealed-unevaluated/snapshot")
        assert response.status_code == 200, response.text
        snapshot = response.json()
        assert snapshot["run_id"] == "sealed-unevaluated" and snapshot["steps"]
        assert snapshot["markers"], "missing optional evaluation cannot hide the sealed database"
        assert_evaluation(snapshot["evaluation"])
        assert snapshot["provenance"]["embeddings"] == "unknown", "task.synthetic=false does not establish real embeddings"
        assert snapshot["provenance"]["vision"] == "not_used"


def test_pending_snapshot_is_partial_and_never_fabricates_zero_cost_or_live_steps(tmp_path):
    app = create_app(tmp_path / "missing")
    app.state.controller.jobs["pending"] = {"run_id": "pending", "title": "Queued offline replay",
                                             "task_id": "t1-nagoya-warehouses", "mode": "replay",
                                             "synthetic": False, "status": "running"}
    with TestClient(app, base_url=ORIGIN) as api:
        response = api.get("/api/runs/pending/snapshot")
        assert response.status_code == 200, response.text
        snapshot = response.json()
        assert snapshot["status"] == "running" and snapshot["mode"] == "replay"
        assert snapshot["steps"] == [] and snapshot["markers"] == []
        assert snapshot["cost_usd"] is None and snapshot["elapsed_ms"] is None
        assert_evaluation(snapshot["evaluation"])
        assert all(section["status"] == "unavailable" for section in snapshot["evaluation"].values())
        assert snapshot["provenance"]["embeddings"] == "unknown"


def test_get_reads_preserve_store_and_do_not_execute_models(sealed_store, monkeypatch, offline_guard):
    before = hashes(sealed_store.root)

    def forbidden(*args, **kwargs):
        pytest.fail("read-only HTTP inspection attempted model/cloud execution")

    monkeypatch.setattr(service, "run", forbidden)
    import boto3
    monkeypatch.setattr(boto3, "client", forbidden)
    with client(sealed_store.root) as api:
        for path in ("/api/runs", "/api/tasks", "/api/capabilities", "/api/runs/sealed-method/snapshot",
                     "/api/runs/sealed-method/investigation", "/api/runs/sealed-method/export"):
            response = api.get(path)
            assert response.status_code == 200, (path, response.text)
            assert all(secret not in response.text for secret in ('"raw_prompt"', '"pixels"', '"api_key"', '"secret_access_key"', '"key_path"'))
    assert not offline_guard.attempts
    assert hashes(sealed_store.root) == before


def test_corrupt_seal_fails_closed_on_snapshot_and_export(tmp_path):
    store = LocalStore(tmp_path / "store")
    run_case(store, "corrupt", claim("claim", [136.85, 35.08]))
    service.evaluate(store, "corrupt")
    path = store.run_dir("corrupt") / "trials/t-0.claims.jsonl"
    path.chmod(0o644)
    path.write_bytes(path.read_bytes() + b" ")
    with client(store.root) as api:
        for suffix in ("snapshot", "export"):
            response = api.get(f"/api/runs/corrupt/{suffix}")
            assert response.status_code == 409, (suffix, response.text)
            assert str(tmp_path) not in response.text
    assert verify(store, "corrupt").ok is False


@pytest.fixture(scope="module")
def replayed_source(tmp_path_factory):
    run_id = "exp-nagoya-sonnet-1"
    source = ROOT / "fixtures/live/experiments/runs" / run_id
    cassette = ROOT / "fixtures/live/cassettes" / f"{run_id}.model.jsonl"
    preserved = {"sealed": hashes(source), "cassette": cassette.read_bytes()}
    store = LocalStore(tmp_path_factory.mktemp("reconciliation-recorded") / "fresh-store")
    replay = runpy.run_path(str(ROOT / "scripts/replay_live.py"))["main"]
    assert replay([run_id, "--store", str(store.root)]) == 0
    yield store, source, run_id
    assert hashes(source) == preserved["sealed"] and cassette.read_bytes() == preserved["cassette"]


def test_valid_recorded_live_source_replays_identical_claims_offline(replayed_source, offline_guard):
    store, source, run_id = replayed_source
    assert verify(store, run_id).ok
    actual = [json.loads(line) for line in (store.run_dir(run_id) / "trials/t-0.claims.jsonl").read_text().splitlines()]
    expected = [json.loads(line) for line in (source / "t-0.claims.jsonl").read_text().splitlines()]
    assert actual and expected, "a valid recorded source must contain real recorded outputs"
    for name in ("cls", "status", "geometry", "confidence"):
        assert [c[name] for c in actual] == [c[name] for c in expected], f"replay changed sealed {name}"
    assert not offline_guard.attempts


def test_recorded_live_cli_replay_has_scores_and_viewable_report(replayed_source, offline_guard):
    store, _, run_id = replayed_source
    with client(store.root) as api:
        for suffix in ("bundle", "snapshot", "export"):
            response = api.get(f"/api/runs/{run_id}/{suffix}")
            assert response.status_code == 200, (suffix, response.text)
        snapshot = api.get(f"/api/runs/{run_id}/snapshot").json()
        assert snapshot["mode"] == "replay" and snapshot["status"] == "complete"
        assert snapshot["steps"] and snapshot["markers"]
        assert_evaluation(snapshot["evaluation"])
        assert snapshot["evaluation"]["reasoning_rules"]["status"] != "unavailable"
        assert snapshot["provenance"]["embeddings"] == "synthetic_reference_derived"
    assert not offline_guard.attempts
