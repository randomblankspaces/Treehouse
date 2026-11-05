"""Score (c) predicted accuracy from reasoning: ridge fit, LOCO and transfer validation vs mean baseline (R7)."""
from __future__ import annotations

import numpy as np
import pytest

from treehouse.score.predicted_accuracy import (
    NO_BETTER,
    PREDICTED_VERSION,
    fit,
    fit_per_target,
    leave_one_config_out,
    predict,
    validate_transfer,
)


def _signal(seed: int = 0, n_configs: int = 6, per: int = 5):
    rng = np.random.default_rng(seed)
    feats, ys, cfgs = [], [], []
    for c in range(n_configs):
        for _ in range(per):
            x = float(rng.uniform(0, 1))
            z = float(rng.uniform(0, 1))  # irrelevant feature
            feats.append({"rv_pass_rate": x, "revisions": z, f"method.m{c % 2}": 1.0})
            ys.append(float(np.clip(0.1 + 0.8 * x + rng.normal(0, 0.03), 0, 1)))
            cfgs.append(f"cfg{c}")
    return feats, ys, cfgs
def _noise(seed: int = 0, n_configs: int = 6, per: int = 4):
    rng = np.random.default_rng(seed)
    feats = [{f"f{j}": float(rng.normal()) for j in range(6)} for _ in range(n_configs * per)]
    ys = [float(rng.uniform(0, 1)) for _ in feats]
    cfgs = [f"cfg{i // per}" for i in range(len(feats))]
    return feats, ys, cfgs
def test_linear_signal_beats_mean_baseline_loco():
    r = leave_one_config_out(*_signal())
    assert r["version"] == PREDICTED_VERSION == "predacc-v1"
    assert r["sufficient"] is True
    assert set(r["per_config"]) == {f"cfg{c}" for c in range(6)}
    assert all(set(v) >= {"n", "errors", "mae", "baseline_mae"} for v in r["per_config"].values())
    assert r["mae"] < r["baseline_mae"]
    assert r["beats_baseline"] is True
    assert r["verdict"] == "beats baseline"
def test_pure_noise_is_no_better_than_baseline():
    # The verdict is a strict MAE comparison, so pure noise can win by chance on some draws (seed 1 does);
    # seeds are pinned so the fixture is deterministic.
    r = leave_one_config_out(*_noise())
    assert r["beats_baseline"] is False
    assert r["verdict"] == NO_BETTER == "no better than baseline"
def test_predictions_clipped_and_labelled():
    feats, ys, cfgs = _signal()
    m = fit(feats, ys, cfgs)
    out = predict(m, [{"rv_pass_rate": 50.0}, {"rv_pass_rate": -50.0}, {"rv_pass_rate": 0.5}])
    for p in out:
        assert p["tier"] == "MODEL-ESTIMATED"
        assert 0.0 <= p["lo"] <= p["point"] <= p["hi"] <= 1.0
        assert p["version"] == PREDICTED_VERSION
    assert out[0]["point"] == 1.0 and out[1]["point"] == 0.0
    assert 0.0 < out[2]["point"] < 1.0 and out[2]["lo"] < out[2]["hi"]
def test_insufficient_configs_handled():
    feats, ys, cfgs = _signal(n_configs=2)
    r = leave_one_config_out(feats, ys, cfgs)
    assert r["sufficient"] is False and r["beats_baseline"] is False
    assert r["mae"] is None and "insufficient" in r["reason"]
    assert r["verdict"] == "insufficient validation"
def test_transfer_validation():
    feats, ys, cfgs = _signal(seed=0)
    gf, gy, _ = _signal(seed=7, n_configs=2)
    m = fit(feats, ys, cfgs)
    t = validate_transfer(m, gf, gy)
    assert t["n"] == len(gy) and t["mae"] < t["baseline_mae"] and t["beats_baseline"] is True
    nf, ny, _ = _noise(seed=2)
    tn = validate_transfer(fit(*_noise(seed=0)), nf, ny)
    assert tn["beats_baseline"] is False and tn["verdict"] == NO_BETTER
    empty = validate_transfer(m, [], [])
    assert empty["sufficient"] is False and empty["mae"] is None
def test_one_model_per_target():
    feats, ys, cfgs = _signal()
    models = fit_per_target(feats, {"site_recall": ys, "cell_precision": [1 - y for y in ys]}, cfgs)
    assert set(models) == {"site_recall", "cell_precision"}
    assert models["site_recall"].target == "site_recall"
    w = dict(zip(models["site_recall"].feature_names, models["site_recall"].coef, strict=True))
    assert w["rv_pass_rate"] > 0 > dict(zip(models["cell_precision"].feature_names,
                                            models["cell_precision"].coef, strict=True))["rv_pass_rate"]
def test_deterministic():
    a, b = leave_one_config_out(*_signal()), leave_one_config_out(*_signal())
    assert a == b
    feats, ys, cfgs = _signal()
    shuffled = [dict(reversed(list(f.items()))) for f in feats]  # key order must not matter
    assert fit(feats, ys, cfgs) == fit(shuffled, ys, cfgs)
def test_bad_input_rejected():
    with pytest.raises(ValueError):
        fit([{"a": 1.0}], [0.5, 0.5], ["c", "c"])
    with pytest.raises(ValueError):
        fit([{"a": 1.0}], [1.5], ["c"])
    with pytest.raises(ValueError):
        fit([{"a": float("nan")}], [0.5], ["c"])


def test_prediction_interval_uses_leave_one_out_residuals_with_held_out_coverage():
    rng = np.random.default_rng(20260312)

    def make_rows(n):
        matrix = rng.uniform(-1.0, 1.0, size=(n, 3))
        noise = rng.normal(0.0, 0.05, size=n)
        values = 0.5 + 0.15 * matrix[:, 0] - 0.1 * matrix[:, 1] + 0.05 * matrix[:, 2] + noise
        features = [
            {"rule_pass": float(row[0]), "coverage": float(row[1]), "revisions": float(row[2])}
            for row in matrix
        ]
        return features, [float(value) for value in values]

    train_features, train_targets = make_rows(40)
    model = fit(train_features, train_targets, [f"cfg{i % 5}" for i in range(40)])
    held_out_features, held_out_targets = make_rows(200)
    predictions = predict(model, held_out_features)

    assert all("leave-one-out" in prediction["interval"] for prediction in predictions)
    coverage = np.mean(
        [
            prediction["lo"] <= actual <= prediction["hi"]
            for prediction, actual in zip(predictions, held_out_targets, strict=True)
        ]
    )
    assert 0.8 <= coverage <= 1.0


def test_prediction_interval_is_none_when_rows_do_not_exceed_features():
    features = [
        {"f0": 0.0, "f1": 1.0, "f2": 2.0, "f3": 3.0},
        {"f0": 1.0, "f1": 2.0, "f2": 3.0, "f3": 4.0},
        {"f0": 2.0, "f1": 3.0, "f2": 4.0, "f3": 5.0},
        {"f0": 3.0, "f1": 4.0, "f2": 5.0, "f3": 6.0},
    ]
    model = fit(features, [0.2, 0.4, 0.6, 0.8], ["a", "b", "c", "d"])
    prediction = predict(model, [{"f0": 1.5, "f1": 2.5, "f2": 3.5, "f3": 4.5}])[0]

    assert prediction["point"] == pytest.approx(0.5)
    assert prediction["lo"] is None and prediction["hi"] is None
    assert prediction["interval"] is None
    assert prediction["reason"] == "insufficient data for an interval"
    assert prediction["tier"] == "MODEL-ESTIMATED"
