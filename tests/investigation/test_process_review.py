"""Independent acceptance for the optional bounded process reviewer; no paid model calls."""
import hashlib
import json

import pytest
from test_adaptive_budget import AdaptiveProvider

from treehouse.schemas.config import InferenceParams
from treehouse.schemas.model_io import Message, ModelResponse, Text, Usage

PRIVATE_MARKER = "PRIVATE_WORKER_CONVERSATION_SENTINEL_97a2"


class WorkerWithPrivateText(AdaptiveProvider):
    async def complete(self, req, *, role, trial_index, turn):
        result = await super().complete(req, role=role, trial_index=trial_index, turn=turn)
        msg = result.message.model_copy(update={"content": result.message.content + [Text(text=PRIVATE_MARKER)]})
        return result.model_copy(update={"message": msg})


class Reviewer:
    provider_name = "independent-reviewer"

    def __init__(self, answer, cost=None, response_model_id="separate-review-model"):
        self.answer = answer
        self.cost = cost
        self.response_model_id = response_model_id
        self.calls = []

    async def complete(self, req, *, role, trial_index, turn):
        self.calls.append((req, role, trial_index, turn))
        text = self.answer if isinstance(self.answer, str) else json.dumps(self.answer)
        return ModelResponse(message=Message(role="assistant", content=[Text(text=text)]), stop_reason="end_turn",
                             usage=Usage(input_tokens=21, output_tokens=11), latency_ms=1,
                             response_model_id=self.response_model_id, cost_usd=self.cost)


def store_snapshot(store):
    root = store.root
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file() and not p.is_symlink()}


def prepared(context):
    store, card, config, execute, evaluate, _ = context
    worker = WorkerWithPrivateText()
    outcome = execute(store, card, config, worker, run_id="review-case")
    report = evaluate(store, "review-case")
    decision = next(d for d in report["decisions"] if d["action_id"] == "inspect")
    return store, card, config, worker, outcome, decision


def valid_answer(decision):
    return {"findings": [{"criterion": "adaptation", "decision_ids": [decision["decision_id"]],
                          "evidence_refs": decision["evidence_refs"], "assessment": "supported",
                          "explanation": "The recorded scene choice follows the earlier search result."}],
            "limitations": ["Image content and real-world correctness were not assessed."]}


def invoke(store, reviewer, *, model_id="separate-review-model"):
    from treehouse.investigation import review_investigation
    return review_investigation(store, "review-case", reviewer, model_id=model_id,
                                params=InferenceParams(max_tokens=800))


def test_review_is_bounded_isolated_self_report_not_a_trust_verdict(context):
    store, card, config, worker, outcome, decision = prepared(context)
    before = store_snapshot(store)
    reviewer = Reviewer(valid_answer(decision), cost=.003)
    result = invoke(store, reviewer)
    assert len(reviewer.calls) == 1
    req, role, trial_index, turn = reviewer.calls[0]
    assert role == "process_reviewer" and req.tools == [] and req.params.max_tokens <= 800
    assert req.model_id == "separate-review-model"
    visible = req.model_dump_json()
    assert card.goal in visible
    assert decision["decision_id"] in visible and decision["evidence_refs"][0] in visible
    for secret in (PRIVATE_MARKER, "keys/synth/", "synthetic world generator", "hidden-a", "hidden-b"):
        assert secret not in visible
    assert result["schema_version"] == "treehouse.process-review/1"
    assert result["source"] == "model_estimated" and result["model_id"] == "separate-review-model"
    assert result["rubric_version"] and result["manifest_ref"] == outcome.manifest.manifest_hash
    assert result["cost_usd"] == pytest.approx(.003)
    assert result["findings"] == valid_answer(decision)["findings"]
    assert result["limitations"] == valid_answer(decision)["limitations"]
    assert "Rely" not in json.dumps(result) and "composite" not in result
    assert store_snapshot(store) == before


@pytest.mark.parametrize("bad_kind", ["decision", "evidence", "invalid_json", "invalid_criterion", "missing_findings"])
def test_review_rejects_fabricated_references_or_invalid_output(context, bad_kind):
    store, _, _, _, _, decision = prepared(context)
    output = valid_answer(decision)
    if bad_kind == "decision":
        output["findings"][0]["decision_ids"] = ["invented-decision"]
    elif bad_kind == "evidence":
        output["findings"][0]["evidence_refs"] = ["r-never-issued"]
    elif bad_kind == "invalid_json":
        output = "not JSON"
    elif bad_kind == "invalid_criterion":
        output["findings"][0]["criterion"] = "rhetorical_fluency"
    else:
        output = {"limitations": []}
    reviewer = Reviewer(output)
    before = store_snapshot(store)
    with pytest.raises((ValueError, RuntimeError)):
        invoke(store, reviewer)
    assert len(reviewer.calls) == 1 and store_snapshot(store) == before


def test_unknown_reviewer_cost_is_not_reported_as_zero(context):
    store, _, _, _, _, decision = prepared(context)
    result = invoke(store, Reviewer(valid_answer(decision), cost=None))
    assert result["cost_usd"] is None and result["source"] == "model_estimated"


@pytest.mark.parametrize("identity", ["configured", "observed"])
def test_worker_model_cannot_be_its_own_reviewer(context, identity):
    store, _, config, _, _, decision = prepared(context)
    reviewer = Reviewer(valid_answer(decision))
    with pytest.raises((ValueError, RuntimeError)):
        invoke(store, reviewer, model_id=config.worker.model_key if identity == "configured" else "independent-test")
    assert reviewer.calls == []


def test_review_rejects_provider_response_from_observed_worker_model(context):
    store, _, _, _, _, decision = prepared(context)
    reviewer = Reviewer(valid_answer(decision), response_model_id="independent-test")
    before = store_snapshot(store)
    with pytest.raises((ValueError, RuntimeError)):
        invoke(store, reviewer)
    assert len(reviewer.calls) == 1 and store_snapshot(store) == before
