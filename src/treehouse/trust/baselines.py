"""Baselines (A7): B0 pooled beta-binomial of keyed precision for the same (family, model, harness, tool set);
B1 the agent's own stated confidence; B2 intercept-only beta-binomial per (model, harness)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy import optimize, special, stats

from treehouse.schemas.config import TrustConfig
from treehouse.schemas.numbers import Interval, Tier, TypedNumber
from treehouse.stats.intervals import poisson_binomial_interval
from treehouse.trust.config import ESTIMATOR_VERSION


@dataclass(frozen=True)
class KeyedRun:
    """One keyed run's precision: k correct of n claims. SYNTHETIC runs never count (B0, B2, regimes)."""

    family: str
    model: str
    harness: str
    toolset: str
    regime: str
    k: int
    n: int
    synthetic: bool = False


def betabinom_fit(ks, ns) -> tuple[float, float]:
    """MLE (mu, kappa) of a beta-binomial over runs, a = mu*kappa, b = (1-mu)*kappa."""
    ks, ns = np.asarray(ks, float), np.asarray(ns, float)

    def nll(x):
        mu, kap = special.expit(x[0]), np.exp(x[1])
        return -stats.betabinom.logpmf(ks, ns, mu * kap, (1 - mu) * kap).sum()

    m0 = np.clip(ks.sum() / ns.sum(), 0.01, 0.99)
    x = optimize.minimize(nll, [special.logit(m0), np.log(10.0)], method="Nelder-Mead",
                          bounds=[(-10, 10), (np.log(1e-2), np.log(1e5))]).x
    return float(special.expit(x[0])), float(np.exp(x[1]))


def betabinom_predictive(mu: float, kappa: float, n_new: int, level: float) -> tuple[float, float]:
    """Central predictive interval for the precision of a new run of ``n_new`` claims."""
    d = stats.betabinom(n_new, mu * kappa, (1 - mu) * kappa)
    return float(d.ppf((1 - level) / 2) / n_new), float(d.ppf((1 + level) / 2) / n_new)


def _fit(runs: Sequence[KeyedRun], cfg: TrustConfig):
    if len(runs) >= cfg.min_runs_mle:
        return (*betabinom_fit([r.k for r in runs], [r.n for r in runs]), "mle")
    if runs:  # too few runs to estimate the spread: pooled mean, pre-registered concentration kappa0
        return sum(r.k for r in runs) / sum(r.n for r in runs), float(cfg.kappa0), "kappa0"
    return None


def _number(metric, estimator, mu, kappa, fit, n_runs, n_new, cfg, meta, reasons=()):
    lo, hi = betabinom_predictive(mu, kappa, n_new, cfg.level)
    return TypedNumber(metric=metric, value=mu, type="proportion", tier=Tier.MODEL_ESTIMATED, panel="trust",
                       n=n_new, interval=Interval(lo=lo, hi=hi, level=cfg.level, method="betabinom-predictive"),
                       estimator_version=ESTIMATOR_VERSION, reasons=list(reasons),
                       detail={"estimator": estimator, "mu": mu, "kappa": kappa, "fit": fit, "n_runs": n_runs},
                       **meta)


def _real(runs):
    return [r for r in runs if not r.synthetic]


def baseline_b0(keyed_runs, family, model, harness, toolset, n_new, cfg, *, meta) -> TypedNumber | None:
    runs = [r for r in _real(keyed_runs) if (r.family, r.model, r.harness, r.toolset) == (family, model, harness, toolset)]
    fit = _fit(runs, cfg)
    return None if fit is None else _number("b0_same_config", "b0", *fit, len(runs), n_new, cfg, meta)


def baseline_b2(keyed_runs, model, harness, n_new, cfg, *, meta) -> TypedNumber:
    runs = [r for r in _real(keyed_runs) if (r.model, r.harness) == (model, harness)]
    fit = _fit(runs, cfg)
    if fit is None:  # no keyed data at all: uniform Beta(1, 1) prior, deliberately wide
        return _number("b2_model_prior", "b2", 0.5, 2.0, "prior", 0, n_new, cfg, meta, ["no keyed runs"])
    return _number("b2_model_prior", "b2", *fit, len(runs), n_new, cfg, meta)


def baseline_b1(confidences: Sequence[float], level: float, *, meta) -> TypedNumber | None:
    """The agent's own stated confidence, read as independent Bernoulli(p_i): shown as "agent's claim"."""
    if not len(confidences):
        return None
    e = poisson_binomial_interval(confidences, level)
    n = len(confidences)
    return TypedNumber(metric="b1_agents_claim", value=e.point / n, type="proportion", tier=Tier.MODEL_ESTIMATED,
                       panel="trust", n=n, interval=Interval(lo=e.lo / n, hi=e.hi / n, level=level,
                                                             method="poisson-binomial"),
                       estimator_version=ESTIMATOR_VERSION, reasons=["agent's claim"],
                       detail={"estimator": "b1", "expected_correct": e.point}, **meta)
