"""LGND Clay precomputed embeddings on Sentinel-2 (source.coop, CC BY 4.0), 1.28 km / 2.56 km cells.

Real access is provided by ``clay_lgnd_real.RealClayLgndSource`` with the optional ``real`` extra.
``ClayLgndSource`` keeps reading a committed AOI-sized fixture
(``fixtures/embeddings/lgnd-<aoi>.npz``) with the same coarse 1,280 m cells and records ``access: fixture``.
The cells are far coarser than the report's 160 m unit: a good agent may still pick this source and must say
why (or reject it for warehouses); RV1 judges that choice.
"""

from __future__ import annotations

from pathlib import Path

from treehouse.paths import fixtures_root
from treehouse.tools.sources.embedding_source import BBox, CellIndex, load_fixture_points, pool_to_grid

REAL_ACCESS_PATH = "s3://us-west-2.opendata.source.coop/clay/lgnd-embeddings/ (GeoParquet, v1.5)"
NATIVE_CELLS_M = (1280.0, 2560.0)


class ClayLgndSource:
    source_id = "lgnd-clay-embeddings"
    licence = "CC-BY-4.0"
    resolution_m = 10.0          # Sentinel-2 input
    native_cell_m = 1280.0

    def __init__(self, fixture: Path | str) -> None:
        self.fixture = Path(fixture)

    @classmethod
    def for_aoi(cls, aoi: str) -> ClayLgndSource:
        return cls(fixtures_root() / "embeddings" / f"lgnd-{aoi}.npz")

    def index(self, aoi_bbox: BBox, cell_size_m: float, year: int) -> CellIndex:
        if cell_size_m not in NATIVE_CELLS_M:
            raise ValueError(f"LGND precomputed cells are {NATIVE_CELLS_M} m only; got {cell_size_m:g}")
        lon, lat, vec, meta = load_fixture_points(self.fixture)
        ids, clon, clat, emb, grid = pool_to_grid(lon, lat, vec, aoi_bbox, cell_size_m)
        return CellIndex(
            grid_id=f"{self.source_id}:{year}:{cell_size_m:g}m:{aoi_bbox}", cell_size_m=cell_size_m,
            crs="EPSG:4326", lon0=grid["lon0"], lat0=grid["lat0"], cell_deg=grid["cell_deg"], nx=grid["nx"],
            ny=grid["ny"], cell_ids=ids, lon=clon, lat=clat, emb=emb, source=meta["source"],
            source_id=self.source_id, date_range=tuple(meta["date_range"]), resolution_m=self.resolution_m,
            licence=self.licence, cost_usd=0.0, synthetic=bool(meta.get("synthetic", True)),
            provenance={"access": "fixture", "fixture": self.fixture.name, "real_access_path": REAL_ACCESS_PATH})
