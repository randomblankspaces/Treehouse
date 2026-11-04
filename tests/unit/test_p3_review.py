"""Regression tests for the judged P3 review doubts (M2, M3, m9, m10, m13-m17, m20, m22)."""

from __future__ import annotations

import asyncio
import base64
import json

import pytest
from test_plain_loop import BASE, TWO_TURN, FakeGateway, _run
from test_providers import SHA, LiveStub, request

from treehouse.canon import canonical_json, sha256_bytes
from treehouse.clock import LogicalClock
from treehouse.gateway.base import ToolOutcome
from treehouse.gateway.budget import BudgetExceeded, BudgetGuard
from treehouse.harness.plain_loop import PlainLoop
from treehouse.ids import IdSource
from treehouse.providers.base import pixel_free_json
from treehouse.providers.cassette import Cassette, CassetteError, RecordingProvider, ReplayProvider
from treehouse.providers.fake import FakeProvider
from treehouse.schemas.config import Budget, InferenceParams
from treehouse.schemas.model_io import Image, Json, Message, ModelRequest, Text, ToolResult, ToolSpec
from treehouse.schemas.trace import SpanRecord
from treehouse.store.local import LocalStore
from treehouse.trace.chain import ChainedJsonlWriter, read_chain
from treehouse.trace.tracer import MissingSpanAttributes, TrialTracer

PIXELS = b"\x89PNG\r\n\x1a\nPIXELDATA"


class ImageGateway(FakeGateway):
    """Returns an image with real bytes, as the P4 gateway does for imagery_window."""

    async def call(self, name, args, *, call_id):
        self.calls.append((name, args, call_id))
        img = Image(format="png", sha256=SHA, bytes_=PIXELS)
        return ToolOutcome(result_id="r-0001", status="success", content=[Text(text="r-0001"), img])


def _run_with_store(tmp_path, provider, gateway=None):
    store = LocalStore(tmp_path / "store")
    ids, clock = IdSource(3), LogicalClock()
    tracer = TrialTracer(ChainedJsonlWriter.for_trial(tmp_path / "t.jsonl", "t-0"), trace_id=ids.trace_id(),
                         clock=clock, ids=ids, base_attrs=BASE)
    loop = PlainLoop(model_id="fake-model", params=InferenceParams(max_tokens=64),
                     blob_sink=lambda b: store.put_blob(b, media_type="application/json", license="CC0-1.0"))
    res = asyncio.run(loop.run(system="sys", user="find bridges", provider=provider, gateway=gateway or FakeGateway(),
                               tracer=tracer, budget=BudgetGuard(Budget(), clock=clock), max_turns=5, role="worker",
                               trial_index=0))
    tracer.close()
    return res, store, [SpanRecord.model_validate(x["rec"]) for x in read_chain(tmp_path / "t.jsonl")]


# --- M2 / M3 / m14: model I/O is in blobs and the trace, pixel-free --------------------------------


def test_m2_m3_chat_spans_name_stored_pixel_free_request_and_response(tmp_path):
    res, store, spans = _run_with_store(tmp_path, FakeProvider.from_yaml(TWO_TURN))
    chats = [s for s in spans if s.op == "chat"]
    assert len(chats) == 2
    for s in chats:
        for k in ("treehouse.input.messages_ref", "treehouse.output.messages_ref"):
            assert store.get(s.attributes[k])  # the blob exists and re-hashes
    req = ModelRequest.model_validate_json(store.get(chats[1].attributes["treehouse.input.messages_ref"]))
    assert req.key() == chats[1].attributes["treehouse.input.messages_ref"] and len(req.messages) == 3
    out0 = json.loads(store.get(chats[0].attributes["treehouse.output.messages_ref"]))
    assert [b["type"] for b in out0["message"]["content"]] == ["tool_use", "tool_use"]
    assert chats[0].attributes["treehouse.output.tool_use_ids"] == ["tu-0-0-0", "tu-0-0-1"]
    assert chats[1].attributes["treehouse.output.text"] == "two crossings found"
    agent = next(s for s in spans if s.op == "invoke_agent")
    assert agent.attributes["treehouse.final_text"] == res.final_text == "two crossings found"


def test_m14_message_blobs_never_hold_pixels(tmp_path):
    script = "- respond: {tool_use: [{name: imagery_window, input: {s: 1}}]}\n- respond: {text: done}\n"
    _, store, spans = _run_with_store(tmp_path, FakeProvider.from_yaml(script), ImageGateway())
    b64 = base64.b64encode(PIXELS)
    for f in (store.root / "blobs").rglob("*"):
        if f.is_file():
            data = f.read_bytes()
            assert PIXELS not in data and b64 not in data and b"PIXELDATA" not in data
    trace = (tmp_path / "t.jsonl").read_bytes()
    assert b64 not in trace and b"PIXELDATA" not in trace
    req = request(True)
    assert sha256_bytes(pixel_free_json(req)) == req.key() == request(False).key()


def test_m2_trace_without_blob_sink_still_names_refs(tmp_path):
    _, _, spans = _run(tmp_path, FakeProvider.from_yaml(TWO_TURN))
    assert all("treehouse.output.messages_ref" in s.attributes for s in spans if s.op == "chat")


# --- m13: only real Image blocks lose bytes_ -------------------------------------------------------


def test_m13_json_lookalike_image_is_part_of_the_key():
    def req(v):
        j = Json(json_={"type": "image", "bytes_": v, "sha256": "a"})
        msg = Message(role="user", content=[ToolResult(tool_use_id="a", status="success", content=[j])])
        return ModelRequest(model_id="m", system="", messages=[msg], params=InferenceParams(max_tokens=1),
                            tools=[ToolSpec(name="t", description="", input_schema={"type": "image", "bytes_": v})])
    assert req("keepme").key() != req("DIFFERENT").key()


# --- m9 / m10: cassette integrity and exhaustion ---------------------------------------------------


def test_m9_hand_edited_cassette_entry_refused(tmp_path):
    cas = Cassette(tmp_path / "m.jsonl")
    asyncio.run(RecordingProvider(LiveStub(), cas).complete(request(True), role="w", trial_index=0, turn=0))
    e = json.loads((tmp_path / "m.jsonl").read_text())
    e["request"]["system"] = "EDITED"
    (tmp_path / "m.jsonl").write_bytes((canonical_json(e) + "\n").encode())
    with pytest.raises(CassetteError, match="request_hash"):
        Cassette(tmp_path / "m.jsonl")


def test_m10_replay_reports_unused_entries(tmp_path):
    cas = Cassette(tmp_path / "m.jsonl")
    rec = RecordingProvider(LiveStub(), cas)
    for turn in (0, 1):
        asyncio.run(rec.complete(request(True, extra_user=f"t{turn}"), role="w", trial_index=0, turn=turn))
    rp = ReplayProvider(Cassette(tmp_path / "m.jsonl"))
    asyncio.run(rp.complete(request(False, extra_user="t0"), role="w", trial_index=0, turn=0))
    assert rp.unused_keys() == [("w", 0, 1)]
    with pytest.raises(CassetteError, match="unused"):
        rp.check_consumed()
    asyncio.run(rp.complete(request(False, extra_user="t1"), role="w", trial_index=0, turn=1))
    rp.check_consumed()
    assert b"\r\n" not in (tmp_path / "m.jsonl").read_bytes()


# --- m15 / m16: FakeProvider input checks ----------------------------------------------------------


def test_m15_from_yaml_path_vs_text():
    with pytest.raises(FileNotFoundError):
        FakeProvider.from_yaml("scripts/missing.yaml")
    long = "# " + "x" * 300 + "\n- respond: {text: hi}\n"
    assert len(FakeProvider.from_yaml(long)._steps) == 1
    with pytest.raises(ValueError):
        FakeProvider.from_yaml("a: 1\nb: 2\n")


def test_m16_callable_script_responses_are_validated(tmp_path):
    with pytest.raises(ValueError, match="unknown keys"):
        _run(tmp_path, FakeProvider(lambda req, **kw: {"txt": "typo"}))


# --- m17 / m22: tracer writes failing spans and tags budget errors ----------------------------------


def test_m17_span_missing_attrs_is_written_as_error(tmp_path):
    ids = IdSource(1)
    tr = TrialTracer(ChainedJsonlWriter.for_trial(tmp_path / "t.jsonl", "t-0"), trace_id=ids.trace_id(),
                     clock=LogicalClock(), ids=ids, base_attrs=BASE)
    with pytest.raises(MissingSpanAttributes), tr.span("chat m", "chat", {"gen_ai.provider.name": "fake"}):
        pass
    [line] = read_chain(tmp_path / "t.jsonl")
    assert line["rec"]["status"] == "error" and line["rec"]["error"]["type"] == "MissingSpanAttributes"


def test_m22_budget_exceeded_in_chat_span_is_tagged_budget(tmp_path):
    class Refusing:
        provider_name = "x"

        async def complete(self, req, **kw):
            raise BudgetExceeded("usd", 1.0, 2.0)

    res, _, spans = _run(tmp_path, Refusing())
    assert res.stop == "budget"
    assert {s.op: s.error.source for s in spans if s.error} == {"chat": "budget", "invoke_agent": "budget"}


# --- m19 / m20: budget semantics -------------------------------------------------------------------


def test_m20_settled_reservation_cannot_be_committed_again():
    g = BudgetGuard(Budget(tool_calls=5))
    r = g.reserve(tool_calls=1)
    g.commit(r)
    with pytest.raises(ValueError, match="already committed or released"):
        g.commit(r)
    r2 = g.reserve(tool_calls=1)
    g.release(r2)
    with pytest.raises(ValueError):
        g.commit(r2)
    assert g.spent["tool_calls"] == 1


def test_m19_none_means_no_limit_zero_means_zero():
    BudgetGuard(Budget(usd=None)).check()
    with pytest.raises(BudgetExceeded):
        BudgetGuard(Budget(usd=0.0)).check()
