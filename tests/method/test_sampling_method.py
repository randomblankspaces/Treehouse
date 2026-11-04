"""M7 (stratified SRSWOR inclusion, HT), M16 (gold from all units), M17 (blindness)."""

from __future__ import annotations

import inspect
import json

import numpy as np
import pytest
from _world import BASE
from hypothesis import given, settings
from hypothesis import strategies as st

from treehouse.sampling.blind import assemble_verifier_batch
from treehouse.sampling.design import ht_mean, srswor_indices, stratified_sample
from treehouse.sampling.gold import draw_gold
from treehouse.schemas.sampling import BlindItem, SampleDesign

pytestmark = pytest.mark.method


def test_m7_inclusion_ht_and_design_id():
    Nh, nh = (30, 20, 10), {"a": 10, "b": 10, "c": 5}
    strata = np.repeat(["a", "b", "c"], Nh)
    y = np.repeat([0.9, 0.5, 0.1], Nh) + np.random.default_rng(BASE + 20).normal(0, 0.05, 60)
    pi = np.array([nh[s] / n for s, n in zip("abc", Nh, strict=True) for _ in range(n)])
    R = 5000
    hits = np.zeros(60)
    ht, ht_bad = np.empty(R), np.empty(R)
    for r in range(R):
        idx = srswor_indices(strata, nh, BASE + 20 + r)
        hits[idx] += 1
        ht[r] = ht_mean(y[idx], pi[idx], 60)
        ht_bad[r] = ht_mean(y[idx], np.full(len(idx), 25 / 60), 60)  # mutation: uniform pi
    se = np.sqrt(pi * (1 - pi) / R)
    assert np.all(np.abs(hits / R - pi) <= 4 * se)
    assert pi.sum() == pytest.approx(25)
    truth, se_ht = y.mean(), ht.std(ddof=1) / np.sqrt(R)
    assert abs(ht.mean() - truth) <= 3 * se_ht
    assert abs(ht_bad.mean() - truth) > 4 * ht_bad.std(ddof=1) / np.sqrt(R)

    frame = [{"unit_id": f"u{i:02d}", "kind": "claim", "ref": f"u{i:02d}", "stratum": s} for i, s in enumerate(strata)]
    d1, d2 = (SampleDesign.model_validate(stratified_sample(frame, nh, seed=s)) for s in (BASE, BASE))
    d3 = SampleDesign.model_validate(stratified_sample(frame, nh, seed=BASE + 1))
    assert d1.design_id == d2.design_id != d3.design_id
    assert {u.stratum: u.pi for u in d1.units} == {"a": 1 / 3, "b": 0.5, "c": 0.5}
    assert len(d1.units) == 25 and sorted(u.order for u in d1.units) == list(range(25))


def test_m16_gold_drawn_from_all_units_including_abstentions():
    assert "verdicts" not in inspect.signature(draw_gold).parameters
    frame = [{"unit_id": f"u{i:03d}", "kind": "claim", "ref": "-", "stratum": "s"} for i in range(60)]
    design = stratified_sample(frame, {"s": 60}, seed=BASE + 80)
    rng = np.random.default_rng(BASE + 80)
    abstained = {u for u in (f"u{i:03d}" for i in range(60)) if rng.random() < 0.15}
    hit = [bool(abstained & set(draw_gold(design, 20, seed=BASE + 80 + s, committed_ref="c",
                                          committed_seq=0)["unit_ids"])) for s in range(50)]
    assert any(hit)


def _claim(uid, label, conf, reason, worker):
    return {"unit_id": uid, "lon": 85.1, "lat": 27.9, "object_definition": "a road bridge over a river",
            "question_id": "damaged", "scene_ids": ["s1"], "status": label, "confidence": conf,
            "reason": reason, "worker_id": worker}


_text = st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=0, max_size=12)


@settings(max_examples=200, deadline=None, derandomize=True)
@given(lab=st.sampled_from(["intact", "destroyed", "present", "absent"]), conf=st.floats(0.001, 0.999),
       reason=_text, worker=st.text(alphabet="XYZQ", min_size=6, max_size=10))
def test_m17_blind_items_ignore_label_confidence_reason(lab, conf, reason, worker):
    ctl = [{"unit_id": "ctl-1", "lon": 85.2, "lat": 27.8, "object_definition": "a road bridge over a river",
            "question_id": "damaged", "scene_ids": ["s2"]}]
    a, _ = assemble_verifier_batch([_claim("c-1", lab, conf, reason, "WK" + worker)], ctl, seed=1, hmac_key=b"k")
    b, _ = assemble_verifier_batch([_claim("c-1", "intact", 0.5, "", "WKother")], ctl, seed=1, hmac_key=b"k")
    as_bytes = [BlindItem.model_validate(x).model_dump_json() for x in a]
    assert as_bytes == [BlindItem.model_validate(x).model_dump_json() for x in b]
    assert len({frozenset(x) for x in a}) == 1  # claims and controls have the same keys
    blob = json.dumps(a)
    assert "WK" + worker not in blob and lab not in blob and repr(conf) not in blob and "c-1" not in blob
