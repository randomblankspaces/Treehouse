"""Deterministic numpy rendering of the synthetic scenes (uint8 grayscale, 2400 x 2400). SYNTHETIC.

Land ~90, water ~40, decks 200, rooftops 230, cloud 250 (low variance), outside the footprint 0
(nodata; valid pixels are clipped to >= 1). Damaged decks lose their middle third; destroyed decks are
gone. Pre scenes show every deck intact. Scenes are rendered lazily and cached per process.
"""

from __future__ import annotations

from functools import cache

import numpy as np

from treehouse.synth.world import (
    AOI,
    DECK_LEN_M,
    DECK_W_M,
    DEG_PER_PX,
    M_PER_DEG,
    M_PER_PX,
    NPX,
    RIVER_HALF_M,
    SCENES,
    SEED,
    crossings,
    distractors,
    pixel_of,
    river_slope,
    river_y,
)

LAND, WATER, DECK, ROOF, CLOUD = 90.0, 40.0, 200.0, 230.0, 250.0


def _box_px(b):
    c0, r1 = pixel_of(b[0], b[1])
    c1, r0 = pixel_of(b[2], b[3])
    return int(round(r0)), int(round(r1)), int(round(c0)), int(round(c1))


def _draw_deck(img: np.ndarray, c, status: str) -> None:
    if status == "destroyed":
        return
    cx, cy = pixel_of(c.lon, c.lat)
    rad = int(DECK_LEN_M / M_PER_PX) + 2
    r0, r1 = max(0, int(cy) - rad), min(NPX, int(cy) + rad + 1)
    c0, c1 = max(0, int(cx) - rad), min(NPX, int(cx) + rad + 1)
    rr, cc = np.mgrid[r0:r1, c0:c1]
    e = (cc + 0.5 - cx) * M_PER_PX
    n = -(rr + 0.5 - cy) * M_PER_PX
    u = e * c.ux + n * c.uy
    v = -e * c.uy + n * c.ux
    mask = (np.abs(u) <= DECK_LEN_M / 2) & (np.abs(v) <= DECK_W_M[c.cls] / 2)
    if status == "damaged":
        mask &= np.abs(u) > DECK_LEN_M / 6
    img[r0:r1, c0:c1][mask] = DECK


@cache
def render_scene(scene_id: str) -> np.ndarray:
    """The full scene as a read-only uint8 array of shape (NPX, NPX)."""
    s = SCENES[scene_id]
    rng = np.random.default_rng([SEED, 100, s.noise_key])
    img = LAND + rng.standard_normal((NPX, NPX), dtype=np.float32) * 6.0
    lon = AOI[0] + (np.arange(NPX) + 0.5) * DEG_PER_PX
    lat = AOI[3] - (np.arange(NPX) + 0.5) * DEG_PER_PX
    half = RIVER_HALF_M / M_PER_DEG * np.sqrt(1 + river_slope(lon) ** 2)
    water = np.abs(lat[:, None] - river_y(lon)[None, :]) <= half[None, :]
    img[water] = WATER + rng.standard_normal(int(water.sum()), dtype=np.float32) * 3.0
    for c in crossings():
        _draw_deck(img, c, c.status_post if s.phase == "post" else "intact")
    roof = int(round(5 / M_PER_PX))
    for x, y in distractors():
        cx, cy = pixel_of(x, y)
        img[int(cy) - roof:int(cy) + roof, int(cx) - roof:int(cx) + roof] = ROOF
    for b in s.clouds:
        r0, r1, c0, c1 = _box_px(b)
        img[r0:r1, c0:c1] = CLOUD + rng.standard_normal((r1 - r0, c1 - c0), dtype=np.float32)
    out = np.clip(np.rint(img), 1, 255).astype(np.uint8)
    if s.shift_px:
        out = np.roll(out, s.shift_px, axis=1)
    r0, r1, c0, c1 = _box_px(s.footprint)
    valid = np.zeros((NPX, NPX), dtype=bool)
    valid[r0:r1, c0:c1] = True
    out[~valid] = 0
    out.setflags(write=False)
    return out


@cache
def overview(scene_id: str, level: int) -> np.ndarray:
    """Level-``level`` overview: 2**level x 2**level block means of the full scene."""
    a = render_scene(scene_id)
    if level == 0:
        return a
    f = 2**level
    n = NPX // f
    o = a[: n * f, : n * f].reshape(n, f, n, f).mean(axis=(1, 3))
    o = np.rint(o).astype(np.uint8)
    o.setflags(write=False)
    return o
