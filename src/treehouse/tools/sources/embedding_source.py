"""Embedding sources behind one protocol (task 2, design.md "New modules").

``EmbeddingSource.index(aoi_bbox, cell_size_m, year) -> CellIndex``. A ``CellIndex`` carries the grid, the
float32 embeddings and the provenance Table 9 asks for (imagery source, date, resolution, cell size, licence,
cost). ``CellIndex.to_npz_arrays()`` produces the same npz layout as ``treehouse.tools.clay.load_embeddings``
reads, so the existing ``clay`` MCP server can serve any source unchanged.

Seam for ``clay_compute`` (Should, not built): a third source that runs Clay v1.5 on 160 m Sentinel-2 chips
on SageMaker/EC2 GPU and caches a CellIndex to S3 would implement the same protocol.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from treehouse.geo.geom import M_PER_DEG

BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class CellIndex:
    grid_id: str
    cell_size_m: float
    crs: str
    lon0: float
    lat0: float
    cell_deg: float
    nx: int
    ny: int
    cell_ids: np.ndarray       # str, one per cell present
    lon: np.ndarray            # cell centroids
    lat: np.ndarray
    emb: np.ndarray            # float32, unit rows
    source: str
    source_id: str
    date_range: tuple[str, str]
    resolution_m: float
    licence: str
    cost_usd: float
    synthetic: bool
    provenance: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        n = len(self.cell_ids)
        if not (len(self.lon) == len(self.lat) == self.emb.shape[0] == n) or n == 0:
            raise ValueError("CellIndex arrays must be non-empty and the same length")
        if self.emb.dtype != np.float32:
            raise ValueError("CellIndex embeddings must be float32")

    def describe(self) -> dict:
        """Provenance for every index built (Req 2.5): source, date, resolution, cell size, licence, cost."""
        return {"grid_id": self.grid_id, "source": self.source, "source_id": self.source_id,
                "date_range": list(self.date_range), "resolution_m": self.resolution_m,
                "cell_size_m": self.cell_size_m, "crs": self.crs, "licence": self.licence,
                "cost_usd": self.cost_usd, "cells": len(self.cell_ids), "dims": int(self.emb.shape[1]),
                "synthetic": self.synthetic, **self.provenance}

    def to_npz_arrays(self) -> dict[str, np.ndarray]:
        meta = {"source": self.source, "cell_m": self.cell_size_m, "date_range": list(self.date_range),
                "predates_event": True, "smallest_resolvable_m": max(self.resolution_m, self.cell_size_m),
                "synthetic": self.synthetic,
                "grid": {"lon0": self.lon0, "lat0": self.lat0, "cell_deg": self.cell_deg,
                         "nx": self.nx, "ny": self.ny}}
        return {"cell_id": self.cell_ids.astype(str), "lon": self.lon, "lat": self.lat,
                "emb": self.emb.astype(np.float16), "meta": np.array(json.dumps(meta, sort_keys=True))}


class EmbeddingSource(Protocol):
    source_id: str
    licence: str
    resolution_m: float
    native_cell_m: float

    def index(self, aoi_bbox: BBox, cell_size_m: float, year: int) -> CellIndex: ...


def cell_deg_for(cell_size_m: float) -> float:
    return cell_size_m / M_PER_DEG


def pool_to_grid(lon: np.ndarray, lat: np.ndarray, vec: np.ndarray, aoi_bbox: BBox,
                 cell_size_m: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict]:
    """Mean-pool point/pixel embeddings into square cells of ``cell_size_m`` over ``aoi_bbox``.

    Returns (cell_ids, centroid lon, centroid lat, pooled unit vectors, grid). Only cells with at least one
    member are returned. The pooled vector is the mean of its members, then L2-normalised.
    """
    d = cell_deg_for(cell_size_m)
    lon0, lat0 = aoi_bbox[0], aoi_bbox[1]
    nx = max(1, math.ceil(round((aoi_bbox[2] - lon0) / d, 9)))
    ny = max(1, math.ceil(round((aoi_bbox[3] - lat0) / d, 9)))
    inside = (lon >= aoi_bbox[0]) & (lon < aoi_bbox[2]) & (lat >= aoi_bbox[1]) & (lat < aoi_bbox[3])
    ix = np.clip(((lon[inside] - lon0) / d).astype(int), 0, nx - 1)
    iy = np.clip(((lat[inside] - lat0) / d).astype(int), 0, ny - 1)
    flat = iy * nx + ix
    v = vec[inside].astype(np.float64)
    keys, inv = np.unique(flat, return_inverse=True)
    sums = np.zeros((len(keys), v.shape[1]))
    np.add.at(sums, inv, v)
    counts = np.bincount(inv, minlength=len(keys)).astype(np.float64)
    mean = sums / counts[:, None]
    unit = (mean / np.linalg.norm(mean, axis=1, keepdims=True).clip(min=1e-12)).astype(np.float32)
    jy, jx = keys // nx, keys % nx
    ids = np.array([f"r{y:03d}c{x:03d}" for y, x in zip(jy, jx, strict=True)])
    clon = np.round(lon0 + (jx + 0.5) * d, 8)
    clat = np.round(lat0 + (jy + 0.5) * d, 8)
    grid = {"lon0": lon0, "lat0": lat0, "cell_deg": d, "nx": nx, "ny": ny}
    return ids, clon, clat, unit, grid


def load_fixture_points(path) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """Read a committed embeddings npz (cell_id/lon/lat/emb/meta) as raw points for pooling."""
    with np.load(path, allow_pickle=False) as z:
        return (z["lon"].astype(np.float64), z["lat"].astype(np.float64), z["emb"].astype(np.float32),
                json.loads(str(z["meta"])))
