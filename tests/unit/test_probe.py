"""K1 probe (AWS-B1): Stubber-driven, golden schema, classification never aborts, cap and reservations."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

boto3 = pytest.importorskip("boto3")
from botocore.exceptions import ClientError  # noqa: E402
from botocore.stub import Stubber  # noqa: E402

from treehouse.probe import PER_CALL_CAP_USD, Probe, classify  # noqa: E402
from treehouse.providers.registry import ModelRegistry  # noqa: E402
from treehouse.providers.spend import SpendLedger  # noqa: E402
from treehouse.schemas.probe import AwsCapabilities, ProbeSpend  # noqa: E402

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "schema" / "aws-capabilities.json"
ACCOUNT = "123456789012"
NOW = datetime(2026, 11, 4, tzinfo=UTC)

def new_ledger(*a, **kw):
    """A test ledger: synthetic tables allowed, genesis written (B1: reserve refuses an un-initialised file)."""
    kw.setdefault("allow_synthetic", True)
    led = SpendLedger(*a, **kw)
    if not led.initialized:
        led.init(note="test")
    return led



def converse_ok(text="mixed"):
    return {"output": {"message": {"role": "assistant", "content": [{"text": text}]}}, "stopReason": "end_turn",
            "usage": {"inputTokens": 90, "outputTokens": 2, "totalTokens": 92}, "metrics": {"latencyMs": 300}}


class Clients:
    """Real boto3 clients with a Stubber each; every Converse call is checked for an open reservation."""

    def __init__(self, ledger: SpendLedger) -> None:
        self.ledger = ledger
        self.clients, self.stubs = {}, {}
        self.converse_calls = 0
        self.unreserved_calls = 0

    def __call__(self, service: str):
        if service not in self.clients:
            c = boto3.client(service, region_name="us-east-1")
            self.clients[service] = c
            self.stubs[service] = Stubber(c)
            self.stubs[service].activate()
            if service == "bedrock-runtime":
                c.meta.events.register("before-parameter-build.bedrock-runtime.Converse", self._on_converse)
        return self.clients[service]

    def _on_converse(self, **kw):
        self.converse_calls += 1
        if self.ledger.status().reserved_usd <= 0:
            self.unreserved_calls += 1

    def stub(self, service: str) -> Stubber:
        self(service)
        return self.stubs[service]


def queue_happy(cl: Clients, *, bucket=True, converse=4):
    cl.stub("sts").add_response("get_caller_identity", {"Account": ACCOUNT, "Arn": f"arn:aws:sts::{ACCOUNT}:x",
                                                        "UserId": "u"})
    b = cl.stub("bedrock")
    b.add_response("list_foundation_models", {"modelSummaries": [
        {"modelArn": "arn:m1", "modelId": "anthropic.claude-sonnet-5-5", "inputModalities": ["TEXT", "IMAGE"]},
        {"modelArn": "arn:m2", "modelId": "amazon.nova-pro-v1:0", "inputModalities": ["TEXT", "IMAGE"]}]})
    b.add_response("list_inference_profiles", {"inferenceProfileSummaries": [
        {"inferenceProfileName": n, "inferenceProfileArn": "arn:p:" + n, "models": [{"modelArn": "arn:m"}], "inferenceProfileId": n,
         "status": "ACTIVE", "type": "SYSTEM_DEFINED"}
        for n in ("us.anthropic.claude-sonnet-5-5", "us.amazon.nova-pro-v1:0")]})
    for _ in range(converse):
        cl.stub("bedrock-runtime").add_response("converse", converse_ok())
    cl.stub("service-quotas").add_response("list_service_quotas", {"Quotas": [
        {"QuotaName": "On-demand model inference requests per minute for Amazon Nova Pro", "Value": 100.0,
         "Adjustable": True},
        {"QuotaName": "Something else", "Value": 1.0}]})
    b.add_response("get_model_invocation_logging_configuration", {"loggingConfig": {
        "s3Config": {"bucketName": "logs"}, "imageDataDeliveryEnabled": True, "textDataDeliveryEnabled": True}})
    s3 = cl.stub("s3")
    s3.add_response("list_buckets", {"Buckets": [{"Name": "tb", "CreationDate": NOW}]})
    if bucket:
        s3.add_response("get_bucket_versioning", {"Status": "Enabled"})
        s3.add_client_error("get_object_lock_configuration", service_error_code="ObjectLockConfigurationNotFoundError")
    cl.stub("athena").add_response("list_work_groups", {"WorkGroups": [{"Name": "primary"}]})
    cl.stub("lambda").add_response("list_functions", {"Functions": []})
    lg = cl.stub("logs")
    lg.add_client_error("create_log_group", service_error_code="ResourceAlreadyExistsException")
    lg.add_response("create_log_stream", {})
    lg.add_response("put_retention_policy", {}, {"logGroupName": "/treehouse/probe", "retentionInDays": 1})
    lg.add_response("put_log_events", {})
    cl.stub("stepfunctions").add_response("list_state_machines", {"stateMachines": []})
    cl.stub("bedrock-agentcore-control").add_client_error("list_agent_runtimes",
                                                          service_error_code="AccessDeniedException")
    cl.stub("budgets").add_response("describe_budgets", {"Budgets": []})


@pytest.fixture
def ledger(tmp_path):
    return new_ledger(tmp_path / "spend.jsonl")  # no price table at all: every probe call is unpriced


async def _nosleep(_s):
    return None


def make_probe(cl, ledger, **kw):
    return Probe(cl, region="us-east-1", registry=ModelRegistry.load(), ledger=ledger, sleep=_nosleep, **kw)


def test_happy_path_matches_golden_schema(ledger):
    cl = Clients(ledger)
    queue_happy(cl)
    report = make_probe(cl, ledger, bucket="tb").run()
    for s in cl.stubs.values():
        s.assert_no_pending_responses()
    doc = json.loads(json.dumps(report.model_dump(mode="json")))
    golden = json.loads(GOLDEN.read_text())
    assert golden["properties"]["schema_version"]["const"] == "treehouse.aws-capabilities/v1"
    assert set(golden["required"]) <= set(doc) and set(doc) <= set(golden["properties"])
    assert AwsCapabilities.model_validate(doc) == report
    assert AwsCapabilities.model_json_schema() == golden
    m = {x.key: x for x in report.models}
    assert m["claude-sonnet-5-5"].user_turn_image == "ok" and m["claude-sonnet-5-5"].tool_result_image == "ok"
    assert m["nova-pro"].recommended_image_delivery == "tool_result" and m["nova-pro"].listed is True
    assert m["nova-pro"].image_input is True and m["nova-pro"].profile_listed is True
    st = {c.name: c.status for c in report.checks}
    assert st["s3.get_bucket_versioning:tb"] == "ok" and st["s3.get_object_lock_configuration:tb"] == "ok"
    assert st["bedrock-agentcore-control.list_agent_runtimes"] == "denied"
    assert report.execution["account"] != ACCOUNT and report.execution["account"].endswith(ACCOUNT[-4:])  # minor 15
    assert ACCOUNT not in report.model_dump_json()
    assert report.invocation_logging["image_data_delivery"] is True and "ARE logged" in report.invocation_logging[
        "policy"]
    assert report.quotas == [{"name": "On-demand model inference requests per minute for Amazon Nova Pro",
                              "value": 100.0, "adjustable": True}]
    # AWS-B1: four calls, each reserved at $0.25, committed at placeholder ceiling prices, tagged estimated
    assert cl.converse_calls == 4 and cl.unreserved_calls == 0
    assert report.spend == ProbeSpend(cap_usd=3.0, per_call_cap_usd=0.25, max_tokens=32, reserved_usd=1.0,
                                      committed_usd=report.spend.committed_usd, calls=4, price_table="probe-ceiling-1")
    led = ledger.status()
    assert led.calls == 4 and led.reserved_usd == 0
    assert led.spent_usd == pytest.approx(led.estimated_usd) == pytest.approx(4 * (90 * 0.05 + 2 * 0.25) / 1000)
    assert report.summary["ok"] >= 12


def test_probe_cap_enforced_and_no_call_without_reservation(ledger):
    cl = Clients(ledger)
    queue_happy(cl, bucket=False, converse=2)
    report = make_probe(cl, ledger, cap_usd=0.5).run()
    for s in cl.stubs.values():
        s.assert_no_pending_responses()
    assert cl.converse_calls == 2 and cl.unreserved_calls == 0
    m = {x.key: x for x in report.models}
    assert (m["claude-sonnet-5-5"].user_turn_image, m["claude-sonnet-5-5"].tool_result_image) == ("ok", "ok")
    assert (m["nova-pro"].user_turn_image, m["nova-pro"].tool_result_image) == ("skipped_budget", "skipped_budget")
    assert report.summary["skipped_budget"] == 2 and report.spend.reserved_usd == 0.5
    assert ledger.status().calls == 2


def test_probe_caps_may_only_be_lowered(ledger):
    with pytest.raises(ValueError):
        make_probe(Clients(ledger), ledger, max_tokens=64)
    with pytest.raises(ValueError):
        make_probe(Clients(ledger), ledger, cap_usd=5)
    assert PER_CALL_CAP_USD == 0.25


def test_ledger_hard_stop_reports_skipped_budget(tmp_path):
    from treehouse.providers.prices import Price, PriceTable
    from treehouse.schemas.model_io import Usage

    big = PriceTable(version="b", region="any", synthetic=True, models={"m": Price(input=1.0, output=5.0)})
    led = new_ledger(tmp_path / "s.jsonl", prices=big)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        led.commit(led.reserve("m", 0, 89_990, allow_over_alarm=True, reason="t"),
                   Usage(input_tokens=0, output_tokens=89_990))  # $449.95
    cl = Clients(led)
    queue_happy(cl, bucket=False, converse=0)
    report = make_probe(cl, led).run()
    assert cl.converse_calls == 0
    assert {x.user_turn_image for x in report.models} == {"skipped_budget"}


class Boom:
    """A client whose every method raises the configured error."""

    def __init__(self, exc):
        self.exc = exc

    def __getattr__(self, name):
        def f(*a, **kw):
            raise self.exc
        return f


def test_classification_never_aborts(ledger):
    def err(code):
        return ClientError({"Error": {"Code": code, "Message": "m"}}, "Op")

    plan = {
        "sts": Boom(err("ExpiredToken")),
        "bedrock": Boom(err("AccessDeniedException")),
        "bedrock-runtime": Boom(err("ValidationException")),
        "service-quotas": Boom(err("NoSuchResourceException")),
        "s3": Boom(RuntimeError("socket exploded")),
        "athena": Boom(err("InternalServerException")),
        "lambda": Boom(err("ResourceNotFoundException")),
        "logs": Boom(err("AccessDeniedException")),
        "stepfunctions": Boom(KeyError("x")),
        "bedrock-agentcore-control": Boom(err("UnknownOperationException")),
        "budgets": Boom(err("AccessDeniedException")),
    }

    def factory(service):
        if service == "athena":
            raise RuntimeError("cannot build client")
        return plan[service]

    report = make_probe(factory, ledger, bucket="tb").run()
    st = {c.name: c.status for c in report.checks}
    assert st["sts.get_caller_identity"] == "denied"
    assert st["bedrock.list_foundation_models"] == "denied"
    assert st["s3.list_buckets"] == "error" and st["athena.list_work_groups"] == "error"
    assert st["lambda.list_functions"] == "unavailable"
    assert st["bedrock-agentcore-control.list_agent_runtimes"] == "unavailable"
    assert st["budgets.describe_budgets"] == "error"  # account unknown because sts was denied
    # ValidationException on the first profile -> the alt (global.) profile is tried, then it stops
    names = [c.name for c in report.checks if c.name.startswith("bedrock.converse:claude")]
    assert names == ["bedrock.converse:claude-sonnet-5-5:user_turn:us.anthropic.claude-sonnet-5-5",
                     "bedrock.converse:claude-sonnet-5-5:user_turn:global.anthropic.claude-sonnet-5-5"]
    # M9: a ValidationException that is not about the model id is our request shape, not "unavailable"
    assert {m.user_turn_image for m in report.models} == {"invalid_request"}
    assert ledger.status().reserved_usd == 0 and ledger.status().calls == 0  # failed calls released
    assert sum(report.summary.values()) == len(report.checks)
    AwsCapabilities.model_validate(report.model_dump(mode="json"))


def test_classify_budget_errors():
    from treehouse.providers.spend import BudgetHardStop, UnpricedModel

    assert classify(BudgetHardStop("x")) == "skipped_budget" and classify(UnpricedModel("x")) == "skipped_budget"


def sample_report() -> AwsCapabilities:
    """Used by the `probe import` CLI test."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        led = new_ledger(Path(d) / "s.jsonl")
        cl = Clients(led)
        queue_happy(cl)
        return make_probe(cl, led, bucket="tb").run()


def test_script_entrypoint_runs_with_stubbed_factory(monkeypatch, tmp_path, ledger):
    import importlib.util

    spec = importlib.util.spec_from_file_location("aws_probe", Path(__file__).resolve().parents[2] / "scripts" /
                                                  "aws_probe.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cl = Clients(new_ledger())
    queue_happy(cl, bucket=False)
    monkeypatch.setattr(mod, "default_client_factory", lambda region: cl)
    out = tmp_path / "caps.json"
    assert mod.main(["--out", str(out)]) == 0
    AwsCapabilities.model_validate_json(out.read_text())


def test_probe_import(tmp_path):
    from typer.testing import CliRunner

    from treehouse.cli import app

    p = tmp_path / "aws-capabilities.json"
    p.write_text(json.dumps(sample_report().model_dump(mode="json")))
    r = CliRunner().invoke(app, ["probe", "import", str(p), "--store", str(tmp_path / "store")])
    assert r.exit_code == 0, r.output
    assert (tmp_path / "store/probes/aws-capabilities.json").is_file()
    assert "model nova-pro" in r.output
    (tmp_path / "bad.json").write_text('{"schema_version": "nope"}')
    r = CliRunner().invoke(app, ["probe", "import", str(tmp_path / "bad.json")])
    assert r.exit_code == 1
