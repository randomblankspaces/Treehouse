"""Deliberation metrics are deterministic summaries of recorded decisions, not hidden cognition."""

from treehouse.investigation.deliberation import evaluate


def metric(result, name):
    return result["metrics"][name]


def test_random_walk_ledger_scores_low_and_flags_unsupported_confidence():
    ledger = {
        "decisions": [
            {"decision_id": "d1", "action": {"tool": "search", "parameters": {"model": "AEF"}},
             "rationale": "Use this model.", "alternatives": [], "confidence": 0.9,
             "evidence_refs": [], "thinking_ref": None},
        ],
        "claims": [{"claim_id": "c1", "confidence": 0.9, "decision_ids": ["d1"]}],
    }

    result = evaluate(ledger)

    assert metric(result, "alternatives_per_decision") == {
        "numerator": 0, "denominator": 1, "value": 0.0, "status": "available"}
    assert metric(result, "alternatives_tried") == {
        "numerator": 0, "denominator": 0, "value": 0.0, "status": "available"}
    assert result["earned_confidence"]["c1"] == "unearned"
    assert result["status"] == "available"


def test_deliberate_ledger_counts_comparison_verification_revision_and_thinking():
    ledger = {
        "decisions": [
            {"decision_id": "d1", "action": {"tool": "configure", "parameters": {
                "model": "AEF", "cell_size_m": 160}}, "rationale": "AEF and 160 m fit the target.",
             "alternatives": ["LGND", "1280 m"], "confidence": 0.8,
             "evidence_refs": ["e1"], "thinking_ref": "t1",
             "thinking_text": "Compared AEF against LGND and 160 m against 1280 m; chose AEF and 160 m."},
            {"decision_id": "d2", "action": {"tool": "verify", "parameters": {"source": "vision"}},
             "rationale": "Independent visual check supports the candidate.", "alternatives": [],
             "confidence": 0.2, "evidence_refs": ["e2"], "thinking_ref": "t2",
             "thinking_text": "The visual check supports the candidate."},
            {"decision_id": "d3", "action": {"tool": "revise", "parameters": {"threshold": 0.6}},
             "rationale": "Revise after the visual evidence.", "alternatives": [], "confidence": 0.8,
             "evidence_refs": ["e2"], "thinking_ref": "t3",
             "thinking_text": "The evidence supports revising the threshold."},
        ],
        "claims": [{"claim_id": "c1", "confidence": 0.2, "decision_ids": ["d1", "d2", "d3"]}],
        "actions": [{"tool": "search", "parameters": {"model": "LGND", "cell_size_m": 1280}}],
    }

    result = evaluate(ledger)

    assert metric(result, "alternatives_per_decision")["numerator"] == 2
    assert metric(result, "alternatives_per_decision")["denominator"] == 3
    assert metric(result, "alternatives_tried")["numerator"] == 2
    assert metric(result, "key_choices_compared")["numerator"] == 2
    assert metric(result, "key_choices_compared")["denominator"] == 2
    assert metric(result, "claims_independently_checked")["numerator"] == 1
    assert metric(result, "revisions_after_evidence")["numerator"] == 1
    assert metric(result, "thinking_coverage")["numerator"] == 3
    assert metric(result, "thinking_rationale_agreement")["numerator"] == 1
    assert result["earned_confidence"]["c1"] == "under-confident"
    assert "self-reported rationale and model thinking text" in result["basis"]


def test_missing_thinking_in_committed_live_ledger_is_unavailable_but_other_metrics_are_numeric():
    ledger = {"decisions": [{"decision_id": "d1", "action": {"tool": "search", "parameters": {}},
                             "rationale": "Recorded rationale.", "alternatives": [], "confidence": 0.5,
                             "evidence_refs": [], "thinking_ref": None}],
              "claims": []}

    result = evaluate(ledger)

    for name in ("thinking_coverage", "thinking_rationale_agreement"):
        assert metric(result, name)["status"] == "unavailable"
        assert metric(result, name)["reason"] == "not recorded"
    assert metric(result, "alternatives_per_decision")["status"] == "available"
    assert metric(result, "alternatives_per_decision")["denominator"] == 1


def test_distinct_alternatives_require_later_successful_execution_and_exact_values():
    ledger = {"decisions": [{"decision_id": "d", "sequence": 3,
        "tool": "search", "parameters": {"model": "AEF"},
        "alternatives": [{"option": " LGND ", "reason": "compare"},
                         {"option": "LGND", "reason": "duplicate"}, {"option": "", "reason": "empty"}],
        "confidence": .9, "evidence_refs": []}], "claims": [], "actions": [
        {"sequence": 2, "status": "success", "parameters": {"model": "LGND"}},
        {"sequence": 4, "status": "error", "parameters": {"model": "LGND"}},
        {"sequence": 5, "status": "success", "parameters": {"model": "LGND-other"}}]}
    result = evaluate(ledger)
    assert metric(result, "alternatives_per_decision")["numerator"] == 1
    assert metric(result, "alternatives_tried")["numerator"] == 0


def test_post_claim_or_failed_check_does_not_earn_confidence():
    ledger = {"decisions": [
        {"decision_id": "claim", "sequence": 2, "action": {"tool": "record_claim"},
         "alternatives": [], "confidence": .9, "evidence_refs": []},
        {"decision_id": "check", "sequence": 4, "action": {"tool": "verify", "status": "success"},
         "alternatives": [], "confidence": .8, "evidence_refs": []}],
        "claims": [{"claim_id": "c", "confidence": .9, "sequence": 3,
                    "decision_ids": ["claim", "check"]}]}
    assert evaluate(ledger)["earned_confidence"]["c"] == "unearned"


def test_uncertain_thinking_at_high_confidence_is_flagged():
    result = evaluate({"decisions": [{"decision_id": "d", "confidence": .7,
        "parameters": {"model": "AEF"}, "alternatives": ["LGND"],
        "thinking_ref": "r", "thinking_text": "I am guessing between AEF and LGND."}], "claims": []})
    assert result["thinking_confidence_flags"] == ["d"]
    assert metric(result, "thinking_rationale_agreement")["numerator"] == 0


def test_report_surfaces_deliberation_and_features_on_a_sealed_run(context):
    from test_investigation_acceptance import ScriptProvider, claim
    store, card, config, run, assess, _ = context
    run(store, card, config, ScriptProvider(claim("c", .002, .002)), run_id="deliberation")
    report = assess(store, "deliberation")
    result = report["process"]["deliberation"]["t-0"]
    assert result["metrics"]["alternatives_per_decision"]["numerator"] == 1
    assert result["metrics"]["thinking_coverage"]["reason"] == "not recorded"
    assert result["scores"][0]["metric"] == "alternatives_per_decision"
    assert result["scores"][0]["denominator"] == 1
    assert report["predicted_accuracy_features"]["t-0"]["deliberation.alternatives_per_decision"] == 1.0
    assert "deliberation.thinking_coverage" not in report["predicted_accuracy_features"]["t-0"]


def test_comparison_uses_matching_parameter_axes_without_thinking():
    result = evaluate({"decisions": [{"decision_id": "d", "sequence": 1,
        "parameters": {"model": "AEF", "cell_size_m": 160}, "alternatives": ["LGND"]}],
        "actions": [{"sequence": 2, "status": "success", "parameters": {"model": "LGND"}}]})
    assert metric(result, "key_choices_compared")["numerator"] == 1
    assert metric(result, "key_choices_compared")["denominator"] == 2


def test_failed_check_and_unknown_revision_evidence_do_not_count():
    result = evaluate({"decisions": [
        {"decision_id": "d1", "sequence": 1, "parameters": {"threshold": .4},
         "action": {"tool": "verify", "status": "error"}},
        {"decision_id": "d2", "sequence": 3, "parent_id": "d1",
         "parameters": {"threshold": .6}, "evidence_refs": ["missing"]}],
        "actions": [{"sequence": 2, "status": "error", "result_id": "failed", "tool": "verify"}],
        "claims": [{"claim_id": "c", "sequence": 4, "confidence": .9, "decision_ids": ["d2"]}]})
    assert result["earned_confidence"]["c"] == "unearned"
    assert metric(result, "revisions_after_evidence")["numerator"] == 0


def test_committed_live_ledgers_have_numeric_exploration_and_unavailable_thinking():
    import json

    from treehouse.paths import repo_root
    root = repo_root() / "fixtures/live/experiments/runs"
    for run_id in ("exp-nagoya-sonnet-1", "exp-gifu-sonnet-1", "exp-bangladesh-sonnet-1"):
        ledger = json.loads((root / run_id / "t-0.investigation.json").read_text())
        result = evaluate(ledger)
        assert result["metrics"]["thinking_coverage"]["reason"] == "not recorded"
        assert result["metrics"]["thinking_rationale_agreement"]["reason"] == "not recorded"
        assert isinstance(result["metrics"]["alternatives_per_decision"]["value"], float)
        assert result["metrics"]["alternatives_per_decision"]["denominator"] == len(ledger["decisions"])


def test_decisions_link_only_thinking_from_the_emitting_turn(context):
    import json

    import pytest
    from test_investigation_acceptance import ScriptProvider, claim

    from treehouse.schemas.model_io import Reasoning

    store, card, config, run, assess, _ = context

    class ThinkingProvider(ScriptProvider):
        async def complete(self, *args, **kwargs):
            response = await super().complete(*args, **kwargs)
            if kwargs["turn"] == 0:
                response = response.model_copy(update={"message": response.message.model_copy(update={
                    "content": [Reasoning(text="Choose this location after considering stop.", signature="sig"),
                                Reasoning(text="A second thinking block."), *response.message.content]})})
            return response

    for harness in ("plain_loop", "strands"):
        if harness == "strands":
            pytest.importorskip("strands")
        provider = ThinkingProvider(claim("c1", .002, .002) + claim("c2", .003, .003))
        run(store, card, config.model_copy(update={"harness": harness}), provider, run_id=harness)
        ledger = json.loads((store.run_dir(harness) / "trials/t-0.investigation.json").read_text())
        first, second = ledger["decisions"]
        response = json.loads(store.blob_path(first["thinking_ref"]).read_bytes())
        assert response["message"]["content"][0]["text"] == "Choose this location after considering stop."
        assert second["thinking_ref"] is None
        report = assess(store, harness)
        result = report["process"]["deliberation"]["t-0"]
        assert result["metrics"]["thinking_coverage"]["numerator"] == 1
        assert result["metrics"]["thinking_coverage"]["denominator"] == 2
        assert "A second thinking block." in report["decisions"][0]["thinking_text"]


def test_revision_requires_evidence_observed_after_parent_decision():
    result = evaluate({"decisions": [
        {"decision_id": "d1", "sequence": 3, "parameters": {"threshold": .4}},
        {"decision_id": "d2", "sequence": 5, "parent_id": "d1",
         "parameters": {"threshold": .6}, "evidence_refs": ["old"]}],
        "actions": [{"sequence": 1, "status": "success", "result_id": "old"}]})
    assert metric(result, "revisions_after_evidence")["numerator"] == 0
