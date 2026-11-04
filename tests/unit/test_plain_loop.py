"""PlainLoop (§3): chat span per turn, gateway.call per ToolUse, one user message of ToolResults;
stops on end_turn, max_turns and BudgetExceeded; never claims. J7 partial (budget on/off)."""

from __future__ import annotations

import asyncio
import dataclasses

from treehouse.clock import LogicalClock
from treehouse.gateway.base import Gateway, ToolOutcome
from treehouse.gateway.budget import BudgetGuard
from treehouse.harness.base import HarnessResult
from treehouse.harness.plain_loop import PlainLoop
from treehouse.ids import IdSource
from treehouse.providers.fake import FakeProvider
from treehouse.schemas.config import Budget, InferenceParams
from treehouse.schemas.model_io import Text, ToolResult, ToolSpec
from treehouse.schemas.trace import SpanRecord
from treehouse.trace.chain import ChainedJsonlWriter, read_chain
from treehouse.trace.tracer import TrialTracer

BASE = {
    "treehouse.task.id": "synth-crossings-v1",
    "treehouse.task.hash": "sha256:" + "0" * 64,
    "treehouse.run.id": "run-0001",
    "treehouse.trial.id": "t-0",
    "treehouse.trial.index": 0,
    "treehouse.role": "worker",
    "treehouse.config.hash": "sha256:" + "1" * 64,
}


class FakeGateway:
    """Minimal gateway: echoes a result id, reserves one tool call per call."""

    def __init__(self, budget: BudgetGuard | None = None) -> None:
        self.calls: list[tuple[str, dict, str]] = []
        self.budget = budget

    def specs(self):
        return [ToolSpec(name="stac_search", description="search", input_schema={"type": "object"})]

    async def call(self, name, args, *, call_id):
        if self.budget is not None:
            self.budget.commit(self.budget.reserve(tool_calls=1))
        self.calls.append((name, args, call_id))
        rid = f"r-{len(self.calls):04d}"
        return ToolOutcome(result_id=rid, status="success", content=[Text(text=rid)])


def _run(tmp_path, provider, *, budget=None, max_turns=5, gateway=None, name="t.jsonl"):
    ids = IdSource(3)
    clock = LogicalClock()
    tracer = TrialTracer(ChainedJsonlWriter.for_trial(tmp_path / name, "t-0"), trace_id=ids.trace_id(),
                         clock=clock, ids=ids, base_attrs=BASE)
    guard = BudgetGuard(budget or Budget(), clock=clock)
    gw = gateway(guard) if gateway else FakeGateway()
    loop = PlainLoop(model_id="fake-model", params=InferenceParams(max_tokens=64))
    res = asyncio.run(loop.run(system="sys", user="find bridges", provider=provider, gateway=gw, tracer=tracer,
                               budget=guard, max_turns=max_turns, role="worker", trial_index=0))
    tracer.close()
    spans = [SpanRecord.model_validate(x["rec"]) for x in read_chain(tmp_path / name)]
    return res, gw, spans


TWO_TURN = """
- expect: {contains: find bridges}
  respond: {tool_use: [{name: stac_search, input: {q: 1}}, {name: stac_search, input: {q: 2}}]}
- expect: {contains: [r-0001, r-0002], n_messages: 3}
  respond: {text: two crossings found}
"""


def always_tool(req, *, role, trial_index, turn):
    return {"tool_use": [{"name": "stac_search", "input": {"turn": turn}}]}


def test_completed_on_end_turn(tmp_path):
    res, gw, spans = _run(tmp_path, FakeProvider.from_yaml(TWO_TURN))
    assert res.stop == "completed" and res.turns == 2 and res.final_text == "two crossings found"
    assert [c[2] for c in gw.calls] == ["tu-0-0-0", "tu-0-0-1"]
    assert [s.op for s in spans] == ["chat", "chat", "invoke_agent"]
    root = spans[-1]
    assert all(s.parent_span_id == root.span_id for s in spans[:-1])
    chat = spans[0].attributes
    assert chat["gen_ai.provider.name"] == "fake" and chat["treehouse.input.messages_ref"].startswith("sha256:")
    assert chat["gen_ai.usage.output_tokens"] >= 1


def test_tool_results_are_one_user_message(tmp_path):
    seen = []

    def spy(req, *, role, trial_index, turn):
        seen.append(req)
        return always_tool(req, role=role, trial_index=trial_index, turn=turn) if turn == 0 else {"text": "ok"}

    _run(tmp_path, FakeProvider(spy))
    last = seen[1].messages[-1]
    assert last.role == "user" and all(isinstance(b, ToolResult) for b in last.content)
    assert [b.tool_use_id for b in last.content] == ["tu-0-0-0"]


def test_stops_at_max_turns(tmp_path):
    res, gw, _ = _run(tmp_path, FakeProvider(always_tool), max_turns=3)
    assert res.stop == "max_turns" and res.turns == 3 and len(gw.calls) == 3


def test_budget_stop_names_the_limit_tokens(tmp_path):
    res, _, spans = _run(tmp_path, FakeProvider(always_tool), budget=Budget(tokens=10), max_turns=10)
    assert res.stop == "budget" and res.turns == 1 and "tokens" in res.detail
    root = spans[-1]
    assert root.status == "error" and root.error.source == "budget"


def test_budget_stop_from_gateway_tool_calls(tmp_path):
    res, gw, _ = _run(tmp_path, FakeProvider.from_yaml(TWO_TURN), budget=Budget(tool_calls=1), gateway=FakeGateway)
    assert res.stop == "budget" and "tool_calls" in res.detail and len(gw.calls) == 1


def test_guard_off_run_completes(tmp_path):
    res, gw, _ = _run(tmp_path, FakeProvider.from_yaml(TWO_TURN),
                      budget=Budget(enabled=False, tokens=1, tool_calls=0), gateway=FakeGateway)
    assert res.stop == "completed" and len(gw.calls) == 2


def test_error_stop_on_truncated_answer(tmp_path):
    res, _, _ = _run(tmp_path, FakeProvider([{"respond": {"text": "partial", "stop_reason": "max_tokens"}}]))
    assert res.stop == "error" and "max_tokens" in res.detail


def test_no_claims_api():
    assert {f.name for f in dataclasses.fields(HarnessResult)} == {"final_text", "stop", "turns", "detail"}
    for obj in (PlainLoop, HarnessResult):
        assert not [a for a in dir(obj) if "claim" in a.lower()]
    assert isinstance(FakeGateway(), Gateway)


def test_trace_is_deterministic(tmp_path):
    _run(tmp_path, FakeProvider.from_yaml(TWO_TURN), name="a.jsonl")
    _run(tmp_path, FakeProvider.from_yaml(TWO_TURN), name="b.jsonl")
    assert (tmp_path / "a.jsonl").read_bytes() == (tmp_path / "b.jsonl").read_bytes()


def test_record_then_replay_through_the_loop(tmp_path):
    from treehouse.providers.cassette import Cassette, RecordingProvider, ReplayProvider

    cas = Cassette(tmp_path / "model.jsonl")
    live, _, live_spans = _run(tmp_path, RecordingProvider(FakeProvider.from_yaml(TWO_TURN), cas), name="rec.jsonl")
    again, _, replay_spans = _run(tmp_path, ReplayProvider(Cassette(tmp_path / "model.jsonl")), name="rep.jsonl")
    assert again == live
    refs = [[s.attributes.get("treehouse.input.messages_ref") for s in sp if s.op == "chat"]
            for sp in (live_spans, replay_spans)]
    assert refs[0] == refs[1]
    assert replay_spans[0].attributes["treehouse.cassette"] == "model.jsonl"
