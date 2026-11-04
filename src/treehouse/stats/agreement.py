"""Chance-corrected agreement. Leaf: numpy only."""

from __future__ import annotations

import numpy as np

from treehouse.stats.intervals import Est


def _kappa(a: np.ndarray, b: np.ndarray, cats: np.ndarray) -> float:
    po = float(np.mean(a == b))
    pe = float(sum(np.mean(a == c) * np.mean(b == c) for c in cats))
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def cohen_kappa(a, b, *, B: int, seed: int, level: float = 0.90) -> Est:
    """Cohen's kappa with a percentile bootstrap over pairs (PCG64 ``seed``)."""
    a, b = np.asarray(a), np.asarray(b)
    cats = np.unique(np.concatenate([a, b]))
    k = _kappa(a, b, cats)
    idx = np.random.default_rng(seed).integers(0, len(a), size=(B, len(a)))
    reps = np.array([_kappa(a[i], b[i], cats) for i in idx])
    lo, hi = np.quantile(reps, [(1 - level) / 2, (1 + level) / 2])
    return Est(k, max(-1.0, float(lo)), min(1.0, float(hi)), level, "kappa-bootstrap", len(a))
