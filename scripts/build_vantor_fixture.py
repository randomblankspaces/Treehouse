"""Build fixtures/stac/vantor-nepal-aug-2026/ from Vantor Open Data STAC metadata. Metadata only, never pixels.

    uv run python scripts/build_vantor_fixture.py --from-json wip/fixtures/nepal-flooding-aug-2026.stac.json
    uv run python scripts/build_vantor_fixture.py            # network mode: re-fetch from the bucket

``--from-json`` converts the metadata fetched on 2026-11-04 (no network). Network mode lists the event
prefix, reads each item JSON and the bucket ETags, writes the same intermediate file next to the output
and converts it. Run outside pytest. Writes items/<id>.json, event.json, collection.json, etags.json and
LICENSE-DATA (CC-BY-NC-4.0 attribution).
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

BUCKET = "https://vantor-opendata.s3.amazonaws.com"
EVENT = "events/Nepal-Flooding-Aug-2026/"
LICENSE = "CC-BY-NC-4.0"
ATTRIBUTION = ("Imagery metadata (c) Vantor, CC-BY-NC-4.0, via the Vantor Open Data program on the AWS Registry "
               "of Open Data. Metadata only: no pixels are stored in this repository.")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fixtures" / "stac" / "vantor-nepal-aug-2026"


def _dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n")


def stac_item(it: dict) -> dict:
    ring = [list(p) for p in it["footprint"]]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    props = {"datetime": it["datetime"], "treehouse:phase": it["phase"], "eo:cloud_cover": it["eo:cloud_cover"],
             "pan_gsd": it["pan_gsd"], "view:off_nadir": it.get("view:off_nadir"),
             "view:sun_elevation": it.get("view:sun_elevation"), "view:sun_azimuth": it.get("view:sun_azimuth"),
             "vehicle_name": it.get("vehicle_name")}
    return {"type": "Feature", "stac_version": "1.0.0", "id": it["id"], "bbox": it["bbox"],
            "geometry": {"type": "Polygon", "coordinates": [ring]}, "properties": props,
            "assets": {"visual": {"href": it["visual_href"], "etag": it["visual_etag"],
                                  "file:size": it.get("visual_bytes"), "type": "image/tiff; application=geotiff"}},
            "license": LICENSE}


def convert(meta: dict, out: Path = OUT) -> list[str]:
    items = sorted(meta["items"], key=lambda i: i["id"])
    for it in items:
        _dump(out / "items" / f"{it['id']}.json", stac_item(it))
    ev = meta["event"]
    _dump(out / "event.json", {"type": "Feature", "id": ev["title"], "geometry": ev["geometry"],
                               "properties": {k: v for k, v in ev.items() if k != "geometry"}})
    _dump(out / "collection.json", {
        "type": "Collection", "stac_version": "1.0.0", "id": "vantor-nepal-aug-2026", "license": LICENSE,
        "description": ev.get("description", ""), "source": meta["source"], "retrieved": meta["retrieved"],
        "footprint_simplification": meta.get("footprint_simplification"), "n_items": len(items),
        "attribution": ATTRIBUTION})
    _dump(out / "etags.json", {it["id"]: it["visual_etag"] for it in items})
    (out / "LICENSE-DATA").write_text(
        f"{LICENSE}: https://creativecommons.org/licenses/by-nc/4.0/\n\n{ATTRIBUTION}\n"
        f"Source: {meta['source']} (retrieved {meta['retrieved']}). Derived datasets are non-commercial.\n")
    return [it["id"] for it in items]


def _get(url: str) -> tuple[bytes, dict]:
    with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310 (fixed https host)
        return r.read(), dict(r.headers)


def fetch(event_date: str = "2026-08-26") -> dict:
    """Network mode: list the event prefix and read every item JSON (metadata only)."""
    listing, _ = _get(f"{BUCKET}/?list-type=2&prefix={EVENT}")
    keys = re.findall(rb"<Key>([^<]+)</Key>", listing)
    etags = dict(zip(keys, re.findall(rb"<ETag>&quot;([^&]+)&quot;</ETag>", listing), strict=False))
    sizes = dict(zip(keys, (int(s) for s in re.findall(rb"<Size>(\d+)</Size>", listing)), strict=False))
    event = json.loads(_get(f"{BUCKET}/{EVENT}event.json")[0])
    items = []
    for k in sorted(k.decode() for k in keys):
        name = k[len(EVENT):]
        if "/" in name or not name.endswith(".json") or name in {"event.json", "collection.json"}:
            continue
        raw = json.loads(_get(f"{BUCKET}/{k}")[0])
        p, tif = raw["properties"], k[:-5] + ".tif"
        geom = raw["geometry"]
        ring = geom["coordinates"][0] if geom["type"] == "Polygon" else geom["coordinates"][0][0]
        items.append({"id": raw["id"], "datetime": p["datetime"],
                      "phase": "post" if p["datetime"][:10] > event_date else "pre",
                      "eo:cloud_cover": p.get("eo:cloud_cover"), "pan_gsd": p.get("pan_gsd"),
                      "view:off_nadir": p.get("view:off_nadir"), "view:sun_elevation": p.get("view:sun_elevation"),
                      "view:sun_azimuth": p.get("view:sun_azimuth"), "vehicle_name": p.get("vehicle_name"),
                      "bbox": raw["bbox"], "footprint": ring, "visual_href": f"{BUCKET}/{tif}",
                      "visual_etag": etags[tif.encode()].decode(), "visual_bytes": sizes[tif.encode()]})
    return {"source": f"{BUCKET}/{EVENT}", "retrieved": __import__("datetime").date.today().isoformat(),
            "license": LICENSE, "attribution": ATTRIBUTION, "event": event, "items": items,
            "footprint_simplification": "none (raw item geometry)"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from-json", type=Path, help="convert already-fetched metadata (no network)")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    if a.from_json:
        meta = json.loads(a.from_json.read_text())
    else:
        meta = fetch()
        _dump(a.out.parent / f"{a.out.name}.fetched.json", meta)
    ids = convert(meta, a.out)
    print(f"wrote {len(ids)} items to {a.out}")


if __name__ == "__main__":
    main()
