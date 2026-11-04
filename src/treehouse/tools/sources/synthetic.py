"""SyntheticImagerySource: windows cut from the numpy-rendered ``synth-crossings-v1`` scenes.

``bytes_read`` is modelled, not measured (§0 row 6, RS-B1, fact-check F7): overview level
``L = max(0, floor(log2(native_px_per_side / out_px)))`` capped at the overviews the scene would have
(halving while the level is still >= one 512 px block wide: the 2400 px scene has factors 2 and 4 only),
then the 512 px blocks the window intersects at level L, x 48 KiB, plus a 16 KiB header on the first
read of each scene. Results carry ``reader="synthetic-v1"`` and ``detail.bytes_model``.
"""

from __future__ import annotations

import math
from datetime import datetime

import numpy as np

from treehouse.gateway.pixel_cache import PixelCache
from treehouse.geo.geom import coverage_fraction, m_to_deg
from treehouse.schemas.tools import Obscuration, ToolError, WindowResult
from treehouse.synth import world
from treehouse.synth.render import overview

BLOCK = 512
BLOCK_BYTES = 48 * 1024
HEADER_BYTES = 16 * 1024
BYTES_MODEL = "synthetic-overview-block-v1"
MIN_COVERAGE = 0.5


def max_overview_level(npx: int, block: int = BLOCK) -> int:
    level = 0
    while npx // 2 ** (level + 1) >= block:
        level += 1
    return level


def overview_level(native_px: float, out_px: int, npx: int) -> int:
    want = max(0, math.floor(math.log2(native_px / out_px))) if native_px > out_px else 0
    return min(want, max_overview_level(npx))


def blocks_at(level: int, cx: float, cy: float, native_px: float, npx: int) -> int:
    """512 px blocks intersected at ``level`` by a square window of ``native_px`` centred at native
    pixel (cx, cy), clipped to the level's raster."""
    f = 2**level
    size = npx // f
    half = native_px / 2 / f

    def span(c: float) -> int:
        lo, hi = max(0.0, c / f - half), min(float(size), c / f + half)
        if hi <= lo:
            return 0
        return math.floor((math.ceil(hi) - 1) / BLOCK) - math.floor(math.floor(lo) / BLOCK) + 1

    return span(cx) * span(cy)


def resample(a: np.ndarray, out_px: int, method: str) -> np.ndarray:
    h, w = a.shape
    if method == "nearest":
        ri = np.minimum((np.arange(out_px) + 0.5) * h / out_px, h - 1).astype(int)
        ci = np.minimum((np.arange(out_px) + 0.5) * w / out_px, w - 1).astype(int)
        return a[np.ix_(ri, ci)]
    re = np.floor(np.linspace(0, h, out_px + 1)).astype(int)[:-1]
    ce = np.floor(np.linspace(0, w, out_px + 1)).astype(int)[:-1]
    s = np.add.reduceat(np.add.reduceat(a.astype(np.float64), re, axis=0), ce, axis=1)
    rn, cn = np.diff(np.append(re, h)), np.diff(np.append(ce, w))
    rn, cn = np.where(rn > 0, rn, 1), np.where(cn > 0, cn, 1)  # upsampling: repeated edges pick one pixel
    return np.rint(s / np.outer(rn, cn)).clip(0, 255).astype(np.uint8)


def obscuration(a: np.ndarray, tile: int = 8) -> Obscuration:
    n = (a.shape[0] // tile) * tile
    t = a[:n, :n].astype(np.float32).reshape(n // tile, tile, n // tile, tile)
    bright = (t.mean(axis=(1, 3)) > 235) & (t.std(axis=(1, 3)) < 5)
    return Obscuration(bright_lowvar_fraction=round(float(bright.mean()), 6),
                       nodata_fraction=round(float((a == 0).mean()), 6))


class SyntheticImagerySource:
    source_id = "synth-imagery"

    def __init__(self, *, allowed: list[str], as_of: datetime, pixels: PixelCache, max_side_m: float,
                 max_out_px: int, max_bytes: int | None = None) -> None:
        self.allowed, self.as_of, self.pixels = set(allowed), as_of, pixels
        self.max_side_m, self.max_out_px, self.max_bytes = max_side_m, max_out_px, max_bytes
        self.bytes_total = 0
        self._opened: set[str] = set()

    def window(self, scene_id: str, lon: float, lat: float, side_m: float, out_px: int,
               resampling: str) -> WindowResult | ToolError:
        s = world.SCENES.get(scene_id)
        if s is None or scene_id not in self.allowed:
            return ToolError(code="not_allowed", message=f"scene {scene_id} is not on the allow-list")
        if s.datetime > self.as_of:
            return ToolError(code="not_available_as_of", message=f"scene {scene_id} is after as_of")
        if side_m > self.max_side_m or out_px > self.max_out_px:
            return ToolError(code="window_too_large",
                             message=f"limits are side_m <= {self.max_side_m} and out_px <= {self.max_out_px}")
        a = world.AOI
        if not (a[0] <= lon <= a[2] and a[1] <= lat <= a[3]):
            return ToolError(code="out_of_bounds", message="window centre is outside the scene raster")
        dlon, dlat = m_to_deg(side_m, lat)
        req = (lon - dlon / 2, lat - dlat / 2, lon + dlon / 2, lat + dlat / 2)
        read = (max(req[0], a[0]), max(req[1], a[1]), min(req[2], a[2]), min(req[3], a[3]))
        win = [[[(req[0], req[1]), (req[2], req[1]), (req[2], req[3]), (req[0], req[3]), (req[0], req[1])]]]
        cov = coverage_fraction(s.footprint_polygons(), win, n=16)
        if cov == 0:
            return ToolError(code="no_coverage", message=f"scene {scene_id} has no pixels in this window")
        if cov < MIN_COVERAGE:
            return ToolError(code="insufficient_coverage", message=f"scene covers {cov:.0%} of the window")
        native_px = side_m / world.M_PER_PX
        level = overview_level(native_px, out_px, world.NPX)
        cx, cy = world.pixel_of(lon, lat)
        n_blocks = blocks_at(level, cx, cy, native_px, world.NPX)
        header = scene_id not in self._opened
        nbytes = n_blocks * BLOCK_BYTES + (HEADER_BYTES if header else 0)
        if self.max_bytes is not None and self.bytes_total + nbytes > self.max_bytes:
            return ToolError(code="budget_exceeded", message=f"max_bytes_per_run={self.max_bytes} would be passed")
        self._opened.add(scene_id)
        self.bytes_total += nbytes
        arr = resample(self._cut(scene_id, level, cx, cy, native_px), out_px, resampling)
        sha = self.pixels.put(arr)
        return WindowResult(
            result_id="", source_id=self.source_id, scene_id=scene_id, etag=world.stac_item(s)["assets"]["visual"]
            ["etag"], bbox_requested=req, bbox_read=read, footprint_coverage_fraction=round(cov, 6),
            scene_datetime=s.datetime, phase=s.phase, nominal_gsd_m=world.PAN_GSD_M,
            pixel_spacing_m=round(world.M_PER_PX * 2**level, 6), effective_gsd_m=round(side_m / out_px, 6),
            overview_level=level, scene_cloud_pct=s.cloud_pct, off_nadir_deg=s.off_nadir_deg,
            out_shape=(out_px, out_px), resampling=resampling, pixel_sha256=sha, bytes_read=nbytes,
            requests=n_blocks + int(header), block_size=BLOCK, reader="synthetic-v1", obscuration=obscuration(arr),
            license=world.LICENSE, synthetic=True,
            detail={"bytes_model": BYTES_MODEL, "blocks": n_blocks, "header": header, "chip": "modelled bytes"})

    @staticmethod
    def _cut(scene_id: str, level: int, cx: float, cy: float, native_px: float) -> np.ndarray:
        """The window at ``level``, padded with nodata (0) where it leaves the raster."""
        src = overview(scene_id, level)
        f = 2**level
        half = native_px / 2 / f
        n = max(1, int(round(2 * half)))
        r0, c0 = int(math.floor(cy / f - half)), int(math.floor(cx / f - half))
        out = np.zeros((n, n), np.uint8)
        rs, cs = max(0, r0), max(0, c0)
        re, ce = min(src.shape[0], r0 + n), min(src.shape[1], c0 + n)
        if re > rs and ce > cs:
            out[rs - r0:re - r0, cs - c0:ce - c0] = src[rs:re, cs:ce]
        return out
