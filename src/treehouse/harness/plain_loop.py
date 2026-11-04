"""PlainLoop: the demo and replay engine (§3 Harnesses).

Each turn: open a ``chat`` span and call the provider; append the assistant message; run
``gateway.call`` for each ToolUse in order; append one user message of ToolResults. Stops on
end_turn, max_turns or BudgetExceeded. Returns a HarnessResult and never claims.

Model I/O in the trace: each chat span names the pixel-free canonical request
(``treehouse.input.messages_ref`` = ``req.key()``) and response (``treehouse.output.messages_ref``) and
carries the turn's text and tool-use ids inline; the agent span carries ``treehouse.final_text``. The
bodies themselves go to blobs through ``blob_sink`` (the runner passes
``lambda b: store.put_blob(b, media_type="application/json", license=...)``); verify() fails a sealed run
whose ``*_ref`` attributes name blobs that are not in the store, so a runner that seals must pass one.

Error contract: BudgetExceeded ends the run with ``stop="budget"``; an odd stop reason ends it with
``stop="error"``. Any other provider or gateway exception (CassetteMiss, ScriptDivergence, MissingPixels,
ToolDivergence, ...) is recorded on the open spans and propagates: the runner maps it to
``TrialHead.stop="error"``.
"""

from __future__ import annotations

from collections.abc import Callable

from treehouse.canon import sha256_bytes
from treehouse.gateway.base import Gateway
from treehouse.gateway.budget import BudgetExceeded, BudgetGuard
from treehouse.harness.base import HarnessResult, Stop
from treehouse.providers.base import ModelProvider, ProviderError, pixel_free_json
from treehouse.schemas.config import InferenceParams
from treehouse.schemas.model_io import Message, ModelRequest, Text, ToolResult, ToolUse
from treehouse.trace.tracer import TrialTracer

DONE = {"end_turn", "stop_sequence"}


class PlainLoop:
    name = "plain_loop"
    version = "1"

    def __init__(self, *, model_id: str, params: InferenceParams,
                 blob_sink: Callable[[bytes], str] | None = None) -> None:
        self.model_id, self.params = model_id, params
        self.blob_sink = blob_sink  # bytes -> sha256 ref (e.g. a bound Store.put_blob)

    def _put(self, data: bytes) -> str:
        ref = sha256_bytes(data)
        if self.blob_sink is not None and self.blob_sink(data) != ref:
            raise ProviderError("blob_sink returned a ref that is not the sha256 of the bytes")
        return ref

    async def run(
        self,
        *,
        system: str,
        user: str,
        provider: ModelProvider,
        gateway: Gateway,
        tracer: TrialTracer,
        budget: BudgetGuard,
        max_turns: int,
        role: str,
        trial_index: int,
    ) -> HarnessResult:
        messages = [Message(role="user", content=[Text(text=user)])]
        stop: Stop = "max_turns"
        detail: str | None = None
        final_text, turns = "", 0
        with tracer.span(f"invoke_agent {role}", "invoke_agent",
                         {"gen_ai.agent.name": role, "treehouse.harness": f"{self.name}/{self.version}"}) as agent:
            try:
                for turn in range(max_turns):
                    budget.check()
                    req = ModelRequest(model_id=self.model_id, system=system, messages=messages,
                                       tools=gateway.specs(), params=self.params)
                    with tracer.span(f"chat {self.model_id}", "chat", {"treehouse.turn": turn}) as s:
                        in_ref = self._put(pixel_free_json(req))  # == req.key()
                        try:
                            resp = await provider.complete(req, role=role, trial_index=trial_index, turn=turn)
                        except BaseException as e:
                            # M7: a failed call keeps its retry/throttle events on the span; spend the ledger
                            # booked for it (ambiguous failure, unparseable response) is charged too
                            for ev in getattr(e, "events", None) or []:
                                s.event(ev.name, ev.attributes)
                            failed_cost = getattr(e, "cost_usd", None)
                            if failed_cost:
                                s.set("treehouse.cost.usd", failed_cost)
                                budget.commit(None, usd=failed_cost)
                            raise
                        turn_text = "".join(b.text for b in resp.message.content if isinstance(b, Text))
                        s.update({
                            "treehouse.output.messages_ref": self._put(pixel_free_json(resp)),
                            "treehouse.output.text": turn_text,
                            "treehouse.output.tool_use_ids": [b.id for b in resp.message.content
                                                              if isinstance(b, ToolUse)],
                        })
                        n_events = len(budget.events)
                        cost = resp.cost_usd or 0.0
                        u = resp.usage
                        budget.commit(None, tokens=u.input_tokens + u.output_tokens + u.cache_read + u.cache_write,
                                      usd=cost)
                        s.update({
                            "gen_ai.provider.name": provider.provider_name,
                            "gen_ai.request.model": self.model_id,
                            "gen_ai.response.model": resp.response_model_id,
                            "gen_ai.usage.input_tokens": resp.usage.input_tokens,
                            "gen_ai.usage.output_tokens": resp.usage.output_tokens,
                            "treehouse.input.messages_ref": in_ref,
                            "treehouse.stop_reason": resp.stop_reason,
                            "gen_ai.usage.cache_read.input_tokens": resp.usage.cache_read,
                            "gen_ai.usage.cache_creation.input_tokens": resp.usage.cache_write,
                            "treehouse.cost.usd": cost,
                            "treehouse.price_table.version": resp.price_table_version
                            or getattr(provider, "price_table_version", "none"),
                            "treehouse.cassette": getattr(provider, "cassette_ref", ""),
                            "treehouse.recorded_latency_ms": resp.latency_ms,
                        })
                        if resp.usage.image_input_tokens is not None:
                            s.set("treehouse.usage.image_input_tokens", resp.usage.image_input_tokens)
                        if provider.provider_name == "replay":
                            s.set("treehouse.cost.replayed", True)  # recorded cost; the SpendLedger pays $0
                            s.set("treehouse.cost.ledger_usd", 0.0)  # panels summing real spend use this
                        for ev in resp.events:
                            s.event(ev.name, ev.attributes)
                        remaining = budget.remaining("usd")
                        if remaining is not None:
                            s.set("treehouse.budget.remaining_usd", remaining)
                        for e in budget.events[n_events:]:
                            s.event(e["name"], axis=e["axis"], pct=e["pct"])
                    turns = turn + 1
                    messages.append(resp.message)
                    final_text = turn_text
                    uses = [b for b in resp.message.content if isinstance(b, ToolUse)]
                    if not uses:
                        if resp.stop_reason in DONE:
                            stop = "completed"
                        else:
                            stop, detail = "error", f"model stopped with stop_reason={resp.stop_reason}"
                        break
                    results = []
                    for tu in uses:
                        out = await gateway.call(tu.name, tu.input, call_id=tu.id)
                        results.append(ToolResult(tool_use_id=tu.id, status="success" if out.status == "success"
                                                  else "error", content=out.content))
                    messages.append(Message(role="user", content=results))
            except BudgetExceeded as e:
                stop, detail = "budget", f"budget limit hit: {e.limit}"
                agent.error("budget", "BudgetExceeded", str(e))
            agent.update({"treehouse.stop": stop, "treehouse.turns": turns, "treehouse.final_text": final_text})
        return HarnessResult(final_text=final_text, stop=stop, turns=turns, detail=detail)
