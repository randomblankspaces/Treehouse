"""Output grader v2 (report Table 7/11 protocol), hand-computed on a toy 4 x 4 grid of 160 m cells.

The AOI straddles the equator so a degree of longitude is exactly ``M_PER_DEG`` metres and ``xy`` maps
local metres (x east from the west edge, y north from the south edge) straight to lon/lat.

Toy world (cells written (col, row), row 0 at the south):

    assets  A1 (80, 80)  -> cell (0,0)
            A2 (320, 400) -> on the edge x = 320: touches (1,2) and (2,2)
            A3 (560, 560) -> cell (3,3)
    asset-holding cells: (0,0) (1,2) (2,2) (3,3) = 4 of 16, base rate 0.25

    claims  C1 (90, 70)   0.9 -> (0,0)  finds A1
            C2 (100, 100) 0.5 -> (0,0)  finds A1 again (counted once)
            C3 (200, 400) 0.8 -> (1,2)  finds A2 by any-touch on the edge
            C4 (400, 80)  0.7 -> (2,0)  empty
            C5 (560, 240) 0.3 -> (3,1)  empty
    flagged cells ranked by max score: (0,0) 0.9, (1,2) 0.8, (2,0) 0.7, (3,1) 0.3
"""
from __future__ import annotations

import pytest

from treehouse.checks import protocol_grader as pg
from treehouse.checks.protocol_grader import Asset, PredictedClaim, grade, transfer_gap
from treehouse.geo.geom import M_PER_DEG

HALF = 320.0
AOI = (0.0, -HALF / M_PER_DEG, 640.0 / M_PER_DEG, HALF / M_PER_DEG)


def xy(x: float, y: float) -> tuple[float, float]:
    return x / M_PER_DEG, (y - HALF) / M_PER_DEG


def asset(x, y, id_):
    return Asset(*xy(x, y), id=id_)


def claim(x, y, score):
    return PredictedClaim(*xy(x, y), score=score)


ASSETS = [asset(80, 80, "A1"), asset(320, 400, "A2"), asset(560, 560, "A3")]
CLAIMS = [claim(90, 70, 0.9), claim(100, 100, 0.5), claim(200, 400, 0.8),
          claim(400, 80, 0.7), claim(560, 240, 0.3)]


def toy(completeness="complete", **kw):
    return grade(CLAIMS, ASSETS, AOI, completeness=completeness, ks=(1, 2, 3, 10), **kw)


def test_version_and_counts():
    r = toy()
    assert pg.GRADER_VERSION == "grade-lgnd-v1" and r.grader_version == "grade-lgnd-v1"
    assert r.cell_size_m == 160.0 and r.completeness == "complete"
    assert (r.n_grid_cells, r.n_assets, r.n_asset_cells) == (16, 3, 4)
    assert (r.n_flagged_cells, r.n_predicted_sites) == (4, 5)
    assert "160 m" in r.units["precision"] and "assets" in r.units["recall"]


def test_hand_computed_metrics():
    r = toy()
    assert r.n_found == 2                     # A1 (once, despite C1 and C2) and A2; A3 missed
    assert r.recall == pytest.approx(2 / 3)
    # top-1 (0,0) -> A1; top-2 adds (1,2) -> A2; (2,0) and (3,1) add nothing; k=10 > 4 flagged = all
    assert r.recall_at_k == pytest.approx({1: 1 / 3, 2: 2 / 3, 3: 2 / 3, 10: 2 / 3})
    assert r.precision == pytest.approx(0.5)  # (0,0) and (1,2) of 4 flagged cells
    assert r.precision_is_lower_bound is False
    assert r.lift == pytest.approx(2.0)       # 0.5 / base rate 4/16
    assert r.count_ratio == pytest.approx(5 / 3)  # 5 predicted sites / 3 known assets
    # 50 % of 3 = 1.5 -> 2 assets -> 2 cells; 80 % and 90 % need all 3, which the flagged cells never reach
    assert r.review_effort == {"50": 2, "80": None, "90": None}
    # AUROC over all 16 cells (empty = 0). Positives 0.9, 0.8, 0, 0; negatives 0.7, 0.3 and ten 0s.
    # 0.9 and 0.8 beat all 12 negatives (24); each 0 positive ties ten 0 negatives (2 x 10 x 0.5 = 10).
    # (24 + 10) / (4 x 12) = 34 / 48
    assert r.auroc == pytest.approx(34 / 48)
    # AP, ties grouped per threshold: 0.9 P=1 dR=1/4; 0.8 P=1 dR=1/4; 0.7 and 0.3 dR=0;
    # 0 (all cells) P=4/16 dR=1/2.  1/4 + 1/4 + 1/2 x 1/4 = 0.625
    assert r.ap == pytest.approx(0.625)
    assert r.null_reasons == {}


def test_review_effort_reaches_all_when_every_asset_is_flagged():
    claims = [*CLAIMS, claim(560, 560, 0.1)]  # (3,3) last in the ranking -> 5th cell finds A3
    r = grade(claims, ASSETS, AOI)
    assert r.recall == pytest.approx(1.0)
    assert r.review_effort == {"50": 2, "80": 5, "90": 5}


def test_any_touch_on_cell_edge_from_either_side():
    left = grade([claim(200, 400, 1.0)], [asset(320, 400, "A2")], AOI)    # cell (1,2)
    right = grade([claim(440, 400, 1.0)], [asset(320, 400, "A2")], AOI)   # cell (2,2)
    assert left.recall == right.recall == 1.0
    assert left.n_asset_cells == 2
    # 20 m inside cell (1,2) is not on an edge: only (1,2) touches it
    off = grade([claim(440, 400, 1.0)], [asset(300, 400, "A")], AOI)
    assert off.recall == 0.0 and off.n_asset_cells == 1


def test_each_asset_counts_once():
    big = Asset(*xy(240, 80), id="P", polygon=[[xy(100, 20), xy(400, 20), xy(400, 140), xy(100, 140),
                                                   xy(100, 20)]])  # spans cells (0,0) (1,0) (2,0)
    r = grade([claim(80, 80, 0.9), claim(240, 80, 0.8), claim(400, 80, 0.7)], [big], AOI)
    assert (r.n_assets, r.n_found, r.recall) == (1, 1, 1.0)
    assert r.n_asset_cells == 3 and r.precision == 1.0
    assert r.count_ratio == 3.0  # three predicted sites for one known asset


def test_incomplete_reference_reports_only_precision_in_pool():
    r = toy("incomplete")
    assert r.completeness == "incomplete"
    assert r.precision == pytest.approx(0.5) and r.precision_is_lower_bound is True
    for name in ("recall", "recall_at_k", "count_ratio", "auroc", "ap", "review_effort", "lift", "n_found"):
        assert getattr(r, name) is None
    for name in ("recall", "recall_at_k", "count_ratio", "auroc", "ap", "review_effort"):
        assert r.null_reasons[name] == "incomplete_reference"
    assert "lower bound" in r.units["precision"]


def test_transfer_gap_is_home_minus_away():
    home = toy()
    away = grade([claim(90, 70, 0.9)], ASSETS, AOI, ks=(1, 2, 3, 10))  # finds A1 only
    gap = transfer_gap(home, away)
    assert gap["recall"] == pytest.approx(2 / 3 - 1 / 3) and gap["recall"] > 0
    assert gap["recall@2"] == pytest.approx(1 / 3)
    assert gap["precision"] == pytest.approx(0.5 - 1.0) and gap["precision"] < 0
    assert transfer_gap(home, toy("incomplete")).keys() == {"precision"}


def test_claims_outside_aoi_and_empty_inputs():
    r = grade([PredictedClaim(10.0, 10.0, 1.0)], ASSETS, AOI)
    assert r.n_flagged_cells == 0 and r.precision is None and r.null_reasons["precision"] == "no_flagged_cells"
    assert r.recall == 0.0
    assert grade([], [], AOI).recall is None
    with pytest.raises(ValueError):
        grade([], [], AOI, completeness="partial")


def test_member_cells_flag_extra_cells():
    c = PredictedClaim(*xy(80, 80), score=0.9, member_cells=((3, 3),))
    r = grade([c], ASSETS, AOI)
    assert r.n_flagged_cells == 2 and r.n_found == 2 and r.n_predicted_sites == 1
