"""Deterministic PNG transport and pixel identity (OBS-B2)."""

from __future__ import annotations

import numpy as np
import pytest

from treehouse.gateway.pixel_cache import PixelCache
from treehouse.pixels import array_sha256
from treehouse.tools.png import decode_png, encode_png


@pytest.mark.parametrize("shape", [(5, 7), (4, 3, 3)])
def test_round_trip_and_determinism(shape):
    a = np.random.default_rng(1).integers(0, 256, shape, dtype=np.uint8)
    assert np.array_equal(decode_png(encode_png(a)), a)
    assert encode_png(a) == encode_png(a)


def test_reencoding_changes_bytes_not_identity():
    a = (np.arange(64 * 64) % 251).astype(np.uint8).reshape(64, 64)
    b1, b9 = encode_png(a, level=1), encode_png(a, level=9)
    assert b1 != b9
    assert array_sha256(decode_png(b1)) == array_sha256(decode_png(b9)) == array_sha256(a)


def test_pixel_cache_keys_by_array_hash():
    a = np.zeros((8, 8), np.uint8)
    c1, c9 = PixelCache(zlib_level=1), PixelCache(zlib_level=9)
    assert c1.put(a) == c9.put(a) == array_sha256(a)
    assert np.array_equal(decode_png(c1.get(array_sha256(a))), a) and c1.get("sha256:none") is None


def test_rejects_non_uint8():
    with pytest.raises(ValueError):
        encode_png(np.zeros((2, 2), np.float32))


def test_hxwx1_hashes_as_the_hxw_it_decodes_to():  # judge D23
    import numpy as np

    from treehouse.gateway.pixel_cache import PixelCache
    from treehouse.pixels import array_sha256
    from treehouse.tools.png import decode_png

    a = np.arange(64, dtype=np.uint8).reshape(8, 8, 1)
    pc = PixelCache()
    sha = pc.put(a)
    assert sha == array_sha256(decode_png(pc.get(sha))) == array_sha256(a[:, :, 0])
