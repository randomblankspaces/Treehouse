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


def _on_segment(p, a, b) -> bool:
    return _orient(a, b, p) == 0 and min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and \
        min(a[1], b[1]) <= p[1] <= max(a[1], b[1])


def point_in_ring(p, ring: Ring) -> bool:
    """True if ``p`` is inside the closed ring or on its boundary (even-odd rule)."""
    inside = False
    for i in range(len(ring) - 1):
        a, b = ring[i], ring[i + 1]
        if _on_segment(p, a, b):
            return True
        if (a[1] > p[1]) != (b[1] > p[1]):
            x = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if p[0] < x:
                inside = not inside
    return inside


def point_in_polygon(p, poly: Sequence[Ring]) -> bool:
    """Inside the outer ring (boundary included) and not strictly inside any hole."""
    if not poly or not point_in_ring(p, poly[0]):
        return False
    return not any(point_in_ring(p, h) and not any(_on_segment(p, h[i], h[i + 1]) for i in range(len(h) - 1))
                   for h in poly[1:])


def rings_intersect(r1: Ring, r2: Ring) -> bool:
    """True if two closed rings' areas or boundaries touch (planar lon/lat)."""
    if any(point_in_ring(p, r2) for p in r1) or any(point_in_ring(p, r1) for p in r2):
        return True
    return any(_segments_cross(r1[i], r1[i + 1], r2[j], r2[j + 1])
               for i in range(len(r1) - 1) for j in range(len(r2) - 1))


def polygons_intersect(a: Sequence[Sequence[Ring]], b: Sequence[Sequence[Ring]]) -> bool:
    """Any polygon of ``a`` meets any polygon of ``b`` (outer rings only; holes are ignored)."""
    return any(rings_intersect(pa[0], pb[0]) for pa in a for pb in b if pa and pb)


def bbox_ring(b: Sequence[float]) -> list[tuple[float, float]]:
    x0, y0, x1, y1 = b
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
