"""Deterministic PNG encode/decode for model-facing image blocks (transport only, OBS-B2).

No timestamps or text chunks, filter type 0 on every row, so the same array and zlib level always give
the same bytes. Identity is ``pixels.array_sha256`` of the decoded array, never of these bytes, so
re-encoding at another zlib level changes nothing that enters keys, traces or heads.
"""

from __future__ import annotations

import struct
import zlib

import numpy as np

SIGNATURE = b"\x89PNG\r\n\x1a\n"
_COLOR = {1: 0, 3: 2}  # channels -> PNG colour type (grey, RGB)


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def encode_png(arr: np.ndarray, *, level: int = 6) -> bytes:
    a = np.ascontiguousarray(arr)
    if a.dtype != np.uint8 or a.ndim not in (2, 3) or (a.ndim == 3 and a.shape[2] not in (1, 3)):
        raise ValueError(f"need uint8 HxW or HxWx{{1,3}}, got {a.dtype} {a.shape}")
    h, w = a.shape[:2]
    ch = 1 if a.ndim == 2 else a.shape[2]
    rows = a.reshape(h, w * ch)
    raw = np.hstack([np.zeros((h, 1), np.uint8), rows]).tobytes()
    ihdr = struct.pack(">IIBBBBB", w, h, 8, _COLOR[ch], 0, 0, 0)
    return SIGNATURE + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(raw, level)) + _chunk(b"IEND", b"")


def decode_png(data: bytes) -> np.ndarray:
    """Decode PNGs written by ``encode_png`` (8-bit grey or RGB, filter type 0 only)."""
    if not data.startswith(SIGNATURE):
        raise ValueError("not a PNG")
    pos, idat, hdr = 8, b"", None
    while pos < len(data):
        (n,) = struct.unpack(">I", data[pos:pos + 4])
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b"IHDR":
            hdr = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
    if hdr is None:
        raise ValueError("PNG without IHDR")
    w, h, depth, color = hdr[0], hdr[1], hdr[2], hdr[3]
    ch = {0: 1, 2: 3}[color]
    rows = np.frombuffer(zlib.decompress(idat), np.uint8).reshape(h, 1 + w * ch)
    if depth != 8 or rows[:, 0].any():
        raise ValueError("only 8-bit, filter-0 PNGs are supported")
    px = rows[:, 1:].copy()
    return px.reshape(h, w) if ch == 1 else px.reshape(h, w, ch)
