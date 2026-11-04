"""Asset-class registry (Req 1.4): class-agnostic definitions load, cover Table 8, and drive RV1/RV3 sizing."""

from __future__ import annotations

import pytest

from treehouse.assets import AssetClasses, UnknownAssetClass

TABLE8 = {"warehouse", "oil_fuel_tank", "bridge", "substation", "ground_solar", "wind_turbine"}


@pytest.fixture(scope="module")
def reg() -> AssetClasses:
    return AssetClasses.load()


def test_registry_loads_and_covers_table8(reg):
    assert TABLE8.issubset(set(reg.classes))
    assert reg.cell_size_default_m == 160


def test_every_class_has_positive_negative_sizes_and_reference(reg):
    for name, c in reg.classes.items():
        assert c.positive and c.negative, name
        assert 0 < c.min_size_m <= c.typical_size_m, name
        assert c.references and all(r.completeness in ("complete", "incomplete", "synthetic")
                                    for r in c.references), name


def test_warehouse_matches_table8_anchor(reg):
    w = reg.get("warehouse")
    assert w.min_area_m2 == 1600 and w.cell_size_m == 160
    assert "factories" in w.negative and "markets" in w.negative
    assert reg.resolvable_at("warehouse", 10)   # Sentinel-2/AEF 10 m resolves warehouses
    assert reg.resolvable_at("warehouse", 0.5)   # GSI aerial


def test_cell_fits_flags_coarse_cells_for_warehouses(reg):
    # RV1: 160 m cells localise ~80 m warehouses; the 1.28 km LGND index does not.
    assert reg.cell_fits("warehouse", 160)
    assert not reg.cell_fits("warehouse", 1280)
    assert not reg.cell_fits("warehouse", 2560)


def test_unknown_class_raises(reg):
    with pytest.raises(UnknownAssetClass):
        reg.get("spaceport")


def test_bad_registry_rejected(tmp_path):
    import yaml

    bad = {
        "schema_version": "treehouse.asset-classes/1",
        "classes": {
            "x": {"label": "X", "positive": "p", "negative": ["n"], "min_size_m": 100,
                  "typical_size_m": 10, "suitable_gsd_m": [10], "cell_size_m": 160,
                  "references": [{"id": "r", "name": "R", "completeness": "complete", "license": "CC-BY-4.0"}]},
        },
    }
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump(bad))
    with pytest.raises(ValueError, match="min_size_m <= typical_size_m"):
        AssetClasses.load(p)


def test_reference_licences_are_known(reg):
    from treehouse.cards import LICENSE_RANK

    for c in reg.classes.values():
        for r in c.references:
            assert r.license in LICENSE_RANK, (c.label, r.license)
