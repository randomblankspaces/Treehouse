"""Nepal demo inputs (IMPLEMENTATION-DESIGN §5.2). Every row here is SYNTHETIC: illustrative, not surveyed bridges.

Nothing is hard-coded about the place: the corridor is the midline of the card AOI, the scene is the
clearest post-event scene on the card's allow-list, and its id, date, pan GSD, cloud and off-nadir come
from the pinned STAC fixture. The 30 candidate points, their classes, statuses and obscuration, and the
pixel hashes are generated from ``SEED``. ``pixel_sha256`` hashes a deterministic synthetic uint8 array
keyed by the window id (the same array-hash rule as OBS-B2); no pixels exist anywhere.
"""

from __future__ import annotations

import math

import numpy as np

from treehouse.canon import sha256_json
from treehouse.geo.geom import M_PER_DEG, m_to_deg, point_in_polygons
from treehouse.pixels import array_sha256
from treehouse.schemas.task import TaskCard
from treehouse.tools.stac import Item

SEED = 20261104
N_POINTS = 30
N_OBSCURED = 8
SIDE_M = 64.0  # 64 m / 128 px = 0.5 m effective GSD (upsampling never beats the pixel spacing)
OUT_PX = 128
NOTE = "illustrative, not surveyed bridges"
BLOCK_BYTES = 48 * 1024
HEADER_BYTES = 16 * 1024
BYTES_MODEL = "synthetic-overview-block-v1"


def clearest_post_scene(card: TaskCard, items: dict[str, Item]) -> Item:
    stac = next(d for d in card.data_allowlist if d.kind == "stac")
    post = [items[i] for i in stac.item_ids if items[i].raw["properties"].get("treehouse:phase") == "post"]
    return min(post, key=lambda it: (it.raw["properties"]["eo:cloud_cover"], it.id))


def corridor(card: TaskCard) -> list[list[float]]:
    """Midline of the AOI's outer ring: from the middle of its first edge to the middle of its third."""
    r = card.aoi.polygons()[0][0]
    a = [(r[0][0] + r[1][0]) / 2, (r[0][1] + r[1][1]) / 2]
    b = [(r[2][0] + r[3][0]) / 2, (r[2][1] + r[3][1]) / 2]
    return [[round(a[0], 6), round(a[1], 6)], [round(b[0], 6), round(b[1], 6)]]


def corridor_geojson(card: TaskCard) -> dict:
    return {"type": "Feature", "geometry": {"type": "LineString", "coordinates": corridor(card)},
            "properties": {"synthetic": True, "note": f"SYNTHETIC corridor (AOI midline); {NOTE}"}}


def points(card: TaskCard, scene: Item) -> list[dict]:
    """30 synthetic candidate points along the corridor, inside both the AOI and the scene footprint."""
    rng = np.random.default_rng([SEED, 52])
    (x0, y0), (x1, y1) = corridor(card)
    aoi, foot = card.aoi.polygons(), scene.footprint.polygons()
    dx, dy = (x1 - x0), (y1 - y0)
    n = math.hypot(dx, dy)
    nx, ny = -dy / n, dx / n  # unit normal in degree space
    classes = rng.permutation(["road_bridge"] * 12 + ["footbridge"] * 18)
    statuses = rng.permutation(["intact"] * 20 + ["damaged"] * 6 + ["destroyed"] * 4)
    obscured = set(rng.choice(N_POINTS, N_OBSCURED, replace=False).tolist())
    out = []
    for i in range(N_POINTS):
        while True:
            t = (i + 0.5) / N_POINTS + rng.uniform(-0.01, 0.01)
            off = rng.uniform(-150, 150) / M_PER_DEG
            lon, lat = round(x0 + t * dx + off * nx, 6), round(y0 + t * dy + off * ny, 6)
            if point_in_polygons(lon, lat, aoi) and point_in_polygons(lon, lat, foot):
                break
        out.append({"point_id": f"NP{i + 1:02d}", "lon": lon, "lat": lat, "cls": str(classes[i]),
                    "status": str(statuses[i]), "obscured": i in obscured, "synthetic": True, "note": NOTE})
    return out


def truth(card: TaskCard, scene: Item) -> dict:
    """The synthetic truth the recorded fake verifier and synthetic gold are drawn from (keys/synth/)."""
    body = {"id": "corridor-demo-truth", "task": card.id, "synthetic": True, "note": NOTE, "scene_id": scene.id,
            "points": points(card, scene)}
    return {**body, "version_hash": sha256_json(body)}


def window_args(scene_id: str, p: dict) -> dict:
    return {"scene_id": scene_id, "lon": p["lon"], "lat": p["lat"], "side_m": SIDE_M, "out_px": OUT_PX,
            "resampling": "average"}


def synthetic_pixels(window_id: str) -> np.ndarray:
    seed = int(sha256_json({"window": window_id})[7:23], 16)
    return np.random.default_rng(seed).integers(1, 256, (OUT_PX, OUT_PX), dtype=np.uint8)


def recorded_windows(card: TaskCard, scene: Item) -> list[dict]:
    """``{args, result}`` rows for ``RecordedImagerySource``: real scene id and pan GSD, computed bboxes and
    effective GSD, modelled bytes, synthetic pixel hashes and obscuration; ``synthetic: true`` on every row."""
    p_ = scene.raw["properties"]
    gsd = float(p_["pan_gsd"])
    level = max(0, math.floor(math.log2((SIDE_M / gsd) / OUT_PX))) if SIDE_M / gsd > OUT_PX else 0
    rng = np.random.default_rng([SEED, 53])
    rows = []
    for k, p in enumerate(points(card, scene)):
        dlon, dlat = m_to_deg(SIDE_M, p["lat"])
        bbox = (round(p["lon"] - dlon / 2, 7), round(p["lat"] - dlat / 2, 7), round(p["lon"] + dlon / 2, 7),
                round(p["lat"] + dlat / 2, 7))
        bright = round(float(rng.uniform(0.45, 0.8) if p["obscured"] else rng.uniform(0.0, 0.08)), 4)
        header = k == 0
        wid = f"vhr-{p['point_id']}"
        result = {
            "result_id": "", "source_id": next(d.source_id for d in card.data_allowlist if d.kind == "imagery"), "scene_id": scene.id, "etag": scene.etag,
            "bbox_requested": bbox, "bbox_read": bbox, "footprint_coverage_fraction": 1.0,
            "scene_datetime": p_["datetime"], "phase": "post", "nominal_gsd_m": gsd, "pixel_spacing_m": gsd,
            "effective_gsd_m": round(SIDE_M / OUT_PX, 6), "overview_level": level,
            "scene_cloud_pct": float(p_["eo:cloud_cover"]), "off_nadir_deg": p_.get("view:off_nadir"),
            "out_shape": (OUT_PX, OUT_PX), "resampling": "average",
            "pixel_sha256": array_sha256(synthetic_pixels(wid)), "bytes_read": BLOCK_BYTES + (HEADER_BYTES if header
                                                                                            else 0),
            "requests": 1 + int(header), "block_size": 512, "reader": "recorded",
            "obscuration": {"bright_lowvar_fraction": bright, "nodata_fraction": 0.0, "method": "heuristic:v1"},
            "license": scene.raw.get("license", "unknown"), "synthetic": True,
            "detail": {"bytes_model": BYTES_MODEL, "chip": "modelled bytes", "note": NOTE, "window_id": wid}}
        rows.append({"args": window_args(scene.id, p), "result": result})
    return rows
