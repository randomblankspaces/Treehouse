"""Score (c) predicted accuracy from reasoning (R7): ridge regression from open-named reasoning features
(rule pass rates, reviewer scores, cell size over object size, method one-hots, revisions, coverage, ...)
to a measured keyed target (site recall or cell precision), one model per target. Validated
leave-one-config-out and on a transfer set against the mean baseline; "no better than baseline" is said
when true. Every prediction is tier MODEL-ESTIMATED. Nothing here is class-specific. Pure: numpy only."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from treehouse.schemas.numbers import Tier

PREDICTED_VERSION = "predacc-v1"
ALPHA = 0.1  # fixed ridge penalty on standardised features
Z = 1.96  # interval half-width in residual SDs
MIN_CONFIGS = 3
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
    residual_sd: float
    n: int
    configs: tuple[str, ...]
    alpha: float = ALPHA
    version: str = PREDICTED_VERSION
def _check(features: Sequence[Mapping[str, float]], targets: Sequence[float], configs: Sequence[str]) -> None:
    if not len(features) == len(targets) == len(configs):
        raise ValueError(f"length mismatch: {len(features)} features, {len(targets)} targets, "
                         f"{len(configs)} configs")
    for f in features:
        for k, v in f.items():
            if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v):
                raise ValueError(f"feature {k!r} must be a finite number, got {v!r}")
    for t in targets:
        if isinstance(t, bool) or not isinstance(t, int | float) or not math.isfinite(t) or not 0 <= t <= 1:
            raise ValueError(f"target must be a finite number in [0, 1], got {t!r}")
def _matrix(names: Sequence[str], features: Sequence[Mapping[str, float]]) -> np.ndarray:
    """Absent features are 0.0 (natural for one-hots); features unseen at fit time are ignored."""
    return np.array([[float(f.get(k, 0.0)) for k in names] for f in features], float).reshape(len(features),
                                                                                             len(names))
def fit(features: Sequence[Mapping[str, float]], targets: Sequence[float], configs: Sequence[str],
        target: str | None = None) -> Model:
    _check(features, targets, configs)
    if not targets:
        raise ValueError("cannot fit on zero runs")
    names = tuple(sorted({k for f in features for k in f}))
    X, y = _matrix(names, features), np.asarray(targets, float)
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)  # constant feature -> standardised 0, no effect
    Xs, ybar = (X - mu) / sd, float(y.mean())
    w = np.linalg.solve(Xs.T @ Xs + ALPHA * np.eye(len(names)), Xs.T @ (y - ybar)) if names \
        else np.zeros(0)
    resid = y - (ybar + Xs @ w)
    rsd = float(np.sqrt(np.sum(resid ** 2) / (len(y) - 1))) if len(y) > 1 else 0.0
    return Model(target, names, tuple(map(float, mu)), tuple(map(float, sd)), tuple(map(float, w)), ybar,
                 rsd, len(y), tuple(sorted(set(configs))))
def fit_per_target(features: Sequence[Mapping[str, float]], targets: Mapping[str, Sequence[float]],
                   configs: Sequence[str]) -> dict[str, Model]:
    """One model per target, e.g. {"site_recall": [...], "cell_precision": [...]}."""
    return {name: fit(features, ys, configs, target=name) for name, ys in targets.items()}
def _raw(model: Model, features: Sequence[Mapping[str, float]]) -> np.ndarray:
    Xs = (_matrix(model.feature_names, features) - np.asarray(model.mean)) / np.asarray(model.scale)
    return model.intercept + Xs @ np.asarray(model.coef, float).reshape(len(model.feature_names))
def predict(model: Model, features: Sequence[Mapping[str, float]]) -> list[dict]:
    _check(features, [0.0] * len(features), [""] * len(features))
    half = Z * model.residual_sd
    return [{"point": float(np.clip(r, 0, 1)), "lo": float(np.clip(r - half, 0, 1)),
             "hi": float(np.clip(r + half, 0, 1)), "interval": f"±{Z}×residual SD (in-sample)",
             "tier": Tier.MODEL_ESTIMATED.value, "target": model.target, "version": PREDICTED_VERSION}
            for r in _raw(model, features)]
def _verdict(mae: float, base: float) -> tuple[bool, str]:
    better = mae < base
    return better, BEATS if better else NO_BETTER
def leave_one_config_out(features: Sequence[Mapping[str, float]], targets: Sequence[float],
                         configs: Sequence[str]) -> dict:
    _check(features, targets, configs)
    groups = sorted(set(configs))
    out = {"version": PREDICTED_VERSION, "method": "leave-one-config-out", "n": len(targets),
           "n_configs": len(groups), "baseline": "mean target of the training configs"}
    if len(groups) < MIN_CONFIGS:
        return out | {"sufficient": False, "per_config": {}, "mae": None, "baseline_mae": None,
                      "beats_baseline": False, "verdict": INSUFFICIENT,
                      "reason": f"insufficient validation: need >= {MIN_CONFIGS} configs, got {len(groups)}"}
    per, errs, base_errs = {}, [], []
    for held in groups:
        tr = [i for i, c in enumerate(configs) if c != held]
        te = [i for i, c in enumerate(configs) if c == held]
        m = fit([features[i] for i in tr], [targets[i] for i in tr], [configs[i] for i in tr])
        pred = np.clip(_raw(m, [features[i] for i in te]), 0, 1)
        y = np.asarray([targets[i] for i in te], float)
        e, b = np.abs(pred - y), np.abs(m.intercept - y)
        per[held] = {"n": len(te), "errors": [float(x) for x in e], "mae": float(e.mean()),
                     "baseline_mae": float(b.mean())}
        errs += list(e)
        base_errs += list(b)
    mae, base = float(np.mean(errs)), float(np.mean(base_errs))
    better, verdict = _verdict(mae, base)
    return out | {"sufficient": True, "per_config": per, "mae": mae, "baseline_mae": base,
                  "beats_baseline": better, "verdict": verdict, "reason": None}
def validate_transfer(model: Model, gifu_features: Sequence[Mapping[str, float]],
                      gifu_targets: Sequence[float]) -> dict:
    """MAE on a transfer set (e.g. Gifu) vs the mean baseline (the model's training-mean target)."""
    _check(gifu_features, gifu_targets, [""] * len(gifu_targets))
    out = {"version": PREDICTED_VERSION, "method": "transfer", "target": model.target, "n": len(gifu_targets),
           "baseline": "mean target of the training runs"}
    if not gifu_targets:
        return out | {"sufficient": False, "mae": None, "baseline_mae": None, "beats_baseline": False,
                      "verdict": INSUFFICIENT, "reason": "insufficient validation: empty transfer set"}
    y = np.asarray(gifu_targets, float)
    mae = float(np.mean(np.abs(np.clip(_raw(model, gifu_features), 0, 1) - y)))
    base = float(np.mean(np.abs(model.intercept - y)))
    better, verdict = _verdict(mae, base)
    return out | {"sufficient": True, "mae": mae, "baseline_mae": base, "beats_baseline": better,
                  "verdict": verdict, "reason": None}
