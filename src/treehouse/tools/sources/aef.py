"""AlphaEarth Foundations (AEF) annual embeddings: 64 numbers per 10 m pixel, CC BY 4.0 (report Table 12).

Real access path (UNVERIFIED from the Workshop container): the Google Satellite Embedding dataset via an Earth
Engine export, or a public cloud mirror. Not reachable here, so ``AefSource`` reads a committed AOI-sized
fixture (``fixtures/embeddings/aef-<aoi>.npz``, built by ``scripts/make_embedding_fixtures.py``) and records
``access: fixture`` plus the real path in the provenance. The fixture stores the 10 m signal pre-pooled to a
160 m base grid to keep the repo light; ``index()`` pools that base to any coarser cell size (160 m x k). The
pooling math itself is the same for raw 10 m pixels (tested on a tiny 10 m array).
"""

from __future__ import annotations

from pathlib import Path

from treehouse.paths import fixtures_root
from treehouse.tools.sources.embedding_source import BBox, CellIndex, load_fixture_points, pool_to_grid

REAL_ACCESS_PATH = "Google Satellite Embedding (AEF) annual 10 m: Earth Engine export or public cloud mirror"


class AefSource:
    source_id = "aef-10m-annual"
    licence = "CC-BY-4.0"
    resolution_m = 10.0
    native_cell_m = 10.0

    def __init__(self, fixture: Path | str) -> None:
        self.fixture = Path(fixture)

    @classmethod
    def for_aoi(cls, aoi: str) -> AefSource:
        return cls(fixtures_root() / "embeddings" / f"aef-{aoi}.npz")

    def index(self, aoi_bbox: BBox, cell_size_m: float, year: int) -> CellIndex:
        lon, lat, vec, meta = load_fixture_points(self.fixture)
        dates = tuple(meta["date_range"])
        if dates != (f"{year}-01-01", f"{year}-12-31"):
            raise ValueError(f"requested year {year} is unavailable; fixture dates are {dates[0]} to {dates[1]}")
        base = float(meta["cell_m"])
        if cell_size_m < base:
            raise ValueError(f"fixture base grid is {base:g} m; request cell_size_m >= {base:g} "
                             "(raw 10 m pixels need the real AEF access path)")
        ids, clon, clat, emb, grid = pool_to_grid(lon, lat, vec, aoi_bbox, cell_size_m)
        return CellIndex(
            grid_id=f"{self.source_id}:{year}:{cell_size_m:g}m:{aoi_bbox}", cell_size_m=cell_size_m,
            crs="EPSG:4326", lon0=grid["lon0"], lat0=grid["lat0"], cell_deg=grid["cell_deg"], nx=grid["nx"],
            ny=grid["ny"], cell_ids=ids, lon=clon, lat=clat, emb=emb, source=meta["source"],
            source_id=self.source_id, date_range=dates,
            resolution_m=self.resolution_m, licence=self.licence, cost_usd=0.0,
            synthetic=bool(meta.get("synthetic", True)),
            provenance={"access": "fixture", "fixture": self.fixture.name, "real_access_path": REAL_ACCESS_PATH,
                        "fixture_base_cell_m": base})
