"""Pitch page demo mode C: the live endpoint is off by default, pinned, guarded and single-flight."""

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient

from treehouse.ui import pitch_live
from treehouse.ui.web import create_app

ORIGIN = "http://127.0.0.1:8765"


def client(tmp_path):
    (tmp_path / "store").mkdir(exist_ok=True)
    return TestClient(create_app(tmp_path / "store", origin=ORIGIN), base_url=ORIGIN, headers={"Origin": ORIGIN})


def test_off_by_default_and_page_load_never_starts(tmp_path, monkeypatch):
    monkeypatch.delenv(pitch_live.ENV_FLAG, raising=False)
    monkeypatch.setattr(pitch_live, "run_job", lambda *a: pytest.fail("must not run"))
    with client(tmp_path) as c:
        st = c.get("/api/pitch/live").json()
        assert st["enabled"] is False and pitch_live.ENV_FLAG in st["reason"]
        assert st["model_key"] == "claude-sonnet-5-5" and st["harness"] == "strands"
        r = c.post("/api/pitch/live", json={})
        assert r.status_code == 403
        assert c.get("/api/runs").json()["runs"] == []


def test_refuses_parameters_and_cross_origin(tmp_path, monkeypatch):
    monkeypatch.setenv(pitch_live.ENV_FLAG, "1")
    monkeypatch.setattr(pitch_live, "_missing_extras", lambda: [])
    monkeypatch.setattr(pitch_live, "budget_check", lambda: (True, "ok"))
    monkeypatch.setattr(pitch_live, "run_job", lambda *a: pytest.fail("must not run"))
    with client(tmp_path) as c:
        assert c.post("/api/pitch/live", json={"model": "x"}).status_code == 400
        assert c.post("/api/pitch/live", content=b"{}", headers={"content-type": "text/plain"}).status_code == 400
        assert c.post("/api/pitch/live", json={}, headers={"Origin": "https://evil.example"}).status_code in (400, 403)


def test_budget_guard_refuses(tmp_path, monkeypatch):
    monkeypatch.setenv(pitch_live.ENV_FLAG, "1")
    monkeypatch.setattr(pitch_live, "_missing_extras", lambda: [])
    monkeypatch.setattr(pitch_live, "budget_check", lambda: (False, "Spend guard level is over_alarm"))
    with client(tmp_path) as c:
        r = c.post("/api/pitch/live", json={})
        assert r.status_code == 403 and "over_alarm" in r.json()["detail"]


def test_enabled_run_is_tracked_and_reported(tmp_path, monkeypatch):
    monkeypatch.setenv(pitch_live.ENV_FLAG, "1")
    monkeypatch.setattr(pitch_live, "_missing_extras", lambda: [])
    monkeypatch.setattr(pitch_live, "budget_check", lambda: (True, "ok"))
    calls = []
    monkeypatch.setattr(pitch_live, "run_job", lambda root, rid, lock: calls.append(rid))
    with client(tmp_path) as c:
        r = c.post("/api/pitch/live", json={})
        assert r.status_code == 202
        rid = r.json()["run_id"]
        assert rid.startswith("pitch-live-")
        c.app.state.controller.jobs[rid]["future"].result(timeout=10)
        summary = c.get(f"/api/runs/{rid}").json()
        assert summary["status"] == "report_ready" and summary["mode"] == "live"
        assert calls == [rid]


def test_failed_run_reports_failure_and_frees_the_worker(tmp_path, monkeypatch):
    monkeypatch.setenv(pitch_live.ENV_FLAG, "1")
    monkeypatch.setattr(pitch_live, "_missing_extras", lambda: [])
    monkeypatch.setattr(pitch_live, "budget_check", lambda: (True, "ok"))

    def boom(*_a):
        raise RuntimeError("throttled")

    monkeypatch.setattr(pitch_live, "run_job", boom)
    with client(tmp_path) as c:
        rid = c.post("/api/pitch/live", json={}).json()["run_id"]
        controller = c.app.state.controller
        controller.jobs[rid]["future"].result(timeout=10)
        assert c.get(f"/api/runs/{rid}").json()["status"] == "failed"
        assert controller.busy is False


def test_single_flight(tmp_path, monkeypatch):
    monkeypatch.setenv(pitch_live.ENV_FLAG, "1")
    monkeypatch.setattr(pitch_live, "_missing_extras", lambda: [])
    monkeypatch.setattr(pitch_live, "budget_check", lambda: (True, "ok"))
    with client(tmp_path) as c:
        c.app.state.controller.busy = True
        assert c.post("/api/pitch/live", json={}).status_code == 409


def test_pitch_page_may_frame_the_app_but_no_other_origin(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>shell</html>")
    (tmp_path / "store").mkdir()
    with TestClient(create_app(tmp_path / "store", origin=ORIGIN, frontend_dist=dist), base_url=ORIGIN) as c:
        csp = c.get("/pitch").headers["content-security-policy"]
    rules = dict(part.strip().split(" ", 1) for part in csp.split(";"))
    assert rules["frame-ancestors"] == "'self'"
