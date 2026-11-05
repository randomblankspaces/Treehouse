"""Row placement and date validation independent of the optional Parquet decoder."""

import io
import json
import struct
import sys
from datetime import UTC, datetime
from types import ModuleType, SimpleNamespace

import pytest


@pytest.mark.parametrize("bbox, date, expected_cell", [
    ((-0.005, 0.0, 0.01, 0.015), datetime(2024, 4, 15, tzinfo=UTC), "r000c001"),
    ((0.01, 0.0, 0.025, 0.015), datetime(2024, 4, 15, tzinfo=UTC), "r000c000"),
    ((0.0, 0.0, 0.04, 0.03), None, None),
])
def test_real_source_places_footprint_centres_and_rejects_null_dates(tmp_path, monkeypatch, bbox, date, expected_cell):
    from treehouse.tools.sources import clay_lgnd_real as real

    # Stub only decoding; exercise the real reader, row validation and grid pooling.
    pa, pq = ModuleType("pyarrow"), ModuleType("pyarrow.parquet")
    pa.BufferReader = io.BytesIO
    pa.parquet = pq
    row = {"bbox": {"xmin": 0.0, "ymin": 0.0, "xmax": 0.014, "ymax": 0.01},
           "datetime": date, "embedding": [1.0] + [0.0] * 255, "stac_item_id": "S2-test"}
    geo = {"primary_column": "geometry", "columns": {"geometry": {"encoding": "WKB"}}}
    metadata = SimpleNamespace(metadata={b"geo": json.dumps(geo).encode()})
    pq.read_metadata = lambda reader: metadata
    pq.ParquetFile = lambda *a, **kw: SimpleNamespace(
        schema_arrow=SimpleNamespace(names=["bbox", "embedding", "stac_item_id", "datetime", "geometry"]),
        read_row_group=lambda *a, **kw: SimpleNamespace(to_pylist=lambda: [row]))
    monkeypatch.setitem(sys.modules, "pyarrow", pa)
    monkeypatch.setitem(sys.modules, "pyarrow.parquet", pq)
    monkeypatch.setattr(real, "_intersecting_groups", lambda *a: [0])
    path = tmp_path / "stub-decoder.parquet"
    path.write_bytes(b"PAR1" + struct.pack("<I", 0) + b"PAR1")
    source = real.RealClayLgndSource(path)
    if date is None:
        with pytest.raises(ValueError, match="datetime"):
            source.index(bbox, 1280, 2024)
    else:
        assert list(source.index(bbox, 1280, 2024).cell_ids) == [expected_cell]
