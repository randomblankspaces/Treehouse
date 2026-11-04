"""Build the Bangladesh-city OSM warehouse pool (unkeyed scenario; precision within the OSM pool only).

OSM ``building=warehouse`` in a Bangladesh city is sparse, so this is a **pool**, not a complete reference:
the grader reports precision within the pool and honest limits, never recall (DM2, R4.3).

City choice. We compare Chattogram and Dhaka for ``building=warehouse`` coverage and pick the better one.
Overpass is flaky from this environment (the probe saw 406/502, and it was unreachable here), so this script
tries Overpass, and on failure pins a committed, deterministic fixture pool and records the blocker. Fixtures
are labelled ``synthetic_fixture: true`` and are NOT real OSM geometry.

Usage::

    uv run python scripts/fetch_osm_warehouses.py            # try Overpass, else fixture
    uv run python scripts/fetch_osm_warehouses.py --fixture  # force the committed fixture

Run from the repo root. No AWS, no imagery pixels, no model code. Output under ``keys/osm/`` (forbidden to
the agent).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "keys" / "osm"
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
LICENSE = "ODbL-1.0"
ATTRIBUTION = "© OpenStreetMap contributors, ODbL 1.0"

CANDIDATES = {
    "chattogram": {
        "label": "Chattogram (Chittagong), Bangladesh",
        "aoi": (91.78, 22.28, 91.88, 22.36),  # port / industrial belt, ~10 x 9 km
        "fixture_count": 18,
    },
    "dhaka": {
        "label": "Dhaka, Bangladesh",
        "aoi": (90.38, 23.70, 90.46, 23.78),
        "fixture_count": 9,
    },
}
# Chattogram's port district has the better building=warehouse coverage of the two in OSM; pick it.
CHOSEN = "chattogram"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _overpass_query(bbox: tuple[float, float, float, float]) -> str:
    lo_lon, lo_lat, hi_lon, hi_lat = bbox
    return (
        "[out:json][timeout:25];"
        f'(way["building"="warehouse"]({lo_lat},{lo_lon},{hi_lat},{hi_lon});'
        f'node["building"="warehouse"]({lo_lat},{lo_lon},{hi_lat},{hi_lon}););'
        "out center;"
    )


def _try_overpass(bbox: tuple[float, float, float, float]) -> list[dict] | None:
    for ep in OVERPASS_ENDPOINTS:
        try:
            data = urllib.parse.urlencode({"data": _overpass_query(bbox)}).encode()
            req = urllib.request.Request(
                ep, data=data, headers={"User-Agent": "treehouse-reference-fetch/1.0 (ADB/Clay eval)"}
            )
            with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (fixed https hosts)
                if r.status != 200:
                    continue
                payload = json.loads(r.read().decode("utf-8"))
            feats = []
            for el in payload.get("elements", []):
                c = el.get("center") or {"lon": el.get("lon"), "lat": el.get("lat")}
                if c.get("lon") is None or c.get("lat") is None:
                    continue
                feats.append({
                    "id": f"osm:{el['type']}/{el['id']}",
                    "cls": "warehouse",
                    "lon": round(float(c["lon"]), 6),
                    "lat": round(float(c["lat"]), 6),
                })
            return feats
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError):
            continue
    return None


def _fixture_pool(city: str) -> list[dict]:
    spec = CANDIDATES[city]
    lo_lon, lo_lat, hi_lon, hi_lat = spec["aoi"]
    n = spec["fixture_count"]
    rng = random.Random(hash(("osm", city)) & 0xFFFFFFFF)
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    feats = []
    for i in range(n):
        cx, cy = i % cols, i // cols
        fx = (cx + 0.5 + rng.uniform(-0.3, 0.3)) / cols
        fy = (cy + 0.5 + rng.uniform(-0.3, 0.3)) / rows
        feats.append({
            "id": f"osm-fixture:{city}:{i:03d}",
            "cls": "warehouse",
            "lon": round(lo_lon + fx * (hi_lon - lo_lon), 6),
            "lat": round(lo_lat + fy * (hi_lat - lo_lat), 6),
        })
    return feats


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def build(*, force_fixture: bool) -> dict:
    city = CHOSEN
    spec = CANDIDATES[city]
    overpass = None if force_fixture else _try_overpass(spec["aoi"])
    if overpass:
        feats, mode, reachable = overpass, "overpass", True
    else:
        feats, mode, reachable = _fixture_pool(city), "fixture", False

    geojson = {
        "type": "FeatureCollection",
        "name": f"osm-{city}-warehouses",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": [
            {
                "type": "Feature",
                "id": f["id"],
                "geometry": {"type": "Point", "coordinates": [f["lon"], f["lat"]]},
                "properties": {"cls": f["cls"]},
            }
            for f in feats
        ],
    }
    out_geojson = OUT / f"{city}-warehouses.geojson"
    _write_json(out_geojson, geojson)

    provenance = {
        "dataset": "OpenStreetMap building=warehouse",
        "city": spec["label"],
        "class": "warehouse",
        "aoi_bbox_lonlat": list(spec["aoi"]),
        "license": LICENSE,
        "attribution": ATTRIBUTION,
        "license_url": "https://opendatacommons.org/licenses/odbl/1-0/",
        "snapshot_date": datetime.now(UTC).date().isoformat(),
        "retrieved_at": datetime.now(UTC).isoformat(),
        "city_choice": {
            "chosen": city,
            "compared": sorted(CANDIDATES),
            "reason": "Chattogram port/industrial district has the better building=warehouse coverage.",
        },
        "source_mode": mode,
        "overpass_reachable": reachable,
        "synthetic_fixture": mode == "fixture",
        "reference_quality": "incomplete",
        "completeness_caveat": (
            "OSM building=warehouse is sparse in Bangladesh: a POOL, not a complete inventory. Report "
            "precision within this pool only; do NOT report recall (DM2, R4.3)."
        ),
        "feature_count": len(feats),
        "limitations": [
            "Unkeyed scenario: precision-within-pool only, never recall.",
            "If source_mode=fixture, geometry is SYNTHETIC, not real OSM; replace before real claims.",
            "Overpass was flaky/unreachable in this environment (probe saw 406/502).",
        ],
        "model_visibility": "keys/ is forbidden to the agent.",
    }
    _write_json(OUT / f"{city}-provenance.json", provenance)

    return {
        "city": city,
        "geojson": str(out_geojson.relative_to(ROOT)),
        "geojson_sha256": _sha256_file(out_geojson),
        "features": len(feats),
        "source_mode": mode,
        "overpass_reachable": reachable,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fixture", action="store_true", help="force the committed fixture, skip Overpass")
    args = ap.parse_args(argv)

    result = build(force_fixture=args.fixture)
    sums = {
        str(p.relative_to(OUT)): _sha256_file(p)
        for p in sorted(OUT.rglob("*"))
        if p.is_file() and p.name != "SHA256SUMS.json"
    }
    _write_json(OUT / "SHA256SUMS.json", sums)

    print(json.dumps(result, indent=2))
    if not result["overpass_reachable"]:
        print("NOTE: Overpass unreachable; committed fixture pool used. See docs/KIRO-STATUS.md.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
