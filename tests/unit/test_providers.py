"""Model providers: pixel-free keys (OBS-B1/B2), FakeProvider scripts, record/replay cassettes."""

from __future__ import annotations

import asyncio
import json

import numpy as np
import pytest

from treehouse.pixels import array_sha256
from treehouse.providers.base import MissingPixels, pixel_free, require_pixels
from treehouse.providers.cassette import (
    Cassette,
    CassetteError,
    CassetteMiss,
    RecordingProvider,
    ReplayProvider,
)
from treehouse.providers.fake import FakeProvider, ScriptDivergence
from treehouse.schemas.config import InferenceParams
from treehouse.schemas.model_io import Image, Message, ModelRequest, ModelResponse, Text, ToolResult, ToolUse

ARR = np.arange(4 * 5 * 3, dtype=np.uint8).reshape(4, 5, 3)
SHA = array_sha256(ARR)


def image(with_bytes: bool) -> Image:
    return Image(format="png", sha256=SHA, bytes_=b"encoded-transport-bytes" if with_bytes else None)


def request(with_bytes=True, extra_user: str | None = None) -> ModelRequest:
    msgs = [
        Message(role="user", content=[Text(text="find bridges")]),
        Message(role="assistant", content=[ToolUse(id="tu-1", name="imagery_window", input={"scene_id": "S1"})]),
        Message(role="user", content=[ToolResult(tool_use_id="tu-1", status="success",
                                                 content=[Text(text="r-0001"), image(with_bytes)])]),
    ]
    if extra_user:
        msgs.append(Message(role="user", content=[Text(text=extra_user)]))
    return ModelRequest(model_id="m", system="sys", messages=msgs, params=InferenceParams(max_tokens=64))


def run(coro):
    return asyncio.run(coro)


class LiveStub:
    """Stands in for a live adapter (Bedrock in P6): it must refuse byte-less images."""

    provider_name = "aws.bedrock"

    def __init__(self, text="ok"):
        self.text = text

    async def complete(self, req, *, role, trial_index, turn):
        require_pixels(req)
        return ModelResponse(message=Message(role="assistant", content=[Text(text=f"{self.text}-{trial_index}")]),
                             stop_reason="end_turn", usage={"input_tokens": 5, "output_tokens": 1},
                             latency_ms=123, response_model_id="m")


# --- pixel hashing and keys -----------------------------------------------------------------------


def test_array_sha256_hashes_decoded_pixels_and_shape():
    assert array_sha256(ARR.copy()) == SHA
    assert array_sha256(ARR.reshape(5, 4, 3)) != SHA  # same bytes, different shape
    t = np.ascontiguousarray(ARR.transpose(1, 0, 2))
    assert array_sha256(ARR.transpose(1, 0, 2)) == array_sha256(t)  # C-order of the logical array
    with pytest.raises(TypeError):
        array_sha256(ARR.astype(np.int16))


def test_key_identical_with_or_without_image_bytes():
    assert request(True).key() == request(False).key() == pixel_free(request(True)).key()
    other = request(True).model_copy(update={"system": "different"})
    assert other.key() != request(True).key()


def test_key_changes_with_pixel_sha():
    r = request(False)
    msgs = list(r.messages)
    msgs[2] = Message(role="user", content=[ToolResult(tool_use_id="tu-1", status="success", content=[
        Text(text="r-0001"), Image(format="png", sha256=array_sha256(ARR + 1))])])
    assert r.model_copy(update={"messages": msgs}).key() != r.key()


def test_live_provider_raises_missing_pixels():
    with pytest.raises(MissingPixels, match=SHA):
        run(LiveStub().complete(request(False), role="worker", trial_index=0, turn=0))
    run(LiveStub().complete(request(True), role="worker", trial_index=0, turn=0))


def test_live_recorded_key_equals_pixel_free_replay_key(tmp_path):
    cas = Cassette(tmp_path / "model.jsonl")
    live = request(True)
    resp = run(RecordingProvider(LiveStub(), cas).complete(live, role="worker", trial_index=0, turn=0))
    raw = (tmp_path / "model.jsonl").read_text()
    assert "encoded-transport-bytes" not in raw and "ZW5jb2Rl" not in raw  # neither raw nor base64 pixels
    entry = json.loads(raw)
    assert entry["request_hash"] == live.key()
    replay = ReplayProvider(Cassette(tmp_path / "model.jsonl"))
    got = run(replay.complete(request(False), role="worker", trial_index=0, turn=0))
    assert got == resp


# --- FakeProvider ---------------------------------------------------------------------------------

SCRIPT = """
- expect: {contains: find bridges}
  respond:
    text: looking
    tool_use: [{name: stac_search, input: {aoi_bbox: [0, 0, 1, 1]}}]
- expect: {contains: r-0001, n_messages: 3}
  respond: {text: done here}
"""


def test_fake_provider_follows_yaml_script():
    fp = FakeProvider.from_yaml(SCRIPT)
    first = Message(role="user", content=[Text(text="please find bridges")])
    req0 = ModelRequest(model_id="m", system="s", messages=[first], params=InferenceParams(max_tokens=9))
    r0 = run(fp.complete(req0, role="worker", trial_index=2, turn=0))
    assert r0.stop_reason == "tool_use"
    (tu,) = [b for b in r0.message.content if isinstance(b, ToolUse)]
    assert tu.id == "tu-2-0-0" and tu.name == "stac_search"
    assert r0.usage.output_tokens == len('looking{"aoi_bbox":[0,0,1,1]}') // 4
    assert r0.usage.input_tokens > 0
    msgs = [first, r0.message,
            Message(role="user", content=[ToolResult(tool_use_id=tu.id, status="success", content=[Text(text="r-0001")])])]
    r1 = run(fp.complete(req0.model_copy(update={"messages": msgs}), role="worker", trial_index=2, turn=1))
    assert r1.stop_reason == "end_turn" and r1.message.content == [Text(text="done here")]
    assert r1.usage.output_tokens == len("done here") // 4


def test_fake_provider_script_divergence():
    fp = FakeProvider.from_yaml(SCRIPT)
    bad = ModelRequest(model_id="m", system="s", messages=[Message(role="user", content=[Text(text="other")])],
                       params=InferenceParams(max_tokens=9))
    with pytest.raises(ScriptDivergence, match="turn 0"):
        run(fp.complete(bad, role="worker", trial_index=0, turn=0))
    with pytest.raises(ScriptDivergence, match="exhausted"):
        run(fp.complete(bad, role="worker", trial_index=0, turn=5))
    with pytest.raises(ValueError):
        FakeProvider([{"expect": {"nonsense": 1}, "respond": {"text": "x"}}])


def test_fake_provider_callable():
    fp = FakeProvider(lambda req, *, role, trial_index, turn: {"text": f"{role}:{trial_index}:{turn}"})
    r = run(fp.complete(request(False), role="verifier", trial_index=1, turn=3))
    assert r.message.content == [Text(text="verifier:1:3")]


# --- cassettes ------------------------------------------------------------------------------------


def _recorded(tmp_path, responses_by_trial):
    cas = Cassette(tmp_path / "model.jsonl")
    for trial, text in responses_by_trial.items():
        run(RecordingProvider(LiveStub(text), cas).complete(request(True), role="worker", trial_index=trial, turn=0))
    return Cassette(tmp_path / "model.jsonl")


def test_trial_scoped_keys(tmp_path):
    cas = _recorded(tmp_path, {0: "alpha", 1: "beta"})
    rp = ReplayProvider(cas)
    a = run(rp.complete(request(False), role="worker", trial_index=0, turn=0))
    b = run(rp.complete(request(False), role="worker", trial_index=1, turn=0))
    assert a.message.content == [Text(text="alpha-0")] and b.message.content == [Text(text="beta-1")]


def test_cassette_miss_missing_key(tmp_path):
    rp = ReplayProvider(_recorded(tmp_path, {0: "alpha"}))
    with pytest.raises(CassetteMiss) as e:
        run(rp.complete(request(False), role="worker", trial_index=0, turn=1))
    assert e.value.key == ("worker", 0, 1) and e.value.first_divergent_message_index is None


def test_cassette_miss_reports_first_divergent_message(tmp_path):
    rp = ReplayProvider(_recorded(tmp_path, {0: "alpha"}))
    r = request(False)
    msgs = list(r.messages)
    msgs[1] = Message(role="assistant", content=[ToolUse(id="tu-1", name="imagery_window", input={"scene_id": "S2"})])
    with pytest.raises(CassetteMiss) as e:
        run(rp.complete(r.model_copy(update={"messages": msgs}), role="worker", trial_index=0, turn=0))
    assert e.value.first_divergent_message_index == 1
    with pytest.raises(CassetteMiss) as e:
        run(rp.complete(request(False, extra_user="more"), role="worker", trial_index=0, turn=0))
    assert e.value.first_divergent_message_index == 3


def test_replay_only_fails_on_miss_and_cassette_refuses_duplicates(tmp_path):
    with pytest.raises(ValueError):
        ReplayProvider(Cassette(), miss="live")
    cas = _recorded(tmp_path, {0: "alpha"})
    with pytest.raises(CassetteError):
        run(RecordingProvider(LiveStub(), cas).complete(request(True), role="worker", trial_index=0, turn=0))
