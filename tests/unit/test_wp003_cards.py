"""Live matrix extensions validate offline without presenting fixtures as real evidence."""
import json
import runpy
from pathlib import Path

import pytest
from pydantic import ValidationError

from treehouse.cards import load_card, validate_card
from treehouse.providers.prices import load_default
from treehouse.providers.registry import ModelRegistry
from treehouse.schemas.task import TaskCard

ROOT = Path(__file__).resolve().parents[2]
CARDS = ("t1-nagoya-warehouses-real", "t1-chattogram-fuel-tanks")


@pytest.mark.parametrize("name", CARDS)
def test_real_cards_validate_without_synthetic_sources(name):
    path = ROOT / "tasks" / f"{name}.yaml"
    report = validate_card(path)
    assert not report.errors
    card = load_card(path)
    source = next(s for s in card.data_allowlist if s.source_id == "lgnd-clay-embeddings")
    assert source.access == "real"
    key = card.steps[0].keying
    assert key.reference_quality == "incomplete" and key.status == "pending_fetch"
    assert key.key_path.startswith("keys/osm/")
    assert all(s.access != "synthetic" for s in card.data_allowlist)
    assert card.minutes_per_cell == 2.0
    if name == CARDS[0]:
        assert card.aoi == load_card(ROOT / "tasks/t1-nagoya-warehouses.yaml").aoi
        assert any(s.source_id == "gsi-seamless-aerial-japan" for s in card.data_allowlist)
    else:
        assert set(card.classes) == {"oil_fuel_tank"}
        assert all(s.kind != "imagery" for s in card.data_allowlist)
        assert "imagery_window" not in card.tools_allowed and not card.needs_vision
        assert "disaster risk finance" in card.goal.lower()


def test_default_analyst_assumption_preserves_existing_card_serialization():
    card = load_card(ROOT / "tasks/t1-nagoya-warehouses.yaml")
    assert card.minutes_per_cell == 2.0
    assert "minutes_per_cell" not in card.model_dump(mode="json")
    assert "minutes_per_cell" not in json.loads(card.model_dump_json())
    explicit = TaskCard.model_validate(card.model_dump() | {"minutes_per_cell": 4.0})
    assert explicit.model_dump()["minutes_per_cell"] == 4.0
    assert explicit.card_hash() != card.card_hash()
    for minutes in (0, -1, float("inf"), float("nan")):
        with pytest.raises(ValidationError):
            TaskCard.model_validate(card.model_dump() | {"minutes_per_cell": minutes})


@pytest.mark.parametrize("name", CARDS)
def test_haiku_live_config_and_ceiling_price(name):
    make_config = runpy.run_path(str(ROOT / "scripts/make_live_config.py"))["make_live_config"]
    config = make_config(ROOT / "tasks" / f"{name}.yaml", "claude-haiku-5-5", "strands")
    assert config.mode == "live" and config.worker.model_key == "claude-haiku-5-5"
    model = ModelRegistry.load().get(config.worker.model_key)
    assert model.invoke_id == "us.anthropic.claude-haiku-5-5" and model.verified
    table = load_default()
    price = table.price(model.price_ref, "us")
    sonnet = table.price("claude-sonnet-5-5", "us")
    assert price.priced and table.live_ok and price.price_basis == "ceiling"
    assert price.input == sonnet.input and price.output == sonnet.output
    assert price.scaled(1.1).price_basis == "ceiling"
