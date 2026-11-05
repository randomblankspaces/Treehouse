"""Excluded overlapping assets cannot silently become held-out negatives."""
from __future__ import annotations

import json
import math
import runpy

import pytest
from helpers import ROOT, claim, run_case

from treehouse import service
from treehouse.checks.protocol_grader import Asset, PredictedClaim, grade
from treehouse.geo.geom import M_PER_DEG
from treehouse.investigation import reporting
from treehouse.store.local import LocalStore


@pytest.fixture
def overlap():
    # Four 160 m cells across, one row. Holdout touches cells 0 and 1; training touches 0.
    north = 160 / M_PER_DEG
    kx = M_PER_DEG * math.cos(math.radians(north / 2))
    aoi = (0, 0, 640 / kx, north)
    train = Asset(80 / kx, 80 / M_PER_DEG, id="train")
    boundary = Asset(160 / kx, 80 / M_PER_DEG, id="excluded-heldout")
    valid = Asset(560 / kx, 80 / M_PER_DEG, id="valid-heldout")
    claims = [PredictedClaim(240 / kx, 80 / M_PER_DEG, .99), PredictedClaim(valid.lon, valid.lat, .8)]
    return aoi, train, boundary, valid, claims


def test_r1_all_cells_of_excluded_overlapping_asset_leave_ranking_population(overlap):
    aoi, train, boundary, valid, claims = overlap
    result = grade(claims, [boundary, valid], aoi, excluded_assets=[train])
    if result.precision is None:
        assert result.null_reasons.get("precision")
        return
    assert result.n_assets == 1
    assert result.n_excluded_cells == 2, "cell 1 belongs to an excluded asset and cannot become a negative"
    assert result.n_grid_cells == 2
    assert result.n_claims == result.n_flagged_cells == 1
    assert result.precision == result.recall == 1.0


def test_r1_calibration_uses_same_excluded_overlap_population(overlap, tmp_path, monkeypatch):
    aoi, train, boundary, valid, claims = overlap
    store = LocalStore(tmp_path / "store")
    run_case(store, "overlap", claim("point", [136.85, 35.08]))
    run = service.load_sealed(store, "overlap")
    trial_panels = runpy.run_path(str(ROOT / "scripts/analyze_experiments.py"))["_trial_panels"]
    monkeypatch.setitem(trial_panels.__globals__, "_examples", lambda card: [train])
    monkeypatch.setitem(trial_panels.__globals__, "_claims", lambda trial: claims)
    panels, _, _, _, _ = trial_panels(store, run, run.trials[0], [boundary, valid], "complete", True, aoi)
    calibration = panels["calibration"]
    if calibration.get("brier") is None:
        assert calibration.get("reason") or calibration.get("no_grade_reason")
        return
    assert calibration["n"] == 1, "excluded holdout's other cell contaminated calibration denominator"
    assert calibration["brier"] == pytest.approx(.04)


def relocated_keys(tmp_path):
    root = tmp_path / "repository"
    keys = root / "keys/plateau"
    keys.mkdir(parents=True)
    original = ROOT / "keys/plateau/nagoya-warehouses.geojson"
    (keys / original.name).write_bytes(original.read_bytes())
    split = json.loads((ROOT / "keys/plateau/nagoya-split.json").read_text())
    return root, keys / "nagoya-split.json", split


@pytest.mark.parametrize("case", ["missing", "malformed", "overlap", "unknown", "wrong-type"])
def test_r1_analyzer_undefined_split_abstains_instead_of_grading_all_references(tmp_path, monkeypatch, case):
    root, split_path, split = relocated_keys(tmp_path)
    if case == "malformed":
        split_path.write_text("{broken")
    elif case != "missing":
        if case == "overlap":
            split["heldout"].append(split["train"][0])
        elif case == "unknown":
            split["heldout"].append("R1-NONEXISTENT-ASSET")
        else:
            split["heldout"] = "not-an-id-list"
        split_path.write_text(json.dumps(split))
    store = LocalStore(tmp_path / "store")
    run_case(store, "bad-split", claim("point", [136.85, 35.08]))
    analyze = runpy.run_path(str(ROOT / "scripts/analyze_experiments.py"))["analyze"]
    monkeypatch.setitem(analyze.__globals__, "repo_root", lambda: root)
    monkeypatch.setitem(analyze.__globals__, "_git_commit", lambda: "independent-r1-no-source-mutation")
    monkeypatch.setitem(analyze.__globals__, "_classifier_comparison", lambda: {"status": "unavailable", "reason": "Unrelated classifier comparison excluded from split test"})
    try:
        output = analyze(store.root)
    except ValueError as exc:
        assert any(word in str(exc).lower() for word in ("split", "held", "population", "reference")), str(exc)
        return
    panels = output["runs"]["bad-split"]["panels_by_trial"]["t-0"]
    assert panels["output"]["precision"] is None and panels["output"]["recall"] is None
    assert panels["output"].get("null_reasons")
    assert panels["calibration"].get("brier") is None
    assert panels["calibration"].get("reason") or panels["calibration"].get("no_grade_reason")


def test_r1_public_historical_scores_cannot_depend_on_mutable_unbound_split(tmp_path, monkeypatch):
    root, split_path, split = relocated_keys(tmp_path)
    store = LocalStore(tmp_path / "store")
    feature = json.loads((root / "keys/plateau/nagoya-warehouses.geojson").read_text())["features"][0]
    run_case(store, "historical", claim("point", feature["geometry"]["coordinates"]))
    run = service.load_sealed(store, "historical")
    monkeypatch.setattr(reporting, "repo_root", lambda: root)
    split_path.write_text(json.dumps(split))
    first, first_reason = reporting.protocol_panels(run)
    split_path.write_text(json.dumps({"train": split["heldout"], "heldout": split["train"]}))
    second, second_reason = reporting.protocol_panels(run)
    assert (first, first_reason) == (second, second_reason), "unbound adjacent split changed sealed run's historical score"
    if first is None:
        assert first_reason and any(word in first_reason.lower() for word in ("bound", "pinned", "histor", "split"))
