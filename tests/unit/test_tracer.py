"""TrialTracer: spans written on end, mandatory attributes, deterministic under LogicalClock + IdSource."""

from __future__ import annotations

import pytest

from treehouse.clock import LogicalClock
from treehouse.ids import IdSource
from treehouse.schemas.trace import SpanRecord
from treehouse.trace.chain import ChainedJsonlWriter, read_chain
from treehouse.trace.tracer import (
    CHAT_ATTRS,
    RUN_CONTEXT_ATTRS,
    TOOL_ATTRS,
    MissingSpanAttributes,
    TrialTracer,
)

BASE = {
    "treehouse.task.id": "synth-crossings-v1",
    "treehouse.task.hash": "sha256:" + "0" * 64,
    "treehouse.run.id": "run-0001",
    "treehouse.trial.id": "t-0",
    "treehouse.trial.index": 0,
    "treehouse.role": "worker",
    "treehouse.config.hash": "sha256:" + "1" * 64,
}


def _tracer(path, seed=7):
    ids = IdSource(seed)
    return TrialTracer(
        ChainedJsonlWriter.for_trial(path, "t-0"), trace_id=ids.trace_id(), clock=LogicalClock(), ids=ids,
        base_attrs=BASE,
    )


def chat_attrs(**over):
    a = {
        "gen_ai.provider.name": "fake",
        "gen_ai.request.model": "fake-model",
        "gen_ai.usage.input_tokens": 10,
        "gen_ai.usage.output_tokens": 3,
        "treehouse.input.messages_ref": "sha256:" + "a" * 64,
        "treehouse.cost.usd": 0.0,
        "treehouse.price_table.version": "none",
        "treehouse.cassette": "",
        "treehouse.recorded_latency_ms": 0,
    }
    return a | over


def tool_attrs(**over):
    a = {
        "treehouse.tool.args_hash": "sha256:" + "b" * 64,
        "treehouse.tool.result_id": "r-0001",
        "treehouse.tool.result_ref": "sha256:" + "c" * 64,
        "treehouse.tool.bytes_read": 0,
        "treehouse.tool.blocked": False,
        "treehouse.tool.block_reason": "",
        "treehouse.key_access_attempt": False,
    }
    return a | over


def tiny_trial(path):
    tr = _tracer(path)
    with tr.span("invoke_agent worker", "invoke_agent"):
        with tr.span("chat fake-model", "chat", chat_attrs()) as s:
            s.event("treehouse.retry", attempt=1)
        with tr.span("execute_tool stac_search", "execute_tool", tool_attrs()) as s:
            s.set("treehouse.scene.id", "S-001")
        with tr.span("execute_tool key_lookup", "execute_tool", tool_attrs(**{"treehouse.tool.blocked": True})) as s:
            s.error("policy", "forbidden_source", "blocked by policy: keys/")
    return tr.close()


def test_spans_written_on_end_with_parents(tmp_path):
    tiny_trial(tmp_path / "t.jsonl")
    spans = [SpanRecord.model_validate(x["rec"]) for x in read_chain(tmp_path / "t.jsonl")]
    assert [s.op for s in spans] == ["chat", "execute_tool", "execute_tool", "invoke_agent"]  # children end first
    root = spans[-1]
    assert root.parent_span_id is None
    assert all(s.parent_span_id == root.span_id for s in spans[:-1])
    assert all(s.trace_id == root.trace_id for s in spans)
    assert spans[2].status == "error" and spans[2].error.source == "policy"
    assert spans[0].events[0].name == "treehouse.retry"
    for s in spans:
        assert set(RUN_CONTEXT_ATTRS) <= set(s.attributes)
        assert s.start_ns < s.end_ns


def test_f10_attribute_names():
    assert "treehouse.input.messages_ref" in CHAT_ATTRS
    assert not any(a.startswith("gen_ai.input") for a in CHAT_ATTRS)
    assert {"treehouse.tool.args_hash", "treehouse.key_access_attempt"} <= set(TOOL_ATTRS)


def test_missing_base_attrs_rejected(tmp_path):
    ids = IdSource(1)
    with pytest.raises(MissingSpanAttributes):
        TrialTracer(ChainedJsonlWriter.for_trial(tmp_path / "x.jsonl", "t-0"), trace_id=ids.trace_id(),
                    clock=LogicalClock(), ids=ids, base_attrs={"treehouse.run.id": "r"})


def test_missing_op_attrs_rejected(tmp_path):
    tr = _tracer(tmp_path / "t.jsonl")
    with pytest.raises(MissingSpanAttributes, match="gen_ai.usage.input_tokens"):
        with tr.span("chat m", "chat", {"gen_ai.provider.name": "fake"}):
            pass


def test_exception_inside_span_is_recorded_not_masked(tmp_path):
    tr = _tracer(tmp_path / "t.jsonl")
    with pytest.raises(KeyError):
        with tr.span("chat m", "chat"):
            raise KeyError("boom")
    tr.close()
    (span,) = [SpanRecord.model_validate(x["rec"]) for x in read_chain(tmp_path / "t.jsonl")]
    assert span.status == "error" and span.error.type == "KeyError"


def test_deterministic_bytes_across_runs(tmp_path):
    h1 = tiny_trial(tmp_path / "a.jsonl")
    h2 = tiny_trial(tmp_path / "b.jsonl")
    assert (tmp_path / "a.jsonl").read_bytes() == (tmp_path / "b.jsonl").read_bytes()
    assert h1 == h2
