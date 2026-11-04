"""M1-M5: PPI coverage, pseudo-unit mutation, narrowing, null verifier, abstention as a third category.
Plus the oracle check against the verbatim prototype."""

from __future__ import annotations

import functools

import numpy as np
import pytest
from _reference_ppi import hyper_ci
from _reference_ppi import ppi as ref_ppi
from _world import BASE

from treehouse.trust.ppi import ppi_core

pytestmark = pytest.mark.method

SCEN = {
    "moderate": {}, "shuffled": dict(shuffle=True), "strong": dict(se=0.95, sp=0.9, abst=(0, 0, 0.1)),
    "perfect": dict(se=1.0, sp=1.0, abst=(0, 0, 0)), "highprec": dict(p=(0.97, 0.95, 0.9)),
    "twophase": dict(Nh=(100, 100, 100), nh=(20, 20, 20)),
}
SEED = {k: BASE + 10 + i for i, k in enumerate(SCEN)}  # +10 .. +15


def sim(R=300, Nh=(20, 20, 20), nh=None, g=20, p=(0.9, 0.75, 0.6), se=0.85, sp=0.7, abst=(0.05, 0.1, 0.35),
        seed=0, shuffle=False, level=0.9, pseudo=0.5, B=400, abst_model=None, gold_from_answered=False):
    rng = np.random.default_rng(seed)
    Nh = np.array(Nh)
    nh = Nh if nh is None else np.array(nh)
    st = np.repeat(np.arange(3), Nh)
    cov, w, wx, err = 0, 0.0, 0.0, 0.0
    for _ in range(R):
        Y = (rng.random(Nh.sum()) < np.array(p)[st]).astype(float)
        idx = np.concatenate([rng.choice(np.flatnonzero(st == h), nh[h], replace=False) for h in range(3)])
        ys, ss = Y[idx], st[idx]
        v = np.where(ys == 1, rng.random(len(ys)) < se, rng.random(len(ys)) > sp).astype(float)
        if shuffle:
            v = rng.permutation(v)
        ab = abst_model(ys, ss, rng) if abst_model else rng.random(len(ys)) < np.array(abst)[ss]
        f = v.copy()
        for h in range(3):
            mm = (ss == h) & ~ab
            f[(ss == h) & ab] = f[mm].mean() if mm.any() else 0.5
        pool = np.flatnonzero(~ab) if gold_from_answered else np.arange(len(ys))
        gold = np.zeros(len(ys), bool)
        gold[rng.choice(pool, g, replace=False)] = True
        th, lo, hi, _ = ppi_core(ss, Nh, f, np.where(gold, ys, np.nan), gold, B=B, level=level,
                                 pseudo_weight=pseudo, rng=rng)
        truth = Y.mean()
        cov += lo <= truth <= hi
        w += hi - lo
        err += th - truth
        if (nh == Nh).all():
            a, b = hyper_ci(int(ys[gold].sum()), g, Nh.sum(), 1 - level)
            wx += b - a
    return {"cov": cov / R, "w": w / R, "wx": wx / R, "bias": err / R}


@functools.cache
def _m1():  # computed inside the first test call so the method-time budget counts it
    return {k: sim(seed=SEED[k], **v) for k, v in SCEN.items()}


def test_m1_coverage_every_scenario():
    m1 = _m1()
    assert {k: r["cov"] for k, r in m1.items() if r["cov"] < 0.86} == {}


def test_m2_no_pseudo_units_undercovers():
    for k in ("strong", "perfect"):
        assert sim(seed=SEED[k], pseudo=0.0, **SCEN[k])["cov"] < 0.80, k


def test_m3_strong_verifier_narrows():
    m1 = _m1()
    assert m1["strong"]["w"] <= 0.85 * m1["strong"]["wx"]


def test_m4_shuffled_verifier_is_no_narrower():
    r = _m1()["shuffled"]
    assert r["cov"] >= 0.86 and r["w"] >= 0.95 * r["wx"]


def _abst_by_truth(ys, ss, rng):
    pa = np.where(ss == 2, np.where(ys == 0, 0.6, 0.1), 0.05)
    return rng.random(len(ys)) < pa


def test_m5_abstention_third_category_and_gold_from_answered_mutation():
    ok = sim(seed=BASE + 16, abst_model=_abst_by_truth)
    bad = sim(seed=BASE + 16, abst_model=_abst_by_truth, gold_from_answered=True)
    assert ok["cov"] >= 0.86
    assert abs(bad["bias"]) > 0.04


def test_core_matches_reference_prototype():
    rng = np.random.default_rng(BASE)
    ss = np.repeat(np.arange(3), 20)
    f = rng.random(60).round()
    y = rng.random(60).round()
    gold = np.zeros(60, bool)
    gold[rng.choice(60, 20, replace=False)] = True
    yy = np.where(gold, y, np.nan)
    Nh = np.array([40, 30, 20])
    ref = ref_ppi(ss, Nh, f, yy, gold, np.random.default_rng(7), B=400, alpha=0.1, pseudo=0.5)
    ours = ppi_core(ss, Nh, f, yy, gold, B=400, level=0.9, pseudo_weight=0.5, rng=np.random.default_rng(7))
    assert np.allclose(ref, ours[:3], atol=1e-12)
