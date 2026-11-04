"""Static STAC catalogue and the ``stac`` MCP server (``stac_search``, ``scene_info``).

Items are STAC-like JSON files under ``fixtures/stac/<source>/items/``. Search returns pinned ids only
(the card's allow-list), drops scenes after ``as_of`` (and counts them), and reports each scene's
coverage of the card AOI on a 30 x 30 grid.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from mcp.server import MCPServer

from treehouse.clock import parse_when
from treehouse.geo.geom import coverage_fraction, polygons_intersect_bbox
from treehouse.schemas.geo import Polygon
from treehouse.schemas.tools import SceneSummary, StacSearchResult, ToolError


@dataclass(frozen=True)
class Item:
    raw: dict

    @property
    def id(self) -> str:
        return self.raw["id"]

    @property
    def datetime(self) -> datetime:
        return datetime.fromisoformat(self.raw["properties"]["datetime"].replace("Z", "+00:00"))

    @property
    def footprint(self) -> Polygon:
        return Polygon.model_validate(self.raw["geometry"])

    @property
    def href(self) -> str | None:
        return self.raw.get("assets", {}).get("visual", {}).get("href")

    @property
    def etag(self) -> str | None:
        return self.raw.get("assets", {}).get("visual", {}).get("etag")


def load_items(fixture_dir: Path | str) -> dict[str, Item]:
    d = Path(fixture_dir) / "items"
    return {i.id: i for i in (Item(json.loads(p.read_text())) for p in sorted(d.glob("*.json")))}


class StacCatalog:
    def __init__(self, items: dict[str, Item], *, pinned: list[str], aoi: Polygon, as_of: datetime) -> None:
        self.items, self.pinned, self.aoi, self.as_of = items, set(pinned), aoi, as_of

    def summary(self, it: Item) -> SceneSummary:
        p = it.raw["properties"]
        return SceneSummary(
            scene_id=it.id, datetime=it.datetime, phase=p.get("treehouse:phase"), cloud_pct=p["eo:cloud_cover"],
            pan_gsd_m=p["pan_gsd"], off_nadir_deg=p.get("view:off_nadir"),
            sun_elevation_deg=p.get("view:sun_elevation"), footprint=it.footprint,
            aoi_coverage_fraction=round(coverage_fraction(it.footprint.polygons(), self.aoi.polygons(), 30), 6),
            license=it.raw.get("license", "unknown"), synthetic=bool(p.get("treehouse:synthetic", False)))

    def search(self, aoi_bbox: tuple[float, float, float, float], start: str, end: str) -> StacSearchResult | ToolError:
        try:
            t0, t1 = parse_when(start), parse_when(end, end=True)
        except ValueError as e:
            return ToolError(code="bad_args", message=f"start/end must be ISO dates: {e}")
        hits = [it for i, it in sorted(self.items.items()) if i in self.pinned and t0 <= it.datetime <= t1
                and polygons_intersect_bbox(it.footprint.polygons(), aoi_bbox)]
        kept = [it for it in hits if it.datetime <= self.as_of]
        kept.sort(key=lambda it: (it.datetime, it.id))
        return StacSearchResult(scenes=[self.summary(it) for it in kept], as_of_applied=self.as_of,
                                dropped_after_as_of=len(hits) - len(kept))

    def scene_info(self, scene_id: str) -> SceneSummary | ToolError:
        it = self.items.get(scene_id)
        if it is None or scene_id not in self.pinned:
            return ToolError(code="not_allowed", message=f"scene {scene_id} is not on the allow-list")
        if it.datetime > self.as_of:
            return ToolError(code="not_available_as_of", message=f"scene {scene_id} is after as_of")
        return self.summary(it)


def make_stac_server(cat: StacCatalog) -> MCPServer:
    srv = MCPServer("stac")

    @srv.tool()
    def stac_search(aoi_bbox: tuple[float, float, float, float], start: str, end: str) -> StacSearchResult | ToolError:
        """Search the pinned scene catalogue: scenes whose footprint meets aoi_bbox
        [min_lon, min_lat, max_lon, max_lat] between start and end (ISO dates), up to the task's as_of."""
        return cat.search(aoi_bbox, start, end)

    @srv.tool()
    def scene_info(scene_id: str) -> SceneSummary | ToolError:
        """Metadata for one pinned scene: date, phase, cloud %, pan GSD, footprint, AOI coverage."""
        return cat.scene_info(scene_id)

    return srv
