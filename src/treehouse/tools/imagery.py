"""The ``imagery`` server: ``imagery_window`` over a synthetic or recorded source.

Errors come back as typed ``ToolError`` codes: not_allowed, not_available_as_of, no_coverage,
out_of_bounds, window_too_large, budget_exceeded, insufficient_coverage (snapshot_changed is W1).
Pixels never travel in the MCP payload; the synthetic source puts them in the gateway's PixelCache.
"""

from __future__ import annotations

from typing import Annotated, Literal, Protocol

from mcp.server import MCPServer
from pydantic import Field

from treehouse.schemas.tools import ToolError, WindowResult

ERROR_CODES = ("not_allowed", "not_available_as_of", "no_coverage", "out_of_bounds", "window_too_large",
               "budget_exceeded", "insufficient_coverage", "snapshot_changed")


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
        effective_gsd_m = side_m / out_px is the detail you actually see; the image follows the metadata."""
        return source.window(scene_id, lon, lat, side_m, out_px, resampling)

    return srv
