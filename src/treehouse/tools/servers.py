"""Builds the five in-process MCP servers (stac, imagery, clay, claims, decoy) for a task card."""

from __future__ import annotations

import logging
from datetime import datetime

from mcp.server import MCPServer

from treehouse.gateway.pixel_cache import PixelCache
from treehouse.paths import repo_root
from treehouse.schemas.task import DataSource, TaskCard
from treehouse.schemas.tools import ToolError
from treehouse.tools.claims import ClaimLedger, make_claims_server
from treehouse.tools.clay import ClayIndex, load_embeddings, make_clay_server
from treehouse.tools.decoy import make_decoy_server
from treehouse.tools.imagery import NoImagery, make_imagery_server
from treehouse.tools.sources.recorded import RecordedImagerySource
from treehouse.tools.sources.synthetic import SyntheticImagerySource
from treehouse.tools.stac import StacCatalog, load_items, make_stac_server

logging.getLogger("mcp").setLevel(logging.WARNING)


class NoClay:
    def search(self, aoi_bbox, lon, lat, cell_id, k) -> ToolError:
        return ToolError(code="no_coverage", message="no pinned embeddings for this task")


def _source(card: TaskCard, kind: str) -> DataSource | None:
    return next((d for d in card.data_allowlist if d.kind == kind), None)


def build_servers(card: TaskCard, *, ledger: ClaimLedger, pixels: PixelCache, as_of: datetime | None = None,
                  recorded_windows: list[dict] | None = None) -> dict[str, MCPServer]:
    as_of = as_of or card.as_of
    root = repo_root()
    stac_src = _source(card, "stac")
    items = load_items(root / stac_src.fixture_path) if stac_src and stac_src.fixture_path else {}
    pinned = list(stac_src.item_ids) if stac_src else []
    cat = StacCatalog(items, pinned=pinned, aoi=card.aoi, as_of=as_of)

    img = _source(card, "imagery")
    w = card.windows
    if img is not None and img.access == "synthetic":
        imagery = SyntheticImagerySource(allowed=pinned, as_of=as_of, pixels=pixels, max_side_m=w.max_side_m,
                                         max_out_px=w.max_out_px, max_bytes=w.max_bytes_per_run)
    elif img is not None and img.access == "recorded":
        imagery = RecordedImagerySource(recorded_windows or [], allowed=pinned, as_of=as_of, source_id=img.source_id,
                                        scene_dates={i: it.datetime for i, it in items.items()})
    else:
        imagery = NoImagery()

    emb = _source(card, "embeddings")
    path = root / emb.fixture_path if emb and emb.fixture_path else None
    clay = ClayIndex(load_embeddings(path), source_id=emb.source_id) if path and path.is_file() else NoClay()

    return {"stac": make_stac_server(cat), "imagery": make_imagery_server(imagery), "clay": make_clay_server(clay),
            "claims": make_claims_server(ledger), "decoy": make_decoy_server()}
