"""W2 contract: StrandsHarness and PlainLoop produce schema-identical sealed runs on the fake provider (same
request keys, same claims, same spans except ``treehouse.harness``); a recorded Strands run replays exactly;
budget, max_turns and provider errors end a Strands run exactly as they end a PlainLoop run."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("strands")

from treehouse.cards import load_card  # noqa: E402
from treehouse.clock import LogicalClock  # noqa: E402
from treehouse.gateway.base import ToolOutcome  # noqa: E402
from treehouse.gateway.budget import BudgetGuard  # noqa: E402
from treehouse.harness.plain_loop import PlainLoop  # noqa: E402
from treehouse.harness.strands_harness import StrandsHarness  # noqa: E402
from treehouse.ids import IdSource  # noqa: E402
from treehouse.paths import tasks_root  # noqa: E402
from treehouse.providers.cassette import Cassette, RecordingProvider, ReplayProvider  # noqa: E402
from treehouse.providers.fake import FakeProvider, ScriptDivergence  # noqa: E402
from treehouse.runner import RunSpec, execute  # noqa: E402
from treehouse.schemas.config import Budget, InferenceParams, RoleConfig, RunConfig  # noqa: E402
from treehouse.schemas.model_io import Text, ToolSpec  # noqa: E402
from treehouse.store.local import LocalStore  # noqa: E402
from treehouse.store.verify import verify  # noqa: E402
from treehouse.synth import world  # noqa: E402
from treehouse.trace.chain import ChainedJsonlWriter, read_chain  # noqa: E402
from treehouse.trace.tracer import TrialTracer  # noqa: E402

CARD_PATH = tasks_root() / "synth-crossings-v1.yaml"
X = next(c for c in world.crossings() if c.lon > world.WEST_STRIP + 0.0005)
BBOX = list(world.AOI)
SCRIPT = [  # understanding -> stac -> clay -> imagery window (an image in a tool result) -> claim -> done
    {"respond": {"tool_use": [{"name": "submit_understanding", "input": {
        "goal_restated": "inventory crossings", "scope": "the synthetic AOI", "planned_data": ["stac"],
        "known_limits": ["cloud in POST-B"]}}]}},
    {"expect": {"contains": "r-0001"},
     "respond": {"tool_use": [{"name": "stac_search", "input": {"aoi_bbox": BBOX, "start": "2026-07-01",
                                                                "end": "2026-09-15"}}]}},
    {"expect": {"contains": "r-0002"},
     "respond": {"tool_use": [{"name": "clay_search", "input": {"aoi_bbox": BBOX, "lon": X.lon, "lat": X.lat,
                                                                "k": 5}}]}},
    {"expect": {"contains": "r-0003"},
     "respond": {"tool_use": [{"name": "imagery_window", "input": {"scene_id": "SYN-POST-A", "lon": X.lon,
                                                                   "lat": X.lat, "side_m": 60, "out_px": 128}}]}},
    {"expect": {"contains": ["r-0004", "image sha256:"]},
     "respond": {"text": "recording", "tool_use": [{"name": "record_claim", "input": {
         "step_id": "status", "lon": X.lon, "lat": X.lat, "cls": X.cls, "status": X.status_post,
         "confidence": 0.9, "reason": "deck visible", "evidence_refs": [{"result_id": "r-0004", "role": "post"}]}}]}},
    {"expect": {"contains": "c-0001"}, "respond": {"text": "one crossing recorded"}},
]


class Spy:
    def __init__(self, inner):
        self.inner, self.requests = inner, []
        self.provider_name = inner.provider_name

    async def complete(self, req, **kw):
        self.requests.append(req)
        return await self.inner.complete(req, **kw)

    def __getattr__(self, name):  # check_consumed, cassette_ref, ...
        return getattr(self.inner, name)


def _cfg(harness: str, mode: str = "fake") -> RunConfig:
    return RunConfig(task_ref="synth-crossings-v1@sha256:" + "0" * 64, mode=mode, harness=harness,
                     worker=RoleConfig(provider="fake", model_key="fake", family="fake",
                                       params=InferenceParams(max_tokens=256)), seed=1, clock="logical")


def _sealed(root, harness, provider, mode="fake"):
    store = LocalStore(root)
    spec = RunSpec(run_id="run-0001", config=_cfg(harness, mode), card=load_card(CARD_PATH),
                   card_bytes=CARD_PATH.read_bytes(), provider=provider)
    out = execute(store, spec)
    return store, out


def _spans(store, harness_neutral=True):
    recs = [x["rec"] for x in read_chain(store.run_dir("run-0001") / "trials" / "t-0.trace.jsonl")]
    if harness_neutral:
        for r in recs:
            r["attributes"].pop("treehouse.harness", None)
            r["attributes"].pop("treehouse.config.hash", None)  # the config names the harness
    return recs


def test_strands_and_plain_loop_seal_schema_identical_runs(tmp_path):
    runs = {}
    for h in ("plain_loop", "strands"):
        spy = Spy(FakeProvider(SCRIPT))
        store, out = _sealed(tmp_path / h, h, spy)
        assert verify(store, "run-0001").ok
        runs[h] = (store, out, spy)
    (sp, op, pp), (ss, os_, ps) = runs["plain_loop"], runs["strands"]
    assert [r.key() for r in pp.requests] == [r.key() for r in ps.requests]  # images included (side channel)
    assert any(b.bytes_ for r in ps.requests for m in r.messages for c in m.content
               for b in getattr(c, "content", []) if getattr(b, "type", "") == "image")
    assert [(t.stop, t.n_claims) for t in op.trials] == [(t.stop, t.n_claims) for t in os_.trials] == [("completed", 1)]
    claims = [(s.run_dir("run-0001") / "trials" / "t-0.claims.jsonl").read_bytes() for s in (sp, ss)]
    assert claims[0] == claims[1] and claims[0]
    assert _spans(sp) == _spans(ss)
    mp, ms = op.manifest.model_dump(), os_.manifest.model_dump()
    assert mp.keys() == ms.keys() and ms["versions"]["harness"] == "strands/1"
    assert {k for k in mp if mp[k] != ms[k]} <= {"config", "config_hash", "versions", "trials",
                                                  "manifest_hash", "files"}
    assert mp["files"].keys() == ms["files"].keys()
    # only the config (it names the harness) and the trace (treehouse.harness) differ; claims and blobs do not
    assert {f for f in mp["files"] if mp["files"][f] != ms["files"][f]} == {"config.json", "trials/t-0.trace.jsonl"}


def test_cassette_replay_of_a_strands_run_is_exact(tmp_path):
    cas = Cassette(tmp_path / "w.model.jsonl")
    _, rec = _sealed(tmp_path / "rec", "strands", RecordingProvider(FakeProvider(SCRIPT), cas))
    replay = ReplayProvider(Cassette(tmp_path / "w.model.jsonl"))
    _, rep = _sealed(tmp_path / "rep", "strands", replay, mode="replay")
    assert replay.unused_keys() == [] and len(replay.served) == len(SCRIPT)
    assert rep.trials[0].stop == "completed" and rep.trials[0].n_claims == 1
    # the same cassette also replays under the plain loop: the harnesses send identical requests
    _, pl = _sealed(tmp_path / "pl", "plain_loop", ReplayProvider(Cassette(tmp_path / "w.model.jsonl")), "replay")
    assert pl.trials[0].stop == "completed"
    assert rec.trials[0].n_claims == rep.trials[0].n_claims == 1


# --- stop and error contract, against a minimal gateway ---------------------------------------------------

BASE = {"treehouse.task.id": "synth-crossings-v1", "treehouse.task.hash": "sha256:" + "0" * 64,
        "treehouse.run.id": "run-0001", "treehouse.trial.id": "t-0", "treehouse.trial.index": 0,
        "treehouse.role": "worker", "treehouse.config.hash": "sha256:" + "1" * 64}


class FakeGateway:
    def __init__(self, budget):
        self.budget, self.calls = budget, []

    def specs(self):
        return [ToolSpec(name="stac_search", description="search", input_schema={"type": "object"})]

    async def call(self, name, args, *, call_id):
        self.budget.commit(self.budget.reserve(tool_calls=1))
        self.calls.append(call_id)
        return ToolOutcome(result_id=f"r-{len(self.calls):04d}", status="success", content=[Text(text="ok")])


def _run(tmp_path, harness_cls, provider, *, budget=None, max_turns=5):
    ids, clock = IdSource(3), LogicalClock()
    path = tmp_path / f"{harness_cls.name}-{id(provider)}.jsonl"
    tracer = TrialTracer(ChainedJsonlWriter.for_trial(path, "t-0"), trace_id=ids.trace_id(), clock=clock, ids=ids,
                         base_attrs=BASE)
    guard = BudgetGuard(budget or Budget(), clock=clock)
    gw = FakeGateway(guard)
    h = harness_cls(model_id="fake-model", params=InferenceParams(max_tokens=64))
    try:
        res = asyncio.run(h.run(system="sys", user="find bridges", provider=provider, gateway=gw, tracer=tracer,
                                budget=guard, max_turns=max_turns, role="worker", trial_index=0))
    finally:
        tracer.close()
    spans = [x["rec"] for x in read_chain(path)]
    for s in spans:
        s["attributes"].pop("treehouse.harness", None)
    return res, gw.calls, spans


def two_tools_each_turn(req, *, role, trial_index, turn):
    return {"tool_use": [{"name": "stac_search", "input": {"turn": turn, "k": k}} for k in range(2)]}


@pytest.mark.parametrize("kw", [{"budget": Budget(tool_calls=3)}, {"max_turns": 2}], ids=["budget", "max_turns"])
def test_stops_match_plain_loop(tmp_path, kw):
    out = [_run(tmp_path, h, FakeProvider(two_tools_each_turn), **kw) for h in (PlainLoop, StrandsHarness)]
    (rp, cp, sp), (rs, cs, ss) = out
    assert rp == rs and cp == cs and sp == ss
    assert rs.stop == ("budget" if "budget" in kw else "max_turns")


def test_odd_stop_reason_and_provider_errors_match_plain_loop(tmp_path):
    odd = [{"respond": {"text": "cut", "stop_reason": "max_tokens"}}]
    (rp, _, sp), (rs, _, ss) = [_run(tmp_path, h, FakeProvider(odd)) for h in (PlainLoop, StrandsHarness)]
    assert rp == rs and rs.stop == "error" and sp == ss
    for h in (PlainLoop, StrandsHarness):  # a script divergence propagates as itself, not wrapped by Strands
        with pytest.raises(ScriptDivergence):
            _run(tmp_path, h, FakeProvider([{"expect": {"contains": "nope"}, "respond": {"text": "x"}}]))

