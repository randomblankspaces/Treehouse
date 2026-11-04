"""Planar geometry on lon/lat rings. Started in P1 for card validation; P4 extends it."""

from __future__ import annotations

import math
from collections.abc import Sequence

Ring = Sequence[Sequence[float]]


def ring_area(ring: Ring) -> float:
    """Signed shoelace area in squared degrees (positive when counter-clockwise)."""
    return 0.5 * sum(ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1] for i in range(len(ring) - 1))


def _orient(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_cross(p1, p2, p3, p4) -> bool:
    d1, d2 = _orient(p3, p4, p1), _orient(p3, p4, p2)
    d3, d4 = _orient(p1, p2, p3), _orient(p1, p2, p4)
    if ((d1 > 0) != (d2 > 0)) and d1 and d2 and ((d3 > 0) != (d4 > 0)) and d3 and d4:
        return True

    def on(a, b, c):  # c collinear with a-b and inside its box
        return min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])

    return (
        (d1 == 0 and on(p3, p4, p1))
        or (d2 == 0 and on(p3, p4, p2))
        or (d3 == 0 and on(p1, p2, p3))
        or (d4 == 0 and on(p1, p2, p4))
    )


def ring_problems(ring: Ring) -> list[str]:
    out = []
    if any(not (-180 <= x <= 180 and -90 <= y <= 90) for x, y in ring):
        out.append("coordinate outside lon [-180, 180] / lat [-90, 90]")
    if ring_area(ring) == 0:
        out.append("ring has zero area")
    n = len(ring) - 1  # edges
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue  # adjacent edges share a vertex
            if _segments_cross(ring[i], ring[i + 1], ring[j], ring[j + 1]):
                out.append(f"ring self-intersects (edges {i} and {j})")
                return out
    return out


def polygon_problems(polygons: Sequence[Sequence[Ring]]) -> list[str]:
    """Problems with a list of polygons (each a list of rings, outer first). Empty means valid."""
    return [f"polygon {p} ring {r}: {msg}" for p, poly in enumerate(polygons) for r, ring in enumerate(poly)
            for msg in ring_problems(ring)]


# --- P4: point-in-polygon, boxes, distances, coverage ---------------------------------------------

EARTH_R_M = 6_371_008.8
M_PER_DEG = 111_320.0  # metres per degree of latitude (and of longitude at the equator)
Polys = Sequence[Sequence[Ring]]  # list of polygons, each a list of rings (outer first, then holes)


def point_in_ring(x: float, y: float, ring: Ring) -> bool:
    """Even-odd ray cast. Points exactly on an edge may fall either way."""
    inside = False
    for i in range(len(ring) - 1):
        (x1, y1), (x2, y2) = ring[i][:2], ring[i + 1][:2]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def point_in_polygons(x: float, y: float, polygons: Polys) -> bool:
    """Inside any polygon's outer ring and outside all of its holes."""
    return any(point_in_ring(x, y, p[0]) and not any(point_in_ring(x, y, h) for h in p[1:]) for p in polygons)


def bbox_of(polygons: Polys) -> tuple[float, float, float, float]:
    xs = [pt[0] for p in polygons for r in p for pt in r]
    ys = [pt[1] for p in polygons for r in p for pt in r]
    return (min(xs), min(ys), max(xs), max(ys))


def bbox_contains(b: Sequence[float], x: float, y: float) -> bool:
    return b[0] <= x <= b[2] and b[1] <= y <= b[3]


def bbox_intersects(a: Sequence[float], b: Sequence[float]) -> bool:
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def bbox_ring(b: Sequence[float]) -> list[tuple[float, float]]:
    return [(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3]), (b[0], b[1])]


def polygons_intersect_bbox(polygons: Polys, b: Sequence[float]) -> bool:
    if not bbox_intersects(bbox_of(polygons), b):
        return False
    if any(bbox_contains(b, *pt[:2]) for p in polygons for pt in p[0]):
        return True
    box = bbox_ring(b)
    if any(point_in_polygons(x, y, polygons) for x, y in box[:4]):
        return True
    return any(_segments_cross(r[i], r[i + 1], box[j], box[j + 1])
               for p in polygons for r in p for i in range(len(r) - 1) for j in range(4))


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R_M * math.asin(math.sqrt(a))


def to_enu(lon: float, lat: float, lon0: float, lat0: float) -> tuple[float, float]:
    """Local east/north metres about (lon0, lat0); fine at window and match-tolerance scales."""
    return ((lon - lon0) * M_PER_DEG * math.cos(math.radians(lat0)), (lat - lat0) * M_PER_DEG)


def point_segment_distance_m(p: Sequence[float], a: Sequence[float], b: Sequence[float]) -> float:
    """Distance in metres from lon/lat point ``p`` to segment ``a``-``b`` in a local ENU frame at ``p``."""
    ax, ay = to_enu(a[0], a[1], p[0], p[1])
    bx, by = to_enu(b[0], b[1], p[0], p[1])
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / L2))
    return math.hypot(ax + t * dx, ay + t * dy)


def m_to_deg(side_m: float, lat: float) -> tuple[float, float]:
    """(degrees of longitude, degrees of latitude) spanned by ``side_m`` metres at ``lat``."""
    return side_m / (M_PER_DEG * math.cos(math.radians(lat))), side_m / M_PER_DEG


def coverage_fraction(cover: Polys, region: Polys, n: int = 30) -> float:
    """Share of an n x n grid of cell centres over ``region``'s bbox (those inside ``region``) that
    also fall inside ``cover``. 0.0 when no grid point lies in the region."""
    x0, y0, x1, y1 = bbox_of(region)
    inside = hits = 0
    for i in range(n):
        for j in range(n):
            x, y = x0 + (i + 0.5) * (x1 - x0) / n, y0 + (j + 0.5) * (y1 - y0) / n
            if point_in_polygons(x, y, region):
                inside += 1
                hits += point_in_polygons(x, y, cover)
    return hits / inside if inside else 0.0
