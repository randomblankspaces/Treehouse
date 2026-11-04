"""Trust core acceptance: estimand naming, upper bound, narrowing note, census guard, export, adjudication."""

from __future__ import annotations

import csv
import dataclasses
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "method"))
from _world import BASE, world  # noqa: E402

from treehouse.sampling.design import allocate, assign_strata  # noqa: E402
from treehouse.schemas.config import TrustConfig  # noqa: E402
from treehouse.schemas.numbers import Interval, Tier, TypedNumber  # noqa: E402
from treehouse.schemas.sampling import BlindItem  # noqa: E402
from treehouse.stats.intervals import hypergeom_exact  # noqa: E402
from treehouse.trust import adjudication  # noqa: E402
from treehouse.trust.export import DATA_DICTIONARY, tables, write_tables  # noqa: E402
from treehouse.trust.passport import UPPER, build_passport  # noqa: E402
from treehouse.trust.tiers import disagreements, select_tier  # noqa: E402

CFG = TrustConfig(B=400)


def test_estimand_precision_without_cannot_assess():
    p = build_passport(world(BASE)[0], CFG, seed=1)
    assert p.estimand.kind == "precision" and p.n_gold_cannot_assess == 0
    assert p.headline.tier == Tier.GOLD_ANCHORED and UPPER not in {a.metric for a in p.alternatives}


def test_verified_precision_and_upper_bound():
    p = build_passport(world(BASE, n_cannot=3)[0], CFG, seed=1)
    assert p.estimand.kind == "verified_precision" and p.n_gold_cannot_assess == 3
    up = next(a for a in p.alternatives if a.metric == UPPER)
    assert up.value >= p.headline.value and up.interval.hi >= p.headline.interval.hi


def test_upper_bound_and_b1_never_enter_disagreement():
    def num(est, lo, hi):
        return TypedNumber(metric=est, value=(lo + hi) / 2, type="proportion", tier=Tier.MODEL_ESTIMATED,
                           panel="trust", n=10, interval=Interval(lo=lo, hi=hi, level=0.9, method="wilson"),
                           estimator_version="v", manifest_ref="m", synthetic=True, detail={"estimator": est})
    assert disagreements([num("ppi", 0.1, 0.2), num("upper", 0.8, 0.9), num("b1", 0.8, 0.9)]) == []
    assert disagreements([num("ppi", 0.1, 0.2), num("b0", 0.8, 0.9)]) == [("ppi", "b0")]


def test_narrowing_note_iff_ratio_at_least_one():
    seen = set()
    for s in range(6):  # a verifier that never answers cannot narrow the interval
        ev, _ = world(BASE + s, abst=(1, 1, 1) if s % 2 else (0, 0, 0), se=0.97, sp=0.97)
        p = build_passport(ev, CFG, seed=s)
        ratio = p.headline.detail["width_ratio_vs_classical"]
        assert (p.narrowing_note is not None) == (ratio >= 1)
        if p.narrowing_note:
            assert p.narrowing_note == f"the verifier did not narrow the interval at n_gold={p.headline.n_gold}"
        seen.add(ratio >= 1)
    assert seen == {True, False}


def test_hypergeom_needs_census_and_two_phase_uses_ppi_comparator():
    with pytest.raises(ValueError, match="census"):
        hypergeom_exact(10, 20, 300, 0.9, N_h={"a": 300}, n_h={"a": 60})
    assert hypergeom_exact(10, 20, 60, 0.9, N_h={"a": 60}, n_h={"a": 60}).method == "hypergeom-exact"
    p = build_passport(world(BASE, Nh=(100, 100, 100), nh=(20, 20, 20))[0], CFG, seed=1)
    classical = next(a for a in p.alternatives if a.metric == "classical_gold_only")
    assert classical.interval.method == "ppi-2phase-rbs-v1"


def test_beat_baseline_and_model_estimated_default():
    ev, _ = world(BASE, n_gold=0)
    p = build_passport(ev, CFG, seed=1)
    assert p.headline.tier == Tier.ABSTAINED and p.gate == "Do not rely"
    assert p.beat_baseline == "not computable: 0 keyed regimes"


def test_export_round_trip(tmp_path):
    ev, _ = world(BASE, n_cannot=2, controls={"control_pos": 5, "placebo": 5, "retest": 3},
                  confidences={"c0-000": 0.9, "c0-001": 0.7})
    t = tables(ev, build_passport(ev, CFG, seed=1))
    for name, rows in t.items():
        assert rows and all(list(r) == list(DATA_DICTIONARY[name]) for r in rows), name
    assert {r["baseline"] for r in t["baselines"]} == {"b1", "b2"}
    assert any(r["verifier_verdict"] == "cannot_assess" for r in t["units"])
    assert any(r["sampled_for_gold"] and r["gold_label"] is None for r in t["units"]) is False
    write_tables(tmp_path / "j", t, fmt="jsonl")
    write_tables(tmp_path / "c", t, fmt="csv")
    for name, rows in t.items():
        back = [json.loads(x) for x in (tmp_path / "j" / f"{name}.jsonl").read_text().splitlines()]
        assert back == rows
        with (tmp_path / "c" / f"{name}.csv").open(newline="") as fh:
            assert list(csv.DictReader(fh)) == [{k: "" if v is None else str(v) for k, v in r.items()} for r in rows]
    assert (tmp_path / "c" / "data_dictionary.csv").exists()


def test_adjudication_file_round_trip_is_refused_as_gold(tmp_path):
    ev, _ = world(BASE)
    items = [BlindItem(unit_id=u, lon=0, lat=0, object_definition="a bridge", question_id="damaged", scene_ids=[])
             for u in ev.gold_draw.unit_ids[:2]]
    adjudication.write_queue(tmp_path / "q.jsonl", items)
    assert [BlindItem.model_validate_json(x) for x in (tmp_path / "q.jsonl").read_text().splitlines()] == items
    (tmp_path / "a.jsonl").write_text("".join(json.dumps({"unit_id": i.unit_id, "question_id": "damaged",
                                                          "label": "no", "ts": "2026-11-04T00:00:00Z"}) + "\n"
                                              for i in items))
    labs = adjudication.read_labels(tmp_path / "a.jsonl", labeller="t", labeller_kind="human",
                                    blind_protocol_hash="bp", synthetic=False)
    d = select_tier(dataclasses.replace(ev, gold=labs), CFG)
    assert d.tier == Tier.ABSTAINED and "adjudication-gold-refused" in d.reasons


def test_strata_collapse_and_allocation():
    units = [{"class": "bridge", "cloud_class": "c" if i < 2 else "k"} for i in range(10)]
    assert set(assign_strata(units, keys=["class", "cloud_class"])) == {"class=bridge"}
    assert allocate({"a": 30, "b": 20}, 60) == {"a": 30, "b": 20}  # census when N <= 60
    n = allocate({"a": 300, "b": 90, "c": 10}, 60)
    assert sum(n.values()) == 60 and n["c"] >= 2 and n["a"] > n["b"]
