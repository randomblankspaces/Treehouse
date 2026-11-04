"""Clay embedding search: numpy cosine similarity over an npz of cell embeddings (the ``clay`` server).

The loader takes a column map so real LGND exports (other column names) load through the same code.
The coverage report says what the embeddings can and cannot show (cell size, dates, synthetic or not).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from mcp.server import MCPServer

from treehouse.schemas.geo import Point
from treehouse.schemas.tools import ClayCell, ClayCoverage, ClaySearchResult, ToolError

DEFAULT_COLUMNS = {"id": "cell_id", "lon": "lon", "lat": "lat", "vec": "emb", "meta": "meta"}


@dataclass
class Embeddings:
    ids: np.ndarray
    lon: np.ndarray
    lat: np.ndarray
    vec: np.ndarray  # unit rows, float32
    meta: dict

    def cell_of(self, lon: float, lat: float) -> int:
        return int(np.argmin((self.lon - lon) ** 2 + (self.lat - lat) ** 2))


def load_embeddings(path: Path | str, columns: dict[str, str] | None = None) -> Embeddings:
    c = {**DEFAULT_COLUMNS, **(columns or {})}
    with np.load(path, allow_pickle=False) as z:
        vec = z[c["vec"]].astype(np.float32)
        vec /= np.linalg.norm(vec, axis=1, keepdims=True).clip(min=1e-12)
        return Embeddings(ids=z[c["id"]].astype(str), lon=z[c["lon"]].astype(np.float64),
                          lat=z[c["lat"]].astype(np.float64), vec=vec, meta=json.loads(str(z[c["meta"]])))


class ClayIndex:
    def __init__(self, emb: Embeddings, *, source_id: str) -> None:
        self.emb, self.source_id = emb, source_id

    def coverage(self, bbox) -> ClayCoverage:
        m, e = self.emb.meta, self.emb
        inside = (e.lon >= bbox[0]) & (e.lon <= bbox[2]) & (e.lat >= bbox[1]) & (e.lat <= bbox[3])
        x0, y0, dx = m["grid"]["lon0"], m["grid"]["lat0"], m["grid"]["cell_deg"]
        nx, ny = m["grid"]["nx"], m["grid"]["ny"]
        gx = x0 + (np.arange(nx) + 0.5) * dx
        gy = y0 + (np.arange(ny) + 0.5) * dx
        expected = int(((gx >= bbox[0]) & (gx <= bbox[2])).sum() * ((gy >= bbox[1]) & (gy <= bbox[3])).sum())
        return ClayCoverage(source=m["source"], cell_m=m["cell_m"], date_range=tuple(m["date_range"]),
                            predates_event=m["predates_event"], aoi_cells_expected=expected,
                            aoi_cells_present=int(inside.sum()), smallest_resolvable_m=m["smallest_resolvable_m"],
                            synthetic=m["synthetic"])

    def search(self, aoi_bbox, lon: float | None, lat: float | None, cell_id: str | None,
               k: int) -> ClaySearchResult | ToolError:
        e = self.emb
        if cell_id is not None:
            hit = np.flatnonzero(e.ids == cell_id)
            if not hit.size:
                return ToolError(code="bad_args", message=f"unknown cell_id {cell_id}")
            q = int(hit[0])
        elif lon is not None and lat is not None:
            q = e.cell_of(lon, lat)
        else:
            return ToolError(code="bad_args", message="give cell_id, or lon and lat")
        inside = np.flatnonzero((e.lon >= aoi_bbox[0]) & (e.lon <= aoi_bbox[2]) & (e.lat >= aoi_bbox[1])
                                & (e.lat <= aoi_bbox[3]))
        sims = e.vec[inside] @ e.vec[q]
        order = sorted(range(len(inside)), key=lambda j: (-round(float(sims[j]), 6), e.ids[inside[j]]))[:k]
        cells = [ClayCell(cell_id=str(e.ids[inside[j]]), center=Point(coordinates=(float(e.lon[inside[j]]),
                 float(e.lat[inside[j]]))), similarity=round(float(sims[j]), 6)) for j in order]
        return ClaySearchResult(cells=cells, coverage=self.coverage(aoi_bbox))


def make_clay_server(index: ClayIndex) -> MCPServer:
    srv = MCPServer("clay")

    # Explicit metadata preserves cassette whitespace when Python cleans function docstrings.
    @srv.tool(description=(
        'Cells in aoi_bbox most similar to the query cell (cell_id, or the cell at lon/lat), by cosine\n'
        '        similarity of Clay embeddings. Read the coverage report: cells are coarse and may predate the event.'
    ))
    def clay_search(aoi_bbox: tuple[float, float, float, float], lon: float | None = None, lat: float | None = None,
                    cell_id: str | None = None, k: int = 10) -> ClaySearchResult | ToolError:
        return index.search(aoi_bbox, lon, lat, cell_id, max(1, min(k, 500)))

    return srv
