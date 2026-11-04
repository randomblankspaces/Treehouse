"""Exact and score intervals for proportions and counts. Leaf: numpy/scipy only."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass(frozen=True)
class Est:
    point: float
    lo: float
    hi: float
    level: float
    method: str
    n: int | None = None


def wilson(k: int, n: int, level: float) -> Est:
    if n == 0:
        return Est(float("nan"), 0.0, 1.0, level, "wilson", 0)
    z = stats.norm.ppf(0.5 + level / 2)
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return Est(p, max(0.0, c - h), min(1.0, c + h), level, "wilson", n)


def clopper_pearson(k: int, n: int, level: float) -> Est:
    a = 1 - level
    lo = 0.0 if k == 0 else float(stats.beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(stats.beta.ppf(1 - a / 2, k + 1, n - k))
    return Est(k / n if n else float("nan"), lo, hi, level, "clopper-pearson", n)


def hypergeom_exact(k: int, n: int, N: int, level: float, *, N_h: Mapping[str, int],
                    n_h: Mapping[str, int]) -> Est:
    """Exact interval for K/N given k successes in an SRSWOR of n from N. Valid only when the phase-1
    sample is a census of every stratum (STAT NB3), so the strata are required and checked here."""
    if any(n_h.get(h) != N_h[h] for h in N_h) or sum(N_h.values()) != N:
        raise ValueError("hypergeom_exact needs every stratum to be a census (n_h == N_h)")
    a = 1 - level
    K = np.arange(N + 1)
    ok = (stats.hypergeom.sf(k - 1, N, K, n) > a / 2) & (stats.hypergeom.cdf(k, N, K, n) > a / 2)
    return Est(k / n, float(K[ok].min() / N), float(K[ok].max() / N), level, "hypergeom-exact", n)


def poisson_binomial_interval(p, level: float) -> Est:
    """Central interval for the count of successes among independent Bernoulli(p_i): exact pmf by convolution."""
    pmf = np.ones(1)
    for q in np.asarray(p, float):
        pmf = np.convolve(pmf, [1 - q, q])
    cdf = np.cumsum(pmf)
    a = 1 - level
    lo = int(np.searchsorted(cdf, a / 2 - 1e-12))
    hi = int(np.searchsorted(cdf, 1 - a / 2 - 1e-12))
    return Est(float(np.sum(p)), float(lo), float(hi), level, "poisson-binomial", len(pmf) - 1)
