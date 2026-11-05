"""Real GeoParquet reads, exercised offline with a tiny local file."""

from __future__ import annotations

import pytest


def test_real_source_reads_only_cells_inside_aoi_and_reports_provenance(tmp_path):
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    import numpy as np

    from treehouse.tools.sources.clay_lgnd_real import RealClayLgndSource

    path = tmp_path / "tiny.parquet"
    pq.write_table(
        pa.table(
            {
                "lon": [0.25, 0.75, 1.25],
                "lat": [0.25, 0.75, 0.25],
                "embedding": [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]],
            }
        ),
        path,
    )

    index = RealClayLgndSource(path).index((0.0, 0.0, 1.0, 1.0), 1280, 2024)

    assert len(index.cell_ids) == 2
    assert np.all((index.lon >= 0.0) & (index.lon < 1.0))
    assert np.all((index.lat >= 0.0) & (index.lat < 1.0))
    provenance = index.describe()
    assert provenance["access"] == "real"
    assert provenance["licence"]
    assert provenance["bytes_read"] > 0


def test_real_source_rejects_parquet_over_byte_cap(tmp_path):
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")

    from treehouse.tools.sources.clay_lgnd_real import RealClayLgndSource

    path = tmp_path / "over-cap.parquet"
    pq.write_table(pa.table({"lon": [0.5], "lat": [0.5], "embedding": [[1.0, 0.0]]}), path)

    with pytest.raises(ValueError, match="byte cap"):
        RealClayLgndSource(path, max_bytes=1).index((0.0, 0.0, 1.0, 1.0), 1280, 2024)
