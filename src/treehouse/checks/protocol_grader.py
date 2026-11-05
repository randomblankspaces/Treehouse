"""Output grader v2: the report's Table 7 protocol and Table 11 metrics (R4; design ``checks/protocol_grader``).

Sits beside the point-distance matcher in ``keyed.py``; it does not replace it.

Grid. A ``cell_size_m`` grid is laid over the AOI bbox in local metres: x east from the west edge,
y north from the south edge, longitude scaled by cos(mid-latitude of the AOI). Columns and rows are
``ceil(side / cell_size_m)``, so the last column/row may stick out past the bbox. Cells are ``(col, row)``,
row 0 at the south; the flat index is ``row * n_cols + col``.

Flagging. A claim flags only the cell containing its point (a point on an interior edge goes to the
cell east/north of it). ``member_cells`` is retained as claim metadata but never affects metrics. Claims
outside the AOI are ignored. Claim scores are confidences and must be finite and non-negative. A cell's
score is the maximum score of the claims it contains.

Matching (any-touch, Table 7). An asset is FOUND when any flagged cell touches it. Assets outside the AOI
bbox are dropped before matching and counted in ``n_assets_outside_aoi``; a polygon is retained when any
part intersects the AOI. A point asset touches every cell whose closed square, grown by ``edge_tol_m`` on
each side, contains the point, so an asset on a shared edge (within ``edge_tol_m``) touches the cells on
both sides. The same tolerance grows a cell bbox when testing polygon intersection. Each asset counts
once whatever its size or however many claims hit it.

Metrics (Table 11). An "asset cell" is a grid cell touched by at least one asset. Ranking of flagged cells
is by score descending, ties by flat index ascending. Review effort walks that ranking and stops at the
first cell where ``found >= share * n_assets``; it is ``None`` when the flagged cells never get there.
AUROC and AP run over grid cells that intersect the AOI (score 0 when unflagged, label = asset cell);
AUROC uses midranks for ties and AP groups tied scores into one threshold (sklearn's
``average_precision_score`` convention). Predicted sites are 8-neighbour connected components of
flagged cells. Count ratio is predicted sites over known assets; ``n_claims`` counts in-AOI claims.

Incomplete reference (R4.3). Only precision within the pool is reported (flagged cells touching a pool
asset / flagged cells), marked as a lower bound. Recall, recall@k, count ratio, AUROC, AP and review effort
are ``None`` with reason ``incomplete_reference``; lift is also ``None`` because the base rate is unknown.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

from treehouse.geo.geom import M_PER_DEG, Ring, bbox_intersects, polygons_intersect_bbox
from treehouse.schemas.base import Frozen

GRADER_VERSION = "grade-lgnd-v1"
COMPLETENESS = ("complete", "incomplete")
EFFORT_SHARES = {"50": 0.5, "80": 0.8, "90": 0.9}
INCOMPLETE = "incomplete_reference"
_EPS = 1e-9


@dataclass(frozen=True)
class PredictedClaim:
    lon: float
    lat: float
    score: float
    member_cells: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class Asset:
    lon: float
    lat: float
    id: str | None = None
    polygon: Sequence[Ring] | None = None  # one polygon: outer ring first, then holes (lon/lat)


class GradeReport(Frozen):
    grader_version: str
    cell_size_m: float
    edge_tol_m: float
    completeness: Literal["complete", "incomplete"]
    n_assets: int
    n_assets_outside_aoi: int
    n_found: int | None
    n_claims: int
    n_predicted_sites: int
    n_flagged_cells: int
    n_grid_cells: int
    n_asset_cells: int
    precision: float | None
    precision_is_lower_bound: bool
    lift: float | None
    recall: float | None
    recall_at_k: dict[int, float] | None
    count_ratio: float | None
    auroc: float | None
    ap: float | None
    review_effort: dict[str, int | None] | None
    null_reasons: dict[str, str]
    units: dict[str, str]


@dataclass(frozen=True)
class _Grid:
    west: float
    south: float
    kx: float  # metres per degree of longitude
    cell: float
    nx: int
    ny: int

    def xy(self, lon: float, lat: float) -> tuple[float, float]:
        return (lon - self.west) * self.kx, (lat - self.south) * M_PER_DEG

    def cell_bbox(self, col: int, row: int, buffer_m: float = 0.0) -> tuple[float, float, float, float]:
        c = self.cell
        dx, dy = buffer_m / self.kx, buffer_m / M_PER_DEG
        return (self.west + col * c / self.kx - dx, self.south + row * c / M_PER_DEG - dy,
                self.west + (col + 1) * c / self.kx + dx,
                self.south + (row + 1) * c / M_PER_DEG + dy)

    def span(self, lo: float, hi: float, n: int) -> range:
        return range(max(0, math.floor(lo / self.cell)), min(n - 1, math.floor(hi / self.cell)) + 1)


def _grid(aoi: Sequence[float], cell: float) -> _Grid:
    west, south, east, north = aoi
    if not (east > west and north > south) or cell <= 0:
        raise ValueError("aoi must be (west, south, east, north) with positive extent; cell_size_m > 0")
    kx = M_PER_DEG * math.cos(math.radians((south + north) / 2))
    nx = max(1, math.ceil((east - west) * kx / cell - _EPS))
    ny = max(1, math.ceil((north - south) * M_PER_DEG / cell - _EPS))
    return _Grid(west, south, kx, cell, nx, ny)


def _asset_in_aoi(a: Asset, aoi: Sequence[float]) -> bool:
    if a.polygon is not None:
        return bool(a.polygon and a.polygon[0]) and polygons_intersect_bbox([a.polygon], aoi)
    west, south, east, north = aoi
    return west <= a.lon <= east and south <= a.lat <= north


def _touched(g: _Grid, a: Asset, tol: float) -> set[int]:
    if a.polygon is not None:
        if not a.polygon or not a.polygon[0]:
            return set()
        xs, ys = zip(*(g.xy(p[0], p[1]) for p in a.polygon[0]), strict=True)
        return {r * g.nx + c for c in g.span(min(xs) - tol, max(xs) + tol, g.nx)
                for r in g.span(min(ys) - tol, max(ys) + tol, g.ny)
                if polygons_intersect_bbox([a.polygon], g.cell_bbox(c, r, tol))}
    x, y = g.xy(a.lon, a.lat)
    return {r * g.nx + c for c in g.span(x - tol, x + tol, g.nx)
            for r in g.span(y - tol, y + tol, g.ny)}


def _aoi_cells(g: _Grid, aoi: Sequence[float]) -> set[int]:
    """Grid cells whose closed bbox intersects the AOI bbox."""
    return {r * g.nx + c for r in range(g.ny) for c in range(g.nx)
            if bbox_intersects(g.cell_bbox(c, r), aoi)}


def _count_sites(cells: Iterable[int], g: _Grid) -> int:
    """Count 8-neighbour connected components among flat-indexed grid cells."""
    remaining = set(cells)
    count = 0
    while remaining:
        count += 1
        pending = [remaining.pop()]
        while pending:
            i = pending.pop()
            col, row = i % g.nx, i // g.nx
            neighbours = {
                rr * g.nx + cc
                for rr in range(max(0, row - 1), min(g.ny, row + 2))
                for cc in range(max(0, col - 1), min(g.nx, col + 2))
            }
            found = remaining & neighbours
            remaining.difference_update(found)
            pending.extend(found)
    return count


def auroc(scores: np.ndarray, labels: np.ndarray) -> float | None:
    """Mann-Whitney AUROC with midranks for tied scores; ``None`` without both classes."""
    pos = labels.astype(bool)
    n_pos, n_neg = int(pos.sum()), int((~pos).sum())
    if n_pos == 0 or n_neg == 0:
        return None
    _, inv, counts = np.unique(scores, return_inverse=True, return_counts=True)
    upper = np.cumsum(counts)
    midrank = (upper - (counts - 1) / 2.0)[inv]  # 1-based average rank of each tie group
    return float((midrank[pos].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def average_precision(scores: np.ndarray, labels: np.ndarray) -> float | None:
    """sum over distinct thresholds (descending) of (R_t - R_t-1) * P_t; ``None`` without positives."""
    pos = labels.astype(bool)
    n_pos = int(pos.sum())
    if n_pos == 0:
        return None
    order = np.argsort(-scores, kind="stable")
    s, y = scores[order], pos[order]
    tp = np.cumsum(y)
    last = np.r_[np.nonzero(np.diff(s))[0], len(s) - 1]  # last index of each tie group
    tp_t, n_t = tp[last], last + 1
    recall = tp_t / n_pos
    d_recall = np.diff(np.r_[0.0, recall])
    return float(np.sum(d_recall * tp_t / n_t))


def grade(claims: Iterable[PredictedClaim], assets: Iterable[Asset], aoi: Sequence[float], *,
          completeness: str = "complete", cell_size_m: float = 160.0, edge_tol_m: float = 1.0,
          ks: Sequence[int] = (10, 20, 50)) -> GradeReport:
    if completeness not in COMPLETENESS:
        raise ValueError(f"completeness must be one of {COMPLETENESS}, got {completeness!r}")
    g = _grid(aoi, cell_size_m)
    aoi_cells = _aoi_cells(g, aoi)
    n_cells = len(aoi_cells)
    west, south, east, north = aoi

    cell_score: dict[int, float] = {}
    n_claims = 0
    for c in claims:
        score = float(c.score)
        if not math.isfinite(score) or score < 0:
            raise ValueError("claim scores must be finite and non-negative")
        if not (west <= c.lon <= east and south <= c.lat <= north):
            continue
        n_claims += 1
        x, y = g.xy(c.lon, c.lat)
        i = min(g.ny - 1, int(y // g.cell)) * g.nx + min(g.nx - 1, int(x // g.cell))
        cell_score[i] = max(cell_score.get(i, -math.inf), score)

    touches: list[set[int]] = []
    n_assets_outside_aoi = 0
    for a in assets:
        if not _asset_in_aoi(a, aoi):
            n_assets_outside_aoi += 1
            continue
        touches.append(_touched(g, a, edge_tol_m) & aoi_cells)
    asset_cells = set().union(*touches) if touches else set()
    ranked = sorted(cell_score, key=lambda i: (-cell_score[i], i))
    n_flag, n_assets = len(ranked), len(touches)
    n_sites = _count_sites(ranked, g)

    reasons: dict[str, str] = {}

    def keep(name: str, value, reason: str):
        if value is None:
            reasons[name] = reason
        return value

    hit_cells = sum(i in asset_cells for i in ranked)
    precision = keep("precision", hit_cells / n_flag if n_flag else None, "no_flagged_cells")
    incomplete = completeness == "incomplete"
    units = {"n_claims": "claims with points inside the AOI",
             "n_predicted_sites": "8-neighbour connected components of flagged cells",
             "claim_score": "finite, non-negative confidence; maximum claim score per flagged cell",
             "recall": "share of assets", "recall_at_k": "share of assets in the top k flagged cells",
             "precision": f"share of flagged {cell_size_m:g} m cells holding an asset",
             "lift": "precision / share of AOI-intersecting cells holding an asset",
             "count_ratio": "8-neighbour connected flagged-cell sites / known assets",
             "auroc": f"over all {cell_size_m:g} m cells intersecting the AOI",
             "ap": f"over all {cell_size_m:g} m cells intersecting the AOI",
             "review_effort": "top-ranked flagged cells to inspect"}
    common = dict(grader_version=GRADER_VERSION, cell_size_m=cell_size_m, edge_tol_m=edge_tol_m,
                  completeness=completeness, n_assets=n_assets,
                  n_assets_outside_aoi=n_assets_outside_aoi, n_claims=n_claims,
                  n_predicted_sites=n_sites, n_flagged_cells=n_flag, n_grid_cells=n_cells,
                  n_asset_cells=len(asset_cells), precision=precision, units=units)
    if incomplete:
        units["precision"] = f"share of flagged {cell_size_m:g} m cells holding a pool asset (lower bound)"
        for name in ("recall", "recall_at_k", "count_ratio", "auroc", "ap", "review_effort", "lift"):
            reasons[name] = INCOMPLETE
        return GradeReport(**common, n_found=None, precision_is_lower_bound=True, lift=None, recall=None,
                           recall_at_k=None, count_ratio=None, auroc=None, ap=None, review_effort=None,
                           null_reasons=reasons)

    # found-after-k: number of distinct assets touched by the top-k ranked cells
    found_curve: list[int] = []
    found = [False] * n_assets
    by_cell: dict[int, list[int]] = {}
    for j, t in enumerate(touches):
        for i in t:
            by_cell.setdefault(i, []).append(j)
    n_found = 0
    for i in ranked:
        for j in by_cell.get(i, ()):
            if not found[j]:
                found[j], n_found = True, n_found + 1
        found_curve.append(n_found)

    def found_at(k: int) -> int:
        return found_curve[min(k, n_flag) - 1] if k > 0 and n_flag else 0

    has_assets = n_assets > 0
    recall = keep("recall", n_found / n_assets if has_assets else None, "no_assets")
    recall_at_k = keep("recall_at_k", {k: found_at(k) / n_assets for k in ks} if has_assets else None,
                       "no_assets")
    count_ratio = keep("count_ratio", n_sites / n_assets if has_assets else None, "no_assets")
    effort = None
    if has_assets:
        effort = {name: next((k + 1 for k, f in enumerate(found_curve) if f >= share * n_assets - _EPS), None)
                  for name, share in EFFORT_SHARES.items()}
    keep("review_effort", effort, "no_assets")
    base_rate = len(asset_cells) / n_cells
    lift = keep("lift", precision / base_rate if precision is not None and base_rate > 0 else None,
                "no_flagged_cells" if precision is None else "no_asset_cells")
    ordered_aoi_cells = sorted(aoi_cells)
    scores = np.array([cell_score.get(i, 0.0) for i in ordered_aoi_cells])
    labels = np.array([i in asset_cells for i in ordered_aoi_cells], dtype=bool)
    au = keep("auroc", auroc(scores, labels), "single_class")
    ap = keep("ap", average_precision(scores, labels), "no_asset_cells")
    return GradeReport(**common, n_found=n_found, precision_is_lower_bound=False, lift=lift, recall=recall,
                       recall_at_k=recall_at_k, count_ratio=count_ratio, auroc=au, ap=ap,
                       review_effort=effort, null_reasons=reasons)


_SCALARS = ("recall", "precision", "lift", "count_ratio", "auroc", "ap")


def transfer_gap(home: GradeReport, away: GradeReport) -> dict[str, float]:
    """Home minus away for every metric both reports carry (recall@k as ``recall@<k>``)."""
    out = {m: getattr(home, m) - getattr(away, m) for m in _SCALARS
           if getattr(home, m) is not None and getattr(away, m) is not None}
    if home.recall_at_k is not None and away.recall_at_k is not None:
        out |= {f"recall@{k}": home.recall_at_k[k] - away.recall_at_k[k]
                for k in sorted(home.recall_at_k.keys() & away.recall_at_k.keys())}
    return out
