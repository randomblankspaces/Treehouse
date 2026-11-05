"""Tiny synthetic GeoPackages exercise the AOI reader; no real GRW labels or network."""
import hashlib
import json
import math
import runpy
import sqlite3
import struct

import pytest


def gpkg(tmp_path, srs=4326, polygon=False):
    path = tmp_path / "synthetic.gpkg"
    points = [(140.7, 35.8), (140.8, 35.9), (135, 34)]
    if srs == 3857:
        points = [(math.radians(x) * 6378137, math.log(math.tan(math.pi / 4 + math.radians(y) / 2)) * 6378137)
                  for x, y in points]
    with sqlite3.connect(path) as db:
        db.executescript('''
            CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, srs_id INTEGER);
            CREATE TABLE assets (fid INTEGER PRIMARY KEY, geom BLOB);
            CREATE VIRTUAL TABLE rtree_assets_geom USING rtree(id, minx, maxx, miny, maxy);
        ''')
        db.execute("INSERT INTO gpkg_geometry_columns VALUES ('assets', 'geom', ?)", (srs,))
        for fid, (x, y) in enumerate(points, 1):
            if polygon:
                ring = [(x, y), (x + .001, y), (x + .001, y + .001), (x, y)]
                wkb = struct.pack("<BIII", 1, 3, 1, len(ring)) + b"".join(struct.pack("<dd", *p) for p in ring)
            else:
                wkb = struct.pack("<BIdd", 1, 1, x, y)
            header = b"GP" + bytes([0, 3]) + struct.pack("<i4d", srs, x, x, y, y)
            db.execute("INSERT INTO assets VALUES (?, ?)", (fid, header + wkb))
            db.execute("INSERT INTO rtree_assets_geom VALUES (?, ?, ?, ?, ?)", (fid, x, x, y, y))
    return path


@pytest.mark.parametrize("srs,polygon", [(4326, False), (3857, False), (4326, True)])
def test_extract_uses_rtree_and_converts_geometry(tmp_path, srs, polygon):
    module = runpy.run_path("scripts/fetch_grw.py")
    features = module["extract_aoi"](gpkg(tmp_path, srs, polygon), (140.6, 35.7, 140.9, 36.0))
    assert len(features) == 2 and [f["id"] for f in features] == ["grw:1", "grw:2"]
    geom = features[0]["geometry"]
    point = geom["coordinates"][0][0] if polygon else geom["coordinates"]
    assert point == pytest.approx([140.7, 35.8])
    assert geom["type"] == ("Polygon" if polygon else "Point")


def test_cli_checks_digest_before_reading_and_pins_subset_provenance(tmp_path):
    module = runpy.run_path("scripts/fetch_grw.py")
    path = gpkg(tmp_path)
    out = tmp_path / "subset.geojson"
    argv = ["--class", "wind_turbine", "--bbox", "140.6", "35.7", "140.9", "36",
            "--out", str(out), "--gpkg", str(path)]
    with pytest.raises(ValueError, match="SHA-256"):
        module["main"](argv)
    assert not out.exists()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    module["ASSETS"]["wind_turbine"]["sha256"] = digest
    assert module["main"](argv) == 0
    result = json.loads(out.read_text())
    assert result["source"]["sha256"] == digest and result["source"]["license"] == "MIT"
    assert "/v1.0/" in result["source"]["url"]
    assert len(result["features"]) == 2
    assert all(f["properties"]["cls"] == "wind_turbine" for f in result["features"])
    with pytest.raises(FileExistsError):
        module["main"](argv)


def test_reader_refuses_missing_rtree_or_unsupported_crs(tmp_path):
    module = runpy.run_path("scripts/fetch_grw.py")
    path = gpkg(tmp_path)
    with sqlite3.connect(path) as db:
        db.execute("DROP TABLE rtree_assets_geom")
    with pytest.raises((ValueError, sqlite3.OperationalError), match="rtree"):
        module["extract_aoi"](path, (140.6, 35.7, 140.9, 36))


@pytest.mark.parametrize("bbox", [(0, 0, 0, 1), (5, 0, 4, 1), (0, -91, 1, 1), (0, 0, float("nan"), 1)])
def test_reader_rejects_invalid_bbox(tmp_path, bbox):
    module = runpy.run_path("scripts/fetch_grw.py")
    with pytest.raises(ValueError, match="bbox"):
        module["extract_aoi"](gpkg(tmp_path), bbox)


def test_cli_rejects_invalid_bbox_before_network(tmp_path, monkeypatch):
    module = runpy.run_path("scripts/fetch_grw.py")

    def forbidden_download(*args, **kwargs):
        pytest.fail("invalid bbox reached download")

    monkeypatch.setitem(module["main"].__globals__, "urlopen", forbidden_download)
    with pytest.raises(ValueError, match="bbox"):
        module["main"](["--class", "ground_solar", "--bbox", "0", "0", "0", "1",
                        "--out", str(tmp_path / "invalid.geojson")])
