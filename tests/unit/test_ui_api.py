"""Public product API reads real sealed records without trusting cached reports."""

import hashlib
import json
import shutil
import threading

import pytest

pytest.importorskip("fastapi", reason="requires api extra")
from fastapi.testclient import TestClient

from treehouse import service
from treehouse.store.local import LocalStore
from treehouse.store.verify import verify


@pytest.fixture(scope="module")
def demo_store(tmp_path_factory):
    path = tmp_path_factory.mktemp("product-api") / "demo"
    results = service.demo(path, echo=lambda *_: None)
    return path / "store", results


def snapshot(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


def client(root, **kwargs):
    from treehouse.ui import create_app

    return TestClient(
        create_app(root, **kwargs),
        base_url="http://127.0.0.1:8765",
        headers={"Origin": "http://127.0.0.1:8765"},
    )


def test_real_demo_public_bundle_searches_events_and_no_get_writes(demo_store):
    root, expected = demo_store
    before = snapshot(root)
    with client(root) as api:
        caps = api.get("/api/capabilities").json()
        assert caps["execution"] == "offline" and caps["limits"]["max_parallel_runs"] == 1
        tasks = api.get("/api/tasks").json()["tasks"]
        assert len(tasks) == 9
        assert "cassette" not in json.dumps(tasks) and "key_path" not in json.dumps(tasks)
        runs = api.get("/api/runs").json()["runs"]
        assert len(runs) == 9 and all(r["status"] == "report_ready" for r in runs)
        rid = "synth-good"
        bundle = api.get(f"/api/runs/{rid}/bundle").json()
        assert bundle["facts"] == expected[rid].bundle.model_dump(mode="json")["facts"]
        assert bundle["scorecard"] == expected[rid].bundle.model_dump(mode="json")["scorecard"]
        assert bundle["passports"][0]["headline"]["reasons"] == ["trust engine not yet built"]
        assert all("treehouse.input.messages_ref" not in row["attributes"] for row in bundle["trace_rows"])
        searches = api.get(f"/api/runs/{rid}/clay-searches").json()["searches"]
        actual = next(c for t in expected[rid].run.trials for c in t.calls if c.name == "clay_search")
        assert searches[0]["result"]["cells"] == actual.payload["cells"]
        assert searches[0]["search_id"] == "t-0:" + actual.span_id
        first = api.get(f"/api/runs/{rid}/events?after=0&limit=2").json()
        second = api.get(f"/api/runs/{rid}/events?after=2&limit=200").json()
        events = first["events"] + second["events"]
        assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
        assert len(events) == sum(len(t.spans) for t in expected[rid].run.trials)
        assert first["next_cursor"] == 2 and second["complete"]
        assert first["source"] == "recorded_trace"
        assert api.get(f"/api/runs/{rid}/associations").json()["associations"] == []
        assert api.get(f"/api/runs/{rid}/verify").json()["ok"]
        exported = api.get(f"/api/runs/{rid}/export")
        assert exported.json() == bundle and "attachment" in exported.headers["content-disposition"]
    assert snapshot(root) == before
    assert verify(LocalStore(root)).ok


def test_modified_unhashed_bundle_is_ignored(demo_store, tmp_path):
    original, expected = demo_store
    root = tmp_path / "store"
    shutil.copytree(original, root)
    path = root / "bundles/synth-good/bundle.json"
    path.chmod(0o644)
    path.write_text('{"facts":{"invented":999},"private":"do not expose"}')
    with client(root) as api:
        response = api.get("/api/runs/synth-good/bundle")
        assert response.status_code == 200
        assert response.json()["facts"] == expected["synth-good"].bundle.model_dump(mode="json")["facts"]
        assert "do not expose" not in response.text


def test_origin_ids_body_preset_and_missing_build(tmp_path):
    root = tmp_path / "uncreated"
    with client(root) as api:
        assert api.get("/api/runs").json() == {"runs": []}
        assert not root.exists()
        assert api.get("/api/tasks", headers={"Host": "evil.example"}).status_code == 400
        assert (
            api.post(
                "/api/runs", json={"preset_id": "synth-good"}, headers={"Origin": "https://evil.example"}
            ).status_code
            == 403
        )
        assert api.get("/api/runs/a..b/bundle").status_code == 400
        assert api.get("/api/runs/" + "a" * 129 + "/bundle").status_code == 400
        assert api.get("/api/runs/missing/bundle").status_code == 404
        assert (
            api.post(
                "/api/runs", content=b"x" * 4097, headers={"Content-Type": "application/json"}
            ).status_code
            == 413
        )
        assert api.post("/api/runs", json={"preset_id": "missing"}).status_code == 422
        assert api.post("/api/runs", json={"preset_id": "synth-good", "mode": "live"}).status_code == 400
        assert api.get("/api/runs/missing/events?limit=201").status_code == 400
        assert api.get("/").status_code == 503
        assert api.get("/api/keys").status_code == 404
    assert not root.exists()


def test_symlink_and_tampered_evaluation_fail_closed(demo_store, tmp_path):
    original, _ = demo_store
    root = tmp_path / "store"
    shutil.copytree(original, root)
    outside = tmp_path / "private.txt"
    outside.write_text("PRIVATE_SOURCE_PROMPT")
    (root / "blobs/private-link").symlink_to(outside)
    with client(root) as api:
        response = api.get("/api/runs/synth-good/bundle")
        assert response.status_code == 409 and "PRIVATE" not in response.text
    (root / "blobs/private-link").unlink()
    evaluation = next((root / "evals/synth-good/score").glob("*.json"))
    evaluation.chmod(0o644)
    evaluation.write_text("{}")
    with client(root) as api:
        assert api.get("/api/runs/synth-good/bundle").status_code == 409
        proof = api.get("/api/runs/synth-good/verify").json()
        assert proof["ok"] is False
        assert str(tmp_path) not in json.dumps(proof)


def test_one_real_pinned_replay_job_and_busy_guard(tmp_path, monkeypatch):
    from treehouse.ui import create_app

    root = tmp_path / "store"
    started, release = threading.Event(), threading.Event()
    real_run = service.run

    def blocked(*args, **kwargs):
        started.set()
        assert release.wait(timeout=10)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(service, "run", blocked)
    app = create_app(root)
    with TestClient(
        app, base_url="http://127.0.0.1:8765", headers={"Origin": "http://127.0.0.1:8765"}
    ) as api:
        response = api.post("/api/runs", json={"preset_id": "synth-looper"})
        assert response.status_code == 202
        rid = response.json()["run_id"]
        assert rid != "synth-looper" and started.wait(timeout=2)
        assert api.post("/api/runs", json={"preset_id": "synth-good"}).status_code == 409
        assert api.get(f"/api/runs/{rid}/events").json()["events"] == []
        release.set()
        app.state.controller.jobs[rid]["future"].result(timeout=30)
        assert api.get(f"/api/runs/{rid}").json()["status"] == "report_ready"
        assert api.get(f"/api/runs/{rid}/bundle").json()["manifest_summary"]["mode"] == "replay"
        assert api.get(f"/api/runs/{rid}/verify").json()["ok"]
