"""TreehouseStrandsModel: a ``strands.models.Model`` whose every call is one of our ``ModelResponse`` turns.

Strands drives the conversation; the model never talks to Bedrock itself. ``stream`` hands the Strands
messages to ``call`` (the harness: request building, chat span, provider wrapper, cassette, spend, budget)
and replays the returned ``ModelResponse`` as Converse stream events. ``strands`` is imported lazily (§1).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from functools import cache
from typing import Any

from treehouse.schemas.model_io import ModelResponse, Reasoning, Text, ToolSpec, ToolUse

Call = Callable[[list[dict[str, Any]]], Awaitable[ModelResponse]]


def strands_spec(spec: ToolSpec) -> dict[str, Any]:
    return {"name": spec.name, "description": spec.description, "inputSchema": {"json": spec.input_schema}}


def stream_events(resp: ModelResponse) -> list[dict[str, Any]]:
    """Converse stream events for a response (text, reasoning and tool-use blocks)."""
    out: list[dict[str, Any]] = [{"messageStart": {"role": "assistant"}}]
    for b in resp.message.content:
        if isinstance(b, ToolUse):
            out.append({"contentBlockStart": {"start": {"toolUse": {"toolUseId": b.id, "name": b.name}}}})
            out.append({"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(b.input)}}}})
        elif isinstance(b, Text):
            out.append({"contentBlockDelta": {"delta": {"text": b.text}}})
        elif isinstance(b, Reasoning):
            out.append({"contentBlockDelta": {"delta": {"reasoningContent": {"text": b.text}}}})
            if b.signature:
                out.append({"contentBlockDelta": {"delta": {"reasoningContent": {"signature": b.signature}}}})
        else:
            continue
        out.append({"contentBlockStop": {}})
    u = resp.usage
    out.append({"messageStop": {"stopReason": resp.stop_reason}})
    out.append({"metadata": {"usage": {"inputTokens": u.input_tokens, "outputTokens": u.output_tokens,
                                       "totalTokens": u.input_tokens + u.output_tokens},
                             "metrics": {"latencyMs": resp.latency_ms}}})
    return out


@cache
def _model_class() -> type:
    from strands.models.model import Model

    class TreehouseStrandsModel(Model):
        def __init__(self, call: Call, model_id: str) -> None:
            self.call, self.config = call, {"model_id": model_id}

        def update_config(self, **model_config: Any) -> None:
            self.config.update(model_config)

        def get_config(self) -> dict[str, Any]:
            return self.config

        async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs: Any) -> AsyncIterator[dict]:
            # tool_specs/system_prompt are ignored: the harness sends the gateway's specs and its own system
            # prompt, so a Strands request hashes exactly like a PlainLoop request
            for ev in stream_events(await self.call(messages)):
                yield ev

        async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs: Any):
            raise NotImplementedError("Treehouse parses verdict JSON itself (verifier/); no Strands structured output")
            yield  # pragma: no cover - makes this an async generator as the base class declares

    return TreehouseStrandsModel


def TreehouseStrandsModel(call: Call, model_id: str) -> Any:  # noqa: N802 - reads as the class it builds
    return _model_class()(call, model_id)
