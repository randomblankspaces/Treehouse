"""The gateway interface the harness sees. The full ToolGateway (policy, meter, MCP servers) is P4."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Protocol, runtime_checkable

from pydantic import Field

from treehouse.schemas.base import Frozen
from treehouse.schemas.model_io import Image, Json, Text, ToolSpec

ToolContent = Annotated[Text | Image | Json, Field(discriminator="type")]


class ToolOutcome(Frozen):
    result_id: str | None
    status: Literal["success", "error", "blocked"]
    content: list[ToolContent]
    bytes_read: int = 0
    latency_ms: int = 0
    block_reason: str | None = None


@runtime_checkable
class Gateway(Protocol):
    def specs(self) -> list[ToolSpec]: ...

    async def call(self, name: str, args: dict[str, Any], *, call_id: str) -> ToolOutcome: ...
