"""The cluster tool uses the existing decision boundary, including blocked unplanned calls."""
import json

import pytest
from test_investigation_acceptance import ScriptProvider, planned

from treehouse.cards import load_card
from treehouse.investigation import run_investigation
from treehouse.service import demo_config
from treehouse.store.local import LocalStore
from treehouse.store.verify import verify


@pytest.mark.parametrize("record_survey", [True, False])
def test_survey_requires_a_prior_matching_decision(tmp_path, record_survey):
    card = load_card("tasks/t1-nagoya-warehouses.yaml")
    card = card.model_copy(update={"tools_allowed": [*card.tools_allowed, "survey_clusters"]})
    build = {"source_id": "aef-10m-annual", "cell_size_m": 160, "year": 2024}
    survey = {"index_id": "idx-001", "n_clusters": 8, "seed": 17}
    actions = [planned("build", "build_index", build), ("build_index", "build", build)]
    if record_survey:
        actions.append(planned("survey", "survey_clusters", survey))
    actions.append(("survey_clusters", "survey", survey))
    store = LocalStore(tmp_path / "store")
    config = demo_config({"policy": "good", "run_id": "clusters"}, card, mode="fake")
    run_investigation(store, card, config, ScriptProvider(actions), run_id="clusters")
    assert verify(store, "clusters").ok
    ledger = json.loads((store.run_dir("clusters") / "trials/t-0.investigation.json").read_text())
    action = next(a for a in ledger["actions"] if a["tool"] == "survey_clusters")
    if record_survey:
        assert action["status"] == "success" and action["decision_id"]
        decision = next(d for d in ledger["decisions"] if d["decision_id"] == action["decision_id"])
        assert decision["parameters"] == survey and decision["action"]["result_id"] == action["result_id"]
    else:
        assert action["status"] == "blocked" and action["block_reason"] == "missing_decision"
