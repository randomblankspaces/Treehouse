"""Synthetic Clay embeddings (§5.1): recall of river cells >= 0.9 and the coverage report."""

from __future__ import annotations

from treehouse.paths import fixtures_root
from treehouse.synth import world
from treehouse.tools.clay import ClayIndex, load_embeddings

NPZ = fixtures_root() / "embeddings" / "synth-crossings-v1.npz"


def test_river_recall_and_coverage_report():
    emb = load_embeddings(NPZ)
    river = set(emb.meta["river_cells"])
    idx = ClayIndex(emb, source_id="synth-embeddings")
    x = world.crossings()[20]
    r = idx.search(world.AOI, x.lon, x.lat, None, k=len(river))
    recall = len({c.cell_id for c in r.cells} & river) / len(river)
    assert recall >= 0.9
    cov = r.coverage
    assert cov.cell_m == 64 and cov.synthetic is True and cov.predates_event is True
    assert cov.aoi_cells_expected == 19 * 19 == cov.aoi_cells_present
    assert "1280" in cov.source and cov.smallest_resolvable_m == 64
    assert emb.vec.shape == (361, 64)


def test_column_map_and_query_by_cell_id(tmp_path):
    import numpy as np

    with np.load(NPZ) as z:
        np.savez(tmp_path / "renamed.npz", id=z["cell_id"], x=z["lon"], y=z["lat"], v=z["emb"], m=z["meta"])
    emb = load_embeddings(tmp_path / "renamed.npz", {"id": "id", "lon": "x", "lat": "y", "vec": "v", "meta": "m"})
    r = ClayIndex(emb, source_id="s").search(world.AOI, None, None, "r09c09", k=3)
    assert r.cells[0].cell_id == "r09c09" and r.cells[0].similarity > 0.999
    assert ClayIndex(emb, source_id="s").search(world.AOI, None, None, None, k=3).code == "bad_args"
