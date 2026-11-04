"""PlainLoop: the demo and replay engine (§3 Harnesses).

Each turn: open a ``chat`` span and call the provider; append the assistant message; run
``gateway.call`` for each ToolUse in order; append one user message of ToolResults. Stops on
end_turn, max_turns or BudgetExceeded. Returns a HarnessResult and never claims.
"""

from __future__ import annotations

from treehouse.gateway.base import Gateway
from treehouse.gateway.budget import BudgetExceeded, BudgetGuard
from treehouse.harness.base import HarnessResult, Stop
from treehouse.providers.base import ModelProvider
from treehouse.schemas.config import InferenceParams
from treehouse.schemas.model_io import Message, ModelRequest, Text, ToolResult, ToolUse
from treehouse.trace.tracer import TrialTracer

DONE = {"end_turn", "stop_sequence"}


class PlainLoop:
    name = "plain_loop"
    version = "1"

    def __init__(self, *, model_id: str, params: InferenceParams) -> None:
        self.model_id, self.params = model_id, params

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
                        resp = await provider.complete(req, role=role, trial_index=trial_index, turn=turn)
                        n_events = len(budget.events)
                        budget.commit(None, tokens=resp.usage.input_tokens + resp.usage.output_tokens)
                        s.update({
                            "gen_ai.provider.name": provider.provider_name,
                            "gen_ai.request.model": self.model_id,
                            "gen_ai.response.model": resp.response_model_id,
                            "gen_ai.usage.input_tokens": resp.usage.input_tokens,
                            "gen_ai.usage.output_tokens": resp.usage.output_tokens,
                            "treehouse.input.messages_ref": req.key(),
                            "treehouse.stop_reason": resp.stop_reason,
                            "treehouse.cost.usd": 0.0,  # TODO(P6): cost from the SpendLedger commit
                            "treehouse.price_table.version": getattr(provider, "price_table_version", "none"),
                            "treehouse.cassette": getattr(provider, "cassette_ref", ""),
                            "treehouse.recorded_latency_ms": resp.latency_ms,
                        })
                        remaining = budget.remaining("usd")
                        if remaining is not None:
                            s.set("treehouse.budget.remaining_usd", remaining)
                        for e in budget.events[n_events:]:
                            s.event(e["name"], axis=e["axis"], pct=e["pct"])
                    turns = turn + 1
                    messages.append(resp.message)
                    final_text = "".join(b.text for b in resp.message.content if isinstance(b, Text))
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
            agent.update({"treehouse.stop": stop, "treehouse.turns": turns})
        return HarnessResult(final_text=final_text, stop=stop, turns=turns, detail=detail)
