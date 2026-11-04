"""PixelCache: the in-process side channel that carries pixels from a tool to the gateway (§0 row 21).

Tools put the decoded array; the cache keys it by ``array_sha256`` and keeps PNG bytes encoded at
``zlib_level``. The gateway reads the bytes to attach an ``Image`` block. Nothing here is persisted:
traces, cassettes and blobs only ever hold the sha256.
"""

from __future__ import annotations

import numpy as np

from treehouse.pixels import array_sha256
from treehouse.tools.png import encode_png


class PixelCache:
    def __init__(self, *, zlib_level: int = 6) -> None:
        self.zlib_level = zlib_level
        self._png: dict[str, bytes] = {}

    def put(self, arr: np.ndarray) -> str:
        if arr.ndim == 3 and arr.shape[2] == 1:
            arr = arr[:, :, 0]  # HxWx1 decodes as HxW; hash the shape that round-trips (judge D23)
        sha = array_sha256(arr)
        if sha not in self._png:
            self._png[sha] = encode_png(arr, level=self.zlib_level)
        return sha

    def get(self, sha: str) -> bytes | None:
        return self._png.get(sha)

    def __contains__(self, sha: str) -> bool:
        return sha in self._png

    def __len__(self) -> int:
        return len(self._png)
