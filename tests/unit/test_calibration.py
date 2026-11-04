"""Score (b) confidence calibration: Brier, reliability bins with n, ECE (R6.1)."""
from __future__ import annotations

import pytest

from treehouse.score.calibration import CALIBRATION_VERSION, calibrate


def test_brier_and_ece_hand_computed():
    # conf    = [0.9, 0.8, 0.3, 0.1]; correct = [1, 0, 1, 0]
    # Brier   = ((0.9-1)^2 + (0.8-0)^2 + (0.3-1)^2 + (0.1-0)^2) / 4
    #         = (0.01 + 0.64 + 0.49 + 0.01) / 4 = 1.15 / 4 = 0.2875
    # With n_bins = 2: bin [0, 0.5) holds 0.3, 0.1 -> mean conf 0.2, accuracy 0.5, |gap| 0.3
    #                  bin [0.5, 1] holds 0.9, 0.8 -> mean conf 0.85, accuracy 0.5, |gap| 0.35
    # ECE     = (2/4) * 0.3 + (2/4) * 0.35 = 0.15 + 0.175 = 0.325
    r = calibrate([0.9, 0.8, 0.3, 0.1], [True, False, True, False], n_bins=2)
    assert r["version"] == CALIBRATION_VERSION == "calib-v1"
    assert r["n"] == 4
    assert r["brier"] == pytest.approx(0.2875)
    assert r["ece"] == pytest.approx(0.325)
    lo_bin, hi_bin = r["bins"]
    assert (lo_bin["lo"], lo_bin["hi"], lo_bin["n"]) == (0.0, 0.5, 2)
    assert lo_bin["mean_confidence"] == pytest.approx(0.2) and lo_bin["accuracy"] == pytest.approx(0.5)
    assert (hi_bin["lo"], hi_bin["hi"], hi_bin["n"]) == (0.5, 1.0, 2)
    assert hi_bin["mean_confidence"] == pytest.approx(0.85) and hi_bin["accuracy"] == pytest.approx(0.5)
    assert "keyed" in r["keyed_only"].lower()
def test_perfect_calibration_gives_ece_zero():
    # Confidence 1.0 and always right, confidence 0.0 and always wrong: every bin's |acc - conf| is 0.
    r = calibrate([1.0, 1.0, 0.0, 0.0], [True, True, False, False])
    assert r["ece"] == pytest.approx(0.0)
    assert r["brier"] == pytest.approx(0.0)
def test_empty_bins_reported_with_none():
    r = calibrate([0.95, 0.05], [True, False], n_bins=10)
    assert len(r["bins"]) == 10
    empty = [b for b in r["bins"] if b["n"] == 0]
    assert len(empty) == 8
    assert all(b["mean_confidence"] is None and b["accuracy"] is None for b in empty)
    assert sum(b["n"] for b in r["bins"]) == 2
    assert r["bins"][9]["n"] == 1 and r["bins"][0]["n"] == 1  # 1.0 edge and 0.0 edge land in end bins
def test_no_claims_returns_none_with_reason():
    r = calibrate([], [])
    assert r["n"] == 0 and r["brier"] is None and r["ece"] is None
    assert r["reason"]
@pytest.mark.parametrize("conf, correct", [
    ([0.5, 0.5], [True]),            # length mismatch
    ([1.2], [True]),                 # out of range
    ([-0.1], [False]),               # out of range
    ([float("nan")], [True]),        # not finite
    ([0.5], [1]),                    # not boolean
    ([True], [True]),                # bool is not a confidence
])
def test_bad_input_rejected(conf, correct):
    with pytest.raises(ValueError):
        calibrate(conf, correct)
def test_bad_n_bins_rejected():
    with pytest.raises(ValueError):
        calibrate([0.5], [True], n_bins=0)
