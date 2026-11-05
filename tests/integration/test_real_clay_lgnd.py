"""Real-schema GeoParquet reads using generated data, never downloaded pixels."""

from __future__ import annotations

import json
import math
import struct
from datetime import UTC, datetime

import pytest


def _geoparquet(path):
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    boxes = [(0.0, 0.0, 0.01, 0.01), (0.02, 0.01, 0.03, 0.02), (10.0, 10.0, 10.01, 10.01)]
    geometry = []
    for x0, y0, x1, y1 in boxes:
        points = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
        geometry.append(struct.pack("<BIII", 1, 3, 1, 5) + b"".join(struct.pack("<dd", *p) for p in points))
    geo = {"version": "1.1.0", "primary_column": "geometry", "columns": {"geometry": {
        "encoding": "WKB", "geometry_types": ["Polygon"],
        "covering": {"bbox": {k: ["bbox", k] for k in ("xmin", "ymin", "xmax", "ymax")}}}}}
    table = pa.table({
        "chips_id": ["chip-0", "chip-1", "chip-2"], "cell_id": ["cell-0", "cell-1", "cell-2"],
        "rasters_id": ["raster"] * 3, "stac_item_id": ["S2-test"] * 3,
        "collection": ["sentinel-2-l2a"] * 3, "datetime": [datetime(2024, 4, 15, tzinfo=UTC)] * 3,
        "embedding": pa.array([[float(i == j) for i in range(256)] for j in range(3)],
                              type=pa.list_(pa.float32())),
        "bbox": [{"xmin": b[0], "ymin": b[1], "xmax": b[2], "ymax": b[3]} for b in boxes],
        "geometry": geometry,
    }).replace_schema_metadata({b"geo": json.dumps(geo).encode()})
    pq.write_table(table, path, row_group_size=1)
    return pq


def test_real_source_filters_row_groups_and_reports_grid_and_provenance(tmp_path, monkeypatch):
    import numpy as np

    from treehouse.tools.sources.embedding_source import cell_deg_for

    path = tmp_path / "tiny.parquet"
    pq = _geoparquet(path)
    from treehouse.tools.sources.clay_lgnd_real import RealClayLgndSource

    groups = []
    original = pq.ParquetFile.read_row_group

    def read_group(self, i, *args, **kwargs):
        groups.append(i)
        return original(self, i, *args, **kwargs)

    monkeypatch.setattr(pq.ParquetFile, "read_row_group", read_group)
    index = RealClayLgndSource(path, cache_dir=tmp_path / "cache").index((0.0, 0.0, 0.04, 0.03), 1280, 2024)
    assert groups == [0, 1]
    assert index.emb.shape == (2, 256)
    assert index.emb.dtype == np.float32
    np.testing.assert_allclose(np.linalg.norm(index.emb, axis=1), 1)
    assert (index.nx, index.ny) == (math.ceil(0.04 / cell_deg_for(1280)), math.ceil(0.03 / cell_deg_for(1280)))
    assert (index.lon0, index.lat0, index.crs) == (0.0, 0.0, "EPSG:4326")
    assert index.cell_deg == cell_deg_for(1280)
    assert list(index.cell_ids) == ["r000c000", "r001c002"]
    provenance = index.describe()
    assert provenance["access"] == "real"
    assert provenance["object_uris"] == [path.resolve().as_uri()]
    assert provenance["objects"][0]["etag"] is None
    assert provenance["objects"][0]["version_id"] is None
    assert provenance["scene_ids"] == ["S2-test"]
    assert provenance["months"] == ["2024-04"]
    assert provenance["date_range"] == ["2024-04-15", "2024-04-15"]
    assert provenance["licence"] == "CC-BY-4.0"
    assert provenance["attribution"] == "LGND / Clay"
    assert provenance["synthetic"] is False  # generated fixture tests the real-access path
    assert 0 < provenance["bytes_read"] <= 64 * 1024 * 1024


def test_real_source_rejects_parquet_over_byte_cap(tmp_path):
    path = tmp_path / "over-cap.parquet"
    _geoparquet(path)
    from treehouse.tools.sources.clay_lgnd_real import RealClayLgndSource

    with pytest.raises(ValueError, match="byte cap"):
        RealClayLgndSource(path, max_bytes=1).index((0.0, 0.0, 0.04, 0.03), 1280, 2024)


def test_real_source_filters_rows_within_intersecting_group(tmp_path):
    path = tmp_path / "tiny.parquet"
    pq = _geoparquet(path)
    table = pq.read_table(path)
    pq.write_table(table, path, row_group_size=3)
    from treehouse.tools.sources.clay_lgnd_real import RealClayLgndSource

    index = RealClayLgndSource(path).index((0.0, 0.0, 0.015, 0.015), 1280, 2024)
    assert index.emb.shape == (1, 256)


def test_real_source_has_clear_no_coverage_error(tmp_path):
    path = tmp_path / "tiny.parquet"
    _geoparquet(path)
    from treehouse.tools.sources.clay_lgnd_real import RealClayLgndSource

    with pytest.raises(ValueError, match="no LGND cells"):
        RealClayLgndSource(path).index((20.0, 20.0, 20.1, 20.1), 1280, 2024)


@pytest.mark.parametrize("invalid", ["dimensions", "statistics", "columns"])
def test_real_source_rejects_invalid_schema_and_vectors(tmp_path, invalid):
    pa = pytest.importorskip("pyarrow")
    path = tmp_path / "invalid.parquet"
    pq = _geoparquet(path)
    table = pq.read_table(path)
    if invalid == "dimensions":
        table = table.set_column(table.schema.get_field_index("embedding"), "embedding", pa.array([[1.0]] * 3))
    if invalid == "columns":
        table = table.drop(["stac_item_id"])
    pq.write_table(table, path, write_statistics=invalid != "statistics")
    from treehouse.tools.sources.clay_lgnd_real import RealClayLgndSource

    with pytest.raises(ValueError, match={"dimensions": "256", "statistics": "statistics", "columns": "columns"}[invalid]):
        RealClayLgndSource(path).index((0.0, 0.0, 0.04, 0.03), 1280, 2024)


@pytest.mark.parametrize("bbox, expected_cell", [((-0.005, 0.0, 0.01, 0.015), "r000c001"),
                                                ((0.01, 0.0, 0.025, 0.015), "r000c000")])
def test_clipped_footprint_keeps_its_centre_assignment(tmp_path, bbox, expected_cell):
    pa = pytest.importorskip("pyarrow")
    path = tmp_path / "edge.parquet"
    pq = _geoparquet(path)
    table = pq.read_table(path).slice(0, 1)
    table = table.set_column(table.schema.get_field_index("bbox"), "bbox", pa.array([
        {"xmin": 0.0, "ymin": 0.0, "xmax": 0.014, "ymax": 0.01}]))
    pq.write_table(table, path)
    from treehouse.tools.sources.clay_lgnd_real import RealClayLgndSource

    index = RealClayLgndSource(path).index(bbox, 1280, 2024)
    assert list(index.cell_ids) == [expected_cell]


def test_real_source_rejects_null_datetime_clearly(tmp_path):
    pa = pytest.importorskip("pyarrow")
    path = tmp_path / "null-date.parquet"
    pq = _geoparquet(path)
    table = pq.read_table(path)
    field = table.schema.field("datetime")
    table = table.set_column(table.schema.get_field_index("datetime"), field, pa.array([None] * 3, type=field.type))
    pq.write_table(table, path)
    from treehouse.tools.sources.clay_lgnd_real import RealClayLgndSource

    with pytest.raises(ValueError, match="datetime"):
        RealClayLgndSource(path).index((0.0, 0.0, 0.04, 0.03), 1280, 2024)
