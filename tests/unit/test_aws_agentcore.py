"""T3: AgentCore Evaluations integration, offline. Real replayed demo runs; botocore Stubber for Evaluate."""

from __future__ import annotations

import json

import boto3
import pytest
from botocore.stub import Stubber

from treehouse import service
from treehouse.aws import agentcore as ac
from treehouse.aws.lambda_evaluator import handler
from treehouse.schemas.config import RunConfig
from treehouse.store.local import LocalStore


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    store = LocalStore(tmp_path_factory.mktemp("store"))
    out = {}
    for rid in ("synth-good", "synth-fabricator", "synth-key-peeker"):
        cfg = RunConfig.model_validate_json((service.demo_root() / "configs" / f"{rid}.json").read_bytes())
        service.run(store, cfg, run_id=rid, mode="replay")
        out[rid] = service.load_sealed(store, rid)
    return store, out


def _event(run, level, **kw):
    return {"schemaVersion": "1.0", "evaluatorId": "treehouse-abc", "evaluatorName": "treehouse_rules",
            "evaluationLevel": level, "evaluationInput": {"sessionSpans": ac.session_spans(run)},
            "evaluationReferenceInputs": [], "evaluationTarget": None, **kw}


# --- span conversion ---------------------------------------------------------------------------------------

def test_session_spans_are_otel_span_logs(runs):
    _, r = runs
    run = r["synth-good"]
    spans = ac.session_spans(run)
    trial = run.trials[0]
    assert len(spans) == len(trial.spans)
    s0 = spans[0]
    assert set(s0) >= {"traceId", "spanId", "parentSpanId", "name", "kind", "startTimeUnixNano",
                       "endTimeUnixNano", "durationNano", "attributes", "status", "resource", "scope"}
    assert {s["attributes"]["session.id"] for s in spans} == {run.run_id}
    assert {s["traceId"] for s in spans} == {trial.spans[0].trace_id}
    tools = [s for s in spans if s["attributes"]["gen_ai.operation.name"] == "execute_tool"]
    assert len(tools) == len(trial.calls) and all(ac.TOOL_PAYLOAD_ATTR in s["attributes"] for s in tools)
    roots = [s for s in spans if ac.CARD_ATTR in s["attributes"]]
    assert len(roots) == 1 and roots[0]["parentSpanId"] == ""
    assert len(json.loads(roots[0]["attributes"][ac.CLAIMS_ATTR])) == len(trial.claims)
    json.dumps(spans)  # must be plain JSON for the API


# --- reference inputs ----------------------------------------------------------------------------------------

def test_reference_inputs_from_card(runs):
    _, r = runs
    run = r["synth-good"]
    refs = ac.reference_inputs(run)
    assert len(refs) == 1
    s = refs[0]
    assert s["context"] == {"spanContext": {"sessionId": run.run_id}}
    assert s["expectedTrajectory"] == {"toolNames": ["imagery_window"]}
    texts = [a["text"] for a in s["assertions"]]
    assert len(texts) == len(run.card.must_notice) + len(run.card.known_limits)
    assert "The agent uses the imagery_window tool." in texts
    assert any("cloud, obscured, haze" in t for t in texts)


def test_expected_response_is_trace_scoped_and_validated(runs):
    _, r = runs
    run = r["synth-good"]
    tid = run.trials[0].spans[0].trace_id
    keyed = any(s.keying.mode != "unkeyed" for s in run.card.steps)
    if not keyed:
        with pytest.raises(ValueError, match="unkeyed"):
            ac.reference_inputs(run, {tid: "x"})
        return
    refs = ac.reference_inputs(run, {tid: "12 crossings, 3 damaged"})
    assert refs[1] == {"context": {"spanContext": {"sessionId": run.run_id, "traceId": tid}},
                       "expectedResponse": {"text": "12 crossings, 3 damaged"}}
    with pytest.raises(ValueError, match="not in the run"):
        ac.reference_inputs(run, {"deadbeef": "x"})


# --- evaluate wrapper ----------------------------------------------------------------------------------------

def _stubbed():
    client = boto3.client("bedrock-agentcore", region_name="us-east-1")
    return client, Stubber(client)


def _res(ev, **kw):
    return {"evaluatorArn": f"arn:aws:bedrock-agentcore:::evaluator/{ev}", "evaluatorId": ev, "evaluatorName": ev,
            "context": {"spanContext": {"sessionId": "synth-good"}}, **kw}


def test_evaluate_success_error_and_ignored_fields(runs):
    _, r = runs
    run = r["synth-good"]
    client, stub = _stubbed()
    spans, refs = ac.session_spans(run), ac.reference_inputs(run)
    ok = _res("Builtin.TrajectoryInOrderMatch", label="Pass", value=1.0, explanation="in order",
              ignoredReferenceInputFields=["assertions"])
    bad = _res("Builtin.GoalSuccessRate", errorCode="ValidationException", errorMessage="no messages")
    for ev, res in (("Builtin.TrajectoryInOrderMatch", ok), ("Builtin.GoalSuccessRate", bad)):
        stub.add_response("evaluate", {"evaluationResults": [res]},
                          {"evaluatorId": ev, "evaluationInput": {"sessionSpans": spans},
                           "evaluationReferenceInputs": refs})
    with stub:
        out = ac.run_agentcore_eval(run, ["Builtin.TrajectoryInOrderMatch", "Builtin.GoalSuccessRate"], client=client)
    stub.assert_no_pending_responses()
    assert [o.ok for o in out] == [True, False]
    assert out[0].label == "Pass" and out[0].value == 1.0 and out[0].ignored_reference_fields == ["assertions"]
    assert out[1].error_code == "ValidationException" and out[1].label is None
    assert out[0].raw == ok and out[1].raw == bad


def test_evaluate_reference_free_omits_references(runs):
    _, r = runs
    run = r["synth-good"]
    client, stub = _stubbed()
    stub.add_response("evaluate", {"evaluationResults": [_res("treehouse-x", label="PASS")]},
                      {"evaluatorId": "treehouse-x", "evaluationInput": {"sessionSpans": ac.session_spans(run)}})
    with stub:
        out = ac.run_agentcore_eval(run, ["treehouse-x"], client=client, references=[])
    assert out[0].label == "PASS"


def test_evaluate_api_error_propagates(runs):
    _, r = runs
    client, stub = _stubbed()
    stub.add_client_error("evaluate", "AccessDeniedException", "no")
    with stub, pytest.raises(client.exceptions.ClientError):
        ac.run_agentcore_eval(r["synth-good"], ["Builtin.GoalSuccessRate"], client=client)


def test_oversize_session_is_refused(runs, monkeypatch):
    _, r = runs
    monkeypatch.setattr(ac, "MAX_INPUT_BYTES", 10)
    with pytest.raises(ValueError, match="at most 10"):
        ac.run_agentcore_eval(r["synth-good"], ["x"], client=object())


def test_record_is_append_only_outside_verified_tree(runs):
    store, r = runs
    run = r["synth-good"]
    res = [ac.AgentCoreResult.from_raw(_res("e", label="PASS"))]
    k1 = ac.record_results(store, run, ["e"], res)
    k2 = ac.record_results(store, run, ["e"], res)
    assert k1.startswith("comparisons/agentcore/synth-good/") and k1 != k2  # evaluated_at differs: two records
    rec = json.loads((store.root / k1).read_text())
    assert rec["manifest_hash"] == run.manifest_ref and rec["results"][0]["label"] == "PASS"
    from treehouse.store.verify import verify
    assert verify(store).ok


# --- Lambda code-based evaluator --------------------------------------------------------------------------

def test_lambda_trace_rules_pass_and_fail(runs):
    _, r = runs
    good = handler(_event(r["synth-good"], "TRACE"))
    assert good["label"] == "PASS" and good["value"] == 1.0
    fab = handler(_event(r["synth-fabricator"], "TRACE"))
    assert fab["label"] == "FAIL" and fab["value"] < 1.0 and "R4:fabrication" in fab["explanation"]
    assert set(good) <= {"label", "value", "explanation"}


def test_lambda_trace_respects_target(runs):
    _, r = runs
    res = handler(_event(r["synth-good"], "TRACE", evaluationTarget={"traceIds": ["not-a-trace"]}))
    assert res["label"] == "NO_CLAIMS" and "value" not in res


def test_lambda_session_guard(runs):
    _, r = runs
    good = handler(_event(r["synth-good"], "SESSION"))
    assert good["label"] == "PASS", good
    peek = handler(_event(r["synth-key-peeker"], "SESSION"))
    assert peek["label"] == "FAIL" and "forbidden-source accesses=2" in peek["explanation"]


@pytest.mark.parametrize("mutate,needle", [
    (lambda e: e.update(schemaVersion="2.0"), "schemaVersion"),
    (lambda e: e.update(evaluationLevel="TOOL_CALL"), "TOOL_CALL"),
    (lambda e: e.update(evaluationInput={}), "sessionSpans"),
    (lambda e: [s["attributes"].pop("treehouse.card", None) for s in e["evaluationInput"]["sessionSpans"]],
     "treehouse.card"),
    (lambda e: [s["attributes"].update({"treehouse.task.hash": "sha256:00"})
                for s in e["evaluationInput"]["sessionSpans"]], "does not match"),
])
def test_lambda_error_response(runs, mutate, needle):
    _, r = runs
    ev = _event(r["synth-good"], "TRACE")
    mutate(ev)
    out = handler(ev)
    assert set(out) == {"errorCode", "errorMessage"} and out["errorCode"] == "VALIDATION_FAILED"
    assert needle in out["errorMessage"]


def test_lambda_module_is_import_light():
    import subprocess
    import sys
    code = ("import sys\nfor m in ['boto3','botocore','strands','rasterio','numpy','scipy','yaml']: sys.modules[m]=None\n"
            "import treehouse.aws.lambda_evaluator\n")
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr


# --- CLI -----------------------------------------------------------------------------------------------------

def test_cli_writes_comparison_record(runs, monkeypatch, capsys):
    import importlib.util
    from pathlib import Path
    store, r = runs
    spec = importlib.util.spec_from_file_location(
        "agentcore_eval", Path(__file__).resolve().parents[2] / "scripts" / "agentcore_eval.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    client, stub = _stubbed()
    stub.add_response("evaluate", {"evaluationResults": [_res("Builtin.TrajectoryInOrderMatch", label="Pass",
                                                              value=1.0)]})
    monkeypatch.setattr(boto3, "client", lambda *a, **k: client)
    with stub:
        rc = mod.main(["--run", str(store.run_dir("synth-good")), "--evaluators", "Builtin.TrajectoryInOrderMatch"])
    out = capsys.readouterr().out
    assert rc == 0 and '"label": "Pass"' in out and "comparisons/agentcore/synth-good/" in out
    assert mod.main(["--run", str(store.root), "--evaluators", "x"]) == 2
