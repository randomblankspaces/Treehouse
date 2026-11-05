"""Vision sub-agent classification and retrieval wiring. No network or AWS."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from treehouse.cards import load_card
from treehouse.providers.base import iter_images
from treehouse.providers.cassette import Cassette, RecordingProvider, ReplayProvider
from treehouse.schemas.model_io import Message, ModelResponse, Text, Usage
from treehouse.schemas.tools import ToolError
from treehouse.tools.retrieval import retrieval_for_card
from treehouse.tools.sources.gsi import (
    GsiSeamlessPhotoSource,
    RecordingGsiSeamlessPhotoSource,
    ReplayGsiSeamlessPhotoSource,
)
from treehouse.verifier.vision_classifier_agent import MAX_CELLS, VisionSubagent

JPEG = b"jpeg-bytes-for-test"
PROVENANCE = {
    "source": "GSI seamless aerial photo",
    "attribution": "出典：国土地理院 (GSI Japan) seamless aerial photographs",
    "licence": "LicenseRef-gsi-japan-attribution",
    "tile": {"z": 18, "x": 1, "y": 2},
    "url": "https://example.test/tile.jpg",
    "gsd_m": 0.5,
    "sha256": "0" * 64,
    "bytes": len(JPEG),
}


class FakeProvider:
    provider_name = "fake"

    def __init__(self, answers):
        self.answers = iter(answers)
        self.requests = []

    async def complete(self, req, *, role, trial_index, turn):
        self.requests.append((req, role, trial_index, turn))
        answer = next(self.answers)
        return ModelResponse(
            message=Message(role="assistant", content=[Text(text=answer)]),
            stop_reason="end_turn",
            usage=Usage(input_tokens=13, output_tokens=7, image_input_tokens=5),
            latency_ms=2,
            response_model_id="test-vision-model",
            cost_usd=0.004,
        )


def chip(_lon, _lat, side_m):
    assert side_m == 160
    return JPEG, PROVENANCE


def test_subagent_sends_image_and_registry_definitions_and_scores_labels():
    provider = FakeProvider(
        [
            json.dumps({"label": "present", "confidence": 0.8, "explanation": "large storage roof"}),
            'prefix {"label":"absent","confidence":0.7,"explanation":"factory"} suffix',
        ]
    )
    agent = VisionSubagent(provider, "requested-model")

    out = asyncio.run(
        agent.classify_cells(
            [
                {"cell_id": "a", "lon": 136.8, "lat": 35.1},
                {"cell_id": "b", "lon": 136.9, "lat": 35.2},
            ],
            chip,
        )
    )

    assert [row["score"] for row in out] == [0.8, pytest.approx(0.3)]
    assert [row["label"] for row in out] == ["present", "absent"]
    req, role, trial_index, turn = provider.requests[0]
    assert req.model_id == "requested-model"
    assert (role, trial_index, turn) == ("classifier", 0, 0)
    assert [image.bytes_ for _, image in iter_images(req.messages)] == [JPEG]
    prompt = "\n".join(
        block.text for message in req.messages for block in message.content if isinstance(block, Text)
    )
    assert "Warehouses and large logistics/storage buildings" in prompt
    for negative in ("factories", "markets", "aircraft hangars", "other large roofs"):
        assert negative in prompt
    assert out[0]["usage"]["input_tokens"] == 13
    assert out[0]["cost_usd"] == 0.004
    assert out[0]["imagery"] == PROVENANCE


def test_subagent_uses_unique_cassette_keys_across_classify_calls():
    provider = FakeProvider(
        [
            '{"label":"present","confidence":0.8,"explanation":"roof"}',
            '{"label":"absent","confidence":0.8,"explanation":"factory"}',
        ]
    )
    agent = VisionSubagent(provider, "requested-model")
    cell = [{"cell_id": "a", "lon": 136.8, "lat": 35.1}]

    asyncio.run(agent.classify_cells(cell, chip))
    asyncio.run(agent.classify_cells(cell, chip))

    assert [(role, trial_index, turn) for _, role, trial_index, turn in provider.requests] == [
        ("classifier", 0, 0),
        ("classifier", 1, 0),
    ]


def test_recorded_gsi_and_cassette_replay_without_pixels_or_fetches(tmp_path: Path):
    cassette_path = tmp_path / "vision.jsonl"
    gsi_log_path = tmp_path / "gsi.jsonl"
    fetches = []

    def fetch(url):
        fetches.append(url)
        return JPEG

    answer = '{"label":"present","confidence":0.73,"explanation":"storage roof"}'
    live_inner = FakeProvider([answer])
    live_agent = VisionSubagent(RecordingProvider(live_inner, Cassette(cassette_path)), "requested-model")
    live_source = RecordingGsiSeamlessPhotoSource(gsi_log_path, fetcher=fetch)
    cells = [{"cell_id": "a", "lon": 136.8, "lat": 35.1}]

    live = asyncio.run(live_agent.classify_cells(cells, live_source.chip))
    assert len(fetches) == 1
    assert JPEG not in cassette_path.read_bytes() and JPEG not in gsi_log_path.read_bytes()
    log_entry = json.loads(gsi_log_path.read_text())
    assert set(log_entry) == {"url", "z", "x", "y", "sha256", "bytes", "retrieved_at"}

    replay_provider = ReplayProvider(Cassette(cassette_path))
    replay_agent = VisionSubagent(replay_provider, "requested-model")
    replay_source = ReplayGsiSeamlessPhotoSource(gsi_log_path)
    replayed = asyncio.run(replay_agent.classify_cells(cells, replay_source.chip))

    assert replayed == live
    assert len(fetches) == 1
    assert replay_provider.unused_keys() == []
    replay_request = replay_provider.cassette.get(("classifier", 0, 0)).request
    assert [image.bytes_ for _, image in iter_images(replay_request.messages)] == [None]


def test_malformed_reply_returns_none_score_instead_of_crashing():
    provider = FakeProvider(["not json"])
    agent = VisionSubagent(provider, "requested-model")

    (row,) = asyncio.run(agent.classify_cells([{"cell_id": "a", "lon": 136.8, "lat": 35.1}], chip))

    assert row["score"] is None and row["label"] is None
    assert "invalid model response" in row["explanation"]
    assert row["usage"]["output_tokens"] == 7


def test_cell_cap_is_checked_before_fetch_or_model_call():
    provider = FakeProvider([])
    agent = VisionSubagent(provider, "requested-model")
    fetched = []

    with pytest.raises(ValueError, match=str(MAX_CELLS)):
        asyncio.run(
            agent.classify_cells(
                [{"cell_id": str(i), "lon": 136.8, "lat": 35.1} for i in range(MAX_CELLS + 1)],
                lambda *args: fetched.append(args),
            )
        )
    assert not fetched and not provider.requests


def test_retrieval_vision_injection_scores_cells_and_reports_gsi_calls():
    card = load_card("tasks/t1-nagoya-warehouses.yaml")
    provider = FakeProvider(
        [json.dumps({"label": "present", "confidence": 0.75, "explanation": "warehouse"})]
    )
    vision = VisionSubagent(provider, "requested-model")
    gsi = GsiSeamlessPhotoSource(fetcher=lambda _url: JPEG)
    tools = retrieval_for_card(card, vision=vision, gsi=gsi)
    built = tools.build_index("aef-10m-annual", 160, 2024, tuple(card.smoke_aoi))
    assert not isinstance(built, ToolError)
    cell_id = str(tools.indexes[built["index_id"]].cell_ids[0])

    out = tools.classify(built["index_id"], "vision_subagent", [cell_id])

    assert out["scores"][0]["score"] == 0.75
    call = out["provenance"]["vision_calls"][0]
    assert call["cell_id"] == cell_id and call["cost_usd"] == 0.004
    assert call["usage"]["image_input_tokens"] == 5
    assert out["provenance"]["imagery"]["attribution"].startswith("出典：国土地理院")
    assert out["provenance"]["cost_usd"] == 0.004


def test_retrieval_without_injection_or_allowlist_stays_not_configured():
    card = load_card("tasks/t1-nagoya-warehouses.yaml")
    offline = retrieval_for_card(card)
    assert offline.classify("idx-does-not-matter", "vision_subagent", ["r000c000"]).code == "not_configured"

    data = card.model_dump()
    data["data_allowlist"] = [
        d for d in data["data_allowlist"] if d["source_id"] != "gsi-seamless-aerial-japan"
    ]
    disallowed = retrieval_for_card(type(card).model_validate(data), vision=object())
    assert (
        disallowed.classify("idx-does-not-matter", "vision_subagent", ["r000c000"]).code == "not_configured"
    )


def test_vision_requires_explicit_cells_and_respects_cap():
    card = load_card("tasks/t1-nagoya-warehouses.yaml")
    tools = retrieval_for_card(card, vision=object(), gsi=object())
    no_cells = tools.classify("idx-does-not-matter", "vision_subagent")
    too_many = tools.classify(
        "idx-does-not-matter", "vision_subagent", [str(i) for i in range(MAX_CELLS + 1)]
    )
    assert no_cells.code == too_many.code == "bad_args"
