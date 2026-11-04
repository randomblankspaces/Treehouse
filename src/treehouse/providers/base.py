"""ModelProvider protocol and the pixel rules every provider shares (OBS-B1).

Recorded and pixel-free sources attach ``Image(format, sha256, bytes_=None)``. ``ModelRequest.key()``
ignores ``bytes_``, so a live-recorded key equals its pixel-free replay key. Live adapters call
``require_pixels`` before sending and raise ``MissingPixels`` on a byte-less image; only
``ReplayProvider`` accepts one.
"""

from __future__ import annotations

import struct
import zlib
from collections.abc import Callable, Iterator
from typing import Protocol, runtime_checkable

import numpy as np

from treehouse.pixels import array_sha256
from treehouse.schemas.model_io import (
    Image,
    Message,
    ModelRequest,
    ModelResponse,
    ToolResult,
    _strip_image_bytes,
)


@runtime_checkable
class ModelProvider(Protocol):
    provider_name: str  # gen_ai.provider.name

    async def complete(self, req: ModelRequest, *, role: str, trial_index: int, turn: int) -> ModelResponse: ...


class ProviderError(RuntimeError):
    pass


class MissingPixels(ProviderError):
    """A live provider was handed an Image without bytes (only replay may see pixel-free images)."""


def iter_images(messages: list[Message]) -> Iterator[tuple[int, Image]]:
    """(message index, image) for every image, including images inside tool results."""
    for i, m in enumerate(messages):
        for b in m.content:
            if isinstance(b, Image):
                yield i, b
            elif isinstance(b, ToolResult):
                for c in b.content:
                    if isinstance(c, Image):
                        yield i, c


class PixelHashMismatch(ProviderError):
    """An image's bytes decode to pixels whose ``array_sha256`` differs from ``Image.sha256``."""


Decoder = Callable[[bytes, str], "np.ndarray | None"]


def decode_png(data: bytes, fmt: str) -> np.ndarray | None:
    """Decode an 8-bit, non-interlaced PNG (gray, gray+alpha, RGB, RGBA) to a uint8 array: ``(h, w)`` for
    gray, else ``(h, w, channels)``. Returns None for other formats (JPEG/GIF/WebP need a codec Treehouse does
    not ship; only the non-empty check applies to them). Raises ValueError on a malformed or unsupported PNG."""
    if fmt != "png":
        return None
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("not a PNG")
    pos, idat, ihdr = 8, [], None
    while pos + 8 <= len(data):
        (n,) = struct.unpack(">I", data[pos:pos + 4])
        tag, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if tag == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif tag == b"IDAT":
            idat.append(body)
        elif tag == b"IEND":
            break
    if ihdr is None:
        raise ValueError("PNG without IHDR")
    w, h, depth, ctype, _comp, _filt, interlace = ihdr
    chans = {0: 1, 2: 3, 4: 2, 6: 4}.get(ctype)
    if depth != 8 or chans is None or interlace:
        raise ValueError(f"unsupported PNG (depth {depth}, colour type {ctype}, interlace {interlace})")
    raw = zlib.decompress(b"".join(idat))
    stride = w * chans
    if len(raw) != h * (stride + 1):
        raise ValueError("PNG data length mismatch")
    out = np.zeros((h, stride), dtype=np.uint8)
    prev = np.zeros(stride, dtype=np.int32)
    for y in range(h):
        ft = raw[y * (stride + 1)]
        row = np.frombuffer(raw, dtype=np.uint8, count=stride, offset=y * (stride + 1) + 1).astype(np.int32)
        if ft == 0:
            rec = row
        elif ft == 2:
            rec = (row + prev) & 0xFF
        elif ft == 1:
            rec = (np.cumsum(row.reshape(w, chans), axis=0) & 0xFF).reshape(stride)
        elif ft in (3, 4):
            rec = row.copy()
            for x in range(stride):
                a = int(rec[x - chans]) if x >= chans else 0
                b = int(prev[x])
                if ft == 3:
                    pred = (a + b) >> 1
                else:
                    c = int(prev[x - chans]) if x >= chans else 0
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    pred = a if pa <= pb and pa <= pc else b if pb <= pc else c
                rec[x] = (rec[x] + pred) & 0xFF
        else:
            raise ValueError(f"bad PNG filter type {ft}")
        out[y] = rec
        prev = rec
    return out.reshape(h, w) if chans == 1 else out.reshape(h, w, chans)


def require_pixels(req: ModelRequest, *, decode: Decoder | None = None) -> None:
    """Raise MissingPixels if any image in ``req`` has no (or empty) bytes. Call from every live adapter.

    With ``decode`` (live adapters pass ``decode_png``), bytes that decode must reproduce ``Image.sha256``
    (``array_sha256`` of the decoded array), else ``PixelHashMismatch``; a format the decoder returns None for
    is checked for non-empty bytes only. TODO(P4): pass the imagery tool's own decoder once it lands."""
    for i, img in iter_images(req.messages):
        if not img.bytes_:
            raise MissingPixels(f"message {i}: image {img.sha256} has no bytes; live providers need pixels")
        if decode is not None:
            try:
                arr = decode(img.bytes_, img.format)
            except ValueError as e:
                raise PixelHashMismatch(f"message {i}: image {img.sha256} does not decode as {img.format}: {e}") \
                    from e
            if arr is not None and array_sha256(arr) != img.sha256:
                raise PixelHashMismatch(f"message {i}: decoded pixels hash to {array_sha256(arr)}, "
                                        f"not {img.sha256}")


def pixel_free(req: ModelRequest) -> ModelRequest:
    """The same request with every image's ``bytes_`` dropped (what cassettes store)."""
    return ModelRequest.model_validate(_strip_image_bytes(req.model_dump(mode="json")))


def pixel_free_response(resp: ModelResponse) -> ModelResponse:
    return ModelResponse.model_validate(_strip_image_bytes(resp.model_dump(mode="json")))
