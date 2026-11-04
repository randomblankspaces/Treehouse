"""Pixel identity (OBS-B2): hash decoded pixels, never encoded PNG/JPEG bytes."""

from __future__ import annotations

import hashlib

import numpy as np


def array_sha256(arr: np.ndarray) -> str:
    """``sha256("uint8[<d0>x<d1>x...]\\n" + C-order bytes)`` of a decoded uint8 array.

    The shape string is part of the hash, so a reshape changes it; re-encoding at another zlib
    level does not. Used for ``Image.sha256`` and ``WindowResult.pixel_sha256``."""
    a = np.asarray(arr)
    if a.dtype != np.uint8:
        raise TypeError(f"pixel arrays must be uint8, got {a.dtype}")
    h = hashlib.sha256()
    h.update(("uint8[" + "x".join(str(d) for d in a.shape) + "]\n").encode())
    h.update(np.ascontiguousarray(a).tobytes(order="C"))
    return "sha256:" + h.hexdigest()
