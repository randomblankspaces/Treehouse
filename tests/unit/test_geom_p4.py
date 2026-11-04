"""geo/geom P4 additions: PIP with holes, boxes, haversine, ENU segment distance, coverage grid."""

from __future__ import annotations

import pytest

from treehouse.geo.geom import (
    bbox_of,
    coverage_fraction,
    haversine_m,
    point_in_polygons,
    point_segment_distance_m,
    polygons_intersect_bbox,
)

SQ = [[(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)]]
HOLE = [[(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)], [(1, 1), (3, 1), (3, 3), (1, 3), (1, 1)]]


def test_point_in_polygon_with_holes():
    assert point_in_polygons(0.5, 0.5, [HOLE]) and not point_in_polygons(2, 2, [HOLE])
    assert point_in_polygons(2, 2, [SQ]) and not point_in_polygons(5, 2, [SQ])
    assert point_in_polygons(6, 6, [SQ, [[(5, 5), (7, 5), (7, 7), (5, 7), (5, 5)]]])


def test_boxes():
    assert bbox_of([HOLE]) == (0, 0, 4, 4)
    assert polygons_intersect_bbox([SQ], (3, 3, 5, 5)) and not polygons_intersect_bbox([SQ], (5, 5, 6, 6))
    assert polygons_intersect_bbox([SQ], (1, -1, 2, 5))  # crosses, no vertex inside either
    assert polygons_intersect_bbox([SQ], (-1, -1, 9, 9))


def test_distances():
    assert haversine_m(0, 0, 0, 1) == pytest.approx(111_195, rel=1e-3)
    d = point_segment_distance_m((0.0, 0.0001), (-0.001, 0.0), (0.001, 0.0))
    assert d == pytest.approx(11.13, rel=1e-2)
    assert point_segment_distance_m((0.002, 0.0), (-0.001, 0.0), (0.001, 0.0)) == pytest.approx(111.3, rel=1e-2)


def test_coverage_fraction():
    assert coverage_fraction([SQ], [SQ]) == 1.0
    half = [[(0, 0), (2, 0), (2, 4), (0, 4), (0, 0)]]
    assert coverage_fraction([half], [SQ]) == pytest.approx(0.5)
    assert coverage_fraction([[[(9, 9), (10, 9), (10, 10), (9, 10), (9, 9)]]], [SQ]) == 0.0
