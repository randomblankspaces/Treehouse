"""The ``imagery`` server: ``imagery_window`` over a synthetic or recorded source.

Errors come back as typed ``ToolError`` codes: not_allowed, not_available_as_of, no_coverage,
out_of_bounds, window_too_large, window_too_small, budget_exceeded, insufficient_coverage (snapshot_changed is W1).
The server checks the window before any source sees it: ``out_px >= MIN_OUT_PX`` and ``side_m >= MIN_SIDE_M``
(``window_too_small``; judge D1/D3) and lon/lat inside [-180, 180] x [-90, 90] (``out_of_bounds``).
Pixels never travel in the MCP payload; the synthetic source puts them in the gateway's PixelCache.
"""

from __future__ import annotations

from typing import Annotated, Literal, Protocol

from mcp.server import MCPServer
from pydantic import Field

from treehouse.schemas.tools import ToolError, WindowResult

ERROR_CODES = ("not_allowed", "not_available_as_of", "no_coverage", "out_of_bounds", "window_too_large",
               "window_too_small", "budget_exceeded", "insufficient_coverage", "snapshot_changed")
MIN_OUT_PX = 32
MIN_SIDE_M = 5.0


def check_window(lon: float, lat: float, side_m: float, out_px: int) -> ToolError | None:
    """Source-independent argument checks; a typed error, never an exception."""
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return ToolError(code="out_of_bounds", message="lon must be in [-180, 180] and lat in [-90, 90]")
    if out_px < MIN_OUT_PX or side_m < MIN_SIDE_M:
        return ToolError(code="window_too_small",
                         message=f"limits are side_m >= {MIN_SIDE_M} and out_px >= {MIN_OUT_PX}")
    return None


class ImagerySource(Protocol):
    def window(self, scene_id: str, lon: float, lat: float, side_m: float, out_px: int,
               resampling: str) -> WindowResult | ToolError: ...


class NoImagery:
    def window(self, scene_id, lon, lat, side_m, out_px, resampling) -> ToolError:
        return ToolError(code="not_allowed", message="this task has no imagery source")


def make_imagery_server(source: ImagerySource) -> MCPServer:
    srv = MCPServer("imagery")

    @srv.tool()
    def imagery_window(scene_id: str, lon: float, lat: float, side_m: Annotated[float, Field(gt=0)],
                       out_px: Annotated[int, Field(gt=0)] = 512,
                       resampling: Literal["average", "nearest"] = "average") -> WindowResult | ToolError:
        """Read a square window of side_m metres centred on lon/lat from a scene, resampled to out_px x out_px.
        effective_gsd_m = max(side_m / out_px, pixel_spacing_m) is the detail you actually see (upsampling
        adds none); the image follows the metadata."""
        bad = check_window(lon, lat, side_m, out_px)
        if bad is not None:
            return bad
        return source.window(scene_id, lon, lat, side_m, out_px, resampling)

    return srv
