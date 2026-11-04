"""Blind verifiers (A5, M17 style): changing only the worker's label, confidence, reason or id leaves both
verifiers' model requests identical, and no worker string reaches them. Abstention, tool restriction and the
provider-wrapper path (cassette key ("verifier", index, 0), chat span) are checked too."""

from __future__ import annotations

import asyncio

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

pytest.importorskip("strands")

from treehouse.canon import canonical_json  # noqa: E402
from treehouse.clock import LogicalClock  # noqa: E402
from treehouse.gateway.base import ToolOutcome  # noqa: E402
from treehouse.gateway.budget import BudgetGuard  # noqa: E402
from treehouse.ids import IdSource  # noqa: E402
from treehouse.providers.cassette import Cassette, RecordingProvider  # noqa: E402
from treehouse.providers.fake import FakeProvider  # noqa: E402
from treehouse.sampling.blind import assemble_verifier_batch  # noqa: E402
from treehouse.schemas.config import Budget, InferenceParams  # noqa: E402
from treehouse.schemas.model_io import Text, ToolSpec  # noqa: E402
from treehouse.schemas.sampling import BlindItem  # noqa: E402
from treehouse.trace.chain import ChainedJsonlWriter, read_chain  # noqa: E402
from treehouse.trace.tracer import TrialTracer  # noqa: E402
from treehouse.verifier.agent import ConverseVerifier, StrandsVerifier, parse_answer  # noqa: E402

BASE = {"treehouse.task.id": "synth-crossings-v1", "treehouse.task.hash": "sha256:" + "0" * 64,
        "treehouse.run.id": "run-0001", "treehouse.trial.id": "v-0", "treehouse.trial.index": 0,
        "treehouse.role": "verifier", "treehouse.config.hash": "sha256:" + "1" * 64}
UNIT = {"unit_id": "u-1", "lon": 85.1, "lat": 27.9, "object_definition": "road bridge", "question_id": "exists",
        "scene_ids": ["SYN-POST-A"]}


class Spy:
    provider_name = "fake"

    def __init__(self, inner):
        self.inner, self.requests = inner, []

    async def complete(self, req, **kw):
        self.requests.append(req)
        return await self.inner.complete(req, **kw)


class WindowGateway:
    def __init__(self, names=("imagery_window",)):
        self.names = names

    def specs(self):
        return [ToolSpec(name=n, description=n, input_schema={"type": "object"}) for n in self.names]

    async def call(self, name, args, *, call_id):
        return ToolOutcome(result_id="r-0001", status="success", content=[Text(text="window")])


def _tracer(path):
    ids, clock = IdSource(5), LogicalClock()
    tr = TrialTracer(ChainedJsonlWriter.for_trial(path, "v-0"), trace_id=ids.trace_id(), clock=clock, ids=ids,
                     base_attrs=BASE)
    return tr, BudgetGuard(Budget(), clock=clock)


def _kw(provider, tracer, guard):
    return dict(model_id="nova-pro", params=InferenceParams(max_tokens=64), provider=provider, tracer=tracer,
                budget=guard, config_hash="sha256:" + "2" * 64, synthetic=True)


def _verify(tmp_path, kind, item, script, n=[0]):  # noqa: B006 - a counter for unique trace paths
    n[0] += 1
    spy = Spy(FakeProvider(script))
    tracer, guard = _tracer(tmp_path / f"{kind}-{n[0]}.jsonl")
    if kind == "converse":
        v = asyncio.run(ConverseVerifier(**_kw(spy, tracer, guard)).verdict(item, index=0, created_seq=7))
    else:
        v = asyncio.run(StrandsVerifier(**_kw(spy, tracer, guard)).verdict(item, index=0, created_seq=7,
                                                                           gateway=WindowGateway()))
    tracer.close()
    return v, spy.requests


YES = [{"respond": {"text": '{"answer": "yes"}'}}]
WINDOW_THEN_NO = [{"respond": {"tool_use": [{"name": "imagery_window", "input": {"scene_id": "SYN-POST-A"}}]}},
                  {"expect": {"contains": "window"}, "respond": {"text": 'I looked. {"answer": "no"}'}}]
worker = st.fixed_dictionaries({
    "label": st.sampled_from(["present", "absent", "damaged"]), "confidence": st.floats(0, 1),
    "reason": st.text(min_size=8, max_size=30).map(lambda s: "WRK-" + s), "worker_id": st.just("WORKER-claude")})


@pytest.mark.parametrize("kind,script", [("converse", YES), ("strands", WINDOW_THEN_NO)])
@settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(a=worker, b=worker)
def test_worker_fields_never_reach_either_verifier(tmp_path, kind, script, a, b):
    (ia,), _ = assemble_verifier_batch([{**UNIT, **a}], [], seed=1, hmac_key=b"k")
    (ib,), _ = assemble_verifier_batch([{**UNIT, **b}], [], seed=1, hmac_key=b"k")
    va, ra = _verify(tmp_path, kind, BlindItem(**ia), script)
    vb, rb = _verify(tmp_path, kind, BlindItem(**ib), script)
    assert [r.key() for r in ra] == [r.key() for r in rb] and va == vb
    blob = "".join(canonical_json(r) for r in ra)
    for s in ("WRK-", "WORKER-claude", "confidence", '"label"'):
        assert s not in blob
    assert va.answer == ("yes" if kind == "converse" else "no") and va.request_hash == ra[-1].key()


def test_converse_verifier_is_one_tool_free_call_on_the_wrapper(tmp_path):
    cas = Cassette()
    tracer, guard = _tracer(tmp_path / "c.jsonl")
    v = ConverseVerifier(**_kw(RecordingProvider(FakeProvider(YES), cas), tracer, guard))
    out = asyncio.run(v.verdict(BlindItem(**UNIT), index=3, created_seq=9))
    tracer.close()
    (entry,) = cas.entries.values()
    assert entry.key == ("verifier", 3, 0) and entry.request.tools == [] and entry.request_hash == out.request_hash
    spans = [x["rec"] for x in read_chain(tmp_path / "c.jsonl")]
    assert [s["op"] for s in spans] == ["chat"] and out.created_seq == 9 and not out.recorded


def test_strands_verifier_refuses_a_gateway_with_claim_tools(tmp_path):
    tracer, guard = _tracer(tmp_path / "s.jsonl")
    v = StrandsVerifier(**_kw(FakeProvider(YES), tracer, guard))
    with pytest.raises(ValueError, match="record_claim"):
        asyncio.run(v.verdict(BlindItem(**UNIT), index=0, created_seq=1,
                              gateway=WindowGateway(("imagery_window", "record_claim"))))


@pytest.mark.parametrize("text,answer", [('{"answer": "no"}', "no"), ('x {"answer":"cannot_assess"} y', "cannot_assess"),
                                         ("yes", "cannot_assess"), ('{"answer": "maybe"}', "cannot_assess"),
                                         ('{bad} {"answer": "yes"}', "yes")])
def test_parse_answer_abstains_on_anything_else(text, answer):
    assert parse_answer(text) == answer
