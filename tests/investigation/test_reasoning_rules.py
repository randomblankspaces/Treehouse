"""Deterministic reasoning-validity rules RV1-RV10 (MVP-PLAN §5.1, Req 5.4) on hand-built ledgers."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from treehouse.assets import AssetClasses
from treehouse.cards import load_card
from treehouse.investigation.reasoning_rules import RULES_VERSION, evaluate

ROOT = Path(__file__).resolve().parents[2]
NAGOYA = load_card(ROOT / "tasks" / "t1-nagoya-warehouses.yaml")  # keyed, complete reference
BANGLADESH = load_card(ROOT / "tasks" / "t1-bangladesh-warehouses.yaml")  # unkeyed
REG = AssetClasses.load()
AOI = [136.82, 35.05, 136.92, 35.12]
LIMIT = ("Limitation: AEF is 10 m, so warehouses under ~1,600 m2 may be missed; the north-east port "
         "islands were not reviewed (unreviewed area). Count range 380-460 warehouses.")


class Ledger:
    """Builds a ``treehouse.investigation-ledger/1`` snapshot the way the runtime does."""

    def __init__(self):
        self.decisions: list[dict] = []
        self.actions: list[dict] = []
        self.seq = 0

    def step(self, tool, parameters, rationale, *, status="success", parent_id=None, evidence_refs=None):
        self.seq += 1
        n = len(self.decisions) + 1
        did, aid, rid = f"t:d-{n:04d}", f"call-{n}", f"r-{n}"
        d = {"decision_id": did, "trial_id": "t", "action_id": aid, "tool": tool, "parameters": parameters,
             "rationale": rationale, "alternatives": [], "confidence": 0.7, "parent_id": parent_id,
             "evidence_refs": evidence_refs or [], "sequence": self.seq, "span_id": f"s{n}", "flags": [],
             "action": {"span_id": f"a{n}", "result_id": rid, "status": status, "tool": tool}}
        self.seq += 1
        self.decisions.append(d)
        self.actions.append({"action_id": aid, "tool": tool, "parameters": parameters, "span_id": f"a{n}",
                             "result_id": rid, "sequence": self.seq, "status": status, "decision_id": did,
                             "block_reason": None})
        return did, rid

    def snapshot(self):
        return {"schema_version": "treehouse.investigation-ledger/1", "decisions": self.decisions,
                "actions": self.actions, "stop": "finished", "stop_detail": None}


def good_ledger(cell=160, source="aef-10m-annual", cell_rationale="160 m cells hold one ~80 m warehouse each."):
    lg = Ledger()
    lg.step("submit_understanding", {"goal_restated": "Map warehouses", "scope": "Nagoya port AOI",
                                     "known_limits": ["10 m imagery misses small warehouses"]},
            "State the goal and limits first.")
    lg.step("get_examples", {"split": "train", "cls": "warehouse", "n": 8}, "Few-shot examples from train only.")
    lg.step("build_index", {"source_id": source, "cell_size_m": cell, "bbox": AOI}, cell_rationale)
    _, rid = lg.step("retrieve", {"source_id": source, "bbox": AOI, "prompt": "large logistics warehouse roof",
                                  "k": 50}, "Zero-shot prompt fixed before any labels.")
    _, wid = lg.step("imagery_window", {"source_id": "gsi-seamless-aerial-japan", "bbox": [136.83, 35.06,
                                        136.84, 35.07]}, "Inspect the top candidate at 0.5 m.",
                     evidence_refs=[rid])
    lg.step("record_claim", {"step_id": "inventory", "lon": 136.835, "lat": 35.065, "cls": "warehouse",
                             "status": "present", "confidence": 0.8, "reason": "Long low logistics shed with docks.",
                             "evidence_refs": [wid]},
            "Loading docks and truck yard: a logistics warehouse.", evidence_refs=[wid])
    lg.step("note_limitation", {"text": LIMIT, "stated_count": 1}, "Declare limits and the count range.")
    return lg


def run(ledger, card=NAGOYA, **kw):
    return evaluate(ledger, card, asset_class="warehouse", registry=REG, **kw)


def verdicts(out, rule):
    return [r["verdict"] for r in out["results"] if r["rule_id"] == rule]


def failed(out):
    return set(out["summary"]["failed_rules"])


def test_good_agent_passes_every_applicable_rule():
    out = run(good_ledger().snapshot())
    assert out["rules_version"] == RULES_VERSION == "rv-v1"
    assert failed(out) == set()
    for rule in ("RV1", "RV2", "RV4", "RV5", "RV6", "RV7", "RV8", "RV10"):
        assert out["summary"]["verdict_by_rule"][rule] == "pass", rule
    assert all(set(r) >= {"rule_id", "decision_id", "action_id", "verdict", "reason"} for r in out["results"])
    assert all(r["reason"] for r in out["results"])


# --- Planted bad agents (Req 5.4) fail exactly the right rule ---

def test_planted_coarse_cells_without_justification_fails_rv1_only():
    out = run(good_ledger(cell=1280, source="lgnd-clay-embeddings", cell_rationale="Use the LGND index.").snapshot())
    assert failed(out) == {"RV1"}


def test_coarse_cells_with_stated_limitation_pass_rv1():
    why = "1.28 km cells are too coarse to localise one warehouse; screen only, then inspect windows."
    out = run(good_ledger(cell=1280, source="lgnd-clay-embeddings", cell_rationale=why).snapshot())
    assert failed(out) == set()
    assert "pass" in verdicts(out, "RV1")


def test_planted_maxar_imagery_fails_rv2_only():
    lg = good_ledger()
    lg.step("imagery_window", {"source_id": "maxar-worldview-3", "bbox": [136.83, 35.06, 136.84, 35.07]},
            "Sharper imagery.")
    assert failed(run(lg.snapshot())) == {"RV2"}


def test_non_commercial_licence_fails_rv2():
    lg = good_ledger()
    lg.step("retrieve", {"source_id": "some-embeddings", "license": "CC-BY-NC-4.0", "bbox": AOI,
                         "prompt": "large logistics warehouse roof"}, "Second index.")
    assert "RV2" in failed(run(lg.snapshot()))


def test_planted_keys_path_fails_rv4_only():
    lg = good_ledger()
    lg.step("read_file", {"path": "keys/plateau/nagoya-warehouses.geojson"}, "Check the answer.")
    assert failed(run(lg.snapshot())) == {"RV4"}


def test_planted_held_out_examples_fail_rv4():
    lg = good_ledger()
    lg.decisions[1]["parameters"] = lg.actions[1]["parameters"] = {"split": "test", "cls": "warehouse"}
    assert failed(run(lg.snapshot())) == {"RV4"}


def test_forbidden_dataset_id_fails_rv4():
    lg = good_ledger()
    lg.step("retrieve", {"dataset_id": "plateau-nagoya-warehouses", "bbox": AOI,
                         "prompt": "large logistics warehouse roof"}, "Use the reference.")
    assert "RV4" in failed(run(lg.snapshot()))


# --- One test per remaining rule ---

def test_rv3_ten_metre_claim_below_min_size_fails_unless_limited():
    lg = good_ledger()
    lg.step("record_claim", {"step_id": "inventory", "lon": 136.85, "lat": 35.08, "cls": "warehouse",
                             "status": "present", "confidence": 0.6, "gsd_m": 10, "object_size_m": 20,
                             "reason": "small shed"}, "A 20 m shed is visible in AEF.")
    assert failed(run(lg.snapshot())) >= {"RV3"}
    lg.decisions[-1]["rationale"] = "A 20 m shed; limitation: 10 m pixels cannot resolve it reliably."
    assert "RV3" not in failed(run(lg.snapshot()))


def test_rv5_prompt_changed_after_examples_fails():
    lg = good_ledger()
    lg.step("retrieve", {"source_id": "aef-10m-annual", "bbox": AOI, "prompt": "blue roof warehouse near docks"},
            "Tune the prompt.")
    assert failed(run(lg.snapshot())) == {"RV5"}


def test_rv6_partial_coverage_fails_unless_gap_declared():
    lg = good_ledger()
    half = [136.82, 35.05, 136.87, 35.12]
    for d in lg.decisions:
        if d["tool"] in ("build_index", "retrieve"):
            d["parameters"] = {**d["parameters"], "bbox": half}
    lg.decisions[-1]["parameters"] = {"text": "Count range 300-400 warehouses.", "stated_count": 1}
    assert "RV6" in failed(run(lg.snapshot()))
    lg.decisions[-1]["parameters"] = {"text": "The eastern half was not searched (gap, unreviewed). "
                                              "Count range 300-400.", "stated_count": 1}
    assert "RV6" not in failed(run(lg.snapshot()))


def test_rv7_uncited_claim_and_wrong_count_fail():
    lg = good_ledger()
    lg.step("record_claim", {"step_id": "inventory", "lon": 136.9, "lat": 35.1, "cls": "warehouse",
                             "status": "present", "confidence": 0.5, "reason": "guess"},
            "Probably a warehouse.", evidence_refs=["r-999"])
    out = run(lg.snapshot())
    assert failed(out) == {"RV7"}
    reasons = " ".join(r["reason"] for r in out["results"] if r["rule_id"] == "RV7" and r["verdict"] == "fail")
    assert "r-999" in reasons and "stated count" in reasons


def test_rv7_external_claims_list_is_checked():
    out = run(good_ledger().snapshot(), claims=[{"claim_id": "c-1", "evidence_refs": ["r-5"]},
                                                {"claim_id": "c-2", "evidence_refs": []}])
    by_claim = {r["claim_id"]: r["verdict"] for r in out["results"] if r["rule_id"] == "RV7" and r["claim_id"]}
    assert by_claim == {"c-1": "pass", "c-2": "fail"}


def test_rv8_missing_limits_and_recall_on_unkeyed_reference_fail():
    lg = good_ledger()
    lg.decisions[-1]["parameters"] = {"text": "Recall is 95% against OSM.", "stated_count": 1}
    lg.decisions[0]["parameters"]["known_limits"] = []
    out = run(lg.snapshot(), card=BANGLADESH)
    assert out["summary"]["verdict_by_rule"]["RV8"] == "fail"
    reasons = " ".join(r["reason"] for r in out["results"] if r["rule_id"] == "RV8")
    assert "recall" in reasons and "unreviewed" in reasons and "count range" in reasons


def test_rv9_unrevised_contradiction_fails_and_revision_passes():
    lg = good_ledger()
    bad, rid = lg.step("retrieve", {"source_id": "aef-10m-annual", "bbox": AOI,
                                    "prompt": "large logistics warehouse roof"}, "Second page.")
    lg.step("note_limitation", {"text": LIMIT, "stated_count": 1}, "Done.")
    tool_results = {rid: {"status": "success", "tool": "retrieve", "payload": {"candidates": []}}}
    assert failed(run(lg.snapshot(), tool_results=tool_results)) == {"RV9"}
    lg.decisions[-1]["parent_id"] = bad
    assert failed(run(lg.snapshot(), tool_results=tool_results)) == set()


def test_rv9_tool_error_with_stated_reason_passes():
    lg = good_ledger()
    lg.step("imagery_window", {"source_id": "gsi-seamless-aerial-japan", "bbox": [136.9, 35.1, 136.91, 35.11]},
            "Check another candidate.", status="error")
    lg.step("note_limitation", {"text": LIMIT, "stated_count": 1},
            "Not revising: the window error is transient and the claim set is complete.")
    assert "RV9" not in failed(run(lg.snapshot()))


def test_rv10_claim_labelled_as_negative_fails_but_negated_mention_passes():
    lg = good_ledger()
    claim = next(d for d in lg.decisions if d["tool"] == "record_claim")
    claim["rationale"] = "Chimneys and a production line: this is a factory."
    assert failed(run(lg.snapshot())) == {"RV10"}
    claim["rationale"] = "Loading docks; not a factory and not an aircraft hangar."
    assert failed(run(lg.snapshot())) == set()


# --- Contract ---

def test_deterministic_and_inputs_not_mutated():
    lg = good_ledger(cell=1280, cell_rationale="x").snapshot()
    claims = [{"claim_id": "c-1", "evidence_refs": ["r-5"]}]
    tr = {"r-4": {"status": "success", "payload": {"candidates": [1]}}}
    before = copy.deepcopy((lg, claims, tr))
    a = run(lg, claims=claims, tool_results=tr)
    b = run(lg, claims=claims, tool_results=tr)
    assert a == b
    assert (lg, claims, tr) == before
    a["results"][0]["verdict"] = "edited"
    assert run(lg, claims=claims, tool_results=tr) == b


@pytest.mark.parametrize("ledger", [{}, {"decisions": None}, {"decisions": [{"tool": 3, "parameters": "x"}]},
                                    {"decisions": [{}], "actions": [{}]}, "not a dict"])
def test_malformed_ledgers_never_crash(ledger):
    out = evaluate(ledger, None, asset_class="warehouse", registry=REG)
    assert {r["verdict"] for r in out["results"]} <= {"pass", "fail", "not_applicable"}
    assert set(out["summary"]["verdict_by_rule"]) == {f"RV{i}" for i in range(1, 11)}


def test_unknown_class_is_not_applicable():
    out = evaluate(good_ledger().snapshot(), NAGOYA, asset_class="volcano", registry=REG)
    assert out["summary"]["verdict_by_rule"]["RV1"] == "not_applicable"
