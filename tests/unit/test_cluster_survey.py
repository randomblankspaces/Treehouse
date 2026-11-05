"""Synthetic embedding experiment, never evidence of real wind detection."""
import asyncio
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from mcp.client import Client
from pydantic import ValidationError

from treehouse.cards import load_card, validate_card
from treehouse.schemas.tools import ToolError
from treehouse.tools.retrieval import make_retrieval_server, retrieval_for_card
from treehouse.tools.sources.embedding_source import CellIndex


@pytest.fixture
def index():
    spec = json.loads(Path("fixtures/embeddings/two-clumps.json").read_text())
    nx, ny = spec["nx"], spec["ny"]
    y, x = np.indices((ny, nx)).reshape(2, -1)
    labels = (x + 2 * y) % 6
    for label, (x0, y0, x1, y1) in enumerate(spec["clumps"], 6):
        labels[(x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)] = label
    return CellIndex("synthetic-clumps", 1280, "EPSG:4326", 140, 40, .01, nx, ny,
                     np.array([f"r{r:03d}c{c:03d}" for r, c in zip(y, x, strict=True)]),
                     140 + (x + .5) * .01, 40 + (y + .5) * .01,
                     np.eye(8, dtype=np.float32)[labels], "synthetic", "lgnd-clay-embeddings",
                     ("2024-01-01", "2024-12-31"), 10, "LicenseRef-synthetic", 0, True)


def card_with_examples(examples):
    card = load_card("tasks/t1-nagoya-warehouses-real.yaml")
    return type(card).model_validate({**card.model_dump(), "user_examples": examples})


@pytest.fixture
def tools(index):
    card = load_card("tasks/t1-nagoya-warehouses-real.yaml")
    card = card.model_copy(update={"tools_allowed": [*card.tools_allowed, "survey_clusters"]})
    tools = retrieval_for_card(card)
    tools.indexes["idx-001"] = index
    return tools


def test_survey_finds_planted_clumps_and_is_repeatable(tools, index):
    result = tools.survey_clusters("idx-001", n_clusters=8, seed=17)
    assert result == tools.survey_clusters("idx-001", n_clusters=8, seed=17)
    clusters = sorted(result["clusters"], key=lambda c: -c["spatial_compactness"])
    assert len(clusters) == 8
    assert sum(c["size"] for c in clusters) == len(index.cell_ids)
    assert [(c["size"], c["spatial_compactness"]) for c in clusters[:2]] == [(9, 1.0), (9, 1.0)]
    assert all(c["spatial_compactness"] == 0 for c in clusters[2:])
    assert sorted(c["bbox"] for c in clusters[:2]) == [[140.01, 40.01, 140.04, 40.04],
                                                               [140.08, 40.08, 140.11, 40.11]]
    medoid = clusters[0]["medoid_cell"]
    ranked = tools.retrieve("idx-001", "few_shot", k=9, query_lonlat=(medoid["lon"], medoid["lat"]))
    assert len(ranked["cells"]) == 9 and all(c["score"] == 1 for c in ranked["cells"])
    assert result["provenance"]["synthetic"] is True


@pytest.mark.parametrize("n,seed", [(7, 0), (65, 0), (8, -1), (8.5, 0), (True, 0), (8, True)])
def test_survey_rejects_invalid_parameters(tools, n, seed):
    assert tools.survey_clusters("idx-001", n, seed).code == "bad_args"


def test_survey_unknown_index_and_degenerate_embeddings(tools, index):
    assert tools.survey_clusters("missing").code == "unknown_index"
    index.emb[:] = np.eye(8, dtype=np.float32)[0]
    result = tools.survey_clusters("idx-001", 8, 3)
    assert len(result["clusters"]) == 1 and result["clusters"][0]["size"] == 144


def test_user_examples_are_separate_from_reference_and_usable(index):
    example = {"lon": float(index.lon[13]), "lat": float(index.lat[13]), "label": "analyst positive"}
    tools = retrieval_for_card(card_with_examples([example]))
    tools.indexes["idx-001"] = index
    result = tools.get_examples(30, split="user")
    assert result["available"] == 1 and result["split"] == "user"
    assert result["provenance"]["source"] == "analyst-supplied"
    assert result["examples"][0] == {**example, "example_id": "user-0001"}
    assert tools.get_examples()["available"] == 0
    for split in ("heldout", "test", "all", "reference"):
        assert tools.get_examples(split=split).code == "heldout_forbidden"
    ranked = tools.retrieve("idx-001", "few_shot", example_ids=["user-0001"])
    assert ranked["cells"][0]["score"] == 1
    assert isinstance(tools.retrieve("idx-001", "few_shot", example_ids=["heldout-001"]), ToolError)


def test_user_examples_from_another_region_seed_target_index(index):
    tools = retrieval_for_card(card_with_examples([{"lon": 142.015, "lat": 42.015}]))
    tools.indexes["idx-001"] = index
    reads = []

    class Source:
        def index(self, bbox, cell_size_m, year):
            reads.append((bbox, cell_size_m, year))
            return replace(index, lon=index.lon + 2, lat=index.lat + 2, lon0=142, lat0=42)

    tools.factories["lgnd-clay-embeddings"] = lambda aoi: Source()
    ranked = tools.retrieve("idx-001", "few_shot", k=9, example_ids=["user-0001"])
    assert isinstance(ranked, dict), ranked
    assert len(reads) == 1 and reads[0][1:] == (1280, 2024)
    assert len(ranked["cells"]) == 9 and all(c["score"] == 1 for c in ranked["cells"])
    assert ranked["dropped_example_ids"] == []
    assert ranked["details"]["user_example_provenance"]["synthetic"] is True
    assert all(c["lon"] < 141 for c in ranked["cells"])


def test_legacy_user_split_error_unchanged():
    tools = retrieval_for_card(load_card("tasks/t1-nagoya-warehouses.yaml"))
    assert tools.get_examples(split="user").code == "heldout_forbidden"


@pytest.mark.parametrize("point", [{"lon": 181, "lat": 0}, {"lon": 0, "lat": -91},
                                   {"lon": float("nan"), "lat": 0},
                                   {"lon": 0, "lat": 0, "key_path": "keys/hidden"}])
def test_user_examples_validate_coordinates_and_reject_reference_fields(point):
    with pytest.raises(ValidationError):
        card_with_examples([point])


def test_real_source_does_not_require_a_fixture_city(monkeypatch):
    card = load_card("tasks/t1-nagoya-warehouses-real.yaml").model_copy(update={"id": "new-region"})
    tools = retrieval_for_card(card)
    assert tools.list_embedding_sources()["sources"]
    seen = []
    monkeypatch.setattr(tools.factories["lgnd-clay-embeddings"]("unused").__class__, "index",
                        lambda self, *args: seen.append(args) or pytest.fail("real reader reached"))
    with pytest.raises(pytest.fail.Exception, match="real reader reached"):
        tools.build_index("lgnd-clay-embeddings", 1280, 2024)
    assert seen


def test_tool_exposure_is_opt_in_and_legacy_card_hash_unchanged(tools):
    async def descriptions(rt):
        async with Client(make_retrieval_server(rt)) as client:
            return {tool.name: tool for tool in (await client.list_tools()).tools}

    legacy = load_card("tasks/t1-nagoya-warehouses.yaml")
    assert legacy.card_hash() == "sha256:7b01f7d060e8550bc99b8001e2f222c0a1edfffbaebe377fca36357e75d18889"
    before = asyncio.run(descriptions(retrieval_for_card(legacy)))
    after = asyncio.run(descriptions(tools))
    assert "survey_clusters" not in before and "survey_clusters" in after
    assert {name: tool.model_dump() for name, tool in before.items()} == {
        name: after[name].model_dump() for name in before}
    user = asyncio.run(descriptions(retrieval_for_card(card_with_examples([{"lon": 140, "lat": 40}]))))
    assert 'split="user"' in user["get_examples"].description


def test_zero_example_wind_card_validates_and_keeps_grading_reference_private():
    path = "tasks/t1-japan-wind-zero-shot.yaml"
    card = load_card(path)
    assert validate_card(path).errors == []
    assert set(card.classes) == {"wind_turbine"} and card.user_examples == []
    assert "survey_clusters" in card.tools_allowed
    assert any(d.source_id == "lgnd-clay-embeddings" and d.access == "real" for d in card.data_allowlist)
    tools = retrieval_for_card(card)
    assert tools.get_examples(split="user")["available"] == 0
    assert tools.get_examples(split="train")["available"] == 0
    assert tools.get_examples(split="heldout").code == "heldout_forbidden"
    assert any(s.kind == "path" and s.pattern == "keys/" for s in card.forbidden_sources)
