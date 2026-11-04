"""Overview-aware modelled bytes (§0 row 6, RS-B1, I3 order checks, fact-check F7).

The 2400 px synthetic scene has overview factors 2 and 4 only (F7: halving stops before a level is
narrower than one 512 px block), so L is capped at 2. The cap does not change the I3 centre counts:
good 60 m/128 px reads 1 block at L0, skimmer 1000 m/256 px reads 4 blocks at L2 and 1000 m/2048 px
reads 25 blocks at L0.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np

from treehouse.gateway.pixel_cache import PixelCache
from treehouse.synth import world
from treehouse.tools.sources.synthetic import (
    BLOCK_BYTES,
    HEADER_BYTES,
    SyntheticImagerySource,
    blocks_at,
    max_overview_level,
    overview_level,
)

NP = world.NPX


def native(side_m: float) -> float:
    return side_m / world.M_PER_PX


def blocks(side_m, out_px, cx, cy):
    return blocks_at(overview_level(native(side_m), out_px, NP), cx, cy, native(side_m), NP)


def test_overviews_limited_by_scene_size():
    assert max_overview_level(2400) == 2 and max_overview_level(8192) == 4 and max_overview_level(511) == 0
    assert overview_level(native(1000), 64, NP) == 2  # would be 4 without the F7 cap


def test_exact_centre_counts():
    c = NP / 2
    assert (blocks(60, 128, c, c), blocks(1000, 256, c, c), blocks(1000, 2048, c, c)) == (1, 4, 25)


def test_i3_order_checks_over_random_centres():
    rng = np.random.default_rng(20261104)
    half = native(1000) / 2
    for cx, cy in rng.uniform(half, NP - half, (2000, 2)):
        good, skim, big = blocks(60, 128, cx, cy), blocks(1000, 256, cx, cy), blocks(1000, 2048, cx, cy)
        assert skim <= 4 * good
        assert big >= 4 * skim


def test_bytes_read_is_the_block_model_sum_with_one_header_per_scene():
    src = SyntheticImagerySource(allowed=list(world.SCENES), as_of=datetime(2026, 9, 15, tzinfo=UTC),
                                 pixels=PixelCache(), max_side_m=1000, max_out_px=4096)
    c = world.AOI[2] / 2
    r1 = src.window("SYN-PRE-1", c, c, 60, 128, "average")
    r2 = src.window("SYN-PRE-1", c, c, 1000, 256, "average")
    r3 = src.window("SYN-PRE-2", c, c, 1000, 2048, "average")
    assert r1.bytes_read == BLOCK_BYTES + HEADER_BYTES and r1.requests == 2
    assert r2.bytes_read == 4 * BLOCK_BYTES and r2.detail["header"] is False
    assert r3.bytes_read == 25 * BLOCK_BYTES + HEADER_BYTES
    assert src.bytes_total == r1.bytes_read + r2.bytes_read + r3.bytes_read
    for r in (r1, r2, r3):
        assert r.detail["bytes_model"] == "synthetic-overview-block-v1" and r.reader == "synthetic-v1"
    assert r3.out_shape == (2048, 2048) and r1.effective_gsd_m == 60 / 128
