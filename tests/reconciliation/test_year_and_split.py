"""Contract regressions for time provenance and held-out experiment populations."""
from __future__ import annotations

import json
import math
import runpy

import numpy as np
import pytest
from helpers import ROOT, claim, run_case

from treehouse.geo.geom import M_PER_DEG
from treehouse.store.local import LocalStore
from treehouse.tools.sources.aef import AefSource

AOI = (136.82, 35.05, 136.92, 35.12)


@pytest.mark.parametrize("year", [2023, 2025])
def test_aef_fixture_does_not_relabel_stored_2024_vectors(year):
    source = AefSource.for_aoi("nagoya")
    baseline = source.index(AOI, 160, 2024)
    try:
        requested = source.index(AOI, 160, year)
    except ValueError as exc:
        assert any(word in str(exc).lower() for word in ("year", "2024", "date"))
        return
    assert requested.date_range == baseline.date_range, "stored 2024 data must retain its actual dates"
    assert str(year) not in requested.grid_id, "unsupported requested year cannot become data provenance"


def test_valid_2024_aef_fixture_remains_deterministic_and_explicit():
    source = AefSource.for_aoi("nagoya")
    first, second = source.index(AOI, 160, 2024), source.index(AOI, 160, 2024)
    assert first.date_range == ("2024-01-01", "2024-12-31")
    assert first.synthetic is True and first.describe()["access"] == "fixture"
    assert np.array_equal(first.emb, second.emb)


@pytest.fixture(scope="module")
def experiment(tmp_path_factory):
    root = tmp_path_factory.mktemp("reconciliation-splits")
    store = LocalStore(root / "store")
    split = json.loads((ROOT / "keys/plateau/nagoya-split.json").read_text())
    features = json.loads((ROOT / "keys/plateau/nagoya-warehouses.geojson").read_text())["features"]
    by_id = {f["id"]: f for f in features}
    train = [by_id[i]["geometry"]["coordinates"] for i in split["train"]]
    heldout = [by_id[i]["geometry"]["coordinates"] for i in split["heldout"]]
    kx = M_PER_DEG * math.cos(math.radians((AOI[1] + AOI[3]) / 2))

    def cell(p):
        return (int((p[0] - AOI[0]) * kx // 160), int((p[1] - AOI[1]) * M_PER_DEG // 160))

    # Choose nonoverlapping, well-inside-cell examples so edge tolerance cannot explain failures.
    train_cells = {cell(p) for p in train}
    held_cells = {cell(p) for p in heldout}
    example = next(p for p in train if cell(p) not in held_cells)
    held = next(p for p in heldout if cell(p) not in train_cells)
    run_case(store, "heldout-alone", claim("held", held))
    run_case(store, "heldout-and-training", claim("held", held) + claim("train", example, confidence=0.99))
    analyze = runpy.run_path(str(ROOT / "scripts/analyze_experiments.py"))["analyze"]
    result = analyze(store.root)
    return result, train_cells


def panel(result, rid):
    return result["runs"][rid]["panels_by_trial"]["t-0"]


def test_correct_training_prediction_does_not_become_heldout_false_positive(experiment):
    result, _ = experiment
    first, augmented = panel(result, "heldout-alone"), panel(result, "heldout-and-training")
    for name in ("precision", "n_claims", "n_flagged_cells", "n_found", "recall"):
        assert augmented["output"][name] == first["output"][name], f"training example changed heldout {name}"


def test_training_prediction_is_excluded_from_calibration_denominator(experiment):
    result, _ = experiment
    first, augmented = panel(result, "heldout-alone"), panel(result, "heldout-and-training")
    if augmented["calibration"].get("brier") is None:
        assert augmented["calibration"].get("reason") or augmented["calibration"].get("no_grade_reason")
        return
    assert augmented["calibration"]["n"] == first["calibration"]["n"] == 1
    assert augmented["calibration"]["brier"] == pytest.approx(first["calibration"]["brier"])


def test_training_cells_are_removed_from_ranking_population_or_ranking_abstains(experiment):
    result, train_cells = experiment
    output = panel(result, "heldout-and-training")["output"]
    if output["auroc"] is None and output["ap"] is None:
        assert output["null_reasons"].get("auroc") and output["null_reasons"].get("ap")
        return
    nx = math.ceil((AOI[2] - AOI[0]) * M_PER_DEG * math.cos(math.radians((AOI[1] + AOI[3]) / 2)) / 160)
    ny = math.ceil((AOI[3] - AOI[1]) * M_PER_DEG / 160)
    assert output["n_grid_cells"] <= nx * ny - len(train_cells), "training-positive cells cannot be heldout negatives"
    assert "held" in json.dumps(output).lower() or "exclud" in json.dumps(output).lower(), "evaluated population must be explicit"


def test_fixture_results_are_not_used_to_validate_generalization(experiment):
    result, _ = experiment
    predictions = result["predicted_accuracy"]
    assert "synthetic" in json.dumps(predictions).lower() or "demonstration" in json.dumps(predictions).lower()
    if predictions.get("status") == "method_test_only":
        assert predictions.get("reason"), "method-only estimates must state why generalization is unvalidated"
        return
    for target in predictions["targets"].values():
        validation = target.get("leave_one_config_out", {})
        assert validation.get("beats_baseline") is not True, "reference-derived fixture vectors cannot validate generalization"
