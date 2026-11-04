"""Design-based two-phase PPI (``ppi-2phase-rbs-v1``), IMPLEMENTATION-DESIGN §3. ``ppi_core`` is a port of
``wip/council2/proto/ppi2.py`` (oracle: ``tests/method/_reference_ppi.py``) and consumes the RNG the same way."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from scipy import stats

from treehouse.schemas.config import TrustConfig
from treehouse.schemas.sampling import GoldDraw, SampleDesign
from treehouse.stats.intervals import hypergeom_exact
from treehouse.trust.config import PPI_METHOD


@dataclass(frozen=True)
class PPIResult:
    theta: float
    lo: float
    hi: float
    level: float
    method: str
    n: int
    g: int
    B: int | None
    seed: int | None
    lam: float = 1.0
    V: float | None = None


def _t_interval(theta, V, g, level):
    q = stats.t.ppf(0.5 + level / 2, df=max(g - 1, 1))
    return theta - q * np.sqrt(V), theta + q * np.sqrt(V)


def ppi_core(ss, Nh, f, y, gold, *, B: int, level: float, pseudo_weight: float, rng):
    """Arrays over the phase-1 sample S: ``ss`` stratum code 0..H-1, ``Nh`` frame sizes, ``f`` predictor,
    ``y`` gold outcome (ignored off ``gold``), ``gold`` mask. lambda = 1. Returns (theta, lo, hi, V)."""
    ss, Nh, f, gold = np.asarray(ss), np.asarray(Nh, float), np.asarray(f, float), np.asarray(gold, bool)
    y = np.nan_to_num(np.asarray(y, float))
    H = len(Nh)
    W = Nh / Nh.sum()
    nh = np.bincount(ss, minlength=H)
    n, g = len(ss), int(gold.sum())
    w = (Nh / nh)[ss]
    theta = sum(W[h] * f[ss == h].mean() for h in range(H))
    d, wg = y[gold] - f[gold], w[gold]
    theta += (wg * d).sum() / wg.sum()
    if pseudo_weight:
        da = np.concatenate([d, [1.0, -1.0]])
        wa = np.concatenate([wg, [wg.mean() * pseudo_weight] * 2])
        ya = np.concatenate([y[gold], [1.0, 0.0]])
    else:
        da, wa, ya = d, wg, y[gold]
    mu = (wa * da).sum() / wa.sum()
    geff = wa.sum() ** 2 / (wa ** 2).sum()
    sd2 = (wa * (da - mu) ** 2).sum() / wa.sum() * geff / max(geff - 1, 1)
    sy2 = ya.var(ddof=1) if len(ya) > 1 else 0.0
    V = sum(W[h] ** 2 * (1 - nh[h] / Nh[h]) * sy2 / nh[h] for h in range(H)) + (1 - g / n) * sd2 / g
    rows = [np.flatnonzero(ss == h) for h in range(H)]
    idx = np.concatenate([r[rng.integers(0, len(r), size=(B, len(r)))] for r in rows], axis=1)
    fb, off = np.zeros(B), 0
    for h, r in enumerate(rows):
        fb += W[h] * f[idx[:, off:off + len(r)]].mean(1)
        off += len(r)
    gm = gold[idx]
    dd = np.where(gm, (y - f)[idx], 0.0)
    ww = np.where(gm, w[idx], 0.0)
    reps = fb + (ww * dd).sum(1) / np.maximum(ww.sum(1), 1e-12)
    ve = reps.var(ddof=1)
    if ve > 0:
        lo, hi = np.quantile(theta + np.sqrt(V / ve) * (reps - theta), [(1 - level) / 2, (1 + level) / 2])
    else:
        lo, hi = _t_interval(theta, V, g, level)
    return float(theta), max(float(lo), 0.0), min(float(hi), 1.0), float(V)


def predictor_values(answers: Mapping[str, str], claimed: Mapping[str, str], strata: Mapping[str, str]):
    """f_i = 1 when the verifier's answer agrees with the claim. A missing or ``cannot_assess`` answer is an
    abstention: f is the mean non-abstained f of its stratum, else the pooled mean, else 0.5.
    Returns (f, abstain) dicts keyed by unit id (the units of ``strata``)."""
    abstain = {u: answers.get(u, "cannot_assess") == "cannot_assess" for u in strata}
    f = {u: float(answers[u] == claimed[u]) for u in strata if not abstain[u]}
    pooled = float(np.mean(list(f.values()))) if f else 0.5
    for h in set(strata.values()):
        seen = [f[u] for u in strata if strata[u] == h and u in f]
        fill = float(np.mean(seen)) if seen else pooled
        f.update({u: fill for u in strata if strata[u] == h and abstain[u]})
    return f, abstain


def _arrays(design: SampleDesign, gold_ids):
    units = sorted((u for u in design.units if u.kind == "claim"), key=lambda u: u.order)
    names = sorted({u.stratum for u in units})
    ss = np.array([names.index(u.stratum) for u in units])
    Nh = np.array([design.N_h[h] for h in names])
    gold = np.array([u.unit_id in gold_ids for u in units])
    return units, names, ss, Nh, gold


def ppi_mean(design: SampleDesign, gold: GoldDraw, f: Mapping[str, float], abstain: Mapping[str, bool],
             y_gold: Mapping[str, float], *, cfg: TrustConfig, seed: int) -> PPIResult:
    """PPI over the claim units of ``design``; G = the drawn gold units that carry a label in ``y_gold``.
    lambda is fixed at 1 (cross-fitted lambda above ``cfg.lam_fixed_below`` is not built)."""
    del abstain  # abstentions are already imputed in f (third category); kept for the §3 signature
    G = set(gold.unit_ids) & set(y_gold)
    units, _, ss, Nh, gm = _arrays(design, G)
    if not G:
        raise ValueError("ppi_mean needs at least one labelled gold unit")
    fa = np.array([f[u.unit_id] for u in units])
    ya = np.array([y_gold.get(u.unit_id, 0.0) for u in units])
    th, lo, hi, V = ppi_core(ss, Nh, fa, ya, gm, B=cfg.B, level=cfg.level, pseudo_weight=cfg.pseudo_weight,
                             rng=np.random.default_rng(seed))
    # the rectified point can leave [0, 1] in small samples; project it like the interval
    return PPIResult(min(max(th, 0.0), 1.0), lo, hi, cfg.level, PPI_METHOD, len(units), len(G), cfg.B, seed, 1.0, V)


def classical_gold_only(design: SampleDesign, gold: GoldDraw, y_gold: Mapping[str, float], *,
                        cfg: TrustConfig, seed: int) -> PPIResult:
    """Human labels alone: exact hypergeometric when every claim stratum is a census, else the PPI
    machinery with f = 0."""
    G = set(gold.unit_ids) & set(y_gold)
    units, names, _, Nh, _ = _arrays(design, G)
    if all(design.n_h[h] == design.N_h[h] for h in names):
        k = int(round(sum(y_gold[u] for u in G)))
        e = hypergeom_exact(k, len(G), int(Nh.sum()), cfg.level, N_h={h: design.N_h[h] for h in names},
                            n_h={h: design.n_h[h] for h in names})
        return PPIResult(e.point, e.lo, e.hi, cfg.level, "hypergeom-exact", len(units), len(G), None, None)
    zeros = {u.unit_id: 0.0 for u in units}
    return ppi_mean(design, gold, zeros, {}, y_gold, cfg=cfg, seed=seed)
