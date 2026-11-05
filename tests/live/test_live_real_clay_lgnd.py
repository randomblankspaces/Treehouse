"""Optional real LGND GeoParquet access check; never runs in the default offline suite."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.live


def test_live_real_read_reports_real_access_and_bytes() -> None:
    source = os.environ.get("TREEHOUSE_LGND_GEOPARQUET")
    if not source:
        pytest.skip("set TREEHOUSE_LGND_GEOPARQUET to an authorized GeoParquet path")

    from treehouse.tools.sources.clay_lgnd_real import RealClayLgndSource

    index = RealClayLgndSource(source).index((136.82, 35.05, 136.92, 35.12), 1280, 2024)
    provenance = index.describe()
    assert provenance["access"] == "real"
    assert provenance["bytes_read"] > 0
