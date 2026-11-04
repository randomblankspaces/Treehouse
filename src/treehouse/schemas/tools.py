"""Structured tool results (every MCP tool returns one of these models)."""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime

from treehouse.schemas.base import Frozen
from treehouse.schemas.geo import BBox, Point, Polygon

Phase = Literal["pre", "post"]


class SceneSummary(Frozen):
    scene_id: str
    datetime: AwareDatetime
    phase: Phase | None = None
    cloud_pct: float
    pan_gsd_m: float
    off_nadir_deg: float | None = None
    sun_elevation_deg: float | None = None
    footprint: Polygon
    aoi_coverage_fraction: float
    license: str


class Obscuration(Frozen):
    bright_lowvar_fraction: float
    nodata_fraction: float
    method: Literal["heuristic:v1"] = "heuristic:v1"


class WindowResult(Frozen):
    """One image window. ``pixel_sha256`` hashes the decoded C-order uint8 array plus its shape.
    ``effective_gsd_m`` = side_m / out_px. ``bytes_read`` may be modelled (see the reader)."""

    result_id: str
    source_id: str
    scene_id: str
    etag: str | None = None
    bbox_requested: BBox
    bbox_read: BBox
    footprint_coverage_fraction: float
    scene_datetime: AwareDatetime
    phase: Phase | None = None
    nominal_gsd_m: float
    pixel_spacing_m: float
    effective_gsd_m: float
    overview_level: int
    scene_cloud_pct: float
    off_nadir_deg: float | None = None
    out_shape: tuple[int, int]
    resampling: str
    pixel_sha256: str
    bytes_read: int
    requests: int
    block_size: int
    reader: str  # synthetic-v1 | recorded | rasterio-<version>
    gdal_version: str | None = None
    obscuration: Obscuration
    license: str
    synthetic: bool
    detail: dict[str, str | int | float | bool] = {}  # e.g. bytes_model="synthetic-overview-block-v1"


class ClayCell(Frozen):
    cell_id: str
    center: Point
    similarity: float


class ClayCoverage(Frozen):
    source: str
    cell_m: float
    date_range: tuple[str, str]
    predates_event: bool
    aoi_cells_expected: int
    aoi_cells_present: int
    smallest_resolvable_m: float
    synthetic: bool


class ClaySearchResult(Frozen):
    cells: list[ClayCell]
    coverage: ClayCoverage


class StacSearchResult(Frozen):
    scenes: list[SceneSummary]
    as_of_applied: AwareDatetime
    dropped_after_as_of: int


class ToolError(Frozen):
    code: str
    message: str


class ClaimReceipt(Frozen):
    claim_id: str
    grounded: bool
    unresolved_refs: list[str] = []


class LimitationReceipt(Frozen):
    limitation_id: str
    recorded: bool


class UnderstandingReceipt(Frozen):
    statement_id: str
    recorded: bool
