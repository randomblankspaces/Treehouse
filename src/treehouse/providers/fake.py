"""FakeProvider: scripted responses for offline tests and the demo.

A script is a list of ``{expect, respond}`` steps indexed by ``turn`` (the same script serves every
trial), or a callable ``fn(req, *, role, trial_index, turn) -> respond-dict | ModelResponse``.

``expect`` keys: ``contains`` (str or list; substrings of the last message), ``n_messages``,
``tool_result_for`` (a tool_use id answered in the last message), ``request_key``.
``respond`` keys: ``text``, ``tool_use`` (list of ``{name, input, id?}``), ``stop_reason``.
Tokens are ``len(text) // 4``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from treehouse.canon import canonical_json
from treehouse.providers.base import pixel_free
from treehouse.schemas.model_io import (
    Image,
    Json,
    Message,
    ModelRequest,
    ModelResponse,
    Text,
    ToolResult,
    ToolUse,
    Usage,
)

EXPECT_KEYS = {"contains", "n_messages", "tool_result_for", "request_key"}
RESPOND_KEYS = {"text", "tool_use", "stop_reason"}


class ScriptDivergence(AssertionError):
    """The request does not match what the script expected at this turn."""


def render_message(m: Message) -> str:
    """Plain text view of a message, used by ``expect.contains``."""
    out: list[str] = []
    for b in m.content:
        if isinstance(b, Text):
            out.append(b.text)
        elif isinstance(b, ToolUse):
            out.append(f"{b.name} {canonical_json(b.input)}")
        elif isinstance(b, ToolResult):
            for c in b.content:
                if isinstance(c, Text):
                    out.append(c.text)
                elif isinstance(c, Json):
                    out.append(canonical_json(c.json_))
                elif isinstance(c, Image):
                    out.append(f"image {c.sha256}")
    return "\n".join(out)


class FakeProvider:
    provider_name = "fake"

    def __init__(self, script: list[dict[str, Any]] | Callable[..., Any]) -> None:
        self._fn = script if callable(script) else None
        self._steps: list[dict[str, Any]] = [] if callable(script) else list(script)
        for i, step in enumerate(self._steps):
            bad = (set(step) - {"expect", "respond"}) | (set(step.get("expect") or {}) - EXPECT_KEYS)
            bad |= set(step.get("respond") or {}) - RESPOND_KEYS
            if bad or "respond" not in step:
                raise ValueError(f"script step {i}: unknown or missing keys {sorted(bad) or ['respond']}")

    @classmethod
    def from_yaml(cls, text_or_path: str | Path) -> FakeProvider:
        """A ``Path`` or a one-line string is a file path (which must exist); multi-line text is YAML."""
        s = str(text_or_path)
        if isinstance(text_or_path, Path) or ("\n" not in s.strip() and not s.lstrip().startswith(("-", "["))):
            p = Path(s)
            if not p.is_file():
                raise FileNotFoundError(f"fake script not found: {s}")
            s = p.read_text(encoding="utf-8")
        steps = yaml.safe_load(s) or []
        if not isinstance(steps, list):
            raise ValueError("a fake script is a YAML list of {expect, respond} steps")
        return cls(steps)

    async def complete(self, req: ModelRequest, *, role: str, trial_index: int, turn: int) -> ModelResponse:
        if self._fn is not None:
            out = self._fn(req, role=role, trial_index=trial_index, turn=turn)
        else:
            if turn >= len(self._steps):
                raise ScriptDivergence(f"script exhausted at turn {turn} ({len(self._steps)} steps)")
            step = self._steps[turn]
            self._check(step.get("expect") or {}, req, turn)
            out = step["respond"]
        if isinstance(out, ModelResponse):
            return out
        bad = set(out) - RESPOND_KEYS if isinstance(out, dict) else {"<not a dict>"}
        if bad:
            raise ValueError(f"turn {turn}: script response has unknown keys {sorted(bad)}")
        return self._response(req, out, trial_index, turn)

    @staticmethod
    def _check(expect: dict[str, Any], req: ModelRequest, turn: int) -> None:
        last = render_message(req.messages[-1]) if req.messages else ""
        wanted = expect.get("contains", [])
        for s in [wanted] if isinstance(wanted, str) else wanted:
            if s not in last:
                raise ScriptDivergence(f"turn {turn}: last message does not contain {s!r}")
        if "n_messages" in expect and len(req.messages) != expect["n_messages"]:
            raise ScriptDivergence(f"turn {turn}: {len(req.messages)} messages, expected {expect['n_messages']}")
        if "tool_result_for" in expect:
            ids = [b.tool_use_id for b in req.messages[-1].content if isinstance(b, ToolResult)]
            if expect["tool_result_for"] not in ids:
                raise ScriptDivergence(f"turn {turn}: no tool result for {expect['tool_result_for']!r}")
        if "request_key" in expect and req.key() != expect["request_key"]:
            raise ScriptDivergence(f"turn {turn}: request key {req.key()} != {expect['request_key']}")

    @staticmethod
    def _response(req: ModelRequest, out: dict[str, Any], trial_index: int, turn: int) -> ModelResponse:
        blocks: list[Any] = []
        text = out.get("text") or ""
        if text:
            blocks.append(Text(text=text))
        out_text = text
        for k, tu in enumerate(out.get("tool_use") or []):
            blocks.append(ToolUse(id=tu.get("id") or f"tu-{trial_index}-{turn}-{k}", name=tu["name"],
                                  input=tu.get("input") or {}))
            out_text += canonical_json(tu.get("input") or {})
        has_tools = any(isinstance(b, ToolUse) for b in blocks)
        stop = out.get("stop_reason") or ("tool_use" if has_tools else "end_turn")
        return ModelResponse(
            message=Message(role="assistant", content=blocks),
            stop_reason=stop,
            usage=Usage(input_tokens=len(canonical_json(pixel_free(req))) // 4, output_tokens=len(out_text) // 4),
            latency_ms=0,
            response_model_id=req.model_id,
        )
