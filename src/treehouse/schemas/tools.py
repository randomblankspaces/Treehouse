"""Structured tool results (every MCP tool returns one of these models)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, model_validator

from treehouse.schemas.base import Frozen
from treehouse.schemas.geo import BBox, Point, Polygon

Phase = Literal["pre", "post"]
Fraction = Annotated[float, Field(ge=0, le=1)]
Percent = Annotated[float, Field(ge=0, le=100)]
PixelSha = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
BYTES_MODELS = ("synthetic-overview-block-v1", "measured")


class SceneSummary(Frozen):
    scene_id: str
    datetime: AwareDatetime
    phase: Phase | None = None
    cloud_pct: Percent
    pan_gsd_m: float
    off_nadir_deg: float | None = None
    sun_elevation_deg: float | None = None
    footprint: Polygon
    aoi_coverage_fraction: Fraction
    license: str
    synthetic: bool  # SYN-* scenes carry the SYNTHETIC chip in the report


class Obscuration(Frozen):
    bright_lowvar_fraction: Fraction
    nodata_fraction: Fraction
    method: Literal["heuristic:v1"] = "heuristic:v1"


class WindowResult(Frozen):
    """One image window. ``pixel_sha256`` hashes the decoded C-order uint8 array plus its shape
    (one implementation: ``treehouse.pixels.array_sha256``). ``effective_gsd_m`` =
    max(side_m / out_px, pixel_spacing_m): upsampling past the pixels read adds no detail.

    ``detail.bytes_model`` (required) says whether ``bytes_read`` was measured or comes from the declared
    ``synthetic-overview-block-v1`` model (RS-B1); the synthetic reader always models its bytes and is
    always synthetic, and a rasterio reader always measures."""

    result_id: str
    source_id: str
    scene_id: str
    etag: str | None = None
    bbox_requested: BBox
    bbox_read: BBox
    footprint_coverage_fraction: Fraction
    scene_datetime: AwareDatetime
    phase: Phase | None = None
    nominal_gsd_m: float
    pixel_spacing_m: float
    effective_gsd_m: float
    overview_level: int
    scene_cloud_pct: Percent
    off_nadir_deg: float | None = None
    out_shape: tuple[int, int]
    resampling: str
    pixel_sha256: PixelSha
    bytes_read: int = Field(ge=0)
    requests: int = Field(ge=0)
    block_size: int
    reader: str  # synthetic-v1 | recorded | rasterio-<version>
    gdal_version: str | None = None
    obscuration: Obscuration
    license: str
    synthetic: bool
    detail: dict[str, str | int | float | bool]

    @model_validator(mode="after")
    def _bytes_model(self) -> WindowResult:
        bm = self.detail.get("bytes_model")
        if bm not in BYTES_MODELS:
            raise ValueError(f"detail.bytes_model: required, one of {', '.join(BYTES_MODELS)}")
        if self.reader == "synthetic-v1":
            if bm != "synthetic-overview-block-v1":
                raise ValueError("detail.bytes_model: the synthetic reader models its bytes")
            if not self.synthetic:
                raise ValueError("synthetic: a synthetic-v1 window is synthetic")
        if self.reader.startswith("rasterio-") and bm != "measured":
            raise ValueError("detail.bytes_model: a rasterio reader measures its bytes")
        return self


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
