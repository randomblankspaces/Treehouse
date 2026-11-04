"""Independent regressions: reference examples do not become held-out negatives."""
import json

from test_investigation_acceptance import ScriptProvider, claim, reference


def _evaluate(context, run_id, actions, ref):
    store, card, config, execute, evaluate, _ = context
    execute(store, card, config, ScriptProvider(actions), run_id=run_id)
    return evaluate(store, run_id, reference=ref)


def test_reference_example_excluded_from_heldout_precision_and_calibration(context, tmp_path):
    store, _, _, _, _, export = context
    ref = reference()
    true_positive = claim("heldout", .002, .002)
    example = claim("example", .004, .004)
    alone = _evaluate(context, "holdout-alone", true_positive, ref)
    augmented = _evaluate(context, "with-example", true_positive + example, ref)
    a, b = alone["output"]["numbers"], augmented["output"]["numbers"]
    for metric in ("catalog_tp", "catalog_fp", "catalog_fn", "catalog_precision", "catalog_recall"):
        assert b[metric]["value"] == a[metric]["value"]
        assert b[metric]["n"] == a[metric]["n"]
    before = alone["confidence"]["numbers"]["brier"]
    after = augmented["confidence"]["numbers"]["brier"]
    assert after["value"] == before["value"] and after["n"] == before["n"]
    excluded = b["reference_examples_excluded"]
    assert excluded["value"] == 1
    assert "reference" in json.dumps({"metric": excluded, "output": augmented["output"]}).lower()
    paths = export(store, "with-example", tmp_path / "export")
    geo = json.loads(open(paths["geojson"]).read())
    assert sorted(feature["geometry"]["coordinates"] for feature in geo["features"]) == [
        [.002, .002], [.004, .004]]


def test_prediction_near_both_reference_and_holdout_is_not_arbitrarily_graded(context):
    ref = reference()
    ref["features"].append({"id": "ambiguous-example", "lon": .002, "lat": .002,
                            "cls": "road_bridge", "split": "reference"})
    try:
        report = _evaluate(context, "ambiguous", claim("ambiguous", .002, .002), ref)
    except (ValueError, RuntimeError):
        return  # Fail closed: overlapping training/holdout spatial neighborhoods.
    for metric in ("catalog_tp", "catalog_fp", "catalog_precision"):
        result = report["output"]["numbers"][metric]
        assert result["tier"] == "ABSTAINED" and result["value"] is None
    assert "ambig" in json.dumps(report).lower() or "overlap" in json.dumps(report).lower()
