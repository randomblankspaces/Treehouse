"""StrandsHarness (W2): a native ``strands.Agent`` runs the loop; Treehouse keeps the guarantees.

- Model: ``TreehouseStrandsModel`` over our ``ModelProvider``; each call is ``chat_turn`` (same chat span,
  blobs, spend, budget, cassette key ``(role, trial_index, turn)`` as PlainLoop).
- Tools: one ``AgentTool`` per gateway spec; each call is ``gateway.call`` (policy, budget, meter, tool cassette).
- ``SequentialToolExecutor`` keeps tool order; ``NullConversationManager`` keeps every message; no Strands
  retries (the provider wrapper owns retries); ``callback_handler=None``.

Exact requests: the request is rebuilt from the Strands messages, but assistant turns and tool results use the
objects we produced (side channel), so images keep ``sha256``/``bytes_`` and the request key equals PlainLoop's.

Errors: Strands turns a tool exception into an error result and keeps going, so the tool adapter stashes any
exception (BudgetExceeded included) and the next model call re-raises it before opening a span; the harness
unwraps ``EventLoopException`` and then behaves exactly like PlainLoop. Known gap: on ``max_tokens`` Strands
raises before running that turn's tool uses (PlainLoop would run them); the run still ends ``stop="error"``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from treehouse.gateway.base import Gateway
from treehouse.gateway.budget import BudgetExceeded, BudgetGuard
from treehouse.harness.base import HarnessResult, Stop
from treehouse.harness.plain_loop import DONE, chat_turn, put_blob, text_of
from treehouse.providers.base import ModelProvider, ProviderError
from treehouse.providers.strands_model import TreehouseStrandsModel, strands_spec
from treehouse.schemas.config import InferenceParams
from treehouse.schemas.model_io import (
    Image,
    Json,
    Message,
    ModelRequest,
    ModelResponse,
    Text,
    ToolResult,
    ToolSpec,
    ToolUse,
)
from treehouse.trace.tracer import TrialTracer


class _MaxTurns(Exception):
    pass


class _State:
    def __init__(self) -> None:
        self.turn = 0
        self.assistant: list[Message] = []
        self.results: dict[str, ToolResult] = {}
        self.last: ModelResponse | None = None
        self.halt: BaseException | None = None


def _strands_content(c: Text | Image | Json) -> dict[str, Any]:
    if isinstance(c, Text):
        return {"text": c.text}
    if isinstance(c, Json):
        return {"json": c.json_}
    return {"text": f"image {c.sha256}"}  # pixels ride the side channel, never through Strands


def to_messages(smsgs: list[dict[str, Any]], st: _State) -> list[Message]:
    out, k = [], 0
    for m in smsgs:
        if m["role"] == "assistant":
            if k >= len(st.assistant):
                raise ProviderError("Strands sent an assistant message Treehouse did not produce")
            out.append(st.assistant[k])
            k += 1
            continue
        blocks: list[Any] = []
        for b in m["content"]:
            if "text" in b:
                blocks.append(Text(text=b["text"]))
            elif "toolResult" in b:
                tr = b["toolResult"]
                blocks.append(st.results.get(tr["toolUseId"]) or ToolResult(  # a result Strands made up itself
                    tool_use_id=tr["toolUseId"], status="error",
                    content=[Text(text=str(c.get("text", c))) for c in tr.get("content", [])]))
            else:
                raise ProviderError(f"unsupported Strands content block {sorted(b)}")
        out.append(Message(role="user", content=blocks))
    return out


def gateway_tools(gateway: Gateway, st: _State) -> tuple[list[Any], Callable[[str], Any]]:
    """Strands tools that call ``gateway.call`` (the gateway's specs are the only tool definitions), plus a
    factory for names the gateway does not list: PlainLoop sends those to the gateway too, which refuses them
    on the trace (``not_allowlisted``/``unknown_tool``), so Strands must not answer them itself."""
    from strands.types.tools import AgentTool

    class GatewayTool(AgentTool):
        def __init__(self, spec) -> None:
            super().__init__()
            self._spec = spec

        @property
        def tool_name(self) -> str:
            return self._spec.name

        @property
        def tool_spec(self) -> dict[str, Any]:
            return strands_spec(self._spec)

        @property
        def tool_type(self) -> str:
            return "treehouse_gateway"

        async def stream(self, tool_use, invocation_state, **kwargs: Any):
            tid = tool_use["toolUseId"]
            if st.halt is not None:  # PlainLoop stops at the first failing call; skip the rest of the turn
                yield {"toolUseId": tid, "status": "error", "content": [{"text": "halted"}]}
                return
            try:
                out = await gateway.call(tool_use["name"], tool_use.get("input") or {}, call_id=tid)
            except BaseException as e:  # noqa: BLE001 - re-raised by the next model call (see module doc)
                st.halt = e
                yield {"toolUseId": tid, "status": "error", "content": [{"text": "halted"}]}
                return
            tr = ToolResult(tool_use_id=tid, status="success" if out.status == "success" else "error",
                            content=out.content)
            st.results[tid] = tr
            yield {"toolUseId": tid, "status": tr.status, "content": [_strands_content(c) for c in tr.content]}

    def unlisted(name: str) -> Any:
        return GatewayTool(ToolSpec(name=name, description="", input_schema={"type": "object"}))

    return [GatewayTool(s) for s in gateway.specs()], unlisted


def _root(e: BaseException) -> BaseException:
    from strands.types.exceptions import EventLoopException

    while isinstance(e, EventLoopException):
        e = e.original_exception
    return e


class StrandsHarness:
    name = "strands"
    version = "1"

    def __init__(self, *, model_id: str, params: InferenceParams,
                 blob_sink: Callable[[bytes], str] | None = None) -> None:
        self.model_id, self.params, self.blob_sink = model_id, params, blob_sink

    async def run(self, *, system: str, user: str, provider: ModelProvider, gateway: Gateway, tracer: TrialTracer,
                  budget: BudgetGuard, max_turns: int, role: str, trial_index: int) -> HarnessResult:
        from strands import Agent
        from strands.agent.conversation_manager import NullConversationManager
        from strands.hooks import BeforeToolCallEvent
        from strands.tools.executors import SequentialToolExecutor
        from strands.types.exceptions import MaxTokensReachedException

        st = _State()

        async def call(smsgs: list[dict[str, Any]]) -> ModelResponse:
            if st.halt is not None:
                raise st.halt
            if st.turn >= max_turns:
                raise _MaxTurns
            budget.check()
            req = ModelRequest(model_id=self.model_id, system=system, messages=to_messages(smsgs, st),
                               tools=gateway.specs(), params=self.params)
            resp = await chat_turn(req, provider=provider, tracer=tracer, budget=budget,
                                   put=lambda b: put_blob(self.blob_sink, b), role=role, trial_index=trial_index,
                                   turn=st.turn)
            st.turn += 1
            st.assistant.append(resp.message)
            st.last = resp
            return resp

        tools, unlisted = gateway_tools(gateway, st)
        agent = Agent(model=TreehouseStrandsModel(call, self.model_id), tools=tools, system_prompt=system,
                      tool_executor=SequentialToolExecutor(), callback_handler=None,
                      conversation_manager=NullConversationManager(), retry_strategy=None)

        def route_unlisted(event: BeforeToolCallEvent) -> None:
            if event.selected_tool is None:
                event.selected_tool = unlisted(event.tool_use["name"])
        agent.hooks.add_callback(BeforeToolCallEvent, route_unlisted)
        stop: Stop = "max_turns"
        detail: str | None = None
        finished = False
        with tracer.span(f"invoke_agent {role}", "invoke_agent",
                         {"gen_ai.agent.name": role, "treehouse.harness": f"{self.name}/{self.version}"}) as span:
            try:
                await agent.invoke_async(user)
                finished = True
            except Exception as e:  # noqa: BLE001 - mapped to PlainLoop's contract, else re-raised as itself
                root = _root(e)
                if isinstance(root, BudgetExceeded):
                    stop, detail = "budget", f"budget limit hit: {root.limit}"
                    span.error("budget", "BudgetExceeded", str(root))
                elif isinstance(root, MaxTokensReachedException):
                    finished = True
                elif not isinstance(root, _MaxTurns):
                    raise root from None
            if finished:
                last = st.last
                if last is not None and last.stop_reason in DONE and not any(
                        isinstance(b, ToolUse) for b in last.message.content):
                    stop = "completed"
                else:
                    stop = "error"
                    detail = f"model stopped with stop_reason={last.stop_reason if last else None}"
            final_text = text_of(st.last) if st.last is not None else ""
            span.update({"treehouse.stop": stop, "treehouse.turns": st.turn, "treehouse.final_text": final_text})
        return HarnessResult(final_text=final_text, stop=stop, turns=st.turn, detail=detail)
