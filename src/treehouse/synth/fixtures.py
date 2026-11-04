"""Writes the committed synthetic fixtures: the STAC items and the Clay-like embeddings npz. SYNTHETIC.

    uv run python -m treehouse.synth.fixtures      # rewrites fixtures/stac/synth-crossings-v1, fixtures/embeddings

The npz is written with fixed zip timestamps, so a rebuild is byte-identical (a test checks it).
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import numpy as np

from treehouse.geo.geom import M_PER_DEG
from treehouse.paths import fixtures_root
from treehouse.synth import world

CELL_M = 64.0
D = 64
EMB_META = {"source": "synthetic-clay-v1 (not LGND; real LGND cells are 1280 m)", "cell_m": CELL_M,
            "date_range": ["2026-01-01", "2026-04-30"], "predates_event": True, "smallest_resolvable_m": CELL_M,
            "synthetic": True}


def stac_dir() -> Path:
    return fixtures_root() / "stac" / world.WORLD_ID


def embeddings_path() -> Path:
    return fixtures_root() / "embeddings" / f"{world.WORLD_ID}.npz"


def write_stac(out: Path | None = None) -> list[Path]:
    out = out or stac_dir()
    paths = []
    for s in world.SCENES.values():
        p = out / "items" / f"{s.id}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(world.stac_item(s), indent=1, sort_keys=True) + "\n")
        paths.append(p)
    return paths


def river_cells(n: int, cell_deg: float) -> set[tuple[int, int]]:
    xs = np.linspace(0, world.W, 4000)
    ys = world.river_y(xs)
    return {(int(x // cell_deg), int(y // cell_deg)) for x, y in zip(xs, ys, strict=True)
            if x < n * cell_deg and y < n * cell_deg}


def embedding_arrays() -> dict[str, np.ndarray]:
    cell_deg = CELL_M / M_PER_DEG
    n = int(np.ceil(world.W / cell_deg))  # 19
    rng = np.random.default_rng([world.SEED, 7])
    proto = rng.standard_normal(D)
    river = river_cells(n, cell_deg)
    ids, lon, lat, vec = [], [], [], []
    for j in range(n):
        for i in range(n):
            ids.append(f"r{j:02d}c{i:02d}")
            lon.append(round((i + 0.5) * cell_deg, 8))
            lat.append(round((j + 0.5) * cell_deg, 8))
            noise = rng.standard_normal(D)
            v = proto + 0.35 * noise if (i, j) in river else noise
            vec.append(v / np.linalg.norm(v))
    meta = {**EMB_META, "grid": {"lon0": 0.0, "lat0": 0.0, "cell_deg": cell_deg, "nx": n, "ny": n},
            "river_cells": sorted(f"r{j:02d}c{i:02d}" for i, j in river)}
    return {"cell_id": np.array(ids), "lon": np.array(lon), "lat": np.array(lat),
            "emb": np.array(vec, dtype=np.float16), "meta": np.array(json.dumps(meta, sort_keys=True))}


def npz_bytes(arrays: dict[str, np.ndarray]) -> bytes:
    """An npz with fixed member timestamps (numpy's savez stamps the current time)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, a in arrays.items():
            b = io.BytesIO()
            np.lib.format.write_array(b, a, allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, b.getvalue())
    return buf.getvalue()


def write_embeddings(out: Path | None = None) -> Path:
    out = out or embeddings_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(npz_bytes(embedding_arrays()))
    return out


if __name__ == "__main__":
    write_stac()
    print(write_embeddings())
