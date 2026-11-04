"""``synth-crossings-v1``: the generated river-crossings world (IMPLEMENTATION-DESIGN §5.1). SYNTHETIC.

A 1.2 km AOI at "Null Island" ([0, 0, 0.0108, 0.0108], EPSG:4326) rendered at 2400 x 2400 px
(about 0.5 m). A 30 m river follows y = 0.0054 + 0.0018 sin(3 pi x / 0.0108). 40 crossings (24
road_bridge 6 x 15 m decks, 16 footbridge 2 x 15 m decks), at least 20 m apart, four of them in the
western 15 % strip that no clear post scene shows. 15 bright rooftops are distractors. Everything is
derived from ``SEED`` and is identical on every machine with the locked numpy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import cache

import numpy as np

from treehouse.canon import sha256_json
from treehouse.geo.geom import M_PER_DEG, bbox_ring, point_in_polygons

SEED = 20261104
WORLD_ID = "synth-crossings-v1"
AOI = (0.0, 0.0, 0.0108, 0.0108)
W = AOI[2] - AOI[0]
NPX = 2400
DEG_PER_PX = W / NPX
M_PER_PX = DEG_PER_PX * M_PER_DEG  # about 0.501 m
RIVER_HALF_M = 15.0
DECK_LEN_M = 15.0
DECK_W_M = {"road_bridge": 6.0, "footbridge": 2.0}
WEST_STRIP = 0.15 * W  # POST-A / POST-C miss x < WEST_STRIP
EAST_GAP = 0.80 * W  # POST-B misses x > EAST_GAP
EVENT_DATE = date(2026, 8, 26)
LICENSE = "LicenseRef-synthetic"
PAN_GSD_M = 0.5


def river_y(x):
    return 0.0054 + 0.0018 * np.sin(3 * np.pi * np.asarray(x) / W)


def river_slope(x):
    return 0.0018 * 3 * np.pi / W * np.cos(3 * np.pi * np.asarray(x) / W)


@dataclass(frozen=True)
class Crossing:
    id: str
    lon: float
    lat: float
    cls: str
    status_post: str  # intact | damaged | destroyed
    ux: float  # unit vector along the deck (east, north)
    uy: float

    def line(self) -> list[list[float]]:
        h = DECK_LEN_M / 2 / M_PER_DEG
        return [[self.lon - h * self.ux, self.lat - h * self.uy], [self.lon + h * self.ux, self.lat + h * self.uy]]


@dataclass(frozen=True)
class Scene:
    id: str
    datetime: datetime
    cloud_pct: float
    footprint: tuple[float, float, float, float]  # a box inside the AOI
    clouds: tuple[tuple[float, float, float, float], ...] = ()
    shift_px: int = 0
    noise_key: int = 0
    off_nadir_deg: float = 10.0
    sun_elevation_deg: float = 60.0

    @property
    def phase(self) -> str:
        return "post" if self.datetime.date() > EVENT_DATE else "pre"

    def footprint_polygons(self) -> list[list[list[tuple[float, float]]]]:
        return [[bbox_ring(self.footprint)]]

    def visible(self, lon: float, lat: float) -> bool:
        f = self.footprint
        inside = f[0] <= lon <= f[2] and f[1] <= lat <= f[3]
        return inside and not any(c[0] <= lon <= c[2] and c[1] <= lat <= c[3] for c in self.clouds)


def _dt(m: int, d: int, h: int = 10, mi: int = 0) -> datetime:
    return datetime(2026, m, d, h, mi, tzinfo=UTC)


_POST_FOOT = (WEST_STRIP, 0.0, W, W)
SCENES: dict[str, Scene] = {s.id: s for s in [
    Scene("SYN-PRE-1", _dt(7, 1), 0.0, AOI, noise_key=1),
    Scene("SYN-PRE-2", _dt(7, 15), 0.0, AOI, noise_key=2, off_nadir_deg=14.0),
    Scene("SYN-POST-A", _dt(8, 30), 3.0, _POST_FOOT, clouds=((0.0090, 0.0090, W, W),), noise_key=3),
    Scene("SYN-POST-B", _dt(8, 28), 70.0, (0.0, 0.0, EAST_GAP, W),
          clouds=((0.0, 0.0, WEST_STRIP, W), (WEST_STRIP, 0.2 * W, EAST_GAP, 0.83 * W)), noise_key=4),
    Scene("SYN-POST-C", _dt(8, 30, 10, 5), 3.0, _POST_FOOT, clouds=((0.0090, 0.0090, W, W),), shift_px=3,
          noise_key=5),
]}


def _river_normal(x: float) -> tuple[float, float]:
    s = float(river_slope(x))
    n = math.hypot(1.0, s)
    return (-s / n, 1.0 / n)  # perpendicular to the tangent (1, s)


@cache
def crossings() -> tuple[Crossing, ...]:
    rng = np.random.default_rng([SEED, 1])
    jit = 3.0 / M_PER_DEG
    west = [0.0003 + i * 0.0004 + rng.uniform(-jit, jit) for i in range(4)]
    start, span = 0.00175, 0.0106 - 0.00175
    east = [start + (i + 0.5) * span / 36 + rng.uniform(-jit, jit) for i in range(36)]
    xs = west + east
    classes = rng.permutation(["road_bridge"] * 24 + ["footbridge"] * 16)
    statuses = rng.permutation(["intact"] * 30 + ["damaged"] * 6 + ["destroyed"] * 4)
    out = []
    for i, x in enumerate(xs):
        ux, uy = _river_normal(x)
        out.append(Crossing(f"X{i + 1:02d}", round(x, 8), round(float(river_y(x)), 8), str(classes[i]),
                            str(statuses[i]), ux, uy))
    return tuple(out)


def _far_from_river(x: float, y: float, m: float) -> bool:
    xs = np.linspace(0, W, 400)
    d = np.hypot(xs - x, river_y(xs) - y).min() * M_PER_DEG
    return d > m


@cache
def distractors() -> tuple[tuple[float, float], ...]:
    """15 bright 10 x 10 m rooftops, at least 60 m from the river and 30 m from each other."""
    rng = np.random.default_rng([SEED, 2])
    pts: list[tuple[float, float]] = []
    margin = 20 / M_PER_DEG
    while len(pts) < 15:
        x, y = (float(v) for v in rng.uniform(margin, W - margin, 2))
        if _far_from_river(x, y, 60) and all(math.hypot(x - a, y - b) * M_PER_DEG > 30 for a, b in pts):
            pts.append((round(x, 8), round(y, 8)))
    return tuple(pts)


@cache
def canaries() -> tuple[tuple[float, float], ...]:
    """3 decoy key entries at empty coordinates (no crossing, no rooftop)."""
    rng = np.random.default_rng([SEED, 3])
    pts: list[tuple[float, float]] = []
    margin = 30 / M_PER_DEG
    while len(pts) < 3:
        x, y = (float(v) for v in rng.uniform(margin, W - margin, 2))
        others = [*distractors(), *pts]
        if _far_from_river(x, y, 100) and all(math.hypot(x - a, y - b) * M_PER_DEG > 40 for a, b in others):
            pts.append((round(x, 8), round(y, 8)))
    return tuple(pts)


def visible_in(c: Crossing) -> dict[str, bool]:
    """Whether a clear view of the deck exists in each scene (inside the footprint, not under cloud)."""
    return {sid: s.visible(c.lon, c.lat) for sid, s in SCENES.items()}


def build_key() -> dict:
    """The answer key (written to ``keys/synth/`` by P5's fixture script; never under a tool root)."""
    items = [{"id": c.id, "point": [c.lon, c.lat], "line": c.line(), "cls": c.cls, "status_post": c.status_post,
              "visible_in": visible_in(c), "canary": False} for c in crossings()]
    items += [{"id": f"CANARY-{i + 1}", "point": [x, y], "line": None, "cls": "road_bridge",
               "status_post": "intact", "visible_in": {}, "canary": True} for i, (x, y) in enumerate(canaries())]
    body = {"id": WORLD_ID, "seed": SEED, "synthetic": True, "crossings": items}
    return {**body, "version_hash": sha256_json(body)}


def pixel_of(lon: float, lat: float) -> tuple[float, float]:
    """(column, row) in native pixels, continuous; row 0 is the northern edge."""
    return (lon - AOI[0]) / DEG_PER_PX, (AOI[3] - lat) / DEG_PER_PX


def in_footprint(scene: Scene, lon: float, lat: float) -> bool:
    return point_in_polygons(lon, lat, scene.footprint_polygons())


def stac_item(scene: Scene) -> dict:
    """A STAC-like item for the static synthetic fixture (metadata only)."""
    body = {"type": "Feature", "stac_version": "1.0.0", "id": scene.id,
            "bbox": list(scene.footprint),
            "geometry": {"type": "Polygon", "coordinates": [[list(p) for p in bbox_ring(scene.footprint)]]},
            "properties": {"datetime": scene.datetime.isoformat().replace("+00:00", "Z"), "treehouse:phase":
                           scene.phase, "eo:cloud_cover": scene.cloud_pct, "pan_gsd": PAN_GSD_M,
                           "view:off_nadir": scene.off_nadir_deg, "view:sun_elevation": scene.sun_elevation_deg,
                           "treehouse:synthetic": True},
            "assets": {"visual": {"href": f"synthetic://{WORLD_ID}/{scene.id}", "type": "synthetic/raster"}},
            "license": LICENSE}
    etag = "synthetic-" + sha256_json(body)[7:23]
    body["assets"]["visual"]["etag"] = etag
    return body
