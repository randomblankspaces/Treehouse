"""BedrockConverseProvider against botocore Stubber and a loopback server (§3 Stubber list, F1–F4, F10)."""

from __future__ import annotations

import asyncio
import http.server
import json
import threading
import time
from typing import Any

import pytest

boto3 = pytest.importorskip("boto3")
from botocore.stub import ANY, Stubber  # noqa: E402

from treehouse.probe import tiny_png  # noqa: E402
from treehouse.providers.base import MissingPixels  # noqa: E402
from treehouse.providers.bedrock import (  # noqa: E402
    STOP_REASONS,
    BedrockConverseProvider,
    BedrockQuotaExceeded,
    BedrockRetriesExhausted,
    BedrockValidationError,
    UnsupportedImage,
    VisionNotSupported,
    default_client_factory,
)
from treehouse.providers.cassette import Cassette, RecordingProvider, ReplayProvider  # noqa: E402
from treehouse.providers.prices import PriceTable, load_fixture  # noqa: E402
from treehouse.providers.registry import ModelRegistry  # noqa: E402
from treehouse.providers.spend import SpendLedger, UnpricedModel  # noqa: E402
from treehouse.schemas.config import InferenceParams  # noqa: E402
from treehouse.schemas.model_io import (  # noqa: E402
    Image,
    Message,
    ModelRequest,
    ModelResponse,
    Reasoning,
    Text,
    ToolResult,
    ToolSpec,
    ToolUse,
)

PARAMS = InferenceParams(max_tokens=64, temperature=0.0)
SONNET_PROFILE = "us.anthropic.claude-sonnet-5-5"


async def _nosleep(_s: float) -> None:
    return None

def new_ledger(*a, **kw):
    """A test ledger: synthetic tables allowed, genesis written (B1: reserve refuses an un-initialised file)."""
    kw.setdefault("allow_synthetic", True)
    led = SpendLedger(*a, **kw)
    if not led.initialized:
        led.init(note="test")
    return led



def ok_response(content=None, stop="end_turn", usage=None) -> dict[str, Any]:
    return {
        "output": {"message": {"role": "assistant", "content": content or [{"text": "hello"}]}},
        "stopReason": stop,
        "usage": usage or {"inputTokens": 100, "outputTokens": 20, "totalTokens": 120},
        "metrics": {"latencyMs": 42},
    }


@pytest.fixture
def ledger(tmp_path):
    return new_ledger(tmp_path / "spend.jsonl", prices=load_fixture(), registry=ModelRegistry.load())


def make(ledger, prices=None, registry=None, **kw):
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    stub = Stubber(client)
    stub.activate()
    p = BedrockConverseProvider(lambda _r: client, registry or ModelRegistry.load(), prices or load_fixture(), ledger,
                                "us-east-1", sleep=_nosleep, **kw)
    return p, stub, client


def text_req(model="claude-sonnet-5-5", text="hi") -> ModelRequest:
    return ModelRequest(model_id=model, system="sys", messages=[Message(role="user", content=[Text(text=text)])],
                        params=PARAMS)


def image_tool_req(model="claude-sonnet-5-5") -> ModelRequest:
    png, sha = tiny_png()
    img = Image(format="png", sha256=sha, bytes_=png)
    tool = ToolSpec(name="get_window", description="d", input_schema={"type": "object", "properties": {}})
    return ModelRequest(model_id=model, system="sys", tools=[tool], params=PARAMS, messages=[
        Message(role="user", content=[Text(text="look")]),
        Message(role="assistant", content=[ToolUse(id="t1", name="get_window", input={})]),
        Message(role="user", content=[ToolResult(tool_use_id="t1", status="success",
                                                 content=[Text(text="window w1"), img])]),
    ])


def run(coro):
    return asyncio.run(coro)


# -- the §3 Stubber list ----------------------------------------------------------------------------
def test_text_turn_call_shape_usage_and_cost(ledger):
    p, stub, _ = make(ledger)
    stub.add_response("converse", ok_response(usage={"inputTokens": 1000, "outputTokens": 100, "totalTokens": 1100,
                                                     "cacheReadInputTokens": 500, "cacheWriteInputTokens": 200}),
                      {"modelId": SONNET_PROFILE, "system": [{"text": "sys"}],
                       "messages": [{"role": "user", "content": [{"text": "hi"}]}],
                       "inferenceConfig": {"maxTokens": 64, "temperature": 0.0}})
    r = run(p.complete(text_req(), role="worker", trial_index=0, turn=0))
    stub.assert_no_pending_responses()
    assert p.provider_name == "aws.bedrock"  # F10
    assert r.message.content == [Text(text="hello")] and r.stop_reason == "end_turn" and r.latency_ms == 42
    assert (r.usage.input_tokens, r.usage.output_tokens, r.usage.cache_read, r.usage.cache_write) == (1000, 100, 500, 200)
    expected = (1000 * 0.003 + 100 * 0.015 + 500 * 0.0003 + 200 * 0.00375) / 1000
    st = ledger.status()
    assert st.spent_usd == pytest.approx(expected) and st.reserved_usd == 0 and st.calls == 1
    assert r.cost_usd == pytest.approx(expected) and r.price_table_version == "fixture-synthetic-1"
    assert p.price_table_version == "fixture-synthetic-1" and r.events == []


def test_tool_use_turn_and_reasoning_stored(ledger):
    p, stub, _ = make(ledger)
    content = [{"reasoningContent": {"reasoningText": {"text": "think", "signature": "sig"}}},
               {"text": "calling"},
               {"toolUse": {"toolUseId": "tu-1", "name": "stac_search", "input": {"bbox": [0, 0, 1, 1]}}}]
    req = ModelRequest(model_id="claude-sonnet-5-5", system="", params=PARAMS,
                       tools=[ToolSpec(name="stac_search", description="search", input_schema={"type": "object"})],
                       messages=[Message(role="user", content=[Text(text="find")])])
    stub.add_response("converse", ok_response(content, stop="tool_use"),
                      {"modelId": SONNET_PROFILE, "messages": ANY, "inferenceConfig": ANY,
                       "toolConfig": {"tools": [{"toolSpec": {"name": "stac_search", "description": "search",
                                                              "inputSchema": {"json": {"type": "object"}}}}]}})
    r = run(p.complete(req, role="worker", trial_index=0, turn=0))
    assert r.stop_reason == "tool_use"
    assert r.message.content[0] == Reasoning(text="think", signature="sig")
    assert r.message.content[2] == ToolUse(id="tu-1", name="stac_search", input={"bbox": [0, 0, 1, 1]})
    # the reasoning block goes back on the wire (signed) when the conversation continues
    req2 = req.model_copy(update={"messages": [*req.messages, r.message]})
    stub.add_response("converse", ok_response(), {"modelId": SONNET_PROFILE, "inferenceConfig": ANY, "toolConfig": ANY,
                                                  "messages": [ANY, {"role": "assistant", "content": content}]})
    run(p.complete(req2, role="worker", trial_index=0, turn=1))
    stub.assert_no_pending_responses()


@pytest.mark.parametrize("mode", ["tool_result", "user_turn"])
def test_both_image_modes_and_key_before_delivery(ledger, mode):
    p, stub, _ = make(ledger, image_delivery=mode)
    req = image_tool_req()
    png, _ = tiny_png()
    img_block = {"image": {"format": "png", "source": {"bytes": png}}}
    if mode == "tool_result":
        last = [{"toolResult": {"toolUseId": "t1", "status": "success",
                                "content": [{"text": "window w1"}, img_block]}}]
    else:
        last = [{"toolResult": {"toolUseId": "t1", "status": "success",
                                "content": [{"text": "window w1"}, {"text": f"[image {req.messages[2].content[0].content[1].sha256} follows in this user message]"}]}},
                img_block]
    stub.add_response("converse", ok_response(), {
        "modelId": SONNET_PROFILE, "system": ANY, "toolConfig": ANY, "inferenceConfig": ANY,
        "messages": [{"role": "user", "content": [{"text": "look"}]},
                     {"role": "assistant", "content": [{"toolUse": {"toolUseId": "t1", "name": "get_window",
                                                                     "input": {}}}]},
                     {"role": "user", "content": last}]})
    key_before = req.key()
    run(p.complete(req, role="worker", trial_index=0, turn=0))
    stub.assert_no_pending_responses()
    assert req.key() == key_before  # delivery mode never enters the request key


def test_registry_default_delivery_is_user_turn():
    reg = ModelRegistry.load()
    assert reg.get("claude-sonnet-5-5").image_delivery == "user_turn"  # U1: UNVERIFIED until K1


def test_two_throttles_then_success_one_retry_event_per_attempt(ledger):
    p, stub, _ = make(ledger)
    stub.add_client_error("converse", service_error_code="ThrottlingException", http_status_code=429)
    stub.add_client_error("converse", service_error_code="ServiceUnavailableException", http_status_code=503)
    stub.add_response("converse", ok_response())
    r = run(p.complete(text_req(), role="worker", trial_index=0, turn=0))
    stub.assert_no_pending_responses()
    assert r.stop_reason == "end_turn"
    retries = [e.attributes for e in r.events if e.name == "treehouse.retry"]
    assert len(retries) == len(r.events) == 2
    assert [(e["attempt"], e["error_code"], e["will_retry"]) for e in retries] == [
        (1, "ThrottlingException", True), (2, "ServiceUnavailableException", True)]
    assert all(e["delay_s"] > 0 for e in retries)
    assert ledger.status().calls == 1


@pytest.mark.parametrize("code", ["ModelNotReadyException", "ModelTimeoutException", "InternalServerException"])
def test_other_retryable_codes(ledger, code):  # F2
    p, stub, _ = make(ledger)
    stub.add_client_error("converse", service_error_code=code, http_status_code=500)
    stub.add_response("converse", ok_response())
    run(p.complete(text_req(), role="worker", trial_index=0, turn=0))
    stub.assert_no_pending_responses()


def test_service_quota_exceeded_is_never_retried(ledger):  # F2
    p, stub, _ = make(ledger)
    stub.add_client_error("converse", service_error_code="ServiceQuotaExceededException", http_status_code=400)
    with pytest.raises(BedrockQuotaExceeded) as ei:
        run(p.complete(text_req(), role="worker", trial_index=0, turn=0))
    stub.assert_no_pending_responses()
    assert ei.value.events == [] and ledger.status().reserved_usd == 0


def test_retries_exhausted_releases_reservation(ledger):
    p, stub, _ = make(ledger, max_attempts=2)
    for _ in range(2):
        stub.add_client_error("converse", service_error_code="ThrottlingException", http_status_code=429)
    with pytest.raises(BedrockRetriesExhausted) as ei:
        run(p.complete(text_req(), role="worker", trial_index=0, turn=0))
    assert [e.attributes["will_retry"] for e in ei.value.events] == [True, False]
    st = ledger.status()
    assert st.reserved_usd == 0 and st.spent_usd == 0


def test_validation_exception_mapped_to_typed_error(ledger):
    p, stub, _ = make(ledger)
    stub.add_client_error("converse", service_error_code="ValidationException",
                          service_message="The provided model identifier is invalid.", http_status_code=400)
    with pytest.raises(BedrockValidationError) as ei:
        run(p.complete(text_req(), role="worker", trial_index=0, turn=0))
    assert ei.value.code == "ValidationException"
    stub.assert_no_pending_responses()


def test_stop_reason_mapping_covers_botocore_enum(ledger):  # F3
    import botocore.session

    enum = botocore.session.get_session().get_service_model("bedrock-runtime").shape_for("StopReason").enum
    assert set(enum) == set(STOP_REASONS)
    allowed = set(ModelResponse.model_fields["stop_reason"].annotation.__args__)
    p, stub, _ = make(ledger)
    for raw in enum:
        stub.add_response("converse", ok_response(stop=raw))
    for t, raw in enumerate(enum):
        r = run(p.complete(text_req(), role="worker", trial_index=0, turn=t))
        assert r.stop_reason == STOP_REASONS[raw] and r.stop_reason in allowed
    # never folded into end_turn: identity except guardrail_intervened -> guardrail (main's StopReason)
    assert all(STOP_REASONS[raw] == ("guardrail" if raw == "guardrail_intervened" else raw) for raw in enum)


def test_unpriced_model_refused_before_any_call(tmp_path, unpriced_prices):
    led = new_ledger(tmp_path / "s.jsonl", prices=unpriced_prices, registry=ModelRegistry.load())
    p, stub, client = make(led, prices=unpriced_prices)
    calls = []
    client.meta.events.register("before-parameter-build.bedrock-runtime.Converse", lambda **kw: calls.append(1))
    with pytest.raises(UnpricedModel):
        run(p.complete(text_req("nova-pro"), role="verifier", trial_index=0, turn=0))
    assert calls == [] and led.status().calls == 0 and not led.status().open_reservations


def _registry_with_text_only() -> ModelRegistry:
    reg = ModelRegistry.load()
    blind = reg.get("nova-pro").model_copy(update={"key": "text-only", "vision": False, "family": "x-text"})
    return ModelRegistry(defaults=reg.defaults, models=[*reg.models, blind])


def test_vision_rule_refuses_images_for_text_only_model(ledger):
    p, stub, client = make(ledger, registry=_registry_with_text_only())
    with pytest.raises(VisionNotSupported):
        run(p.complete(image_tool_req("text-only"), role="worker", trial_index=0, turn=0))
    assert ledger.status().calls == 0


def test_image_format_validation(ledger):  # F4
    p, stub, _ = make(ledger)
    png, sha = tiny_png()
    bad_fmt = Image.model_construct(type="image", format="bmp", sha256=sha, bytes_=b"BM....")
    req = text_req().model_copy(update={"messages": [Message.model_construct(role="user", content=[bad_fmt])]})
    with pytest.raises(UnsupportedImage):
        p.prepare(req)
    mismatch = Image(format="jpeg", sha256=sha, bytes_=png)
    req = text_req().model_copy(update={"messages": [Message(role="user", content=[mismatch])]})
    with pytest.raises(UnsupportedImage):
        p.prepare(req)
    gif = Image.model_construct(type="image", format="gif", sha256=sha, bytes_=b"GIF89a" + b"\x00" * 8)
    req = text_req().model_copy(update={"messages": [Message.model_construct(role="user", content=[gif])]})
    _, kw = p.prepare(req)
    assert kw["messages"][0]["content"][0]["image"]["format"] == "gif"


def test_missing_pixels_raise(ledger):
    p, _, _ = make(ledger)
    _, sha = tiny_png()
    req = text_req().model_copy(update={"messages": [Message(role="user", content=[Image(format="png", sha256=sha)])]})
    with pytest.raises(MissingPixels):
        run(p.complete(req, role="worker", trial_index=0, turn=0))


def test_record_then_replay_costs_nothing(ledger, tmp_path):
    p, stub, _ = make(ledger)
    stub.add_response("converse", ok_response())
    cas = Cassette(tmp_path / "c.jsonl")
    req = image_tool_req()
    run(RecordingProvider(p, cas).complete(req, role="worker", trial_index=0, turn=0))
    spent = ledger.status().spent_usd
    assert spent > 0
    r = run(ReplayProvider(Cassette(tmp_path / "c.jsonl")).complete(req, role="worker", trial_index=0, turn=0))
    assert r.message.content == [Text(text="hello")]
    assert r.cost_usd == pytest.approx(spent) and r.price_table_version == "fixture-synthetic-1"  # as recorded
    assert ledger.status().spent_usd == spent and ledger.status().calls == 1


def test_semaphore_caps_concurrency(ledger):
    class SlowClient:
        def __init__(self):
            self.now = self.peak = 0
            self.lock = threading.Lock()

        def converse(self, **kw):
            with self.lock:
                self.now += 1
                self.peak = max(self.peak, self.now)
            time.sleep(0.03)
            with self.lock:
                self.now -= 1
            return ok_response()

    c = SlowClient()
    p = BedrockConverseProvider(lambda _r: c, ModelRegistry.load(), load_fixture(), ledger, "us-east-1",
                                concurrency=2, sleep=_nosleep)

    async def go():
        await asyncio.gather(*(p.complete(text_req(), role="worker", trial_index=i, turn=0) for i in range(6)))
    run(go())
    assert c.peak == 2 and ledger.status().calls == 6


# -- F1: exactly one HTTP attempt per our-loop attempt --------------------------------------------
class _Throttler(http.server.BaseHTTPRequestHandler):
    hits = 0

    def do_POST(self):  # noqa: N802
        type(self).hits += 1
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        body = json.dumps({"message": "Too many requests"}).encode()
        self.send_response(429)
        self.send_header("x-amzn-ErrorType", "ThrottlingException")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture
def throttle_server():
    _Throttler.hits = 0
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Throttler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


@pytest.mark.allow_loopback
def test_f1_one_http_attempt_per_loop_attempt(throttle_server, ledger):
    client = default_client_factory("us-east-1", endpoint_url=throttle_server)
    p = BedrockConverseProvider(lambda _r: client, ModelRegistry.load(), load_fixture(), ledger, "us-east-1",
                                max_attempts=3, sleep=_nosleep)
    with pytest.raises(BedrockRetriesExhausted) as ei:
        run(p.complete(text_req(), role="worker", trial_index=0, turn=0))
    assert _Throttler.hits == 3
    assert [e.name for e in ei.value.events] == ["treehouse.retry"] * 3


@pytest.mark.allow_loopback
def test_f1_legacy_max_attempts_1_makes_two_http_attempts(throttle_server):
    """Documents why we use total_max_attempts: {"max_attempts": 1} hides one botocore retry."""
    from botocore.exceptions import ClientError

    client = default_client_factory("us-east-1", endpoint_url=throttle_server, retries={"max_attempts": 1})
    with pytest.raises(ClientError):
        client.converse(modelId="m", messages=[{"role": "user", "content": [{"text": "x"}]}])
    assert _Throttler.hits == 2


def test_price_table_null_is_unpriced(unpriced_prices):
    t = unpriced_prices
    assert not t.is_priced("claude-sonnet-5-5") and not t.is_priced("nova-pro")
    assert PriceTable.load


# -- M10: pixel hashes are verified on the live path ------------------------------------------------
def test_pixel_hash_mismatch_refused(ledger):
    from treehouse.providers.base import PixelHashMismatch

    p, _, _ = make(ledger)
    png, _ = tiny_png()
    req = text_req().model_copy(update={"messages": [
        Message(role="user", content=[Image(format="png", sha256="sha256:" + "0" * 64, bytes_=png)])]})
    with pytest.raises(PixelHashMismatch):
        p.prepare(req)
    req = text_req().model_copy(update={"messages": [
        Message(role="user", content=[Image(format="png", sha256="sha256:" + "1" * 64, bytes_=b"")])]})
    with pytest.raises(MissingPixels):
        p.prepare(req)


@pytest.mark.parametrize("ftype", [0, 1, 2, 3, 4])
def test_decode_png_all_filters(ftype):
    import struct
    import zlib

    import numpy as np

    from treehouse.pixels import array_sha256
    from treehouse.providers.base import decode_png

    rng = np.random.default_rng(ftype)
    arr = rng.integers(0, 256, (5, 4, 3), dtype=np.uint8)
    bpp, rows, prev = 3, [], np.zeros(12, dtype=np.int32)
    for y in range(5):
        cur = arr[y].reshape(-1).astype(np.int32)
        f = np.zeros(12, dtype=np.int32)
        for x in range(12):
            a = int(cur[x - bpp]) if x >= bpp else 0
            b = int(prev[x])
            c = int(prev[x - bpp]) if x >= bpp else 0
            pa, pb, pc = abs(a + b - c - a), abs(a + b - c - b), abs(a + b - c - c)
            pred = [0, a, b, (a + b) >> 1, a if pa <= pb and pa <= pc else b if pb <= pc else c][ftype]
            f[x] = (int(cur[x]) - pred) & 0xFF
        rows.append(bytes([ftype]) + bytes(f.astype(np.uint8)))
        prev = cur

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 5, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))
    out = decode_png(png, "png")
    assert out.shape == (5, 4, 3) and array_sha256(out) == array_sha256(arr)
    assert decode_png(b"\xff\xd8\xff", "jpeg") is None


# -- M7/M9: PlainLoop copies cost, price table, cache usage and retry events onto the chat span -------
def test_plain_loop_chat_span_gets_cost_and_retry_events(ledger, tmp_path):
    from treehouse.clock import LogicalClock
    from treehouse.gateway.budget import BudgetGuard
    from treehouse.harness.plain_loop import PlainLoop
    from treehouse.ids import IdSource
    from treehouse.schemas.config import Budget
    from treehouse.trace.chain import ChainedJsonlWriter
    from treehouse.trace.tracer import TrialTracer

    class NoTools:
        def specs(self):
            return []

    p, stub, _ = make(ledger)
    stub.add_client_error("converse", service_error_code="ThrottlingException", http_status_code=429)
    stub.add_response("converse", ok_response(usage={"inputTokens": 1000, "outputTokens": 100, "totalTokens": 1100,
                                                     "cacheReadInputTokens": 7, "cacheWriteInputTokens": 3}))
    base = {k: "x" for k in ("treehouse.task.id", "treehouse.task.hash", "treehouse.run.id", "treehouse.trial.id",
                             "treehouse.role", "treehouse.config.hash")} | {"treehouse.trial.index": 0}
    ids = IdSource(1)
    path = tmp_path / "t.jsonl"
    tr = TrialTracer(ChainedJsonlWriter.for_trial(path, "t-0"), trace_id=ids.trace_id(), clock=LogicalClock(),
                     ids=ids, base_attrs=base)
    budget = BudgetGuard(Budget(usd=1.0))
    res = run(PlainLoop(model_id="claude-sonnet-5-5", params=PARAMS).run(
        system="s", user="u", provider=p, gateway=NoTools(), tracer=tr, budget=budget, max_turns=2,
        role="worker", trial_index=0))
    tr.close()
    assert res.stop == "completed"
    chat = [json.loads(line) for line in path.read_text().splitlines()]
    chat = [c.get("rec", c) for c in chat]
    chat = [c for c in chat if c.get("op") == "chat"][0]
    a = chat["attributes"]
    assert a["gen_ai.provider.name"] == "aws.bedrock"
    assert a["treehouse.cost.usd"] > 0 and a["treehouse.cost.usd"] == pytest.approx(ledger.status().spent_usd)
    assert a["treehouse.price_table.version"] == "fixture-synthetic-1"
    assert (a["gen_ai.usage.cache_read.input_tokens"], a["gen_ai.usage.cache_creation.input_tokens"]) == (7, 3)
    assert [e["name"] for e in chat["events"]] == ["treehouse.retry"]
    assert budget.spent["usd"] == pytest.approx(a["treehouse.cost.usd"])
