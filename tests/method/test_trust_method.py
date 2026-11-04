"""M8 planted errors, M9 placebo, M10 test-retest, M11 determinism, M13 baselines, M14 tier table."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest
from _world import BASE, label, verdict, world

from treehouse.canon import canonical_json
from treehouse.schemas.config import TrustConfig
from treehouse.schemas.numbers import Tier, TypedNumber
from treehouse.stats.agreement import cohen_kappa
from treehouse.stats.intervals import clopper_pearson, poisson_binomial_interval
from treehouse.trust.adjudication import ADJ_PREFIX
from treehouse.trust.baselines import KeyedRun, baseline_b0, baseline_b2, betabinom_fit
from treehouse.trust.passport import build_passport
from treehouse.trust.ppi import ppi_core
from treehouse.trust.tiers import DISAGREE_REASON, select_tier

pytestmark = pytest.mark.method
CFG = TrustConfig()
FAST = TrustConfig(B=400)
META = {"manifest_ref": "m", "synthetic": True}


def test_m8_planted_errors_move_the_estimate_down():
    rng = np.random.default_rng(BASE + 30)
    means, truths = [], []
    for k in (0, 6, 12, 18, 24):
        est = []
        for _ in range(50):
            y = np.ones(60)
            y[rng.choice(60, k, replace=False)] = 0
            f = np.where(y == 1, rng.random(60) < 0.85, rng.random(60) < 0.20).astype(float)
            gold = np.zeros(60, bool)
            gold[rng.choice(60, 20, replace=False)] = True
            est.append(ppi_core(np.zeros(60, int), [60], f, y, gold, B=50, level=0.9, pseudo_weight=0.5, rng=rng)[0])
        means.append(np.mean(est))
        truths.append((60 - k) / 60)
    assert all(a > b for a, b in zip(means, means[1:], strict=False))
    assert np.max(np.abs(np.array(means) - truths)) <= 0.05


def test_m9_placebo_coverage_and_always_damaged_stub():
    rng = np.random.default_rng(BASE + 40)
    for q in (0.0, 0.1, 0.3):
        ks = rng.binomial(40, q, size=300)
        cov = np.mean([(e := clopper_pearson(int(k), 40, 0.9)).lo <= q <= e.hi for k in ks])
        assert cov >= 0.88, q
    ev, _ = world(BASE + 40, p=(1, 1, 1), se=1, sp=1, abst=(0, 0, 0), threshold=0.5, controls={"placebo": 40})
    assert build_passport(ev, FAST, seed=1).gate == "Rely"  # the placebo is what blocks Rely below
    stub = dataclasses.replace(ev, verdicts=[verdict(v.unit_id, "yes") if v.unit_id.startswith("placebo")
                                             else v for v in ev.verdicts])
    p = build_passport(stub, FAST, seed=1)
    assert p.controls.placebo_far.value == 1.0
    assert "verifier-fails-placebo" in p.gate_reasons and p.gate != "Rely"


def test_m10_test_retest_kappa():
    rng = np.random.default_rng(BASE + 41)
    a = rng.random(200) < 0.5
    b = np.where(rng.random(200) < 0.8, a, ~a)  # agreement 0.8 on balanced answers: kappa = 0.6
    assert abs(cohen_kappa(a, b, B=200, seed=BASE + 41).point - 0.6) <= 0.1
    ev, _ = world(BASE + 41, controls={"retest": 5})
    k = build_passport(ev, FAST, seed=1).controls.retest_kappa
    assert k.n == 5 and "anecdotal" in k.reasons


def test_m11_determinism():
    ev, _ = world(BASE + 42, n_cannot=2)
    a, b = (canonical_json(build_passport(ev, CFG, seed=BASE + 42)) for _ in range(2))
    assert a == b
    h1 = build_passport(ev, CFG, seed=BASE + 42).headline.interval
    h2 = build_passport(ev, CFG, seed=BASE + 43).headline.interval
    assert abs(h1.lo - h2.lo) < 0.02 and abs(h1.hi - h2.hi) < 0.02


def test_m13_baselines():
    rng = np.random.default_rng(BASE + 60)
    conf = rng.uniform(0.5, 1.0, 40)
    e = poisson_binomial_interval(conf, 0.9)
    mc = (rng.random((20000, 40)) < conf).sum(1)
    q = np.quantile(mc, [0.05, 0.95])
    assert abs(e.lo - q[0]) <= 1 and abs(e.hi - q[1]) <= 1
    b2 = baseline_b2([], "m", "h", 40, CFG, meta=META)
    assert b2.interval.hi - b2.interval.lo >= 0.4
    # A single 30-run kappa MLE lands outside x2 of the truth ~23 % of the time (checked against a grid), so
    # the check is on the median over 50 seeded replicate datasets: it tests the estimator, not one draw.
    rng = np.random.default_rng(BASE + 61)
    fits = np.array([betabinom_fit(rng.binomial(40, rng.beta(16, 4, 30)), [40] * 30) for _ in range(50)])
    mu, kap = np.median(fits, axis=0)
    assert abs(mu - 0.8) <= 0.03 and 10 <= kap <= 40
    one = baseline_b0([KeyedRun("f", "m", "h", "t", "va", 30, 40)], "f", "m", "h", "t", 40, CFG, meta=META)
    assert one.detail["fit"] == "kappa0" and one.detail["kappa"] == CFG.kappa0


RUN = KeyedRun("bridges", "m", "plain_loop", "t1", "virginia", 35, 40)


def _gold(ev, **kw):
    return [label(g.unit_id, g.label, **kw) for g in ev.gold]


def _keyed():
    return TypedNumber(metric="precision", value=0.9, type="proportion", tier=Tier.KEYED, panel="output", n=60,
                       estimator_version="k", manifest_ref="m", synthetic=True, detail={"key_version": "v1"})


def _rows():
    base, _ = world(BASE + 70)
    late, _ = world(BASE + 70, gold_seq=20)
    small, _ = world(BASE + 70, n_gold=3)
    r = dataclasses.replace
    return [
        ("keyed", r(base, keyed=_keyed()), Tier.KEYED, "L1", []),
        ("gold cross-family", base, Tier.GOLD_ANCHORED, "L3", []),
        ("gold same-family", r(base, same_family_verifier=True), Tier.GOLD_ANCHORED, "L2", []),
        ("late gold, keyed runs", r(late, keyed_runs=[RUN]), Tier.MODEL_ESTIMATED, None, ["gold-not-precommitted"]),
        ("late gold, no runs", late, Tier.ABSTAINED, None,
         ["gold-not-precommitted", "no gold and no keyed runs for family bridges"]),
        ("adjudication gold only", r(base, gold=_gold(base, ref=ADJ_PREFIX + "x")), Tier.ABSTAINED, None,
         ["adjudication-gold-refused", "no gold and no keyed runs for family bridges"]),
        ("adjudication beside gold", r(base, gold=[*base.gold, *_gold(base, ref=ADJ_PREFIX + "x")]),
         Tier.GOLD_ANCHORED, "L3", ["adjudication-gold-refused"]),
        ("gold outside draw", r(base, gold=[*base.gold, label("c9-999", "yes")]), Tier.GOLD_ANCHORED, "L3",
         ["gold-not-in-draw"]),
        ("anecdotal gold", small, Tier.GOLD_ANCHORED, "L3", ["anecdotal"]),
        ("incomplete gold", r(base, gold=base.gold[:15]), Tier.GOLD_ANCHORED, "L3", ["gold-incomplete: 15 of 20 labelled"]),
        ("no blind protocol", r(base, gold=_gold(base, protocol="")), Tier.ABSTAINED, None,
         ["no-blind-protocol", "no gold and no keyed runs for family bridges"]),
        ("no gold, family runs", r(base, gold=[], gold_draw=None, keyed_runs=[RUN]), Tier.MODEL_ESTIMATED, None, []),
        ("no gold, other family", r(base, gold=[], keyed_runs=[r(RUN, family="solar")]), Tier.ABSTAINED, None,
         ["no gold and no keyed runs for family bridges"]),
        ("no gold, synthetic runs only", r(base, gold=[], keyed_runs=[r(RUN, synthetic=True)]), Tier.ABSTAINED, None,
         ["no gold and no keyed runs for family bridges"]),
        ("relabels only", r(base, gold=_gold(base, relabel=True)), Tier.ABSTAINED, None,
         ["no gold and no keyed runs for family bridges"]),
    ]


def test_m14_tier_table():
    got = {name: (d := select_tier(ev, CFG)) and (d.tier, d.rung, d.reasons) for name, ev, *_ in _rows()}
    want = {name: (t, rung, reasons) for name, _, t, rung, reasons in _rows()}
    assert got == want


def test_m14_non_overlap_forces_do_not_rely():
    ev, _ = world(BASE + 71, p=(0.5, 0.5, 0.5), threshold=0.4,
                  keyed_runs=[dataclasses.replace(RUN, regime=f"r{i}", k=39) for i in range(5)])
    p = build_passport(ev, FAST, seed=1)
    assert ("precision", "b0_same_config") in p.disagreement
    assert p.gate == "Do not rely" and p.gate_reasons == [DISAGREE_REASON]
