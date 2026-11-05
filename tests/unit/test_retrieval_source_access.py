"""Card access selects the real LGND reader only by explicit opt-in."""

from treehouse.cards import load_card
from treehouse.tools.retrieval import retrieval_for_card
from treehouse.tools.sources.clay_lgnd import ClayLgndSource
from treehouse.tools.sources.clay_lgnd_real import RealClayLgndSource

SOURCE = "lgnd-clay-embeddings"
BBOX = (136.82, 35.05, 136.92, 35.12)


def test_card_real_access_selects_real_reader(monkeypatch):
    card = load_card("tasks/t1-nagoya-warehouses.yaml")
    data = card.model_dump()
    next(source for source in data["data_allowlist"] if source["source_id"] == SOURCE)["access"] = "real"
    card = type(card).model_validate(data)
    reads = []
    fixture_index = ClayLgndSource.for_aoi("nagoya").index(BBOX, 1280, 2024)

    def read(self, bbox, cell_size_m, year):
        reads.append((self, bbox, cell_size_m, year))
        return fixture_index  # Synthetic stand-in; no network or Parquet decoder.

    monkeypatch.setattr(RealClayLgndSource, "index", read)
    tools = retrieval_for_card(card)
    listed = next(source for source in tools.list_embedding_sources()["sources"] if source["source_id"] == SOURCE)
    assert listed["access"] == "real"
    built = tools.build_index(SOURCE, 1280, 2024, BBOX)
    assert built["cells"] == len(fixture_index.cell_ids)
    assert len(reads) == 1 and isinstance(reads[0][0], RealClayLgndSource)
    assert reads[0][1:] == (BBOX, 1280, 2024)


def test_default_card_access_keeps_fixture_reader(monkeypatch):
    def unexpected_read(*args, **kwargs):
        raise AssertionError("default access must not reach the real reader")

    monkeypatch.setattr(RealClayLgndSource, "index", unexpected_read)
    tools = retrieval_for_card(load_card("tasks/t1-nagoya-warehouses.yaml"))
    assert isinstance(tools.factories[SOURCE]("nagoya"), ClayLgndSource)
    listed = next(source for source in tools.list_embedding_sources()["sources"] if source["source_id"] == SOURCE)
    assert listed["access"] == "fixture"
    assert tools.build_index(SOURCE, 1280, 2024, BBOX)["provenance"]["access"] == "fixture"
