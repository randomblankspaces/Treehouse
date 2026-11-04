"""ModelProvider protocol and the pixel rules every provider shares (OBS-B1).

Recorded and pixel-free sources attach ``Image(format, sha256, bytes_=None)``. ``ModelRequest.key()``
ignores ``bytes_``, so a live-recorded key equals its pixel-free replay key. Live adapters call
``require_pixels`` before sending and raise ``MissingPixels`` on a byte-less image; only
``ReplayProvider`` accepts one.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

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


def require_pixels(req: ModelRequest) -> None:
    """Raise MissingPixels if any image in ``req`` has no bytes. Call from every live adapter."""
    for i, img in iter_images(req.messages):
        if img.bytes_ is None:
            raise MissingPixels(f"message {i}: image {img.sha256} has no bytes; live providers need pixels")


def pixel_free(req: ModelRequest) -> ModelRequest:
    """The same request with every image's ``bytes_`` dropped (what cassettes store)."""
    return ModelRequest.model_validate(_strip_image_bytes(req.model_dump(mode="json")))


def pixel_free_response(resp: ModelResponse) -> ModelResponse:
    return ModelResponse.model_validate(_strip_image_bytes(resp.model_dump(mode="json")))
