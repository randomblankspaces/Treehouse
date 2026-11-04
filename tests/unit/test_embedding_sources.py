"""Embedding sources (task 2): one protocol, AEF + LGND Clay, committed fixtures, provenance on every index."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from treehouse.cards import LICENSE_RANK
from treehouse.tools.clay import ClayIndex, load_embeddings
from treehouse.tools.sources.aef import AefSource
from treehouse.tools.sources.clay_lgnd import ClayLgndSource
from treehouse.tools.sources.embedding_source import CellIndex, cell_deg_for, pool_to_grid

ROOT = Path(__file__).resolve().parents[2]
NAGOYA = (136.82, 35.05, 136.92, 35.12)


def _builder():
    spec = importlib.util.spec_from_file_location("mef", ROOT / "scripts" / "make_embedding_fixtures.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("src,cell", [(AefSource.for_aoi("nagoya"), 160), (ClayLgndSource.for_aoi("nagoya"), 1280)])
def test_sources_return_wellformed_cellindex_with_provenance(src, cell):
    idx = src.index(NAGOYA, cell, 2024)
    assert isinstance(idx, CellIndex) and idx.cell_size_m == cell
    assert idx.emb.dtype == np.float32 and idx.emb.shape[0] > 0
    assert idx.licence in LICENSE_RANK
    d = idx.describe()
    for k in ("source", "date_range", "resolution_m", "cell_size_m", "licence", "cost_usd", "access"):
        assert k in d, k
    assert d["access"] == "fixture" and d["real_access_path"]
    assert np.allclose(np.linalg.norm(idx.emb, axis=1), 1, atol=1e-3)


def test_lgnd_cells_are_coarse_and_only_native_sizes():
    src = ClayLgndSource.for_aoi("nagoya")
    assert src.index(NAGOYA, 1280, 2024).cell_size_m >= 1280
    assert src.index(NAGOYA, 2560, 2024).cell_size_m == 2560
    with pytest.raises(ValueError):
        src.index(NAGOYA, 160, 2024)


def test_aef_pools_to_coarser_cells_and_refuses_finer_than_fixture():
    src = AefSource.for_aoi("nagoya")
    n160 = len(src.index(NAGOYA, 160, 2024).cell_ids)
    n320 = len(src.index(NAGOYA, 320, 2024).cell_ids)
    assert n320 < n160
    with pytest.raises(ValueError):
        src.index(NAGOYA, 10, 2024)


def test_pooling_is_the_mean_of_members_on_a_10m_array():
    # 4 x 4 pixels at 10 m inside one 40 m cell + one pixel in the next cell
    d10 = cell_deg_for(10)
    lon = np.array([(i + 0.5) * d10 for i in range(4) for _ in range(4)] + [5.5 * d10])
    lat = np.array([(j + 0.5) * d10 for _ in range(4) for j in range(4)] + [0.5 * d10])
    rng = np.random.default_rng(0)
    vec = rng.standard_normal((17, 3)).astype(np.float32)
    ids, clon, clat, unit, grid = pool_to_grid(lon, lat, vec, (0.0, 0.0, 0.01, 0.01), 40)
    assert len(ids) == 2
    want = vec[:16].mean(axis=0)
    want /= np.linalg.norm(want)
    first = int(np.argmin(clon))
    assert np.allclose(unit[first], want, atol=1e-6)


def test_fixture_loads_through_the_existing_clay_server_path():
    emb = load_embeddings(ROOT / "fixtures" / "embeddings" / "aef-nagoya.npz")
    idx = ClayIndex(emb, source_id="aef-10m-annual")
    res = idx.search(NAGOYA, 136.85, 35.08, None, 5)
    assert len(res.cells) == 5 and res.coverage.cell_m == 160


def test_cellindex_round_trips_to_npz_layout(tmp_path):
    from treehouse.synth.fixtures import npz_bytes

    idx = AefSource.for_aoi("nagoya").index(NAGOYA, 320, 2024)
    p = tmp_path / "x.npz"
    p.write_bytes(npz_bytes(idx.to_npz_arrays()))
    emb = load_embeddings(p)
    assert len(emb.ids) == len(idx.cell_ids)
    assert ClayIndex(emb, source_id="x").coverage(NAGOYA).cell_m == 320


def test_builder_is_byte_identical(tmp_path):
    mod = _builder()
    for p in mod.write_all(tmp_path):
        assert p.read_bytes() == (ROOT / "fixtures" / "embeddings" / p.name).read_bytes(), p.name


def test_warehouse_cells_carry_signal():
    """Synthetic signal: cells holding a reference warehouse are more alike than random pairs."""
    idx = AefSource.for_aoi("nagoya").index(NAGOYA, 160, 2024)
    meta_near = idx.emb[np.argsort(-(idx.emb @ idx.emb.mean(axis=0)))[:20]]
    assert float((meta_near @ meta_near.T).mean()) > float((idx.emb[:20] @ idx.emb[:20].T).mean())
