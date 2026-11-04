"""Provider-neutral model request/response records."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field

from treehouse.canon import sha256_json
from treehouse.schemas.base import Frozen
from treehouse.schemas.config import InferenceParams


class Text(Frozen):
    type: Literal["text"] = "text"
    text: str


class Image(Frozen):
    """An image block. ``sha256`` hashes the decoded C-order uint8 pixel array plus its shape,
    not the encoded bytes, so re-encoding never changes it. ``bytes_`` is transport only and is
    excluded from request keys and cassettes."""

    model_config = ConfigDict(frozen=True, extra="forbid", ser_json_bytes="base64", val_json_bytes="base64")
    type: Literal["image"] = "image"
    format: Literal["png", "jpeg"]
    sha256: str
    bytes_: bytes | None = None


class Json(Frozen):
    type: Literal["json"] = "json"
    json_: dict[str, Any]


class ToolUse(Frozen):
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any]


class ToolResult(Frozen):
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    status: Literal["success", "error"]
    content: list[Annotated[Text | Image | Json, Field(discriminator="type")]]


class Reasoning(Frozen):
    type: Literal["reasoning"] = "reasoning"
    text: str
    signature: str | None = None


Block = Annotated[Text | Image | ToolUse | ToolResult | Reasoning, Field(discriminator="type")]


class Message(Frozen):
    role: Literal["user", "assistant"]
    content: list[Block]


class ToolSpec(Frozen):
    name: str
    description: str
    input_schema: dict[str, Any]


def _strip_image_bytes(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_image_bytes(v) for k, v in obj.items() if not (obj.get("type") == "image" and k == "bytes_")}
    if isinstance(obj, list):
        return [_strip_image_bytes(v) for v in obj]
    return obj


class ModelRequest(Frozen):
    model_id: str
    system: str
    messages: list[Message]
    tools: list[ToolSpec] = []
    params: InferenceParams

    def key(self) -> str:
        """sha256 of the canonical request with image bytes replaced by their pixel sha256 only."""
        return sha256_json(_strip_image_bytes(self.model_dump(mode="json")))


class Usage(Frozen):
    input_tokens: int
    output_tokens: int
    cache_read: int = 0
    cache_write: int = 0
    image_input_tokens: int | None = None


class ProviderEvent(Frozen):
    """A span event raised inside a provider call (e.g. ``treehouse.retry``); the harness copies it onto the
    chat span."""

    name: str
    attributes: dict[str, Any] = {}


class ModelResponse(Frozen):
    message: Message
    # fact-check F3: every Bedrock stopReason is kept as-is (never folded into end_turn); "guardrail" is the
    # provider-neutral spelling used by fake scripts
    stop_reason: Literal["end_turn", "tool_use", "max_tokens", "stop_sequence", "content_filtered", "guardrail",
                         "guardrail_intervened", "malformed_model_output", "malformed_tool_use",
                         "model_context_window_exceeded"]
    usage: Usage
    latency_ms: int
    response_model_id: str
    request_id: str | None = None
    # set by live providers from the SpendLedger commit; cassettes keep them, replay reports them but the
    # SpendLedger is charged $0
    cost_usd: float | None = None
    price_table_version: str | None = None
    events: list[ProviderEvent] = []
