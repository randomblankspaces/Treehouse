"""Retrieval tool server (task 3): sources, index, examples, retrieve, classify, aggregate. Offline."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from mcp.client import Client

from treehouse.cards import load_card
from treehouse.paths import keys_root
from treehouse.schemas.tools import ToolError
from treehouse.tools.retrieval import NoExamples, RetrievalTools, make_retrieval_server, retrieval_for_card

NAGOYA = (136.82, 35.05, 136.92, 35.12)
SMOKE_AOI = (136.82, 35.05, 136.87, 35.085)
TOOLS = {"list_embedding_sources", "build_index", "get_examples", "retrieve", "classify", "aggregate"}


@pytest.fixture(scope="module")
def card():
    return load_card("tasks/t1-nagoya-warehouses.yaml")


@pytest.fixture(scope="module")
def rt(card) -> RetrievalTools:
    return retrieval_for_card(card)


@pytest.fixture(scope="module")
def idx_id(rt) -> str:
    out = rt.build_index("aef-10m-annual", 160, 2024, NAGOYA)
    assert not isinstance(out, ToolError)
    return out["index_id"]


def _split():
    return json.loads((keys_root() / "plateau" / "nagoya-split.json").read_text())


def _key_points() -> dict[str, tuple[float, float]]:
    fc = json.loads((keys_root() / "plateau" / "nagoya-warehouses.geojson").read_text())
    return {f["id"]: tuple(f["geometry"]["coordinates"]) for f in fc["features"]}


PROV = {"source", "source_id", "date_range", "resolution_m", "cell_size_m", "licence", "cost_usd"}


def test_list_embedding_sources_has_both_with_licences(rt):
    out = rt.list_embedding_sources(NAGOYA)
    ids = {s["source_id"]: s for s in out["sources"]}
    assert set(ids) == {"aef-10m-annual", "lgnd-clay-embeddings"}
    for s in ids.values():
        assert s["licence"] == "CC-BY-4.0" and s["model"] and s["native_cell_m"] > 0
        assert s["resolution_m"] == 10.0 and len(s["date_range"]) == 2 and "estimated_cost_usd" in s
    assert ids["lgnd-clay-embeddings"]["native_cell_m"] == 1280.0


def test_build_index_provenance_complete(rt, idx_id):
    out = rt.build_index("aef-10m-annual", 160, 2024, NAGOYA)
    assert out["index_id"] == idx_id  # cached in-process
    assert out["cells"] > 1000 and PROV <= set(out["provenance"])
    assert out["provenance"]["licence"] == "CC-BY-4.0" and out["provenance"]["cell_size_m"] == 160


@pytest.mark.parametrize("sid,code", [("sentinel-2-l2a-cogs", "not_allowlisted"), ("other-embeddings", "not_allowlisted"),
                                      ("maxar-wv3", "forbidden_source"), ("Vantor-legion", "forbidden_source")])
def test_build_index_refuses(rt, sid, code):
    out = rt.build_index(sid, 160, 2024, NAGOYA)
    assert isinstance(out, ToolError) and out.code == code
    assert "maxar" not in out.message.casefold() and "vantor" not in out.message.casefold()


def test_get_examples_train_only(rt):
    out = rt.get_examples(100)
    ids = [e["example_id"] for e in out["examples"]]
    sp = _split()
    assert ids and set(ids) <= set(sp["train"]) and not set(ids) & set(sp["heldout"])
    assert len(rt.get_examples(3)["examples"]) == 3 and "licence" in out["provenance"]
    assert all(not str(v).startswith("keys") for v in out["provenance"].values())
    for split in ("heldout", "test", "all"):
        bad = rt.get_examples(5, split=split)
        assert isinstance(bad, ToolError) and bad.code == "heldout_forbidden"


def test_example_provider_is_selected_explicitly(card):
    keyed_copy = card.model_copy(update={"id": "renamed-card"})
    assert not isinstance(retrieval_for_card(keyed_copy).examples, NoExamples)

    data = card.model_dump()
    data["id"] = "nagoya-unrelated"
    data["steps"][0]["keying"]["key_path"] = "keys/other/reference.geojson"
    unrelated = type(card).model_validate(data)
    assert isinstance(retrieval_for_card(unrelated).examples, NoExamples)


def test_gifu_has_no_examples():
    rt = retrieval_for_card(load_card("tasks/t5-gifu-warehouses.yaml"))
    assert isinstance(rt.examples, NoExamples) and rt.get_examples(5)["examples"] == []


def test_few_shot_ranks_warehouse_cells_high(rt, idx_id):
    train = [e["example_id"] for e in rt.get_examples(100)["examples"]]
    out = rt.retrieve(idx_id, "few_shot", 60, example_ids=train)
    assert PROV <= set(out["provenance"]) and len(out["cells"]) == 60
    scores = [c["score"] for c in out["cells"]]
    assert scores == sorted(scores, reverse=True)
    # held-out warehouse cells (never shown to the tool) carry the signal
    idx = rt.indexes[idx_id]
    pts = _key_points()
    held = {str(idx.cell_ids[np.argmin((idx.lon - x) ** 2 + (idx.lat - y) ** 2)])
            for i in _split()["heldout"] for x, y in [pts[i]]}
    top = {c["cell_id"] for c in out["cells"]}
    assert len(top & held) >= 15
    q = rt.retrieve(idx_id, "few_shot", 5, query_lonlat=pts[train[0]])
    assert len(q["cells"]) == 5
    cv = rt.retrieve(idx_id, "concept_vector", 60, example_ids=train)
    assert len({c["cell_id"] for c in cv["cells"]} & held) >= 10


def test_examples_outside_index_are_dropped(card):
    tools = retrieval_for_card(card)
    built = tools.build_index("aef-10m-annual", 160, 2024, SMOKE_AOI)
    assert not isinstance(built, ToolError)
    index_id = built["index_id"]
    idx = tools.indexes[index_id]
    examples = tools.examples.train_examples()
    inside = {
        e["example_id"]
        for e in examples
        if np.any(
            (np.abs(idx.lon - e["lon"]) <= idx.cell_deg / 2 + 1e-8)
            & (np.abs(idx.lat - e["lat"]) <= idx.cell_deg / 2 + 1e-8)
        )
    }
    expected_dropped = [e["example_id"] for e in examples if e["example_id"] not in inside]
    out = tools.retrieve(index_id, "few_shot", 5)
    assert out["example_cells"] <= len(inside)
    assert out["dropped_example_ids"] == expected_dropped

    outside = next(e["example_id"] for e in examples if e["example_id"] not in inside)
    none = tools.classify(index_id, "linear_probe", example_ids=[outside])
    assert isinstance(none, ToolError) and none.code == "no_examples"


def test_retrieve_rejects_heldout_and_unknown(rt, idx_id):
    bad = rt.retrieve(idx_id, "few_shot", 5, example_ids=[_split()["heldout"][0]])
    assert isinstance(bad, ToolError) and bad.code == "bad_args"
    assert rt.retrieve("idx-999", "few_shot", 5).code == "unknown_index"


@pytest.mark.parametrize("method", ["linear_probe", "linear_svm"])
def test_classifiers_in_unit_interval_and_deterministic(rt, idx_id, method):
    train = [e["example_id"] for e in rt.get_examples(100)["examples"]]
    a = rt.classify(idx_id, method, None, train)
    b = rt.classify(idx_id, method, None, train)
    assert a == b and PROV <= set(a["provenance"])
    s = np.array([c["score"] for c in a["scores"]])
    assert len(s) == 200 and a["n_scored"] == len(rt.indexes[idx_id].cell_ids)
    assert s.min() >= 0 and s.max() <= 1 and np.all(s[:-1] >= s[1:])
    assert set(a["score_summary"]) == {"min", "median", "max"}
    assert 0 <= a["score_summary"]["min"] <= a["score_summary"]["median"] <= a["score_summary"]["max"] <= 1
    assert a["score_summary"]["max"] == s.max()

    all_ids = rt.indexes[idx_id].cell_ids.tolist()
    capped = rt.classify(idx_id, method, all_ids, train, k=2_000)
    assert len(capped["scores"]) == 1_000 and capped["n_scored"] == len(all_ids)
    sub = rt.classify(idx_id, method, [a["scores"][0]["cell_id"]], train)
    assert len(sub["scores"]) == 1 and sub["scores"][0]["score"] == a["scores"][0]["score"]
    assert sub["n_scored"] == 1 and sub["score_summary"] == {
        "min": a["scores"][0]["score"],
        "median": a["scores"][0]["score"],
        "max": a["scores"][0]["score"],
    }


def test_not_configured_seams(rt, idx_id):
    z = rt.retrieve(idx_id, "zero_shot_text", 5)
    v = rt.classify(idx_id, "vision_subagent", None, None)
    assert z.code == v.code == "not_configured"


def test_aggregate_merges_neighbours(rt, idx_id):
    idx = rt.indexes[idx_id]
    ids = set(idx.cell_ids.tolist())
    a, b, far = "r010c010", "r010c011", "r040c060"
    assert {a, b, far} <= ids
    scored = [{"cell_id": a, "score": 0.9}, {"cell_id": b, "score": 0.7}, {"cell_id": far, "score": 0.6},
              {"cell_id": "r020c020", "score": 0.1}]
    out = rt.aggregate(idx_id, scored, 0.5)
    assert len(out["sites"]) == 2
    s1 = next(s for s in out["sites"] if a in s["member_cell_ids"])
    assert set(s1["member_cell_ids"]) == {a, b} and s1["max_score"] == 0.9
    assert out["count"] == {"low": 1, "high": 2, "low_score_threshold": 0.8}
    assert "75th percentile" in out["count_rule"]
    assert out["unreviewed_cell_count"] == idx.nx * idx.ny - 4
    assert out["unreviewed_area_km2"] == pytest.approx((idx.nx * idx.ny - 4) * 160**2 / 1_000_000)
    assert PROV <= set(out["provenance"])
    diag = rt.aggregate(idx_id, [{"cell_id": "r010c010", "score": 1}, {"cell_id": "r011c011", "score": 1}], 0.5)
    four = rt.aggregate(idx_id, [{"cell_id": "r010c010", "score": 1}, {"cell_id": "r011c011", "score": 1}], 0.5,
                        merge_rule="4-neighbour")
    assert len(diag["sites"]) == 1 and len(four["sites"]) == 2
    assert rt.aggregate(idx_id, [{"cell_id": "nope", "score": 1}], 0.5).code == "bad_args"


def test_aggregate_validates_scores_and_preserves_negative_max(rt, idx_id):
    negative = rt.aggregate(
        idx_id,
        [{"cell_id": "r010c010", "score": -0.4}, {"cell_id": "r010c010", "score": -0.2}],
        -0.3,
    )
    assert negative["sites"][0]["max_score"] == -0.2

    for scored, threshold in [
        ([{"cell_id": "r010c010"}], 0.5),
        ([{"cell_id": "r010c010", "score": "0.7"}], 0.5),
        ([{"cell_id": "r010c010", "score": float("nan")}], 0.5),
        ([{"cell_id": "r010c010", "score": float("inf")}], 0.5),
        ([{"cell_id": "r010c010", "score": 0.7}], float("nan")),
        ([{"cell_id": "r010c010", "score": 0.7}], float("inf")),
    ]:
        bad = rt.aggregate(idx_id, scored, threshold)
        assert isinstance(bad, ToolError) and bad.code == "bad_args"


def test_aggregate_low_count_adapts_to_score_scale(rt, idx_id):
    scored = [
        {"cell_id": "r010c010", "score": 0.2},
        {"cell_id": "r020c020", "score": 0.3},
        {"cell_id": "r030c030", "score": 0.4},
        {"cell_id": "r040c040", "score": 0.5},
    ]
    out = rt.aggregate(idx_id, scored, 0.1)
    assert out["count"] == {"low": 1, "high": 4, "low_score_threshold": 0.425}
    assert "75th percentile" in out["count_rule"]


def test_every_retrieval_tool_succeeds_through_gateway(tmp_path, card):
    sys.path.insert(0, str(Path(__file__).parents[1] / "integration"))
    try:
        from gwrig import make_rig
    finally:
        sys.path.pop(0)
    rig = make_rig(tmp_path / "retrieval.trace.jsonl", task=card)

    async def go():
        async with rig.gateway as gateway:
            outcomes = []
            outcomes.append(await gateway.call(
                "list_embedding_sources", {"aoi_bbox": list(SMOKE_AOI)}, call_id="retrieval-1"
            ))
            built = await gateway.call(
                "build_index",
                {"source_id": "aef-10m-annual", "cell_size_m": 160, "year": 2024,
                 "aoi_bbox": list(SMOKE_AOI)},
                call_id="retrieval-2",
            )
            outcomes.append(built)
            index_id = built.content[0].json_["index_id"]
            examples = await gateway.call("get_examples", {"n": 3}, call_id="retrieval-3")
            outcomes.append(examples)
            example_ids = [e["example_id"] for e in examples.content[0].json_["examples"]]
            retrieved = await gateway.call(
                "retrieve",
                {"index_id": index_id, "method": "few_shot", "k": 5, "example_ids": example_ids},
                call_id="retrieval-4",
            )
            outcomes.append(retrieved)
            cell_ids = [c["cell_id"] for c in retrieved.content[0].json_["cells"]]
            classified = await gateway.call(
                "classify",
                {"index_id": index_id, "method": "linear_probe", "cell_ids": cell_ids,
                 "example_ids": example_ids},
                call_id="retrieval-5",
            )
            outcomes.append(classified)
            outcomes.append(await gateway.call(
                "aggregate",
                {"index_id": index_id, "scored_cells": classified.content[0].json_["scores"],
                 "threshold": 0.5},
                call_id="retrieval-6",
            ))
            return outcomes

    outcomes = asyncio.run(go())
    rig.tracer.close()
    assert [out.status for out in outcomes] == ["success"] * len(TOOLS)


def test_mcp_server_exposes_tools_with_descriptions(rt, idx_id):
    async def go():
        async with Client(make_retrieval_server(rt)) as c:
            tools = {t.name: t for t in (await c.list_tools()).tools}
            r = await c.call_tool("build_index", {"source_id": "aef-10m-annual", "cell_size_m": 160, "year": 2024,
                                                  "aoi_bbox": list(NAGOYA)})
            return tools, r.structured_content
    tools, sc = asyncio.run(go())
    assert set(tools) == TOOLS and all(t.description for t in tools.values())
    assert sc["result"]["index_id"] == idx_id


def test_build_servers_adds_retrieval_only_when_card_needs_it(card):
    from treehouse.gateway.pixel_cache import PixelCache
    from treehouse.tools.claims import ClaimLedger
    from treehouse.tools.servers import build_servers

    def names(c):
        return list(build_servers(c, ledger=ClaimLedger(c, run_id="r", trial_id="t"), pixels=PixelCache()))
    assert names(card)[-1] == "retrieval"
    old = load_card("tasks/synth-crossings-v1.yaml")
    assert names(old) == ["stac", "imagery", "clay", "claims", "decoy"]
