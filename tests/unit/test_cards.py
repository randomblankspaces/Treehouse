"""Task cards: the four shipped cards validate; bad cards are rejected with field paths."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from treehouse.cards import license_floor, load_card, validate_card
from treehouse.cli import app

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / "tasks"
CARDS = [
    "synth-crossings-v1.yaml",
    "nepal-bhote-koshi-bridges.yaml",
    "virginia-solar-18sth.yaml",
    "india-brahmaputra-bridges.yaml",
]
GOLDEN_HASHES = ROOT / "tests" / "golden" / "card-hashes.json"


@pytest.mark.parametrize("name", CARDS)
def test_shipped_cards_validate(name):
    report = validate_card(TASKS / name)
    assert report.errors == [], report.errors
    assert report.license_floor
    assert any("footprint" in w for w in report.warnings)  # TODO until the STAC fixture lands (P4)


def test_card_hashes_are_stable():
    want = json.loads(GOLDEN_HASHES.read_text())
    got = {name: load_card(TASKS / name).card_hash() for name in CARDS}
    assert got == want
    assert load_card(TASKS / CARDS[0]).card_hash() == load_card(TASKS / CARDS[0]).card_hash()


def test_nepal_notice_says_synthetic_not_adb():
    card = load_card(TASKS / "nepal-bhote-koshi-bridges.yaml")
    assert card.synthetic
    notice = card.synthetic_notice.lower()
    assert "synthetic task" in notice and "not from adb" in notice
    assert "synthetic task" in card.goal.lower()


def test_virginia_key_pending_fetch_only_warns():
    report = validate_card(TASKS / "virginia-solar-18sth.yaml")
    card = load_card(TASKS / "virginia-solar-18sth.yaml")
    assert any(s.keying.status == "pending_fetch" for s in card.steps)
    assert report.errors == [] and any("pending_fetch" in w for w in report.warnings)


def _write(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "card.yaml"
    p.write_text(yaml.safe_dump(data, sort_keys=False))
    return p


@pytest.fixture
def synth() -> dict:
    return yaml.safe_load((TASKS / "synth-crossings-v1.yaml").read_text())


def _keyed_step(card: dict) -> dict:
    return next(s for s in card["steps"] if s["keying"]["mode"] != "unkeyed")


def test_rejects_unknown_field_with_path(synth, tmp_path):
    bad = copy.deepcopy(synth)
    bad["classes"]["road_bridge"]["colour"] = "red"
    errs = validate_card(_write(tmp_path, bad)).errors
    assert any(e.startswith("classes.road_bridge.colour") for e in errs), errs


def test_rejects_keyed_step_without_forbidden_sources(synth, tmp_path):
    bad = copy.deepcopy(synth)
    bad["forbidden_sources"] = []
    errs = validate_card(_write(tmp_path, bad)).errors
    assert any("forbidden_sources" in e for e in errs), errs


def test_rejects_key_path_outside_keys(synth, tmp_path):
    bad = copy.deepcopy(synth)
    _keyed_step(bad)["keying"]["key_path"] = "fixtures/stac/leaked.key.json"
    errs = validate_card(_write(tmp_path, bad)).errors
    assert any("key_path" in e and "keys/" in e for e in errs), errs
    _keyed_step(bad)["keying"]["key_path"] = "keys/../fixtures/x.json"
    assert any("key_path" in e for e in validate_card(_write(tmp_path, bad)).errors)


def test_rejects_invalid_aoi(synth, tmp_path):
    bad = copy.deepcopy(synth)
    bad["aoi"]["coordinates"] = [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]  # bow-tie
    errs = validate_card(_write(tmp_path, bad)).errors
    assert any(e.startswith("aoi") for e in errs), errs
    bad["aoi"]["coordinates"] = [[[0, 0], [1, 0], [2, 0], [0, 0]]]  # zero area
    assert any(e.startswith("aoi") for e in validate_card(_write(tmp_path, bad)).errors)
    bad["aoi"]["coordinates"] = [[[0, 0], [200, 0], [200, 1], [0, 0]]]  # lon out of range
    assert any(e.startswith("aoi") for e in validate_card(_write(tmp_path, bad)).errors)


def test_rejects_unknown_license(synth, tmp_path):
    bad = copy.deepcopy(synth)
    bad["data_allowlist"][0]["license"] = "Whatever-1.0"
    errs = validate_card(_write(tmp_path, bad)).errors
    assert any("license" in e for e in errs), errs


def test_pinned_source_needs_fixture_and_etags(synth, tmp_path):
    bad = copy.deepcopy(synth)
    bad["data_allowlist"][0]["status"] = "pinned"
    bad["data_allowlist"][0]["fixture_path"] = "fixtures/does-not-exist.json"
    errs = validate_card(_write(tmp_path, bad)).errors
    assert any("fixture" in e for e in errs) and any("etag" in e.lower() for e in errs), errs


def test_license_floor():
    assert license_floor(["CC0-1.0", "CC-BY-4.0"]) == "CC-BY-4.0"
    assert license_floor(["ODbL-1.0", "CC-BY-NC-4.0", "MIT"]) == "CC-BY-NC-4.0"
    assert license_floor(["LicenseRef-synthetic"]) == "LicenseRef-synthetic"
    assert license_floor(["ODbL-1.0", "CC-BY-SA-4.0"]) == "CC-BY-SA-4.0+ODbL-1.0"


def test_cli_task_validate(tmp_path, synth):
    r = CliRunner().invoke(app, ["task", "validate", str(TASKS / CARDS[1])])
    assert r.exit_code == 0, r.output
    assert "license floor: CC-BY-NC-4.0" in r.output and "sha256:" in r.output
    bad = copy.deepcopy(synth)
    bad["forbidden_sources"] = []
    r = CliRunner().invoke(app, ["task", "validate", str(_write(tmp_path, bad))])
    assert r.exit_code == 1 and "ERROR" in r.output


@pytest.mark.parametrize("name", CARDS)
def test_card_round_trip_and_frozen(name):
    from pydantic import ValidationError

    from treehouse.schemas.task import TaskCard

    card = load_card(TASKS / name)
    again = TaskCard.model_validate_json(card.model_dump_json())
    assert again == card and again.card_hash() == card.card_hash()
    with pytest.raises(ValidationError):
        card.title = "changed"
