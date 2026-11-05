"""Opt-in anonymous read of the real Nagoya LGND April 2024 partition."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.live


def test_live_real_read_reports_real_access_and_bytes(tmp_path) -> None:
    from treehouse.providers.spend import SpendLedger, repo_ledger_path
    from treehouse.tools.sources.clay_lgnd_real import RealClayLgndSource

    # Use the same mandatory guard as other live steps; never create a missing ledger.
    path = repo_ledger_path()
    assert path.is_file() and path.stat().st_size > 0, "live read needs the existing project spend ledger"
    ledger = SpendLedger(path)
    status = ledger.status()
    assert status.initialized and status.spent_usd + status.reserved_usd <= 350, "spend alarm reached"
    index = RealClayLgndSource(cache_dir=tmp_path / "lgnd").index((136.82, 35.05, 136.92, 35.12), 1280, 2024)
    provenance = index.describe()
    assert provenance["access"] == "real"
    assert 0 < provenance["bytes_read"] <= 64 * 1024 * 1024
    assert index.emb.shape[1] == 256
    assert provenance["months"] == ["2024-04"]
    assert provenance["scene_ids"]
    assert provenance["object_uris"]
    assert all("geohash=xn/year=2024/month=04/" in uri for uri in provenance["object_uris"])
