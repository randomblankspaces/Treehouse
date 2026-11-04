"""Read-only HTTP acceptance, using a real sealed investigation and separate exports."""
import hashlib
import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient
from test_investigation_acceptance import claim, run

from treehouse.service import demo
from treehouse.ui import create_app

ORIGIN = "http://127.0.0.1:8765"


def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file() and not p.is_symlink()}


def test_investigation_endpoints_return_verified_sealed_data_without_writes(context, tmp_path):
    store, _, _, _, evaluate, export = context
    run(context, claim("one", .002, .002))
    direct = evaluate(store, "case")
    paths = export(store, "case", tmp_path / "expected")
    expected = json.loads(Path(paths["geojson"]).read_text())
    root = store.root
    before = snapshot(root)
    with TestClient(create_app(root, origin=ORIGIN, frontend_dist=tmp_path), base_url=ORIGIN,
                    headers={"Origin": ORIGIN}) as c:
        report = c.get("/api/runs/case/investigation")
        geo = c.get("/api/runs/case/database")
        assert report.status_code == geo.status_code == 200
        assert report.json() == direct
        assert geo.json() == expected
        text = report.text + geo.text
        assert "keys/synth/" not in text and '"bytes_"' not in text
    assert snapshot(root) == before


def test_tampered_seal_fails_both_read_endpoints(context, tmp_path):
    store, _, _, _, _, _ = context
    run(context, claim("one", .002, .002))
    path = store.run_dir("case") / "trials/t-0.claims.jsonl"
    path.chmod(0o644)  # Tampering requires write permission on sealed 0444 files.
    path.write_bytes(path.read_bytes() + b" ")
    with TestClient(create_app(store.root, origin=ORIGIN, frontend_dist=tmp_path), base_url=ORIGIN) as c:
        assert c.get("/api/runs/case/investigation").status_code == 409
        assert c.get("/api/runs/case/database").status_code == 409


def test_legacy_replay_reports_unavailable_reasoning_without_fabrication(tmp_path):
    root = tmp_path / "demo"
    demo(root, echo=lambda *_: None)
    with TestClient(create_app(root / "store", origin=ORIGIN, frontend_dist=tmp_path), base_url=ORIGIN) as c:
        response = c.get("/api/runs/synth-good/investigation")
        assert response.status_code == 200
        report = response.json()
        assert report["decisions"] == [] and report["pathways"] == []
        assert report["process"]["limitations"]
