"""Offline experiment analysis keeps run/config panels separate."""
from __future__ import annotations

import json
import runpy
import subprocess
import sys
from pathlib import Path

from treehouse.cards import load_card
from treehouse.investigation import run_investigation
from treehouse.schemas.config import RunConfig
from treehouse.store.local import LocalStore

ROOT = Path(__file__).parents[2]
WAREHOUSE_E2E = runpy.run_path(str(ROOT / "tests/investigation/test_warehouse_strands_e2e.py"))
OFFLINE_LABEL = "offline, synthetic fixture embeddings, not a live agent run"
WarehouseScriptProvider = WAREHOUSE_E2E["WarehouseScriptProvider"]


class BangladeshScriptProvider(WarehouseScriptProvider):
    """A cheap unkeyed run: build one index, record one claim, and state limitations."""

    def _action(self) -> tuple[str, dict]:
        if self.index == 0:
            return "submit_understanding", {
                "goal_restated": "Find warehouses in the Chattogram AOI.",
                "scope": "The full task AOI.",
                "planned_data": ["AEF 10 m annual embeddings"],
                "known_limits": ["There is no complete reference."],
            }
        if self.index == 1:
            return "build_index", {"source_id": "aef-10m-annual", "cell_size_m": 160, "year": 2024}
        if self.index == 2:
            return "record_claim", {
                "step_id": "inventory",
                "lon": 91.795533,
                "lat": 22.288508,
                "cls": "warehouse",
                "status": "present",
                "confidence": 0.7,
                "reason": "Synthetic-fixture smoke claim at 160 m cell scale.",
                "evidence_refs": [],
            }
        return "note_limitation", {
            "text": "The reference pool is incomplete, so this run cannot claim recall or complete coverage."
        }


def _config(name: str) -> RunConfig:
    live = RunConfig.model_validate_json((Path("fixtures/live/configs") / name).read_bytes())
    return live.model_copy(
        update={
            "mode": "fake",
            "clock": "logical",
            "worker": live.worker.model_copy(update={"provider": "fake"}),
        }
    )


def test_classifier_comparison_uses_card_review_assumption(monkeypatch):
    comparison = runpy.run_path(str(ROOT / "scripts/analyze_experiments.py"))["_classifier_comparison"]
    card = load_card("tasks/t1-nagoya-warehouses.yaml").model_copy(update={"minutes_per_cell": 3.0})
    monkeypatch.setitem(comparison.__globals__, "load_card", lambda path: card)
    for trial in comparison()["trials"]:
        for report in trial["methods"].values():
            assert report["minutes_per_cell"] == 3.0
            for target, cells in report["review_effort"].items():
                assert report["analyst_hours"][target] == (cells * 3.0 / 60 if cells is not None else None)


def test_analyze_experiments_writes_separate_offline_panels(tmp_path: Path) -> None:
    store = LocalStore(tmp_path / "store")
    nagoya = load_card("tasks/t1-nagoya-warehouses.yaml").model_copy(update={"minutes_per_cell": 3.0})
    nagoya_config = _config("t1-nagoya-sonnet-strands.json").model_copy(update={"task_ref": nagoya.ref()})
    for run_id in ("nagoya-a", "nagoya-b"):
        run_investigation(store, nagoya, nagoya_config, WarehouseScriptProvider(), run_id=run_id)

    bangladesh = load_card("tasks/t1-bangladesh-warehouses.yaml")
    bangladesh_config = _config("t1-bangladesh-sonnet-strands.json")
    run_investigation(
        store,
        bangladesh,
        bangladesh_config,
        BangladeshScriptProvider(),
        run_id="bangladesh-a",
    )

    output = tmp_path / "metrics.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/analyze_experiments.py"),
            "--store",
            str(store.root),
            "--out",
            str(output),
        ],
        cwd=ROOT,
        check=True,
    )
    metrics = json.loads(output.read_text())
    assert set(metrics["runs"]) == {"nagoya-a", "nagoya-b", "bangladesh-a"}
    for run_id in ("nagoya-a", "nagoya-b"):
        panels = metrics["runs"][run_id]["panels_by_trial"]["t-0"]
        assert panels["output"]["recall"] is not None
        assert panels["output"]["precision"] is not None
        assert panels["output"]["minutes_per_cell"] == 3.0
        assert panels["output"]["minutes_per_cell_basis"] == "assumption"
        assert panels["calibration"]["n_bins"] == 5
    unkeyed = metrics["runs"]["bangladesh-a"]["panels_by_trial"]["t-0"]
    assert unkeyed["calibration"] == {"no_grade_reason": "unkeyed"}
    assert unkeyed["output"]["recall"] is None

    label = "t1-nagoya-warehouses|claude-sonnet-5-5|strands"
    config = metrics["configs"][label]
    assert config["n_trials"] == 2
    assert config["metrics"]["output.recall"]["interval_95"] is not None
    assert config["metrics"]["output.recall"]["interval_reason"] is None

    assert metrics["predicted_accuracy"]["label"] == "MODEL-ESTIMATED"
    classifier = metrics["comparisons"]["classifier"]
    assert classifier["label"] == OFFLINE_LABEL
    assert set(classifier["methods"]) == {"linear_probe", "linear_svm"}
    assert "not applicable" in classifier["gifu_transfer"]["status"]
    json.dumps(metrics)
