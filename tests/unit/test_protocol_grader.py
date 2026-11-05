"""Output grader v2 (report Table 7/11 protocol), hand-computed on a toy 4 x 4 grid.

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
    predicted sites (8-neighbour components): {(0,0)}, {(1,2)}, {(2,0),(3,1)} = 3
"""
from __future__ import annotations

import numpy as np
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
CLAIMS = [
    claim(90, 70, 0.9),
    claim(100, 100, 0.5),
    claim(200, 400, 0.8),
    claim(400, 80, 0.7),
    claim(560, 240, 0.3),
]


def toy(completeness="complete", **kw):
    return grade(CLAIMS, ASSETS, AOI, completeness=completeness, ks=(1, 2, 3, 10), **kw)


def test_version_and_counts():
    r = toy()
    assert pg.GRADER_VERSION == "grade-lgnd-v1" and r.grader_version == "grade-lgnd-v1"
    assert r.cell_size_m == 160.0 and r.completeness == "complete"
    assert (r.n_grid_cells, r.n_assets, r.n_assets_outside_aoi, r.n_asset_cells) == (16, 3, 0, 4)
    assert (r.n_claims, r.n_flagged_cells, r.n_predicted_sites) == (5, 4, 3)
    assert "160 m" in r.units["precision"] and "assets" in r.units["recall"]
    assert "8-neighbour" in r.units["n_predicted_sites"]
    assert "finite, non-negative" in r.units["claim_score"]


def test_hand_computed_metrics():
    r = toy()
    assert r.n_found == 2  # A1 (once, despite C1 and C2) and A2; A3 missed
    assert r.recall == pytest.approx(2 / 3)
    # top-1 (0,0) -> A1; top-2 adds (1,2) -> A2; (2,0) and (3,1) add nothing; k=10 > 4 flagged = all
    assert r.recall_at_k == pytest.approx({1: 1 / 3, 2: 2 / 3, 3: 2 / 3, 10: 2 / 3})
    assert r.precision == pytest.approx(0.5)  # (0,0) and (1,2) of 4 flagged cells
    assert r.precision_is_lower_bound is False
    assert r.lift == pytest.approx(2.0)  # 0.5 / base rate 4/16
    assert r.count_ratio == pytest.approx(1.0)  # 3 connected predicted sites / 3 known assets
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
    left = grade([claim(200, 400, 1.0)], [asset(320, 400, "A2")], AOI)  # cell (1,2)
    right = grade([claim(440, 400, 1.0)], [asset(320, 400, "A2")], AOI)  # cell (2,2)
    assert left.recall == right.recall == 1.0
    assert left.n_asset_cells == 2
    # 20 m inside cell (1,2) is not on an edge: only (1,2) touches it
    off = grade([claim(440, 400, 1.0)], [asset(300, 400, "A")], AOI)
    assert off.recall == 0.0 and off.n_asset_cells == 1


def test_point_asset_on_interior_cell_corner_touches_four_cells():
    r = grade([], [asset(320, 320, "corner")], AOI)
    assert r.n_asset_cells == 4


def test_polygon_edge_tolerance_reaches_neighbouring_cell():
    polygon = Asset(
        *xy(150, 80),
        id="P",
        polygon=[[
            xy(140, 40),
            xy(159.5, 40),
            xy(159.5, 120),
            xy(140, 120),
            xy(140, 40),
        ]],
    )
    without_tolerance = grade([claim(200, 80, 1.0)], [polygon], AOI, edge_tol_m=0.0)
    with_tolerance = grade([claim(200, 80, 1.0)], [polygon], AOI, edge_tol_m=1.0)
    assert without_tolerance.n_asset_cells == 1 and without_tolerance.recall == 0.0
    assert with_tolerance.n_asset_cells == 2 and with_tolerance.recall == 1.0


def test_each_asset_counts_once():
    big = Asset(
        *xy(240, 80),
        id="P",
        polygon=[[xy(100, 20), xy(400, 20), xy(400, 140), xy(100, 140), xy(100, 20)]],
    )  # spans cells (0,0) (1,0) (2,0)
    r = grade([claim(80, 80, 0.9), claim(240, 80, 0.8), claim(400, 80, 0.7)], [big], AOI)
    assert (r.n_assets, r.n_found, r.recall) == (1, 1, 1.0)
    assert r.n_asset_cells == 3 and r.precision == 1.0
    assert r.count_ratio == 1.0  # three adjacent flagged cells merge into one predicted site


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


def test_assets_and_claims_outside_ragged_aoi_are_excluded():
    ragged_aoi = (0.0, -250.0 / M_PER_DEG, 500.0 / M_PER_DEG, 250.0 / M_PER_DEG)

    def ragged_xy(x_m, y_m):
        return x_m / M_PER_DEG, (y_m - 250.0) / M_PER_DEG

    inside_asset = Asset(*ragged_xy(470, 250), id="inside")
    outside_asset = Asset(*ragged_xy(510, 250), id="outside")  # 10 m east, within rounded-up grid
    inside_claim = PredictedClaim(*ragged_xy(470, 250), score=0.8)
    outside_claim = PredictedClaim(*ragged_xy(510, 250), score=1.0)
    r = grade([inside_claim, outside_claim], [inside_asset, outside_asset], ragged_aoi)

    assert (r.n_assets, r.n_assets_outside_aoi, r.n_claims) == (1, 1, 1)
    assert (r.n_grid_cells, r.n_asset_cells, r.n_flagged_cells) == (16, 1, 1)
    assert r.recall == r.precision == r.auroc == r.ap == 1.0
    assert r.count_ratio == 1.0


def test_polygon_with_no_part_in_aoi_is_excluded():
    outside_polygon = Asset(
        *xy(700, 80),
        id="outside-polygon",
        polygon=[[xy(650, 40), xy(700, 40), xy(700, 120), xy(650, 120), xy(650, 40)]],
    )
    r = grade([], [outside_polygon], AOI)
    assert (r.n_assets, r.n_assets_outside_aoi, r.n_asset_cells) == (0, 1, 0)


def test_claims_outside_aoi_and_empty_inputs():
    r = grade([PredictedClaim(10.0, 10.0, 1.0)], ASSETS, AOI)
    assert r.n_claims == 0 and r.n_flagged_cells == 0
    assert r.precision is None and r.null_reasons["precision"] == "no_flagged_cells"
    assert r.recall == 0.0
    assert grade([], [], AOI).recall is None
    with pytest.raises(ValueError):
        grade([], [], AOI, completeness="partial")


def test_member_cells_cannot_flag_extra_cells_or_raise_recall():
    c = PredictedClaim(*xy(80, 80), score=0.9, member_cells=((3, 3),))
    r = grade([c], ASSETS, AOI)
    assert r.n_flagged_cells == 1 and r.n_found == 1 and r.n_predicted_sites == 1
    assert r.recall == pytest.approx(1 / 3)


def test_duplicate_and_adjacent_claim_cells_merge_into_sites():
    claims = [
        claim(40, 40, 0.9),
        claim(80, 80, 0.8),  # duplicate flagged cell (0,0)
        claim(200, 200, 0.7),  # diagonal 8-neighbour cell (1,1)
        claim(560, 560, 0.6),  # disconnected cell (3,3)
    ]
    r = grade(claims, [asset(80, 80, "A1"), asset(560, 560, "A3")], AOI)
    assert (r.n_claims, r.n_flagged_cells, r.n_predicted_sites) == (4, 3, 2)
    assert r.count_ratio == 1.0


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -0.01])
def test_claim_scores_must_be_finite_and_non_negative(score):
    with pytest.raises(ValueError, match="finite and non-negative"):
        grade([claim(80, 80, score)], ASSETS, AOI)


def test_mid_latitude_grid_uses_cosine_longitude_scaling():
    # Hand-checked: 111,320 m/degree * cos(35 degrees) = 91,188.00557025056 m/degree.
    metres_per_lon_degree = 91_188.00557025056
    mid_latitude_aoi = (
        136.0,
        35.0 - 160.0 / M_PER_DEG,
        136.0 + 400.0 / metres_per_lon_degree,
        35.0 + 160.0 / M_PER_DEG,
    )
    g = pg._grid(mid_latitude_aoi, 160.0)
    assert g.kx == pytest.approx(metres_per_lon_degree)
    assert g.xy(136.0 + 240.0 / metres_per_lon_degree, 35.0) == pytest.approx((240.0, 160.0))
    assert (g.nx, g.ny) == (3, 2)

    point = (136.0 + 240.0 / metres_per_lon_degree, 35.0)
    r = grade([PredictedClaim(*point, score=1.0)], [Asset(*point, id="nagoya")], mid_latitude_aoi)
    assert r.n_grid_cells == 6 and r.recall == 1.0


def test_tie_heavy_auroc_and_ap_match_brute_force():
    rng = np.random.default_rng(20261104)
    for _ in range(100):
        scores = rng.integers(0, 5, size=30).astype(float)
        labels = rng.integers(0, 2, size=30).astype(bool)
        labels[0], labels[1] = False, True

        positive_scores = scores[labels]
        negative_scores = scores[~labels]
        pairwise = [
            float(positive > negative) + 0.5 * float(positive == negative)
            for positive in positive_scores
            for negative in negative_scores
        ]
        brute_auroc = sum(pairwise) / len(pairwise)

        n_positive = int(labels.sum())
        previous_tp = 0
        brute_ap = 0.0
        for threshold in sorted(set(scores), reverse=True):
            selected = scores >= threshold
            tp = int(labels[selected].sum())
            brute_ap += (tp - previous_tp) / n_positive * tp / int(selected.sum())
            previous_tp = tp

        assert pg.auroc(scores, labels) == pytest.approx(brute_auroc)
        assert pg.average_precision(scores, labels) == pytest.approx(brute_ap)
