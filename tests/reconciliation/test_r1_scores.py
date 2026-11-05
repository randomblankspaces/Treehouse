"""Percentages and recorded-rationale summaries on the actual local HTTP bridge."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from helpers import ORIGIN, claim, hashes, planned, run_case

from treehouse import service
from treehouse.store.local import LocalStore
from treehouse.ui import create_app

NAMES = ("reasoning_rules", "reviewer", "agentcore", "output", "calibration", "predicted_accuracy")


@pytest.fixture(scope="module")
def scored(tmp_path_factory):
    store = LocalStore(tmp_path_factory.mktemp("r1-scores") / "store")
    actions = planned("index", "build_index", {"source_id": "aef-10m-annual", "cell_size_m": 160, "year": 2024})
    actions += claim("point", [136.85, 35.08])
    run_case(store, "scores", actions)
    service.evaluate(store, "scores")
    with TestClient(create_app(store.root), base_url=ORIGIN) as api:
        response = api.get("/api/runs/scores/snapshot")
        assert response.status_code == 200, response.text
        snapshot = response.json()
    return store, snapshot


def scores(section):
    assert isinstance(section.get("scores"), list), "evaluation needs named readable scores, not only pass/fail or raw JSON"
    for score in section["scores"]:
        assert score["metric"] and score["basis"]
        assert score["unit"] in {"percent", "raw"}
        assert score["status"] in {"available", "unavailable", "method_test_only"}
        assert {"numerator", "denominator", "value", "reason"} <= score.keys()
        if score["status"] == "unavailable":
            assert score["value"] is None and score["reason"]
        else:
            assert isinstance(score["value"], (int, float)) and not isinstance(score["value"], bool)
            if score["unit"] == "percent":
                assert 0 <= score["value"] <= 100
                assert score["denominator"] is not None and score["denominator"] > 0
    return {s["metric"]: s for s in section["scores"]}


def test_r1_all_sections_expose_named_score_availability(scored):
    _, snapshot = scored
    for name in NAMES:
        section = snapshot["evaluation"][name]
        items = scores(section)
        if not items:
            assert section["reason"], f"{name} has neither numeric scores nor an unavailable explanation"
    for name in ("reviewer", "agentcore", "predicted_accuracy"):
        assert all(s["value"] is None for s in snapshot["evaluation"][name]["scores"]), "missing rubric/model must not fabricate numeric quality"


def test_r1_rules_percent_uses_passed_over_assessed_excluding_not_applicable(scored):
    _, snapshot = scored
    rules = snapshot["evaluation"]["reasoning_rules"]
    raw = rules["value"]["t-0"]["summary"]
    passed, failed = len(raw["passed_rules"]), len(raw["failed_rules"])
    score = scores(rules)["rules_pass_rate"]
    assert score["unit"] == "percent"
    assert score["numerator"] == passed and score["denominator"] == passed + failed
    assert score["value"] == pytest.approx(100 * passed / (passed + failed))


def test_r1_output_and_calibration_values_have_honest_units_and_denominators(scored):
    _, snapshot = scored
    output = snapshot["evaluation"]["output"]
    output_scores = scores(output)
    if output["status"] != "unavailable":
        raw = output["value"]["t-0"]["output"]
        for metric, denominator in (("precision", "n_flagged_cells"), ("recall", "n_assets")):
            score = output_scores[metric]
            assert score["unit"] == "percent" and score["denominator"] == raw[denominator]
            assert score["value"] == pytest.approx(raw[metric] * 100)
            assert score["status"] == "method_test_only"
    calibration = snapshot["evaluation"]["calibration"]
    calibration_scores = scores(calibration)
    if calibration["status"] != "unavailable":
        raw = calibration["value"]["t-0"]["calibration"]
        brier, ece = calibration_scores["brier"], calibration_scores["ece"]
        assert brier["unit"] == "raw" and brier["value"] == pytest.approx(raw["brier"])
        assert ece["unit"] == "percent" and ece["value"] == pytest.approx(raw["ece"] * 100)
        assert brier["denominator"] == ece["denominator"] == raw["n"]
    assert not any("accuracy" in s["metric"].lower() for s in calibration.get("scores", [])), "1-Brier is not accuracy"


def test_r1_thinking_summary_is_recorded_rationale_deterministic_and_read_only(scored, monkeypatch, offline_guard):
    store, snapshot = scored
    from treehouse.ui import snapshot as snapshot_module
    summary = snapshot.get("thinking_summary")
    assert summary and summary["status"] == "available"
    assert summary["basis"] == "recorded_decisions" and summary["text"]
    text = summary["text"].lower()
    assert "recorded" in text and ("rationale" in text or "decision" in text)
    for required in ("build_index", "record_claim", "independent", "plain_loop"):
        assert required in text, f"recorded summary omitted {required}"
    assert "hidden" in text or "chain of thought" in text, "summary must distinguish recorded explanations from hidden reasoning"
    before = hashes(store.root)

    def forbidden(*args, **kwargs):
        pytest.fail("GET narrative summary must not call models/cloud")

    monkeypatch.setattr(service, "run", forbidden)
    import boto3
    monkeypatch.setattr(boto3, "client", forbidden)
    assert snapshot_module is not None
    with TestClient(create_app(store.root), base_url=ORIGIN) as api:
        again = api.get("/api/runs/scores/snapshot").json()
        exported = api.get("/api/runs/scores/export").json()
    assert again["thinking_summary"] == summary
    assert json.dumps(summary, sort_keys=True) in json.dumps(exported, sort_keys=True)
    assert hashes(store.root) == before and not offline_guard.attempts


def test_r1_explicit_current_reference_comparison_produces_numeric_percentages(tmp_path):
    """Current supplied comparison is distinct from an unbound historical split score."""
    store = LocalStore(tmp_path / "store")
    actions = planned("index", "build_index", {"source_id": "aef-10m-annual", "cell_size_m": 160, "year": 2024})
    actions += claim("matched", [136.85, 35.08], confidence=.8)
    actions += claim("unmatched", [136.89, 35.10], confidence=.6)
    run_case(store, "current-comparison", actions)
    reference = {
        "schema_version": "treehouse.reference/1", "quality": "complete",
        "source": {"dataset": "Independent synthetic comparison", "version": "r1-current-comparison",
                   "url": "https://example.invalid/r1", "license": "CC0-1.0",
                   "attribution": "Synthetic method test; no field measurements"},
        "coverage": {"type": "Polygon", "coordinates": [[[136.82, 35.05], [136.92, 35.05],
                      [136.92, 35.12], [136.82, 35.12], [136.82, 35.05]]]},
        "features": [{"id": "match", "lon": 136.85, "lat": 35.08, "cls": "warehouse", "split": "holdout"},
                     {"id": "missed", "lon": 136.83, "lat": 35.06, "cls": "warehouse", "split": "holdout"}],
    }
    path = tmp_path / "current-reference.json"
    path.write_text(json.dumps(reference))
    before = hashes(store.root)
    with TestClient(create_app(store.root, server_reference=path), base_url=ORIGIN) as api:
        response = api.get("/api/runs/current-comparison/snapshot")
    assert response.status_code == 200, response.text
    snapshot = response.json()
    output = snapshot["evaluation"]["output"]
    assert output["status"] == "method_test_only"
    raw = output["value"]["numbers"]
    values = scores(output)
    for metric in ("precision", "recall"):
        value = values[metric]
        assert value["unit"] == "percent" and value["value"] == pytest.approx(50)
        assert value["numerator"] == 1 and value["denominator"] == 2
        assert value["status"] == "method_test_only"
        assert "catalog" in value["basis"].lower(), "catalogue matching and cell protocol have different units"
        assert raw[f"catalog_{metric}"]["value"] == pytest.approx(.5)
    calibration = snapshot["evaluation"]["calibration"]
    assert calibration["status"] == "method_test_only"
    brier = scores(calibration)["brier"]
    assert brier["unit"] == "raw" and brier["denominator"] == 2
    assert brier["value"] == pytest.approx(.2)
    assert calibration["value"]["numbers"]["brier"]["value"] == pytest.approx(.2)
    assert hashes(store.root) == before
