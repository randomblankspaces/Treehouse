"""Write the committed AEF-like and LGND-like embedding fixtures for the warehouse AOIs. SYNTHETIC.

    uv run python scripts/make_embedding_fixtures.py

Real AEF (Earth Engine) and LGND (GeoParquet, needs pyarrow) are not readable from the Workshop container, so
these small fixtures stand in. Cells near a reference warehouse get a shared "warehouse-like" direction plus
noise, so retrieval has signal; everything is labelled ``synthetic: true``. Byte-stable (fixed zip timestamps).
AEF fixture: 160 m base grid (pooled 10 m signal), 16 dims. LGND fixture: 1,280 m cells, 16 dims.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from treehouse.geo.geom import M_PER_DEG
from treehouse.paths import fixtures_root, keys_root
from treehouse.synth.fixtures import npz_bytes

D = 16
AOIS = {
    "nagoya": ((136.82, 35.05, 136.92, 35.12), "plateau/nagoya-warehouses.geojson", 101),
    "gifu": ((136.72, 35.38, 136.82, 35.45), "plateau/gifu-warehouses.geojson", 102),
    "chattogram": ((91.78, 22.28, 91.88, 22.36), "osm/chattogram-warehouses.geojson", 103),
}


def _sites(rel: str) -> np.ndarray:
    fc = json.loads((keys_root() / rel).read_text())
    return np.array([f["geometry"]["coordinates"] for f in fc["features"]], dtype=np.float64)


def arrays(aoi: str, cell_m: float, source: str) -> dict[str, np.ndarray]:
    bbox, key_rel, seed = AOIS[aoi]
    d = cell_m / M_PER_DEG
    nx = math.ceil(round((bbox[2] - bbox[0]) / d, 9))
    ny = math.ceil(round((bbox[3] - bbox[1]) / d, 9))
    rng = np.random.default_rng([seed, int(cell_m)])
    proto = rng.standard_normal(D)
    sites = _sites(key_rel)
    ids, lon, lat, vec = [], [], [], []
    for j in range(ny):
        for i in range(nx):
            x, y = round(bbox[0] + (i + 0.5) * d, 8), round(bbox[1] + (j + 0.5) * d, 8)
            near = bool(((np.abs(sites[:, 0] - x) <= d / 2) & (np.abs(sites[:, 1] - y) <= d / 2)).any())
            noise = rng.standard_normal(D)
            v = proto + 0.6 * noise if near else noise
            ids.append(f"r{j:03d}c{i:03d}")
            lon.append(x)
            lat.append(y)
            vec.append(v / np.linalg.norm(v))
    meta = {"source": source, "cell_m": cell_m, "date_range": ["2024-01-01", "2024-12-31"],
            "predates_event": True, "smallest_resolvable_m": cell_m, "synthetic": True,
            "grid": {"lon0": bbox[0], "lat0": bbox[1], "cell_deg": d, "nx": nx, "ny": ny}}
    return {"cell_id": np.array(ids), "lon": np.array(lon), "lat": np.array(lat),
            "emb": np.array(vec, dtype=np.float16), "meta": np.array(json.dumps(meta, sort_keys=True))}


def write_all(out: Path | None = None) -> list[Path]:
    out = out or fixtures_root() / "embeddings"
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for aoi in AOIS:
        for prefix, cell_m, source in (
                ("aef", 160.0, "synthetic-aef-v1 (not AlphaEarth; 10 m signal pooled to a 160 m base grid)"),
                ("lgnd", 1280.0, "synthetic-lgnd-clay-v1 (not LGND; same 1,280 m cell size)")):
            p = out / f"{prefix}-{aoi}.npz"
            p.write_bytes(npz_bytes(arrays(aoi, cell_m, source)))
            paths.append(p)
    return paths


if __name__ == "__main__":
    for p in write_all():
        print(p, p.stat().st_size)
