"""Registry-selected OSM pools retain provenance and never silently fabricate a live reference."""
import hashlib
import json
import runpy
from pathlib import Path

import pytest
import yaml

from treehouse.cards import load_card
from treehouse.checks.protocol_grader import PredictedClaim, grade
from treehouse.tools.retrieval import retrieval_for_card

ROOT = Path(__file__).resolve().parents[2]


def fetcher():
    return runpy.run_path(str(ROOT / "scripts/fetch_osm_pool.py"))


def test_all_classes_have_osm_selectors():
    classes = yaml.safe_load((ROOT / "config/asset-classes.yaml").read_text())["classes"]
    assert len(classes) == 6
    assert all(c.get("osm", {}).get("tags") for c in classes.values())


@pytest.mark.parametrize("cls,tags", [
    ("warehouse", {"building": "warehouse"}),
    ("oil_fuel_tank", {"man_made": "storage_tank", "content": "diesel"}),
    ("bridge", {"bridge": "yes"}),
    ("substation", {"power": "substation"}),
    ("wind_turbine", {"power": "generator", "generator:source": "wind"}),
    ("ground_solar", {"power": "generator", "generator:source": "solar", "location": "ground"}),
    ("ground_solar", {"power": "plant", "plant:source": "solar", "location": "ground"}),
])
def test_pinned_overpass_extract_filters_and_pins_pool(tmp_path, cls, tags):
    payload = {"osm3s": {"timestamp_osm_base": "2026-11-05T04:00:00Z"}, "elements": [
        {"type": "way", "id": 1, "center": {"lon": 1.25, "lat": 2.25}, "tags": tags},
        {"type": "node", "id": 2, "lon": 10, "lat": 20, "tags": tags},
        {"type": "way", "id": 3, "center": {"lon": 1.25, "lat": 2.25},
         "tags": {"man_made": "storage_tank", "content": "water"}},
    ]}
    source = tmp_path / "extract.json"
    source.write_text(json.dumps(payload))
    output = tmp_path / "pool.geojson"
    assert fetcher()["main"](["--class", cls, "--bbox", "1", "2", "2", "3", "--extract", str(source), "--out", str(output)]) == 0
    pool = json.loads(output.read_text())
    assert len(pool["features"]) == 1
    assert pool["features"][0]["properties"]["cls"] == cls
    assert pool["features"][0]["geometry"]["coordinates"] == [1.25, 2.25]
    provenance = json.loads(output.with_suffix(".provenance.json").read_text())
    assert provenance["license"] == "ODbL-1.0"
    assert provenance["snapshot_date"] == "2026-11-05"
    assert provenance["reference_quality"] == "incomplete"
    assert not provenance["synthetic_fixture"]
    assert provenance["geojson_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert provenance["extract_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


@pytest.mark.parametrize("name,cls,bbox", [
    ("nagoya-warehouses-real", "warehouse", [136.82, 35.05, 136.92, 35.12]),
    ("chattogram-fuel-tanks", "oil_fuel_tank", [91.78, 22.28, 91.88, 22.37]),
])
def test_offline_geojson_fixture_stays_synthetic(tmp_path, name, cls, bbox):
    output = tmp_path / "pool.geojson"
    args = ["--class", cls, "--bbox", *map(str, bbox), "--extract", str(ROOT / "fixtures/osm" / f"{name}.geojson"), "--out", str(output)]
    assert fetcher()["main"](args) == 0
    assert json.loads(output.read_text())["features"]
    assert json.loads(output.with_suffix(".provenance.json").read_text())["synthetic_fixture"] is True


@pytest.mark.parametrize("name", ["nagoya-warehouses-real", "chattogram-fuel-tanks"])
def test_fetched_pool_grades_new_card_without_training_leakage(tmp_path, monkeypatch, name):
    card = load_card(ROOT / "tasks" / f"t1-{name}.yaml")
    analyzer = runpy.run_path(str(ROOT / "scripts/analyze_experiments.py"))
    monkeypatch.setitem(analyzer["_reference"].__globals__, "repo_root", lambda: tmp_path)
    bbox = analyzer["_aoi_bbox"](card)
    output = tmp_path / card.steps[0].keying.key_path
    assert fetcher()["main"]([
        "--class", next(iter(card.classes)), "--bbox", *map(str, bbox),
        "--extract", str(ROOT / "fixtures/osm" / f"{name}.geojson"), "--out", str(output),
    ]) == 0

    assets, completeness, keyed, note = analyzer["_reference"](card)
    assert completeness == "incomplete" and keyed is True
    assert {asset.id for asset in assets} == {f["id"] for f in json.loads(output.read_text())["features"]}
    assert "held-out split" in note
    assert analyzer["_examples"](card) == []
    assert retrieval_for_card(card).get_examples()["examples"] == []
    report = grade([PredictedClaim(assets[0].lon, assets[0].lat, 0.9)], assets, bbox,
                   completeness=completeness, minutes_per_cell=card.minutes_per_cell)
    assert report.precision == 1.0 and report.precision_is_lower_bound
    assert report.recall is None and report.null_reasons["recall"] == "incomplete_reference"


def test_fetch_failure_does_not_create_synthetic_fallback(tmp_path, monkeypatch):
    module = fetcher()

    def unavailable(*args, **kwargs):
        raise OSError("offline")

    monkeypatch.setattr(module["urllib"].request, "urlopen", unavailable)
    output = tmp_path / "pool.geojson"
    with pytest.raises(RuntimeError, match="extract"):
        module["main"](["--class", "warehouse", "--bbox", "1", "2", "2", "3", "--out", str(output)])
    assert not output.exists()


def test_invalid_bbox_is_rejected(tmp_path):
    with pytest.raises((ValueError, SystemExit)):
        fetcher()["main"](["--class", "warehouse", "--bbox", "2", "3", "1", "2", "--out", str(tmp_path / "pool.geojson")])


def test_extract_without_snapshot_date_is_rejected(tmp_path):
    source = tmp_path / "unknown-date.json"
    source.write_text('{"elements": []}')
    with pytest.raises(ValueError, match="snapshot"):
        fetcher()["main"](["--class", "warehouse", "--bbox", "1", "2", "2", "3", "--extract", str(source), "--out", str(tmp_path / "pool.geojson")])
