"""Fetch an incomplete OSM candidate pool selected by the asset-class registry.

--bbox is west south east north. --extract reads pinned Overpass JSON or GeoJSON
without network access. Pinned extracts need a snapshot_date (or --snapshot-date).
Outputs are point GeoJSON and a .provenance.json sidecar containing SHA256 hashes,
ODbL attribution and snapshot date. Never silently substitute synthetic geometry.
An adjacent <stem>-split.json keeps every candidate grading-only, with no training examples.
Write live grading pools under keys/osm/; keep them off the agent's allowlist.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)


def _values(value):
    return value if isinstance(value, list) else [value]


def _overpass_query(selectors, bbox):
    west, south, east, north = bbox
    clauses = []
    for tags in selectors:
        filters = "".join(
            f"[{json.dumps(key)}~{json.dumps('^(' + '|'.join(re.escape(v) for v in _values(value)) + ')$')}]"
            for key, value in tags.items()
        )
        clauses.append(f"nwr{filters}({south},{west},{north},{east});")
    return "[out:json][timeout:25];(" + "".join(clauses) + ");out center;"


def _fetch(query):
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            request = urllib.request.Request(
                endpoint, data=urllib.parse.urlencode({"data": query}).encode(),
                headers={"User-Agent": "treehouse-reference-fetch/1.0 (ADB/Clay eval)"},
            )
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 (fixed https hosts)
                payload = json.load(response)
            if "elements" in payload and not payload.get("remark"):
                return payload, endpoint
        except (urllib.error.URLError, OSError, ValueError):
            continue
    raise RuntimeError("Overpass unavailable or incomplete; retry with --extract <pinned file>")


def _center(geometry):
    if geometry["type"] == "Point":
        return geometry["coordinates"][:2]

    def points(coords):
        if isinstance(coords[0], (int, float)):
            return [coords]
        return [point for child in coords for point in points(child)]

    coords = points(geometry["coordinates"])
    return [(min(p[i] for p in coords) + max(p[i] for p in coords)) / 2 for i in (0, 1)]


def _features(payload, selectors, bbox, class_id):
    west, south, east, north = bbox
    candidates = []
    if payload.get("type") == "FeatureCollection":
        for feature in payload["features"]:
            props = feature.get("properties", {})
            candidates.append((feature.get("id", props.get("@id")), props.get("tags", props),
                               _center(feature["geometry"])))
    else:
        for element in payload["elements"]:
            center = element.get("center", element)
            if "lon" in center and "lat" in center:
                candidates.append((f"osm:{element['type']}/{element['id']}", element.get("tags", {}),
                                   [center["lon"], center["lat"]]))
    features = {}
    for identifier, tags, coordinates in candidates:
        if not any(all(tags.get(k) in _values(v) for k, v in clause.items()) for clause in selectors):
            continue
        lon, lat = map(float, coordinates)
        if not (math.isfinite(lon) and math.isfinite(lat)):
            raise ValueError("OSM coordinates must be finite")
        if not (west <= lon <= east and south <= lat <= north):
            continue
        if identifier is None:
            raise ValueError("OSM candidates need a stable feature id")
        features[str(identifier)] = {
            "type": "Feature", "id": str(identifier),
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"cls": class_id, "tags": tags},
        }
    return [features[key] for key in sorted(features)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    classes = yaml.safe_load((ROOT / "config/asset-classes.yaml").read_text())["classes"]
    parser.add_argument("--class", dest="class_id", required=True, choices=sorted(classes))
    parser.add_argument("--bbox", type=float, nargs=4, required=True, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--extract", type=Path)
    parser.add_argument("--snapshot-date", type=date.fromisoformat)
    args = parser.parse_args(argv)
    west, south, east, north = args.bbox
    if not all(map(math.isfinite, args.bbox)) or not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        parser.error("bbox must be finite west south east north in lon/lat order")
    selectors = classes[args.class_id]["osm"]["tags"]
    query = _overpass_query(selectors, args.bbox)
    if args.extract:
        raw = args.extract.read_bytes()
        payload, source = json.loads(raw), str(args.extract)
    else:
        payload, source = _fetch(query)
    if payload.get("remark"):
        raise ValueError("Overpass extract reports an error or incomplete response")
    snapshot = args.snapshot_date or payload.get("snapshot_date") or payload.get("osm3s", {}).get("timestamp_osm_base")
    if not snapshot:
        raise ValueError("extract has no snapshot date; provide --snapshot-date YYYY-MM-DD")
    snapshot = date.fromisoformat(str(snapshot)[:10]).isoformat()
    features = _features(payload, selectors, args.bbox, args.class_id)
    synthetic = payload.get("synthetic_fixture", False)
    pool = {"type": "FeatureCollection", "snapshot_date": snapshot,
            "synthetic_fixture": synthetic, "features": features}
    content = json.dumps(pool, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    provenance = {
        "dataset": "OpenStreetMap candidate pool", "class": args.class_id,
        "aoi_bbox_lonlat": args.bbox, "osm_selectors": selectors, "query": query,
        "license": "ODbL-1.0", "attribution": "© OpenStreetMap contributors, ODbL 1.0",
        "license_url": "https://opendatacommons.org/licenses/odbl/1-0/",
        "snapshot_date": snapshot, "retrieved_at": datetime.now(UTC).isoformat(),
        "source": source, "source_mode": "extract" if args.extract else "overpass",
        "synthetic_fixture": synthetic, "reference_quality": "incomplete",
        "completeness_caveat": "Precision within this pool only; never recall. Centers approximate OSM geometries.",
        "feature_count": len(features), "geojson_sha256": hashlib.sha256(content.encode()).hexdigest(),
    }
    if args.extract:
        provenance["extract_sha256"] = hashlib.sha256(raw).hexdigest()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(content, encoding="utf-8")
    args.out.with_suffix(".provenance.json").write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    split = {"train": [], "heldout": [feature["id"] for feature in features]}
    args.out.with_name(args.out.stem + "-split.json").write_text(json.dumps(split, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(provenance, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
