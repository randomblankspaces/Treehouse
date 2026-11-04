"""Black-box investigation contract. All reference objects below are synthetic, not field labels."""
import json
import sqlite3
from pathlib import Path

import pytest

from treehouse.cards import load_card
from treehouse.paths import repo_root
from treehouse.schemas.model_io import Message, ModelResponse, Text, ToolUse, Usage
from treehouse.service import demo_config
from treehouse.store.local import LocalStore

ROOT = repo_root()


class ScriptProvider:
    provider_name = "independent-acceptance"

    def __init__(self, actions):
        self.actions = iter(actions)
        self.requests = []

    async def complete(self, req, *, role, trial_index, turn):
        self.requests.append(req.model_dump(mode="json"))
        action = next(self.actions, None)
        if action is None:
            content, reason = [Text(text="Finished")], "end_turn"
        else:
            tool, call_id, args = action
            content, reason = [ToolUse(id=call_id, name=tool, input=args)], "tool_use"
        return ModelResponse(message=Message(role="assistant", content=content), stop_reason=reason,
                             usage=Usage(input_tokens=1, output_tokens=1), latency_ms=1,
                             response_model_id="independent-test")


def planned(action_id, tool, params, *, refs=None):
    return ("record_decision", "decision-call-" + action_id,
            {"action_id": action_id, "tool": tool, "parameters": params,
             "rationale": "Inspect or record this location", "alternatives": [
                 {"option": "stop", "reason": "would leave the location unexamined"}],
             "confidence": 0.7, "evidence_refs": refs or []})


def claim(call_id, lon, lat, cls="road_bridge", status="present", confidence=0.91):
    params = {"step_id": "inventory", "lon": lon, "lat": lat, "cls": cls,
              "status": status, "confidence": confidence, "reason": "synthetic test observation",
              "evidence_refs": []}
    return [planned(call_id, "record_claim", params), ("record_claim", call_id, params)]


@pytest.fixture
def context(tmp_path):
    from treehouse.investigation import evaluate_investigation, export_database, run_investigation
    card = load_card(ROOT / "tasks/synth-crossings-v1.yaml")
    card = card.model_copy(update={"tools_allowed": card.tools_allowed + ["record_decision", "classify_window"]})
    config = demo_config({"policy": "good", "run_id": "independent"}, card, mode="fake")
    config = config.model_copy(update={"max_turns": 50})
    return LocalStore(tmp_path / "store"), card, config, run_investigation, evaluate_investigation, export_database


def reference(quality="complete"):
    return {"schema_version": "treehouse.reference/1",
            "source": {"dataset": "synthetic acceptance", "version": "1", "url": "https://example.invalid/fixture",
                       "license": "LicenseRef-synthetic", "attribution": "Independent synthetic test"},
            "quality": quality,
            "coverage": {"type": "Polygon", "coordinates": [[[0, 0], [.0108, 0], [.0108, .0108], [0, .0108], [0, 0]]]},
            "features": [{"id": "hidden-a", "lon": .002, "lat": .002, "cls": "road_bridge", "split": "holdout"},
                         {"id": "hidden-b", "lon": .008, "lat": .008, "cls": "footbridge", "split": "holdout"},
                         {"id": "example-not-graded", "lon": .004, "lat": .004, "cls": "road_bridge", "split": "reference"}]}


def run(context, actions, run_id="case"):
    store, card, config, execute, _, _ = context
    provider = ScriptProvider(actions)
    outcome = execute(store, card, config, provider, run_id=run_id)
    assert provider.requests, "the injected ModelProvider must actually be used"
    return outcome, provider


def test_worker_never_receives_heldout_or_grader_material(context):
    _, provider = run(context, [])
    visible = json.dumps(provider.requests)
    assert "keys/synth" not in visible
    assert "synthetic world generator" not in visible
    assert "four crossings show in no clear post scene" not in visible
    assert "hidden-a" not in visible and "hidden-b" not in visible


def test_export_is_exactly_sealed_claims_and_does_not_overwrite(context, tmp_path):
    store, _, _, _, _, export = context
    run(context, claim("one", .002, .002) + claim("two", .008, .008, "footbridge", "absent"))
    paths = export(store, "case", tmp_path / "export")
    geo = json.loads(Path(paths["geojson"]).read_text())
    with sqlite3.connect(paths["sqlite"]) as db:
        rows = db.execute("SELECT claim_id, lon, lat, cls, status, agent_confidence FROM detections ORDER BY claim_id").fetchall()
    assert len(rows) == 2
    assert [(r[1], r[2], r[3], r[4], r[5]) for r in rows] == [
        (.002, .002, "road_bridge", "present", .91), (.008, .008, "footbridge", "absent", .91)]
    assert geo["type"] == "FeatureCollection" and len(geo["features"]) == 1
    feature = geo["features"][0]
    assert feature["geometry"]["coordinates"] == [.002, .002]
    assert feature["properties"]["claim_id"] == rows[0][0]
    assert feature["properties"]["agent_confidence"] == .91
    assert "evidence_refs" in feature["properties"] and "decision_id" in feature["properties"]
    before = {k: Path(v).read_bytes() for k, v in paths.items()}
    with pytest.raises((FileExistsError, ValueError, RuntimeError)):
        export(store, "case", tmp_path / "export")
    assert before == {k: Path(v).read_bytes() for k, v in paths.items()}


def test_tampered_sealed_claims_cannot_be_evaluated_or_exported(context, tmp_path):
    store, _, _, _, evaluate, export = context
    run(context, claim("one", .002, .002))
    claims = store.run_dir("case") / "trials/t-0.claims.jsonl"
    claims.chmod(0o644)  # Simulate an actor able to modify the sealed file.
    claims.write_bytes(claims.read_bytes() + b" ")
    with pytest.raises((ValueError, RuntimeError)):
        evaluate(store, "case", reference=reference())
    with pytest.raises((ValueError, RuntimeError)):
        export(store, "case", tmp_path / "export")


def test_denied_unplanned_action_does_not_create_claim(context, tmp_path):
    store, _, _, _, evaluate, export = context
    action = claim("one", .002, .002)[1]
    run(context, [action])
    paths = export(store, "case", tmp_path / "export")
    with sqlite3.connect(paths["sqlite"]) as db:
        assert db.execute("SELECT COUNT(*) FROM detections").fetchone()[0] == 0
    report = evaluate(store, "case", reference=reference())
    assert report["run_id"] == "case" and report["schema_version"] == "treehouse.investigation-report/1"
    assert report["process"]["limitations"]


def test_unkeyed_and_incomplete_reference_do_not_claim_calibration(context):
    store, _, _, _, evaluate, _ = context
    run(context, claim("one", .002, .002))
    for ref in (None, reference("incomplete")):
        report = evaluate(store, "case", reference=ref)
        assert report["confidence"]["no_grade_reason"] or all(
            n["tier"] == "ABSTAINED" for n in report["confidence"]["numbers"].values())
        assert report["run_id"] == "case"
        json.dumps(report)


@pytest.mark.parametrize("variant", ["future_evidence", "wrong_id", "wrong_tool", "wrong_parameters", "posthoc"])
def test_invalid_decision_cannot_authorize_claim(context, tmp_path, variant):
    store, _, _, _, evaluate, export = context
    decision, action = claim("one", .002, .002)
    name, did, args = decision
    if variant == "future_evidence":
        args = {**args, "evidence_refs": ["r-999999"]}
    elif variant == "wrong_id":
        args = {**args, "action_id": "other"}
    elif variant == "wrong_tool":
        args = {**args, "tool": "note_limitation"}
    elif variant == "wrong_parameters":
        args = {**args, "parameters": {**args["parameters"], "lon": .008}}
    decision = (name, did, args)
    actions = [action, decision] if variant == "posthoc" else [decision, action]
    run(context, actions)
    paths = export(store, "case", tmp_path / "export")
    with sqlite3.connect(paths["sqlite"]) as db:
        assert db.execute("SELECT COUNT(*) FROM detections").fetchone()[0] == 0
    assert evaluate(store, "case", reference=reference())["process"]["limitations"]


def test_decision_cannot_be_reused_for_second_action(context, tmp_path):
    store, _, _, _, _, export = context
    decision, action = claim("one", .002, .002)
    second = ("record_claim", "two", action[2])
    run(context, [decision, action, second])
    paths = export(store, "case", tmp_path / "export")
    with sqlite3.connect(paths["sqlite"]) as db:
        assert db.execute("SELECT COUNT(*) FROM detections").fetchone()[0] == 1


def test_report_is_post_seal_and_cannot_leak_supplied_holdout(context):
    store, _, _, _, evaluate, _ = context
    _, provider = run(context, claim("one", .002, .002))
    requests_before = json.dumps(provider.requests, sort_keys=True)
    report = evaluate(store, "case", reference=reference())
    assert json.dumps(provider.requests, sort_keys=True) == requests_before
    assert "hidden-a" not in requests_before and "hidden-b" not in requests_before
    assert report["manifest_ref"] and report["decisions"]
    assert isinstance(report["pathways"], list)
    assert report["synthetic"] is True


def numbers(report):
    return {k: v["value"] for k, v in report["output"]["numbers"].items()}


def test_keyed_matching_counts_duplicates_wrong_class_outside_and_missed(context):
    store, _, _, _, evaluate, _ = context
    actions = (claim("correct", .002, .002) + claim("duplicate", .002, .002)
               + claim("wrong-class", .008, .008, "road_bridge") + claim("outside", .02, .02))
    run(context, actions)
    report = evaluate(store, "case", reference=reference())
    n = numbers(report)
    assert (n["catalog_tp"], n["catalog_fp"], n["catalog_fn"]) == (1, 3, 1)
    assert n["catalog_precision"] == pytest.approx(1 / 4)
    assert n["catalog_recall"] == pytest.approx(1 / 2)
    for key in ("catalog_precision", "catalog_recall"):
        metric = report["output"]["numbers"][key]
        assert metric["tier"] == "KEYED" and metric["n"] in (2, 4)
    assert report["confidence"]["numbers"]["brier"]["tier"] == "KEYED"


def test_empty_predictions_report_holdout_misses_not_reference_examples(context):
    store, _, _, _, evaluate, _ = context
    run(context, [])
    n = numbers(evaluate(store, "case", reference=reference()))
    assert n["catalog_tp"] == 0 and n["catalog_fn"] == 2


def test_incomplete_key_does_not_call_unmatched_prediction_false_positive(context):
    store, _, _, _, evaluate, _ = context
    run(context, claim("unmatched", .006, .006))
    report = evaluate(store, "case", reference=reference("incomplete"))
    fp = report["output"]["numbers"]["catalog_fp"]
    assert fp["tier"] == "ABSTAINED" and fp["value"] is None and fp["reasons"]
    assert report["confidence"]["no_grade_reason"] or report["confidence"]["numbers"]["brier"]["tier"] == "ABSTAINED"


def test_equivalent_strategies_have_same_keyed_outcomes(context):
    store, card, config, execute, evaluate, _ = context
    first = claim("a", .002, .002) + claim("b", .008, .008, "footbridge")
    second = claim("b", .008, .008, "footbridge") + claim("a", .002, .002)
    execute(store, card, config, ScriptProvider(first), run_id="first")
    execute(store, card, config, ScriptProvider(second), run_id="second")
    a, b = (numbers(evaluate(store, rid, reference=reference())) for rid in ("first", "second"))
    for k in ("catalog_tp", "catalog_fp", "catalog_fn", "catalog_precision", "catalog_recall"):
        assert a[k] == b[k]
    assert (a["catalog_tp"], a["catalog_fp"], a["catalog_fn"]) == (2, 0, 0)


def test_decisions_and_pathways_show_actual_bound_actions(context):
    store, _, _, _, evaluate, _ = context
    run(context, claim("one", .002, .002))
    report = evaluate(store, "case", reference=reference())
    decisions = report["decisions"]
    d = next(d for d in decisions if d["action_id"] == "one")
    assert {"decision_id", "action_id", "tool", "parameters", "rationale", "alternatives", "confidence",
            "parent_id", "evidence_refs", "sequence", "span_id", "action", "flags"} <= d.keys()
    assert d["tool"] == "record_claim" and d["action"]["tool"] == "record_claim"
    assert d["action"]["span_id"] and d["action"]["result_id"] and d["action"]["status"] == "success"
    assert {"decision_id": d["decision_id"], "parent_id": d["parent_id"],
            "action_id": "one", "result_id": d["action"]["result_id"]} in report["pathways"]
    assert report["process"]["numbers"]["decision_coverage"]["value"] == 1


def test_official_public_subset_ingests_as_incomplete_reference_only(context):
    from treehouse.schemas.geo import Polygon
    store, _, _, execute, evaluate, _ = context
    base = ROOT / "keys/public-benchmark"
    metadata = json.loads((base / "provenance.json").read_text())
    examples = json.loads((base / "public-reference-examples/features.json").read_text())
    heldout = json.loads((base / "heldout-grading/features.json").read_text())
    assert len(examples) == len(heldout) == 12
    assert set(x["id"] for x in examples).isdisjoint(x["id"] for x in heldout)
    card = load_card(ROOT / "tasks/virginia-solar-18sth.yaml")
    polygon = {"type": "Polygon", "coordinates": [[[-84, 36], [-75, 36], [-75, 40], [-84, 40], [-84, 36]]]}
    card = card.model_copy(update={"aoi": Polygon.model_validate(polygon),
                                   "tools_allowed": card.tools_allowed + ["record_decision", "classify_window"]})
    config = demo_config({"policy": "good", "run_id": "public"}, card, mode="fake")
    provider = ScriptProvider([])
    execute(store, card, config, provider, run_id="public")
    ref = {"schema_version": "treehouse.reference/1",
           "source": {"dataset": metadata["dataset"], "version": metadata["version"],
                      "url": metadata["official_release_page"], "license": metadata["license"],
                      "attribution": metadata["attribution"]},
           "quality": "incomplete", "coverage": polygon,
           "features": [{**x, "split": "reference"} for x in examples] +
                       [{**x, "split": "holdout"} for x in heldout]}
    report = evaluate(store, "public", reference=ref)
    assert report["output"]["numbers"]["catalog_precision"]["tier"] == "ABSTAINED"
    assert report["confidence"]["no_grade_reason"] or report["confidence"]["numbers"]["brier"]["tier"] == "ABSTAINED"
    visible = json.dumps(provider.requests)
    assert all(x["id"] not in visible for x in heldout)
