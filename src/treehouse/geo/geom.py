"""Planar geometry on lon/lat rings. Started in P1 for card validation; P4 extends it."""

from __future__ import annotations

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
