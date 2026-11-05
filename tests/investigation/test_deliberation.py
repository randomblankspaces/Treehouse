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
