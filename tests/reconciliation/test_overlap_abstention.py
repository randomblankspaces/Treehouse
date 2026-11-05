"""Adversarial synthetic reference populations must not produce apparent heldout accuracy."""
import pytest
from helpers import claim, run_case

from treehouse.investigation import evaluate_investigation
from treehouse.store.local import LocalStore


def reference(features):
    return {"schema_version": "treehouse.reference/1", "quality": "complete",
            "source": {"dataset": "independent synthetic reference", "version": "acceptance-1",
                       "url": "https://example.invalid/reconciliation", "license": "CC0-1.0",
                       "attribution": "Constructed method test; no physical measurements"},
            "coverage": {"type": "Polygon", "coordinates": [
                [[136.82, 35.05], [136.92, 35.05], [136.92, 35.12], [136.82, 35.12], [136.82, 35.05]]]},
            "features": features}


@pytest.mark.parametrize("overlap", [False, True], ids=["no-heldout", "training-overlap"])
def test_no_valid_heldout_population_abstains_consistently(tmp_path, overlap):
    store = LocalStore(tmp_path / "store")
    run_case(store, "invalid-population", claim("positive", [136.85, 35.08]), synthetic=True)
    features = [{"id": "example", "lon": 136.85, "lat": 35.08, "cls": "warehouse", "split": "reference"}]
    if overlap:
        features.append({"id": "heldout-same-cell", "lon": 136.85, "lat": 35.08, "cls": "warehouse", "split": "holdout"})
    try:
        report = evaluate_investigation(store, "invalid-population", reference=reference(features))
    except ValueError as exc:
        assert any(word in str(exc).lower() for word in ("overlap", "held", "split", "population"))
        return
    for name in ("catalog_tp", "catalog_fp", "catalog_fn", "catalog_precision", "catalog_recall"):
        number = report["output"]["numbers"][name]
        assert number["tier"] == "ABSTAINED" and number["value"] is None and number["reasons"]
    brier = report["confidence"]["numbers"]["brier"]
    assert brier["tier"] == "ABSTAINED" and brier["value"] is None and brier["reasons"]
