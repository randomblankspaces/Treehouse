"""Score (c) predicted accuracy from reasoning (R7).

Fits ridge regression from open-named reasoning features to a measured keyed target, with one model per
target. Validation is leave-one-config-out and transfer-set MAE against the mean baseline. Prediction
intervals use out-of-sample leave-one-row-out residuals. Every prediction is tier MODEL-ESTIMATED.
Nothing here is class-specific. Pure: numpy only.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from treehouse.schemas.numbers import Tier

PREDICTED_VERSION = "predacc-v1"
ALPHA = 0.1  # fixed ridge penalty on standardised features
MIN_CONFIGS = 3
MIN_ROWS = 4
INTERVAL_QUANTILE = 0.95
INTERVAL_METHOD = "±95th percentile of absolute leave-one-out residuals"
INTERVAL_INSUFFICIENT = "insufficient data for an interval"
TARGETS = ("site_recall", "cell_precision")
NO_BETTER = "no better than baseline"
BEATS = "beats baseline"
INSUFFICIENT = "insufficient validation"


@dataclass(frozen=True)
class Model:
    target: str | None
    feature_names: tuple[str, ...]  # sorted: deterministic order regardless of dict key order
    mean: tuple[float, ...]
    scale: tuple[float, ...]
    coef: tuple[float, ...]
    intercept: float  # == mean training target (features are centred), i.e. the mean baseline
    residual_sd: float | None  # leave-one-out residual SD; None when interval data are insufficient
    n: int
    configs: tuple[str, ...]
    alpha: float = ALPHA
    version: str = PREDICTED_VERSION
    interval_half_width: float | None = None
    interval_reason: str | None = INTERVAL_INSUFFICIENT


def _check(features: Sequence[Mapping[str, float]], targets: Sequence[float], configs: Sequence[str]) -> None:
    if not len(features) == len(targets) == len(configs):
        raise ValueError(
            f"length mismatch: {len(features)} features, {len(targets)} targets, "
            f"{len(configs)} configs"
        )
    for f in features:
        for k, v in f.items():
            if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v):
                raise ValueError(f"feature {k!r} must be a finite number, got {v!r}")
    for t in targets:
        if (
            isinstance(t, bool)
            or not isinstance(t, int | float)
            or not math.isfinite(t)
            or not 0 <= t <= 1
        ):
            raise ValueError(f"target must be a finite number in [0, 1], got {t!r}")


def _matrix(names: Sequence[str], features: Sequence[Mapping[str, float]]) -> np.ndarray:
    """Absent features are 0.0 (natural for one-hots); features unseen at fit time are ignored."""
    return np.array(
        [[float(f.get(k, 0.0)) for k in names] for f in features], float
    ).reshape(len(features), len(names))


def _fit_values(
    features: Sequence[Mapping[str, float]], targets: Sequence[float]
) -> tuple[tuple[str, ...], np.ndarray, np.ndarray, np.ndarray, float]:
    """Fit ridge parameters without calculating an interval."""
    names = tuple(sorted({k for f in features for k in f}))
    X, y = _matrix(names, features), np.asarray(targets, float)
    mean = X.mean(axis=0)
    scale = X.std(axis=0)
    scale = np.where(scale > 0, scale, 1.0)  # constant feature -> standardised 0, no effect
    standardised = (X - mean) / scale
    intercept = float(y.mean())
    coef = (
        np.linalg.solve(
            standardised.T @ standardised + ALPHA * np.eye(len(names)),
            standardised.T @ (y - intercept),
        )
        if names
        else np.zeros(0)
    )
    return names, mean, scale, coef, intercept


def _predict_values(
    parameters: tuple[tuple[str, ...], np.ndarray, np.ndarray, np.ndarray, float],
    features: Sequence[Mapping[str, float]],
) -> np.ndarray:
    names, mean, scale, coef, intercept = parameters
    standardised = (_matrix(names, features) - mean) / scale
    return intercept + standardised @ coef.reshape(len(names))


def fit(
    features: Sequence[Mapping[str, float]],
    targets: Sequence[float],
    configs: Sequence[str],
    target: str | None = None,
) -> Model:
    _check(features, targets, configs)
    if not targets:
        raise ValueError("cannot fit on zero runs")

    parameters = _fit_values(features, targets)
    names, mean, scale, coef, intercept = parameters
    residual_sd: float | None = None
    interval_half_width: float | None = None
    interval_reason: str | None = INTERVAL_INSUFFICIENT

    # With too few rows, or no residual degrees of freedom relative to the feature count, an interval
    # would look more certain than the data support. The point model remains usable in this case.
    if len(targets) >= MIN_ROWS and len(targets) > len(names) + 1:
        loo_residuals = []
        for held_out in range(len(targets)):
            train_features = [f for i, f in enumerate(features) if i != held_out]
            train_targets = [value for i, value in enumerate(targets) if i != held_out]
            loo_parameters = _fit_values(train_features, train_targets)
            prediction = float(_predict_values(loo_parameters, [features[held_out]])[0])
            loo_residuals.append(float(targets[held_out]) - prediction)

        residual_sd = float(np.std(loo_residuals, ddof=1))
        interval_half_width = float(np.quantile(np.abs(loo_residuals), INTERVAL_QUANTILE))
        interval_reason = None

    return Model(
        target=target,
        feature_names=names,
        mean=tuple(map(float, mean)),
        scale=tuple(map(float, scale)),
        coef=tuple(map(float, coef)),
        intercept=intercept,
        residual_sd=residual_sd,
        n=len(targets),
        configs=tuple(sorted(set(configs))),
        interval_half_width=interval_half_width,
        interval_reason=interval_reason,
    )


def fit_per_target(
    features: Sequence[Mapping[str, float]],
    targets: Mapping[str, Sequence[float]],
    configs: Sequence[str],
) -> dict[str, Model]:
    """One model per target, e.g. {"site_recall": [...], "cell_precision": [...]}."""
    return {name: fit(features, ys, configs, target=name) for name, ys in targets.items()}


def _raw(model: Model, features: Sequence[Mapping[str, float]]) -> np.ndarray:
    standardised = (
        _matrix(model.feature_names, features) - np.asarray(model.mean)
    ) / np.asarray(model.scale)
    return model.intercept + standardised @ np.asarray(model.coef, float).reshape(
        len(model.feature_names)
    )


def predict(model: Model, features: Sequence[Mapping[str, float]]) -> list[dict]:
    _check(features, [0.0] * len(features), [""] * len(features))
    predictions = []
    for raw in _raw(model, features):
        point = float(np.clip(raw, 0, 1))
        if model.interval_half_width is None:
            lo = hi = None
            interval = None
        else:
            lo = float(np.clip(raw - model.interval_half_width, 0, 1))
            hi = float(np.clip(raw + model.interval_half_width, 0, 1))
            interval = INTERVAL_METHOD
        predictions.append(
            {
                "point": point,
                "lo": lo,
                "hi": hi,
                "interval": interval,
                "reason": model.interval_reason,
                "tier": Tier.MODEL_ESTIMATED.value,
                "target": model.target,
                "version": PREDICTED_VERSION,
            }
        )
    return predictions


def _verdict(mae: float, base: float) -> tuple[bool, str]:
    better = mae < base
    return better, BEATS if better else NO_BETTER


def leave_one_config_out(
    features: Sequence[Mapping[str, float]], targets: Sequence[float], configs: Sequence[str]
) -> dict:
    _check(features, targets, configs)
    groups = sorted(set(configs))
    out = {
        "version": PREDICTED_VERSION,
        "method": "leave-one-config-out",
        "n": len(targets),
        "n_configs": len(groups),
        "baseline": "mean target of the training configs",
    }
    if len(groups) < MIN_CONFIGS:
        return out | {
            "sufficient": False,
            "per_config": {},
            "mae": None,
            "baseline_mae": None,
            "beats_baseline": False,
            "verdict": INSUFFICIENT,
            "reason": f"insufficient validation: need >= {MIN_CONFIGS} configs, got {len(groups)}",
        }
    per, errs, base_errs = {}, [], []
    for held in groups:
        train = [i for i, config in enumerate(configs) if config != held]
        test = [i for i, config in enumerate(configs) if config == held]
        model = fit(
            [features[i] for i in train],
            [targets[i] for i in train],
            [configs[i] for i in train],
        )
        prediction = np.clip(_raw(model, [features[i] for i in test]), 0, 1)
        actual = np.asarray([targets[i] for i in test], float)
        errors = np.abs(prediction - actual)
        baseline_errors = np.abs(model.intercept - actual)
        per[held] = {
            "n": len(test),
            "errors": [float(value) for value in errors],
            "mae": float(errors.mean()),
            "baseline_mae": float(baseline_errors.mean()),
        }
        errs += list(errors)
        base_errs += list(baseline_errors)
    mae, base = float(np.mean(errs)), float(np.mean(base_errs))
    better, verdict = _verdict(mae, base)
    return out | {
        "sufficient": True,
        "per_config": per,
        "mae": mae,
        "baseline_mae": base,
        "beats_baseline": better,
        "verdict": verdict,
        "reason": None,
    }


def validate_transfer(
    model: Model,
    gifu_features: Sequence[Mapping[str, float]],
    gifu_targets: Sequence[float],
) -> dict:
    """MAE on a transfer set (e.g. Gifu) vs the mean baseline (the model's training-mean target)."""
    _check(gifu_features, gifu_targets, [""] * len(gifu_targets))
    out = {
        "version": PREDICTED_VERSION,
        "method": "transfer",
        "target": model.target,
        "n": len(gifu_targets),
        "baseline": "mean target of the training runs",
    }
    if not gifu_targets:
        return out | {
            "sufficient": False,
            "mae": None,
            "baseline_mae": None,
            "beats_baseline": False,
            "verdict": INSUFFICIENT,
            "reason": "insufficient validation: empty transfer set",
        }
    actual = np.asarray(gifu_targets, float)
    mae = float(np.mean(np.abs(np.clip(_raw(model, gifu_features), 0, 1) - actual)))
    base = float(np.mean(np.abs(model.intercept - actual)))
    better, verdict = _verdict(mae, base)
    return out | {
        "sufficient": True,
        "mae": mae,
        "baseline_mae": base,
        "beats_baseline": better,
        "verdict": verdict,
        "reason": None,
    }


def deliberation_features(result):
    """Available deterministic observations only; absent thinking is never a measured zero."""
    return {f"deliberation.{name}": metric["value"]
            for name, metric in result["metrics"].items()
            if metric["status"] == "available" and metric["denominator"] > 0}
