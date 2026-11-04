"""Regression tests for the judged P6 review doubts (judge-p6.md): ledger safety, prices, ambiguous failures,
usage-before-parse, single price source, profile pricing, failure-path events, pixel cache, probe fixes."""

from __future__ import annotations

import asyncio
import json
import threading
import time
import warnings
from pathlib import Path

import pytest

boto3 = pytest.importorskip("boto3")
from botocore.exceptions import (  # noqa: E402
    ConnectionClosedError,
    EndpointConnectionError,
    ReadTimeoutError,
)
from botocore.stub import Stubber  # noqa: E402
from typer.testing import CliRunner  # noqa: E402

from treehouse.cli import app  # noqa: E402
from treehouse.probe import classify, near_matches, redact_arn, scrub, tiny_png  # noqa: E402
from treehouse.providers import bedrock as bedrock_mod  # noqa: E402
from treehouse.providers.bedrock import (  # noqa: E402
    BedrockConverseProvider,
    BedrockError,
    BedrockRetriesExhausted,
    BedrockValidationError,
    UnsupportedImage,
    estimate_input_tokens,
)
from treehouse.providers.prices import (  # noqa: E402
    GEO_PREMIUM,
    Price,
    PriceError,
    PriceTable,
    load_fixture,
    profile_of,
)
from treehouse.providers.registry import ModelRegistry  # noqa: E402
from treehouse.providers.spend import (  # noqa: E402
    LedgerCorrupt,
    LedgerMissing,
    SpendError,
    SpendLedger,
    SpendWarning,
)
from treehouse.schemas.config import InferenceParams  # noqa: E402
from treehouse.schemas.model_io import Image, Message, ModelRequest, Text, ToolSpec, Usage  # noqa: E402

PARAMS = InferenceParams(max_tokens=64)


def new_ledger(path, **kw):
    kw.setdefault("allow_synthetic", True)
    kw.setdefault("prices", load_fixture())
    led = SpendLedger(path, **kw)
    led.init(note="test")
    return led


async def _nosleep(_s):
    return None


def run(coro):
    return asyncio.run(coro)


def text_req(model="claude-sonnet-5-5", **kw) -> ModelRequest:
    return ModelRequest(model_id=model, system="s", messages=[Message(role="user", content=[Text(text="hi")])],
                        params=kw.pop("params", PARAMS), **kw)


def ok_response(content=None, usage=True):
    r = {"output": {"message": {"role": "assistant", "content": content or [{"text": "ok"}]}},
         "stopReason": "end_turn", "metrics": {"latencyMs": 5}}
    if usage:
        r["usage"] = {"inputTokens": 100, "outputTokens": 10, "totalTokens": 110}
    return r


class RaisingClient:
    def __init__(self, exc=None, block: threading.Event | None = None, response=None):
        self.exc, self.block, self.response, self.calls = exc, block, response, 0

    def converse(self, **kw):
        self.calls += 1
        if self.block is not None:
            self.block.wait(5)
        if self.exc is not None:
            raise self.exc
        return self.response


def provider(ledger, client, **kw):
    return BedrockConverseProvider(lambda _r: client, ModelRegistry.load(), None, ledger, "us-east-1",
                                   sleep=_nosleep, **kw)


# -- B1: the ledger never silently restarts at $0 ---------------------------------------------------------
def test_b1_reserve_refuses_missing_or_genesisless_ledger(tmp_path):
    led = SpendLedger(tmp_path / "missing.jsonl", prices=load_fixture(), allow_synthetic=True)
    with pytest.raises(LedgerMissing, match="budget init"):
        led.reserve("claude-sonnet-5-5", 10, 10)
    assert not (tmp_path / "missing.jsonl").exists()  # reserve did not create a fresh $0 file
    (tmp_path / "nogen.jsonl").write_text('{"kind":"commit","id":"a","usd":1.0}\n')
    with pytest.raises(LedgerMissing):
        SpendLedger(tmp_path / "nogen.jsonl", prices=load_fixture(), allow_synthetic=True).reserve("nova-pro", 1, 1)
    good = new_ledger(tmp_path / "s.jsonl")
    with pytest.raises(SpendError, match="already exists"):
        good.init()


def test_b1_torn_final_line_tolerated_and_sealed_midfile_garbage_raises(tmp_path):
    p = tmp_path / "s.jsonl"
    led = new_ledger(p)
    led.commit(led.reserve("nova-pro", 1000, 100), Usage(input_tokens=1000, output_tokens=100))
    spent = led.status().spent_usd
    with open(p, "a") as f:
        f.write('{"kind":"commit","id":"zz","us')  # crash mid-append
    with pytest.warns(SpendWarning, match="torn"):
        assert led.status().spent_usd == pytest.approx(spent)
    with pytest.warns(SpendWarning):
        r = led.reserve("nova-pro", 10, 10)  # the write seals the torn line
    led.release(r)
    lines = p.read_text().splitlines()
    assert json.loads(lines[4])["kind"] == "torn"  # genesis, reserve, commit, torn fragment, seal
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert led.status().spent_usd == pytest.approx(spent)  # sealed: no warning, no error
    p.write_text(p.read_text() + "<<<<<<< HEAD\n" + lines[-1] + "\n")
    with pytest.raises(LedgerCorrupt, match="do NOT delete"):
        led.status()


def test_b1_budget_status_flags_wrong_ledger(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / ".spend").mkdir(parents=True)
    monkeypatch.setattr("treehouse.providers.spend.repo_ledger_path", lambda: root / ".spend" / "spend.jsonl")
    repo = new_ledger(root / ".spend" / "spend.jsonl")
    repo.commit(repo.reserve("nova-pro", 10, 10), Usage(input_tokens=10, output_tokens=10))
    other = tmp_path / "elsewhere.jsonl"
    new_ledger(other)
    monkeypatch.setenv("TREEHOUSE_SPEND_LEDGER", str(other))
    r = CliRunner().invoke(app, ["budget", "status"])
    assert r.exit_code == 4 and "WRONG LEDGER" in r.output


# -- B2: implausible prices are refused ----------------------------------------------------------------------
@pytest.mark.parametrize("row", [
    {"input": 0.0, "output": 0.015},          # zero: free calls bypass the hard stop
    {"input": 0.000003, "output": 0.000015},  # per-token value written as per-1K: 1000x too small
    {"input": 3.0, "output": 15.0},           # per-1M value written as per-1K
])
def test_b2_implausible_real_table_refused(row):
    with pytest.raises((PriceError, ValueError)):
        PriceTable(version="real", region="us-east-1", models={"claude-sonnet-5-5@us": Price(**row)})


def test_b2_synthetic_and_placeholder_tables_refused_for_live_spend(tmp_path):
    with pytest.raises(SpendError, match="synthetic"):
        SpendLedger(tmp_path / "s.jsonl", prices=load_fixture())
    from treehouse.providers.prices import load_probe_ceiling
    with pytest.raises(SpendError):
        SpendLedger(tmp_path / "s.jsonl", prices=load_probe_ceiling())


def test_b2_prices_check_prints_per_million_and_rejects_band(tmp_path):
    good = tmp_path / "good.yaml"
    good.write_text("""schema_version: treehouse.prices/1
version: real-1
region: us-east-1
source: test
retrieved: 2026-11-04
models:
  claude-sonnet-5-5@us: {input: 0.0033, output: 0.0165}
  claude-sonnet-5-5@global: {input: 0.003, output: 0.015}
  nova-pro@us: {input: 0.0008, output: 0.0032}
""")
    r = CliRunner().invoke(app, ["prices", "check", "--table", str(good)])
    assert r.exit_code == 0, r.output
    assert "input=$3.3/1M" in r.output and "row claude-sonnet-5-5@us" in r.output
    bad = tmp_path / "bad.yaml"
    bad.write_text(good.read_text().replace("0.0008", "0.0000008"))
    r = CliRunner().invoke(app, ["prices", "check", "--table", str(bad)])
    assert r.exit_code == 1 and "implausible" in r.output


# -- M3: ambiguous failures book the worst case; known-unbilled ones release -------------------------------------
@pytest.mark.parametrize("exc,booked", [
    (ReadTimeoutError(endpoint_url="https://x"), True),
    (ConnectionClosedError(endpoint_url="https://x"), True),
    (RuntimeError("unknown"), True),
    (EndpointConnectionError(endpoint_url="https://x"), False),
])
def test_m3_ambiguous_failure_commits_worst_case(tmp_path, exc, booked):
    led = new_ledger(tmp_path / "s.jsonl")
    p = provider(led, RaisingClient(exc))
    with pytest.raises(Exception) as ei:
        run(p.complete(text_req(), role="worker", trial_index=0, turn=0))
    st = led.status()
    assert st.open_reservations == [] and st.reserved_usd == 0
    if booked:
        assert st.calls == 1 and st.spent_usd > 0 and st.ambiguous_usd == pytest.approx(st.spent_usd)
        assert ei.value.cost_usd == pytest.approx(st.spent_usd)
    else:
        assert st.calls == 0 and st.spent_usd == 0


def test_m3_service_error_releases(tmp_path):
    led = new_ledger(tmp_path / "s.jsonl")
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    stub = Stubber(client)
    stub.add_client_error("converse", service_error_code="ThrottlingException", http_status_code=429)
    stub.activate()
    p = BedrockConverseProvider(lambda _r: client, ModelRegistry.load(), None, led, max_attempts=1, sleep=_nosleep)
    with pytest.raises(BedrockRetriesExhausted):
        run(p.complete(text_req(), role="worker", trial_index=0, turn=0))
    assert led.status().calls == 0 and led.status().reserved_usd == 0


def test_m3_cancel_mid_call_commits_worst_case(tmp_path):
    led = new_ledger(tmp_path / "s.jsonl")
    gate = threading.Event()
    p = provider(led, RaisingClient(block=gate, response=ok_response()))

    async def go():
        t = asyncio.create_task(p.complete(text_req(), role="worker", trial_index=0, turn=0))
        await asyncio.sleep(0.05)
        t.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t
        gate.set()

    run(go())
    st = led.status()
    assert st.calls == 1 and st.ambiguous_usd > 0 and st.reserved_usd == 0


# -- M4: usage is committed before content mapping; stale reservations can be resolved --------------------
def test_m4_unmappable_response_still_commits_usage(tmp_path):
    led = new_ledger(tmp_path / "s.jsonl")
    bad = ok_response(content=[{"toolUse": {"toolUseId": "t", "input": {}}}])  # no name
    p = provider(led, RaisingClient(response=bad))
    with pytest.raises(BedrockError) as ei:
        run(p.complete(text_req(), role="worker", trial_index=0, turn=0))
    st = led.status()
    assert ei.value.code == "MalformedResponse" and st.calls == 1 and st.open_reservations == []
    assert st.ambiguous_usd == 0 and st.spent_usd > 0 and ei.value.cost_usd == pytest.approx(st.spent_usd)


def test_m4_response_without_usage_books_worst_case(tmp_path):
    led = new_ledger(tmp_path / "s.jsonl")
    p = provider(led, RaisingClient(response=ok_response(usage=False)))
    with pytest.raises(BedrockError):
        run(p.complete(text_req(), role="worker", trial_index=0, turn=0))
    assert led.status().ambiguous_usd > 0 and led.status().reserved_usd == 0


def test_m4_open_and_release_stale(tmp_path, monkeypatch):
    p = tmp_path / "s.jsonl"
    led = new_ledger(p)
    r1 = led.reserve("nova-pro", 1000, 1000)
    led.reserve("nova-pro", 1000, 1000)
    monkeypatch.setenv("TREEHOUSE_SPEND_LEDGER", str(p))
    out = CliRunner().invoke(app, ["budget", "open"]).output
    assert r1.id in out and "2 open reservation(s)" in out
    r = CliRunner().invoke(app, ["budget", "release-stale", "--older-than-min", "0", "--reason", "crashed K3"])
    assert r.exit_code == 0 and "2 stale reservation(s) booked as spent" in r.output
    st = led.status()
    assert st.open_reservations == [] and st.spent_usd == pytest.approx(2 * r1.worst_usd) and st.ambiguous_usd > 0


# -- M5: one price source ---------------------------------------------------------------------------
def test_m5_provider_and_ledger_tables_must_match(tmp_path):
    led = new_ledger(tmp_path / "s.jsonl")
    other = PriceTable(version="other", region="us-east-1", synthetic=True,
                       models={"claude-sonnet-5-5@us": Price(input=0.001, output=0.002)})
    with pytest.raises(ValueError, match="only price source"):
        BedrockConverseProvider(None, ModelRegistry.load(), other, led)
    p = BedrockConverseProvider(None, ModelRegistry.load(), None, led)
    assert p.price_table_version == load_fixture().version


# -- M6: prices per (model, profile); fall back to the most expensive (+geo premium) -----------------------
def test_m6_profile_rows_and_conservative_fallback():
    t = PriceTable(version="r", region="us-east-1", models={
        "m@global": Price(input=0.003, output=0.015), "m@us": Price(input=None, output=None)})
    assert profile_of("us.anthropic.x") == "us" and profile_of("amazon.nova-pro-v1:0") is None
    p, row = t.resolve("m", "us")
    assert p.output == pytest.approx(0.015 * GEO_PREMIUM) and "x1.1" in row
    assert t.price("m", "global").output == 0.015
    t2 = t.model_copy(update={"models": {**t.models, "m@us": Price(input=0.0033, output=0.0165)}})
    assert t2.resolve("m", "us") == (Price(input=0.0033, output=0.0165), "m@us")


# -- M7: retry events reach the span on the failure path ---------------------------------------------
def test_m7_failed_call_keeps_retry_events_on_span(tmp_path):
    from treehouse.clock import LogicalClock
    from treehouse.gateway.budget import BudgetGuard
    from treehouse.harness.plain_loop import PlainLoop
    from treehouse.ids import IdSource
    from treehouse.schemas.config import Budget
    from treehouse.trace.chain import ChainedJsonlWriter
    from treehouse.trace.tracer import TrialTracer

    class NoTools:
        def specs(self):
            return []

    led = new_ledger(tmp_path / "s.jsonl")
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    stub = Stubber(client)
    for _ in range(2):
        stub.add_client_error("converse", service_error_code="ThrottlingException", http_status_code=429)
    stub.activate()
    p = BedrockConverseProvider(lambda _r: client, ModelRegistry.load(), None, led, max_attempts=2, sleep=_nosleep)
    base = {k: "x" for k in ("treehouse.task.id", "treehouse.task.hash", "treehouse.run.id", "treehouse.trial.id",
                             "treehouse.role", "treehouse.config.hash")} | {"treehouse.trial.index": 0}
    ids = IdSource(1)
    path = tmp_path / "t.jsonl"
    tr = TrialTracer(ChainedJsonlWriter.for_trial(path, "t-0"), trace_id=ids.trace_id(), clock=LogicalClock(),
                     ids=ids, base_attrs=base)
    with pytest.raises(BedrockRetriesExhausted):
        run(PlainLoop(model_id="claude-sonnet-5-5", params=PARAMS).run(
            system="s", user="u", provider=p, gateway=NoTools(), tracer=tr, budget=BudgetGuard(Budget(usd=1.0)),
            max_turns=2, role="worker", trial_index=0))
    tr.close()
    recs = [json.loads(line) for line in path.read_text().splitlines()]
    chat = [c.get("rec", c) for c in recs]
    chat = [c for c in chat if c.get("op") == "chat"][0]
    assert [e["name"] for e in chat["events"]] == ["treehouse.retry", "treehouse.retry"]


# -- M8: each image is decoded once per provider ----------------------------------------------------------
def test_m8_pixel_verification_cached(tmp_path, monkeypatch):
    led = new_ledger(tmp_path / "s.jsonl")
    calls = []
    real = bedrock_mod.decode_png
    monkeypatch.setattr(bedrock_mod, "decode_png", lambda b, f: calls.append(1) or real(b, f))
    png, sha = tiny_png()
    img = Image(format="png", sha256=sha, bytes_=png)
    req = ModelRequest(model_id="claude-sonnet-5-5", system="s", params=PARAMS,
                       messages=[Message(role="user", content=[Text(text="a"), img, img])])
    p = BedrockConverseProvider(None, ModelRegistry.load(), None, led)
    p.prepare(req)
    p.prepare(req)
    assert len(calls) == 1


# -- M9/M10: probe classification, no sampling params, discovered ids ---------------------------------------
def test_m9_validation_exception_classified_with_reason():
    from botocore.exceptions import ClientError

    def ve(msg):
        return ClientError({"Error": {"Code": "ValidationException", "Message": msg}}, "Converse")

    assert classify(ve("The provided model identifier is invalid.")) == "unavailable"
    assert classify(ve("Invocation of model ID x with on-demand throughput isn't supported.")) == "unavailable"
    assert classify(ve("temperature is not supported for this model")) == "invalid_request"


def test_m9_probe_request_has_no_sampling_params(tmp_path):
    from treehouse.probe import Probe

    pr = Probe(lambda s: None, region="us-east-1", registry=ModelRegistry.load(), ledger=new_ledger(tmp_path / "s"))
    for mode in ("user_turn", "tool_result"):
        req = pr._request(ModelRegistry.load().get("claude-sonnet-5-5"), mode)
        assert req.params.temperature is None and req.params.top_p is None


def test_m10_near_matches_find_suffixed_ids():
    e = ModelRegistry.load().get("claude-sonnet-5-5")
    profiles = {"us.anthropic.claude-sonnet-5-5-20261001-v1:0", "us.anthropic.claude-sonnet-5-5",
                "eu.anthropic.claude-sonnet-5-5-20261001-v1:0", "global.anthropic.claude-sonnet-5-5-20261001-v1:0"}
    fms = {"anthropic.claude-sonnet-5-5-20261001-v1:0", "anthropic.claude-haiku-5"}
    assert near_matches(e, profiles, fms) == ["global.anthropic.claude-sonnet-5-5-20261001-v1:0",
                                              "us.anthropic.claude-sonnet-5-5-20261001-v1:0",
                                              "anthropic.claude-sonnet-5-5-20261001-v1:0"]


# -- M12: reconcile with the AWS bill ---------------------------------------------------------------------
def test_m12_reconcile_recorded_and_shown(tmp_path, monkeypatch, isolated_repo_ledger):
    p = tmp_path / "s.jsonl"
    new_ledger(p)
    monkeypatch.setenv("TREEHOUSE_SPEND_LEDGER", str(p))
    r = CliRunner().invoke(app, ["budget", "reconcile", "--aws-usd", "40", "--source", "ce"])
    assert r.exit_code == 2 and "STOP" in r.output  # AWS far above the ledger
    r = CliRunner().invoke(app, ["budget", "status"])
    assert "last AWS reconcile" in r.output and "+40.00" in r.output


# -- minors -------------------------------------------------------------------------------------------
def test_minor13_max_image_px_enforced_and_tools_allowance(tmp_path):
    import numpy as np

    from treehouse.pixels import array_sha256

    led = new_ledger(tmp_path / "s.jsonl")
    reg = ModelRegistry.load()
    small = reg.get("claude-sonnet-5-5").model_copy(update={"max_image_px": 4})
    p = BedrockConverseProvider(None, ModelRegistry(defaults=reg.defaults, models=[small, reg.get("nova-pro")]),
                                None, led)
    png, sha = tiny_png()  # 8x8
    req = ModelRequest(model_id="claude-sonnet-5-5", system="s", params=PARAMS,
                       messages=[Message(role="user", content=[Image(format="png", sha256=sha, bytes_=png)])])
    with pytest.raises(UnsupportedImage, match="max_image_px"):
        p.prepare(req)
    assert array_sha256(np.zeros((1, 1), dtype=np.uint8))  # pixels helper importable
    tool = ToolSpec(name="t", description="d", input_schema={"type": "object"})
    assert estimate_input_tokens(text_req(tools=[tool])) >= estimate_input_tokens(text_req()) + 1000


def test_minor20_bypass_knobs_clamped(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="HARD_STOP_OVERRIDE"):
        SpendLedger(tmp_path / "s", hard_stop=1000)
    led = new_ledger(tmp_path / "s.jsonl")
    with pytest.raises(ValueError, match="unpriced_cap_usd"):
        BedrockConverseProvider(None, ModelRegistry.load(), None, led, unpriced_cap_usd=5.0)
    p = BedrockConverseProvider(None, ModelRegistry.load(), None, led, unpriced_cap_usd=0.25)
    with pytest.raises(BedrockValidationError, match="max_tokens"):
        run(p.complete(text_req(), role="probe", trial_index=0, turn=0))


def test_minor17_region_mismatch_refused(tmp_path):
    led = new_ledger(tmp_path / "s.jsonl")
    with pytest.raises(ValueError, match="us-east-1"):
        BedrockConverseProvider(None, ModelRegistry.load(), None, led, "us-west-2")
    p = BedrockConverseProvider(None, ModelRegistry.load(), None, SpendLedger(tmp_path / "x"), "us-west-2")
    with pytest.raises(BedrockValidationError, match="registered in us-east-1"):
        p.prepare(text_req())


def test_minor23_temperature_and_top_p_refused_for_claude(tmp_path):
    p = BedrockConverseProvider(None, ModelRegistry.load(), None, new_ledger(tmp_path / "s.jsonl"))
    with pytest.raises(BedrockValidationError, match="top_p"):
        p.prepare(text_req(params=InferenceParams(max_tokens=8, temperature=0.1, top_p=0.9)))


def test_minor15_redaction():
    assert redact_arn("arn:aws:sts::123456789012:assumed-role/WSParticipantRole/Participant") == \
        "assumed-role/WSParticipantRole"
    assert "123456789012" not in scrub("User: arn:aws:sts::123456789012:assumed-role/R/s is not authorized")
    assert ".treehouse/" in (Path(__file__).resolve().parents[2] / ".gitignore").read_text()


def test_minor22_replay_span_ledger_cost_zero_attribute():
    src = (Path(__file__).resolve().parents[2] / "src/treehouse/harness/plain_loop.py").read_text()
    assert '"treehouse.cost.ledger_usd", 0.0' in src


def test_overshoot_recorded(tmp_path):
    led = new_ledger(tmp_path / "s.jsonl")
    r = led.reserve("nova-pro", 10, 10)
    with pytest.warns(SpendWarning, match="reserved"):
        led.commit(r, Usage(input_tokens=100_000, output_tokens=0))
    assert led.status().overshoot_usd > 0
    assert time.time() > 0
