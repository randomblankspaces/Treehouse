"""Fetch a checksum-pinned GRW v1.0 asset and extract an AOI via its SQLite rtree.

No imagery is fetched. The global GeoPackage is temporary; only the AOI GeoJSON persists.
Example: python scripts/fetch_grw.py --class wind_turbine --bbox 140.64 35.72 140.75 35.81 --out subset.geojson
Use --gpkg for an already downloaded release asset (the same checksum is required).
Pins: https://api.github.com/repos/microsoft/global-renewables-watch/releases/tags/v1.0
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sqlite3
import struct
import tempfile
from pathlib import Path
from urllib.request import urlopen

RELEASE = "https://github.com/microsoft/global-renewables-watch/releases/download/v1.0/"
ASSETS = {
    "wind_turbine": {"name": "wind_all_2024q2_v1.gpkg",
                     "sha256": "c859544f9e04b064880d30d7288aacf9940dc361d576c3ef73565d2f1bb0398a"},
    "ground_solar": {"name": "solar_all_2024q2_v1.gpkg",
                     "sha256": "9f27c76313fcd78418a7277e4f7526c536887965fd3ef80160ed1d1ceedf947b"},
}


def _project(x, y, srs, *, inverse=False):
    if srs == 4326:
        return [x, y]
    if srs != 3857:
        raise ValueError(f"unsupported GRW CRS EPSG:{srs}; expected 4326 or 3857")
    if inverse:
        return [math.degrees(x / 6378137), math.degrees(2 * math.atan(math.exp(y / 6378137)) - math.pi / 2)]
    if abs(y) >= 90:
        raise ValueError("bbox cannot include a pole in EPSG:3857")
    return [math.radians(x) * 6378137, math.log(math.tan(math.pi / 4 + math.radians(y) / 2)) * 6378137]


def _geometry(blob, srs):
    if blob[:2] != b"GP" or blob[2] != 0 or blob[3] & 0b110000:
        raise ValueError("unsupported or empty GeoPackage geometry")
    envelope = (blob[3] >> 1) & 7
    envelope_size = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}.get(envelope)
    if envelope_size is None:
        raise ValueError("invalid GeoPackage envelope")
    offset = 8 + envelope_size

    def read_geometry():
        nonlocal offset
        endian = "<" if blob[offset] == 1 else ">"
        offset += 1

        def read(fmt):
            nonlocal offset
            values = struct.unpack_from(endian + fmt, blob, offset)
            offset += struct.calcsize(endian + fmt)
            return values

        kind = read("I")[0]
        if kind == 1:
            return {"type": "Point", "coordinates": _project(*read("dd"), srs, inverse=True)}
        if kind == 3:
            rings = [[_project(*read("dd"), srs, inverse=True) for _ in range(read("I")[0])]
                     for _ in range(read("I")[0])]
            return {"type": "Polygon", "coordinates": rings}
        if kind == 6:
            polygons = [read_geometry() for _ in range(read("I")[0])]
            if any(p["type"] != "Polygon" for p in polygons):
                raise ValueError("invalid MultiPolygon member")
            return {"type": "MultiPolygon", "coordinates": [p["coordinates"] for p in polygons]}
        raise ValueError(f"unsupported GRW WKB geometry type {kind}")

    return read_geometry()


def _validate_bbox(bbox):
    if (len(bbox) != 4 or not all(math.isfinite(v) for v in bbox)
            or not -180 <= bbox[0] < bbox[2] <= 180 or not -90 <= bbox[1] < bbox[3] <= 90):
        raise ValueError("bbox must be finite west south east north within lon/lat bounds")


def extract_aoi(path: Path, bbox: tuple[float, float, float, float]) -> list[dict]:
    _validate_bbox(bbox)

    def quote(identifier):
        return '"' + identifier.replace('"', '""') + '"'

    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        layers = db.execute("SELECT table_name, column_name, srs_id FROM gpkg_geometry_columns").fetchall()
        if len(layers) != 1:
            raise ValueError("expected one GRW geometry layer")
        table, geometry, srs = layers[0]
        west, south = _project(bbox[0], bbox[1], srs)
        east, north = _project(bbox[2], bbox[3], srs)
        primary = [row[1] for row in db.execute(f"PRAGMA table_info({quote(table)})") if row[5]]
        if len(primary) != 1:
            raise ValueError("expected one GRW feature primary key")
        rtree = quote(f"rtree_{table}_{geometry}")
        rows = db.execute(
            f"SELECT f.{quote(primary[0])}, f.{quote(geometry)} FROM {rtree} r "
            f"JOIN {quote(table)} f ON f.{quote(primary[0])} = r.id "
            "WHERE r.minx <= ? AND r.maxx >= ? AND r.miny <= ? AND r.maxy >= ? ORDER BY r.id",
            (east, west, north, south))
        return [{"type": "Feature", "id": f"grw:{fid}", "geometry": _geometry(blob, srs), "properties": {}}
                for fid, blob in rows]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--class", dest="asset_class", choices=ASSETS, required=True)
    parser.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--gpkg", type=Path, help="local copy of the checksum-pinned release asset")
    args = parser.parse_args(argv)
    _validate_bbox(args.bbox)
    if args.out.exists():
        raise FileExistsError(args.out)
    asset = ASSETS[args.asset_class]
    url = RELEASE + asset["name"]
    with tempfile.TemporaryDirectory(prefix="treehouse-grw-") as temporary:
        path = args.gpkg or Path(temporary) / asset["name"]
        if args.gpkg is None:
            with urlopen(url, timeout=60) as response, path.open("wb") as target:  # noqa: S310 (pinned HTTPS release)
                shutil.copyfileobj(response, target)
        with path.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        if digest != asset["sha256"]:
            raise ValueError(f"GRW SHA-256 mismatch for {asset['name']}")
        features = extract_aoi(path, tuple(args.bbox))
    for feature in features:
        feature["properties"]["cls"] = args.asset_class
    result = {"type": "FeatureCollection", "bbox": args.bbox, "features": features,
              "source": {"dataset": "Global Renewables Watch", "version": "v1.0", "url": url,
                         "sha256": digest, "license": "MIT", "attribution": "Microsoft Global Renewables Watch",
                         "license_url": "https://github.com/microsoft/global-renewables-watch/blob/v1.0/LICENSE"},
              "limitations": ["Model-derived detections, not a complete ground-truth census.",
                              "AOI selection uses intersecting feature envelopes from the release rtree."]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x") as target:
        target.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"features": len(features), "out": str(args.out), "sha256": digest}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
