"""Nepal Vantor STAC fixture (§5.2): golden scene list over the card AOI; the builder is offline and
reproduces the committed fixture; metadata only, CC-BY-NC-4.0 attribution."""

from __future__ import annotations

import importlib.util
import json

from gwrig import card

from treehouse.geo.geom import bbox_of
from treehouse.paths import fixtures_root, repo_root
from treehouse.tools.stac import StacCatalog, load_items

FIXTURE = fixtures_root() / "stac" / "vantor-nepal-aug-2026"
GOLDEN_SCENES = [
    "10300100C86CED00", "10500100364E8400", "B040001100881410", "B040001100881610", "B040001100882F10",
    "B040001100881710", "B030001100CF1110", "B030001100CF1310", "B030001100CF1610", "B110001101165110",
    "B130001101153A10", "B1400011010A2910", "B1400011010A2E10", "B120001101226410", "B0500011006DC010",
    "B1300011011E5610", "B1300011011E5810", "B120001101250A10", "B1300011011F4F10", "B030001100EF5910",
    "B14000110116A310", "B0400011009ECD10", "B1200011012B2A10",
]


def _catalog():
    c = card("nepal-bhote-koshi-bridges")
    src = c.data_allowlist[0]
    return c, StacCatalog(load_items(repo_root() / src.fixture_path), pinned=src.item_ids, aoi=c.aoi, as_of=c.as_of)


def test_golden_nepal_scene_list():
    c, cat = _catalog()
    r = cat.search(bbox_of(c.aoi.polygons()), str(c.time_window[0]), str(c.time_window[1]))
    assert [s.scene_id for s in r.scenes] == GOLDEN_SCENES
    assert r.dropped_after_as_of == 0
    by_id = {s.scene_id: s for s in r.scenes}
    assert by_id["B1300011011E5610"].aoi_coverage_fraction == 1.0 and by_id["B1300011011E5610"].cloud_pct == 18
    assert by_id["B1300011011E5610"].pan_gsd_m == 0.35 and by_id["B1300011011E5610"].phase == "post"
    assert all(s.license == "CC-BY-NC-4.0" for s in r.scenes)


def test_fixture_has_33_items_etags_and_licence():
    items = load_items(FIXTURE)
    assert len(items) == 33
    etags = json.loads((FIXTURE / "etags.json").read_text())
    assert etags == {i: it.etag for i, it in items.items()}
    assert "CC-BY-NC-4.0" in (FIXTURE / "LICENSE-DATA").read_text()
    for f in ("event.json", "collection.json"):
        assert (FIXTURE / f).is_file()
    c = card("nepal-bhote-koshi-bridges").data_allowlist[0]
    assert set(c.item_ids) <= set(items) and all(c.etags[i] == items[i].etag for i in c.item_ids)


def test_builder_from_json_reproduces_committed_fixture(tmp_path):
    spec = importlib.util.spec_from_file_location("bvf", repo_root() / "scripts" / "build_vantor_fixture.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    meta = json.loads((repo_root() / "wip" / "fixtures" / "nepal-flooding-aug-2026.stac.json").read_text())
    mod.convert(meta, tmp_path)
    got = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    want = sorted(p.relative_to(FIXTURE).as_posix() for p in FIXTURE.rglob("*") if p.is_file())
    assert got == want
    for rel in got:
        assert (tmp_path / rel).read_bytes() == (FIXTURE / rel).read_bytes(), rel
