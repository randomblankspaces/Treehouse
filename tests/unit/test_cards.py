"""Task cards: the four shipped cards validate; bad cards are rejected with field paths."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from treehouse.cards import license_floor, license_obligations, load_card, validate_card
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
NEPAL_STAC = ROOT / "wip" / "fixtures" / "nepal-flooding-aug-2026.stac.json"  # real Vantor metadata


@pytest.mark.parametrize("name", CARDS)
def test_shipped_cards_validate(name):
    report = validate_card(TASKS / name)
    assert report.errors == [], report.errors
    assert report.license_floor
    # No shipped card has a pinned STAC source yet (P4 pins them), so the footprint check only warns.
    assert any("footprint" in w for w in report.warnings)


def test_card_hashes_are_stable():
    want = json.loads(GOLDEN_HASHES.read_text())
    got = {name: load_card(TASKS / name).card_hash() for name in CARDS}
    assert got == want


def test_card_hash_ignores_key_order_and_utc_offset(synth, tmp_path):
    base = load_card(_write(tmp_path, synth)).card_hash()
    reordered = dict(reversed(list(synth.items())))
    assert load_card(_write(tmp_path, reordered)).card_hash() == base
    shifted = {**synth, "as_of": "2026-09-16T05:44:00+05:45"}  # the same instant as 2026-09-15T23:59Z
    assert load_card(_write(tmp_path, shifted)).card_hash() == base


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


def test_license_floor_and_obligations():
    assert license_floor(["CC0-1.0", "CC-BY-4.0"]) == "CC-BY-4.0"
    assert license_floor(["ODbL-1.0", "CC-BY-NC-4.0", "MIT"]) == "CC-BY-NC-4.0"
    assert license_floor(["LicenseRef-synthetic"]) == "LicenseRef-synthetic"
    assert license_floor(["ODbL-1.0", "CC-BY-SA-4.0"]) == "CC-BY-SA-4.0+ODbL-1.0"
    assert license_floor([]) is None
    # the floor drops obligations; the obligations list keeps every one
    assert license_obligations(["ODbL-1.0", "CC-BY-NC-4.0", "MIT", "CC0-1.0"]) == ["CC-BY-NC-4.0", "ODbL-1.0", "MIT"]
    assert license_obligations(["LicenseRef-synthetic"]) == []


def test_nepal_reports_every_obligation():
    report = validate_card(TASKS / "nepal-bhote-koshi-bridges.yaml")
    assert report.license_floor == "CC-BY-NC-4.0"
    assert report.license_obligations == ["CC-BY-NC-4.0", "ODbL-1.0", "CC-BY-4.0"]


def test_no_licences_is_an_error_not_a_crash(synth, tmp_path):
    bad = copy.deepcopy(synth)
    bad["data_allowlist"] = []
    for st in bad["steps"]:
        st["keying"] = {"mode": "unkeyed", "status": "none"}
    bad["forbidden_sources"] = []
    errs = validate_card(_write(tmp_path, bad)).errors
    assert any("no licences" in e for e in errs), errs


def test_cli_task_validate(tmp_path, synth):
    r = CliRunner().invoke(app, ["task", "validate", str(TASKS / CARDS[1])])
    assert r.exit_code == 0, r.output
    assert "license floor: CC-BY-NC-4.0" in r.output and "sha256:" in r.output
    assert "license obligations: CC-BY-NC-4.0 (attribution, non_commercial); ODbL-1.0" in r.output
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


# ---- paths a card names ------------------------------------------------------------------------

@pytest.mark.parametrize("field,value", [
    ("fixture", "keys/synth/synth-crossings-v1.key.json"),
    ("fixture", "KEYS/synth/x.json"),
    ("fixture", "../../etc"),
    ("fixture", "prereg/gold-seed.txt"),  # inside the repo but not under a tool root
    ("footprint", "keys/x.json"),
    ("seed", "keys/seed.txt"),
    ("seed", "../outside.txt"),
])
def test_card_paths_stay_out_of_keys_and_in_tool_roots(synth, tmp_path, field, value):
    bad = copy.deepcopy(synth)
    if field == "fixture":
        bad["data_allowlist"][0]["fixture_path"] = value
        want = "data_allowlist.0.fixture_path"
    elif field == "footprint":
        bad["event"]["footprint_ref"] = value
        want = "event.footprint_ref"
    else:
        bad["gold_plan"]["seed_file"] = value
        want = "gold_plan.seed_file"
    errs = validate_card(_write(tmp_path, bad)).errors
    assert any(e.startswith(want) for e in errs), errs


# ---- semantic card rules (each error names its field path) -------------------------------------

def _nepal() -> dict:
    return yaml.safe_load((TASKS / "nepal-bhote-koshi-bridges.yaml").read_text())


@pytest.mark.parametrize("mutate,path", [
    (lambda c: c.__setitem__("forbidden_sources", []), "forbidden_sources"),
    (lambda c: c.__setitem__("synthetic_notice", None), "synthetic_notice"),
    (lambda c: c.__setitem__("time_window", ["2026-10-01", "2026-09-01"]), "time_window"),
    (lambda c: c.__setitem__("as_of", "2020-01-01T00:00:00Z"), "as_of"),
    (lambda c: c["steps"].append(copy.deepcopy(c["steps"][0])), "steps"),
    (lambda c: c["steps"][0].__setitem__("statuses_allowed", ["destroyed"]), "steps.0"),
    (lambda c: c["steps"][0]["keying"]["match_rule"]["tolerance_m"].__setitem__("ferry", 5),
     "steps.0.keying.match_rule.tolerance_m"),
    (lambda c: c["sampling_plan"].__setitem__("strata_keys", ["class", "class"]), "sampling_plan.strata_keys"),
    (lambda c: c["gold_plan"].__setitem__("n_gold", -1), "gold_plan.n_gold"),
    (lambda c: c["sampling_plan"].__setitem__("n_total", 0), "sampling_plan.n_total"),
    (lambda c: c["windows"].__setitem__("max_out_px", -5), "windows.max_out_px"),
    (lambda c: c["steps"][0]["keying"].__setitem__("completeness_caveat", None), "steps.0.keying"),
    (lambda c: c.__setitem__("smoke_aoi", [85.33, 28.14, 85.37, 28.18]), "smoke_aoi"),  # the draft value
])
def test_bad_cards_rejected_with_field_paths(tmp_path, mutate, path):
    card = _nepal()
    mutate(card)
    errs = validate_card(_write(tmp_path, card)).errors
    assert any(e.startswith(path + ":") or e.startswith(path + ".") for e in errs), errs


def test_present_key_missing_on_disk_is_an_error(synth, tmp_path):
    bad = copy.deepcopy(synth)
    for st in bad["steps"]:
        st["keying"] = {**st["keying"], "status": "present", "version_hash": "sha256:k"}
    errs = validate_card(_write(tmp_path, bad)).errors
    assert any("not on disk" in e for e in errs), errs


def test_unkeyed_step_without_gold_plan_warns():
    report = validate_card(TASKS / "india-brahmaputra-bridges.yaml")
    assert report.errors == [] and any("gold_plan" in w for w in report.warnings)


def test_synth_key_is_pending_generation_not_fetch():
    report = validate_card(TASKS / "synth-crossings-v1.yaml")
    assert any("pending_generation" in w and "generated" in w for w in report.warnings)
    assert not any("fetched" in w for w in report.warnings)


def test_nepal_cloud_count_matches_item_list():
    card = load_card(TASKS / "nepal-bhote-koshi-bridges.yaml")
    text = (TASKS / "nepal-bhote-koshi-bridges.yaml").read_text()
    cloudy = [ln for ln in text.splitlines() if "# post" in ln and 71 <= int(ln.split("cloud ")[1].split()[0]) <= 94]
    assert len(cloudy) == 16 and card.known_limits[0].startswith("Sixteen")


# ---- AOI against pinned footprints (real Vantor footprints from wip/fixtures) -------------------

def _pinned_nepal_repo(tmp_path: Path, monkeypatch, swap: bool = False, layout: str = "dir") -> Path:
    """A throwaway repo root with the Nepal card's STAC source pinned to the real item footprints."""
    root = tmp_path / "repo"
    (root / "src" / "treehouse").mkdir(parents=True)
    (root / "pyproject.toml").write_text("")
    stac = json.loads(NEPAL_STAC.read_text())
    card = _nepal()
    src = card["data_allowlist"][0]
    items = {i["id"]: i for i in stac["items"] if i["id"] in src["item_ids"]}
    if layout == "dir":
        d = root / "fixtures" / "stac" / "vantor-nepal-aug-2026"
        (d / "items").mkdir(parents=True)
        for x, item in items.items():
            (d / "items" / f"{x}.json").write_text(json.dumps(item))
        (d / "etags.json").write_text(json.dumps(src["etags"]))
    else:
        f = root / "fixtures" / "stac" / "vantor-nepal.json"
        f.parent.mkdir(parents=True)
        f.write_text(json.dumps({"items": list(items.values())}))
        src["fixture_path"] = "fixtures/stac/vantor-nepal.json"
    src["status"] = "pinned"
    card["event"]["footprint_ref"] = None
    if swap:  # lat/lon swapped on every AOI vertex
        card["aoi"]["coordinates"] = [[[y, x] for x, y in ring] for ring in card["aoi"]["coordinates"]]
        card["smoke_aoi"] = None
    monkeypatch.setenv("TREEHOUSE_ROOT", str(root))
    return _write(tmp_path, card)


@pytest.mark.parametrize("layout", ["dir", "file"])
def test_aoi_intersects_pinned_footprints(tmp_path, monkeypatch, layout):
    report = validate_card(_pinned_nepal_repo(tmp_path, monkeypatch, layout=layout))
    assert report.errors == [], report.errors
    assert not any("footprint" in w for w in report.warnings)


def test_swapped_aoi_misses_every_footprint(tmp_path, monkeypatch):
    errs = validate_card(_pinned_nepal_repo(tmp_path, monkeypatch, swap=True)).errors
    assert any(e.startswith("aoi:") and "intersect" in e for e in errs), errs


def test_pinned_items_need_files_and_matching_etags(tmp_path, monkeypatch):
    path = _pinned_nepal_repo(tmp_path, monkeypatch)
    d = tmp_path / "repo" / "fixtures" / "stac" / "vantor-nepal-aug-2026"
    (d / "items" / "B1300011011E5610.json").unlink()
    etags = json.loads((d / "etags.json").read_text())
    etags["B1300011011E5810"] = "stale"
    (d / "etags.json").write_text(json.dumps(etags))
    errs = validate_card(path).errors
    assert any("items/B1300011011E5610.json" in e for e in errs), errs
    assert any("etags.json" in e for e in errs), errs
