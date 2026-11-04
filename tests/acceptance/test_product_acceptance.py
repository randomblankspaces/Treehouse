"""Independent acceptance tests for the frozen treehouse.ui/1 contract.
Run with the integrated package on PYTHONPATH and pytest + httpx installed.
All mutation experiments use a disposable copy of the nine-run store.
"""

import hashlib
import json
import os
import shutil
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from starlette.testclient import TestClient

from treehouse.schemas.checks import CheckLedger
from treehouse.schemas.passport import TrustPassport
from treehouse.schemas.scorecard import Scorecard
from treehouse.schemas.tools import ClaySearchResult
from treehouse.service import build_bundle, demo, load_sealed
from treehouse.store.local import LocalStore
from treehouse.store.verify import verify
from treehouse.ui.web import create_app

ORIGIN = "http://localhost:8765"
RUN = "synth-good"


@pytest.fixture(scope="session")
def source_store(tmp_path_factory):
    if os.environ.get("TREEHOUSE_ACCEPTANCE_STORE"):
        return Path(os.environ["TREEHOUSE_ACCEPTANCE_STORE"])
    out = tmp_path_factory.mktemp("sealed-demo") / "demo"
    demo(out, echo=lambda *_: None)
    return out / "store"


@pytest.fixture
def store(tmp_path, source_store):
    p = tmp_path / "store"
    shutil.copytree(source_store, p)
    return p


@pytest.fixture
def client(store, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>test shell</html>")
    with TestClient(
        create_app(store, origin=ORIGIN, frontend_dist=dist, judge_app=None),
        base_url=ORIGIN,
        headers={"Origin": ORIGIN},
    ) as c:
        yield c


def snapshot(root):
    return {
        str(p.relative_to(root)): (
            p.is_symlink(),
            p.stat().st_mode,
            hashlib.sha256(p.read_bytes()).hexdigest(),
        )
        for p in root.rglob("*")
        if p.is_file() and not p.is_symlink()
    }


def expected_bundle(root, rid):
    s = LocalStore(root)
    assert verify(s, rid).ok
    run = load_sealed(s, rid)
    rules = s.list_records(rid, "rules")[-1].record
    ledgers = [CheckLedger.model_validate(x) for x in rules["ledgers"]]
    score = Scorecard.model_validate(s.list_records(rid, "score")[-1].record)
    passport = TrustPassport.model_validate(s.list_records(rid, "trust")[-1].record)
    return build_bundle(run, ledgers, score, passport).model_dump(mode="json")


def test_read_endpoints_match_verified_records_and_do_not_write(client, store):
    before = snapshot(store)
    runs = client.get("/api/runs").json()["runs"]
    assert len(runs) == 9 and RUN in {r["run_id"] for r in runs}
    expected = expected_bundle(store, RUN)
    b = client.get(f"/api/runs/{RUN}/bundle")
    assert b.status_code == 200
    actual = b.json()
    for field in ("manifest_ref", "claims", "evidence", "facts", "scorecard", "passports", "synthetic"):
        assert actual[field] == expected[field], field
    assert actual["manifest_summary"]["mode"] == "replay"
    assert actual["passports"][0]["headline"]["tier"] == "ABSTAINED"
    assert actual["passports"][0]["headline"]["reasons"]
    assert all(
        ref["result_id"] in {e["result_id"] for e in actual["evidence"]}
        for claim in actual["claims"]
        for ref in claim["evidence_refs"]
        if claim["grounded"]
    )
    v = client.get(f"/api/runs/{RUN}/verify").json()
    assert v["ok"] is True and v["scope"] == "sealed_run_and_evaluation_ledger"
    assert v["manifest_ref"] == actual["manifest_ref"]
    assert v["bundle_source"] == "reconstructed_from_verified_records"
    export = client.get(f"/api/runs/{RUN}/export")
    assert export.json() == actual and "attachment" in export.headers["content-disposition"].lower()
    assert client.get(f"/api/runs/{RUN}/associations").json() == {
        "associations": [],
        "reason": "No verified cell-to-claim association is recorded.",
    }
    for path in (
        "/api/capabilities",
        "/api/tasks",
        f"/api/runs/{RUN}",
        f"/api/runs/{RUN}/events",
        f"/api/runs/{RUN}/clay-searches",
    ):
        assert client.get(path).status_code == 200
    assert snapshot(store) == before


def test_clay_and_events_come_from_verified_sealed_records(client, store):
    run = load_sealed(LocalStore(store), RUN)
    searches = client.get(f"/api/runs/{RUN}/clay-searches").json()["searches"]
    calls = [
        (t.trial_id, c)
        for t in run.trials
        for c in t.calls
        if c.name == "clay_search" and c.status == "success"
    ]
    assert len(searches) == len(calls) and calls
    for search in searches:
        trial, call = next(
            (t, c) for t, c in calls if t == search["trial_id"] and c.result_id == search["result_id"]
        )
        assert search["result"] == ClaySearchResult.model_validate(
            {k: v for k, v in call.payload.items() if k != "result_id"}
        ).model_dump(mode="json")
        assert search["search_id"] == f"{trial}:{search['span_id']}"
    spans = sorted(
        ((s.end_ns, t.trial_id, s.span_id, s) for t in run.trials for s in t.spans), key=lambda x: x[:3]
    )
    events, cursor = [], 0
    while True:
        page = client.get(f"/api/runs/{RUN}/events", params={"after": cursor, "limit": 3}).json()
        assert page["source"] == "recorded_trace"
        events.extend(page["events"])
        assert page["next_cursor"] >= cursor
        if not page["events"]:
            break
        assert page["next_cursor"] > cursor
        cursor = page["next_cursor"]
    assert [e["sequence"] for e in events] == list(range(1, len(spans) + 1))
    assert [(e["trial_id"], e["span_id"], e["time_ns"], e["name"], e["status"]) for e in events] == [
        (trial, sid, end, span.name, span.status) for end, trial, sid, span in spans
    ]
    assert len({e["event_id"] for e in events}) == len(events)
    assert (
        client.get(f"/api/runs/{RUN}/events", params={"after": 0, "limit": 3}).json()["events"] == events[:3]
    )


def test_mutable_cached_bundle_is_not_authority(client, store):
    baseline = client.get(f"/api/runs/{RUN}/bundle").json()
    p = store / "bundles" / RUN / "bundle.json"
    p.chmod(0o644)
    p.write_text('{"claims": [{"claim_id": "FORGED"}], "facts": {}}')
    assert client.get(f"/api/runs/{RUN}/bundle").json() == baseline
    assert client.get(f"/api/runs/{RUN}/export").json() == baseline


def test_corrupt_sealed_run_fails_closed(client, store):
    p = store / "runs" / RUN / "manifest.json"
    p.chmod(0o644)
    p.write_bytes(p.read_bytes() + b" ")
    assert client.get(f"/api/runs/{RUN}/verify").json()["ok"] is False
    for endpoint in ("bundle", "clay-searches", "events", "export"):
        assert client.get(f"/api/runs/{RUN}/{endpoint}").status_code == 409


def test_unconfigured_capabilities_and_no_private_paths(client):
    caps = client.get("/api/capabilities").json()
    assert caps["schema_version"] == "treehouse.ui/1" and caps["execution"] == "offline"
    assert caps["limits"]["max_parallel_runs"] == 1
    for c in caps["capabilities"]:
        assert c["status"] in {"available", "offline_demo", "not_configured", "unsupported"} and c["reason"]
    for fragment in ("bedrock", "strands", "agentcore", "simulation"):
        matches = [c for c in caps["capabilities"] if fragment in (c["id"] + c["label"]).lower()]
        assert matches and all(c["status"] in {"not_configured", "unsupported"} for c in matches)
    for path in (
        "/api/keys",
        "/api/blobs",
        "/api/runs/synth-good/raw",
        "/api/runs/synth-good/pixels",
        "/api/runs/synth-good/messages",
    ):
        assert client.get(path).status_code in (400, 404)
    tasks = json.dumps(client.get("/api/tasks").json()).lower()
    for sensitive in ("cassette_path", "script_path", "answer_key", "forbidden_sources", "grader_plan"):
        assert sensitive not in tasks


def test_invalid_requests_and_symlink_rejected(client, store, tmp_path):
    assert client.get("/api/runs/" + "x" * 129).status_code == 400
    assert client.get("/api/runs/bad..id").status_code == 400
    assert client.get("/api/runs/missing").status_code == 404
    assert client.get("/api/runs", headers={"Origin": "https://evil.example"}).status_code in (400, 403)
    assert client.post("/api/runs", json={"preset_id": "not-a-preset"}).status_code == 422
    assert client.post(
        "/api/runs", content=b"{}", headers={"Origin": "", "Content-Type": "application/json"}
    ).status_code in (400, 403)
    assert client.post("/api/runs", content=b"{}", headers={"Content-Type": "text/plain"}).status_code in (
        400,
        415,
    )
    preset = client.get("/api/tasks").json()["tasks"][0]["preset_id"]
    assert client.post("/api/runs", json={"preset_id": preset, "mode": "live"}).status_code in (400, 422)
    assert (
        client.post(
            "/api/runs", content=b"x" * 1_000_000, headers={"Content-Type": "application/json"}
        ).status_code
        == 413
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    (store / "runs" / "linked").symlink_to(outside, target_is_directory=True)
    assert client.get("/api/runs/linked/bundle").status_code in (400, 404, 409)


def test_pinned_replay_produces_verified_bundle(client):
    preset = client.get("/api/tasks").json()["tasks"][0]["preset_id"]
    response = client.post("/api/runs", json={"preset_id": preset})
    assert response.status_code == 202
    rid = response.json()["run_id"]
    assert response.json()["status"] in ("queued", "running")
    second = client.post("/api/runs", json={"preset_id": preset})
    # Fast jobs may complete between requests; otherwise a second concurrent job must be refused.
    assert second.status_code in (202, 409)
    if second.status_code == 202:
        assert second.json()["run_id"] != rid
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        result = client.get(f"/api/runs/{rid}/bundle")
        if result.status_code == 200:
            break
        assert result.status_code == 409
        time.sleep(0.2)
    assert result.status_code == 200
    assert result.json()["manifest_summary"]["mode"] == "replay"
    assert client.get(f"/api/runs/{rid}/verify").json()["ok"] is True
