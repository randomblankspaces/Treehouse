"""Build PLATEAU warehouse reference keys for Nagoya and Gifu (Table 8: warehouse use, >= 1,600 m2).

This writes grading references under ``keys/plateau/`` with a licence, a snapshot date and a sha256, and
records a train/held-out split for Nagoya few-shot examples. Grading references never reach the agent (the
gateway forbids anything under ``keys/``).

Access path. PLATEAU ships 3D city models (CityGML / 3D Tiles) per municipality on the G-spatial portal.
Extracting "warehouse use, >= 1,600 m2" buildings means downloading the municipality's ``bldg`` CityGML,
reading ``bldg:usage`` (Japanese building-use codes; warehouse = code 441/"倉庫") and the footprint area, and
clipping to the AOI. That bulk download + CityGML parse is heavy and the exact per-municipality URLs must be
discovered at run time. When the portal or a dataset is unreachable from the Workshop container (recorded as a
blocker), this script falls back to a committed, deterministic AOI-sized **fixture** reference so the rest of
the pipeline (grader v2, calibration, reports) has reference geometry to run against. Fixtures are clearly
labelled ``synthetic_fixture: true`` and are NOT the report's real PLATEAU counts (Nagoya 403 / Gifu 63 over
the full cities); they are a small subset inside a ~10 km AOI.

Usage::

    uv run python scripts/fetch_plateau_warehouses.py            # attempt live, else fixture
    uv run python scripts/fetch_plateau_warehouses.py --fixture  # force the committed fixture

Run from the repo root. No AWS, no imagery pixels, no model code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "keys" / "plateau"
STATUS = ROOT / "docs" / "KIRO-STATUS.md"

# PLATEAU municipality datasets. These are the entry points to verify/resolve the CityGML bldg download.
PLATEAU_PORTAL = "https://www.geospatial.jp/ckan/dataset"
CITIES = {
    "nagoya": {
        "muni_code": "23100",
        "label": "Nagoya city (Aichi)",
        # ~10 x 8 km over Nagoya Port / Minato-ku logistics district.
        "aoi": (136.82, 35.05, 136.92, 35.12),
        "full_city_warehouse_count_report": 403,
        "fixture_count": 46,
        "split": {"train": 16, "heldout": 30},
    },
    "gifu": {
        "muni_code": "21201",
        "label": "Gifu city (Gifu)",
        # ~9 x 7 km over Gifu city industrial belt.
        "aoi": (136.72, 35.38, 136.82, 35.45),
        "full_city_warehouse_count_report": 63,
        "fixture_count": 12,
        "split": {"train": 0, "heldout": 12},  # Gifu is the transfer target: no new labels (DM2).
    },
}
LICENSE = "CC-BY-4.0"  # PLATEAU is published under CC BY 4.0; attribution recorded in provenance.
ATTRIBUTION = "国土交通省 Project PLATEAU (CityGML), CC BY 4.0"
MIN_AREA_M2 = 1600.0


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _try_live(city: str) -> bool:
    """Reachability probe for the PLATEAU portal dataset page. True only if we could actually resolve a
    CityGML download; here we only confirm the portal responds and record why a full parse is not attempted."""
    url = f"{PLATEAU_PORTAL}?q=plateau+{CITIES[city]['muni_code']}+bldg"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "treehouse-reference-fetch/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 (fixed https host)
            return r.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _fixture_warehouses(city: str) -> list[dict]:
    """Deterministic AOI-sized warehouse points, each with a plausible footprint area >= 1,600 m2.

    Deterministic (seeded by the municipality code) so the committed key is byte-stable. Points are spread on
    a jittered grid inside the AOI; areas are drawn >= MIN_AREA_M2 so every fixture row satisfies Table 8.
    """
    spec = CITIES[city]
    lo_lon, lo_lat, hi_lon, hi_lat = spec["aoi"]
    n = spec["fixture_count"]
    rng = random.Random(int(spec["muni_code"]))
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    feats: list[dict] = []
    for i in range(n):
        cx, cy = i % cols, i // cols
        # cell centre within the AOI, with sub-cell jitter, kept off the exact border
        fx = (cx + 0.5 + rng.uniform(-0.3, 0.3)) / cols
        fy = (cy + 0.5 + rng.uniform(-0.3, 0.3)) / rows
        lon = round(lo_lon + fx * (hi_lon - lo_lon), 6)
        lat = round(lo_lat + fy * (hi_lat - lo_lat), 6)
        area = round(MIN_AREA_M2 + rng.uniform(0, 9000), 1)  # 1,600 .. ~10,600 m2
        feats.append({
            "id": f"plateau-fixture:{city}:{i:03d}",
            "cls": "warehouse",
            "lon": lon,
            "lat": lat,
            "footprint_area_m2": area,
            "bldg_usage": "441",  # PLATEAU warehouse-use code
        })
    return feats


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def build(city: str, *, force_fixture: bool) -> dict:
    spec = CITIES[city]
    live_ok = False if force_fixture else _try_live(city)
    # A reachable portal is not enough to extract warehouses: the CityGML bulk parse is out of scope for the
    # Workshop window, so we always emit the fixture and record the real access path + blocker.
    source_mode = "fixture"
    feats = _fixture_warehouses(city)
    lo_lon, lo_lat, hi_lon, hi_lat = spec["aoi"]

    geojson = {
        "type": "FeatureCollection",
        "name": f"plateau-{city}-warehouses",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": [
            {
                "type": "Feature",
                "id": f["id"],
                "geometry": {"type": "Point", "coordinates": [f["lon"], f["lat"]]},
                "properties": {k: v for k, v in f.items() if k not in ("lon", "lat")},
            }
            for f in feats
        ],
    }
    out_geojson = OUT / f"{city}-warehouses.geojson"
    _write_json(out_geojson, geojson)

    # Train / held-out split for Nagoya few-shot examples (RV4: examples come from the training split only).
    ids = [f["id"] for f in feats]
    n_train = spec["split"]["train"]
    split = {"train": ids[:n_train], "heldout": ids[n_train:]}
    out_split = OUT / f"{city}-split.json"
    _write_json(out_split, {
        "city": city,
        "policy": "few-shot examples may only come from 'train'; 'heldout' is grading-only (RV4)",
        **split,
        "counts": {"train": len(split["train"]), "heldout": len(split["heldout"])},
    })

    provenance = {
        "dataset": "Project PLATEAU 3D city model (building usage)",
        "city": spec["label"],
        "municipality_code": spec["muni_code"],
        "class": "warehouse",
        "class_definition": "PLATEAU bldg:usage = warehouse (code 441), footprint area >= 1,600 m2 (Table 8)",
        "aoi_bbox_lonlat": list(spec["aoi"]),
        "license": LICENSE,
        "attribution": ATTRIBUTION,
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "snapshot_date": datetime.now(UTC).date().isoformat(),
        "retrieved_at": datetime.now(UTC).isoformat(),
        "portal_reachable": live_ok,
        "source_mode": source_mode,
        "synthetic_fixture": True,
        "real_access_path": (
            "Download the municipality CityGML (bldg) from the PLATEAU G-spatial portal, read bldg:usage "
            "(441 = warehouse) and footprint area, clip to the AOI. Not performed in the Workshop window."
        ),
        "report_full_city_warehouse_count": spec["full_city_warehouse_count_report"],
        "fixture_count": spec["fixture_count"],
        "limitations": [
            "SYNTHETIC FIXTURE: deterministic AOI-sized warehouse points, NOT the real PLATEAU footprints.",
            "Not a complete inventory; counts are a small AOI subset, not the report's full-city 403/63.",
            "Points only, no footprint polygons; footprint_area_m2 is a plausible >= 1,600 m2 placeholder.",
            "Replace with the real CityGML-derived key before claiming real output accuracy.",
        ],
        "model_visibility": "keys/ is forbidden to the agent; only the 'train' split may seed few-shot examples.",
    }
    _write_json(OUT / f"{city}-provenance.json", provenance)

    return {
        "city": city,
        "geojson": str(out_geojson.relative_to(ROOT)),
        "geojson_sha256": _sha256_file(out_geojson),
        "features": len(feats),
        "split_counts": {"train": len(split["train"]), "heldout": len(split["heldout"])},
        "portal_reachable": live_ok,
        "source_mode": source_mode,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fixture", action="store_true", help="force the committed fixture, skip the live probe")
    ap.add_argument("--city", choices=sorted(CITIES), help="only this city (default: all)")
    args = ap.parse_args(argv)

    cities = [args.city] if args.city else sorted(CITIES)
    results = [build(c, force_fixture=args.fixture) for c in cities]

    # Checksums manifest for the whole keys/plateau tree.
    sums = {
        str(p.relative_to(OUT)): _sha256_file(p)
        for p in sorted(OUT.rglob("*"))
        if p.is_file() and p.name != "SHA256SUMS.json"
    }
    _write_json(OUT / "SHA256SUMS.json", sums)

    print(json.dumps({"results": results}, indent=2))
    if any(not r["portal_reachable"] for r in results):
        print("NOTE: PLATEAU CityGML not parsed in this run; committed fixtures used. See docs/KIRO-STATUS.md.",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
