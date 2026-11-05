"""Reference-key builders (task 1): PLATEAU warehouses and the OSM pool build deterministic, well-formed
keys with provenance, a licence and a sha256; grading references stay under keys/ and off the agent."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(script: str):
    path = ROOT / "scripts" / script
    spec = importlib.util.spec_from_file_location(script.replace(".py", ""), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _geojson_ok(fc: dict, cls: str = "warehouse") -> None:
    assert fc["type"] == "FeatureCollection" and fc["features"]
    for feat in fc["features"]:
        assert feat["type"] == "Feature"
        assert feat["geometry"]["type"] == "Point"
        lon, lat = feat["geometry"]["coordinates"]
        assert -180 <= lon <= 180 and -90 <= lat <= 90
        assert feat["properties"]["cls"] == cls


def test_committed_plateau_keys_exist_and_well_formed():
    for city in ("nagoya", "gifu"):
        fc = json.loads((ROOT / "keys" / "plateau" / f"{city}-warehouses.geojson").read_text())
        _geojson_ok(fc)
        prov = json.loads((ROOT / "keys" / "plateau" / f"{city}-provenance.json").read_text())
        assert prov["license"] == "CC-BY-4.0" and prov["snapshot_date"]
        assert prov["class_definition"].startswith("PLATEAU") and "1,600" in prov["class_definition"]


def test_committed_osm_pool_is_incomplete_precision_only():
    fc = json.loads((ROOT / "keys" / "osm" / "chattogram-warehouses.geojson").read_text())
    _geojson_ok(fc)
    prov = json.loads((ROOT / "keys" / "osm" / "chattogram-provenance.json").read_text())
    assert prov["license"] == "ODbL-1.0"
    assert prov["reference_quality"] == "incomplete"
    caveat = prov["completeness_caveat"].lower()
    assert "recall" in caveat and ("not report recall" in caveat or "never recall" in caveat)


def test_nagoya_split_train_and_heldout_disjoint():
    split = json.loads((ROOT / "keys" / "plateau" / "nagoya-split.json").read_text())
    train, heldout = set(split["train"]), set(split["heldout"])
    assert train and heldout and train.isdisjoint(heldout)
    fc = json.loads((ROOT / "keys" / "plateau" / "nagoya-warehouses.geojson").read_text())
    ids = {f["id"] for f in fc["features"]}
    assert train | heldout == ids  # the split partitions the reference


def test_gifu_has_no_train_examples():
    """Transfer target: no new labels (DM2)."""
    split = json.loads((ROOT / "keys" / "plateau" / "gifu-split.json").read_text())
    assert split["train"] == [] and split["heldout"]


def test_plateau_builder_is_deterministic(tmp_path, monkeypatch):
    mod = _load("fetch_plateau_warehouses.py")
    a = mod._fixture_warehouses("nagoya")
    b = mod._fixture_warehouses("nagoya")
    assert a == b  # seeded by municipality code
    assert all(f["footprint_area_m2"] >= mod.MIN_AREA_M2 for f in a)  # every fixture >= 1,600 m2


def test_legacy_osm_script_accepts_registry_fetcher_arguments(tmp_path):
    mod = _load("fetch_osm_warehouses.py")
    output = tmp_path / "pool.geojson"
    assert mod.main(["--class", "oil_fuel_tank", "--bbox", "91.78", "22.28", "91.88", "22.37",
                     "--extract", str(ROOT / "fixtures/osm/chattogram-fuel-tanks.geojson"),
                     "--out", str(output)]) == 0
    _geojson_ok(json.loads(output.read_text()), "oil_fuel_tank")


def test_sha256sums_cover_the_keys():
    for sub in ("plateau", "osm"):
        sums = json.loads((ROOT / "keys" / sub / "SHA256SUMS.json").read_text())
        for rel, want in sums.items():
            got = hashlib.sha256((ROOT / "keys" / sub / rel).read_bytes()).hexdigest()
            assert got == want, rel
