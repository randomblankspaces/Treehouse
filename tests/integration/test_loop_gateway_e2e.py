"""PlainLoop + ToolGateway + live in-process MCP servers, end to end under LogicalClock: a "good"-like
mini trajectory (understanding -> stac_search -> clay_search -> imagery_window -> record_claim), sealed
into a LocalStore, and ``verify`` passes. Re-encoding the PNGs at another zlib level leaves request keys,
pixel_sha256 and the trace head unchanged (OBS-B2)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from gwrig import card, make_rig

from treehouse.canon import canonical_json, sha256_bytes
from treehouse.clock import LogicalClock
from treehouse.harness.plain_loop import PlainLoop
from treehouse.ids import IdSource
from treehouse.providers.base import iter_images
from treehouse.providers.fake import FakeProvider
from treehouse.schemas.config import InferenceParams, RoleConfig, RunConfig
from treehouse.schemas.manifest import TrialHead
from treehouse.store.backends import resolve_backends
from treehouse.store.local import LocalStore
from treehouse.store.seal import seal
from treehouse.store.verify import verify
from treehouse.synth import world

X = next(c for c in world.crossings() if c.lon > world.WEST_STRIP + 0.0005)
BBOX = list(world.AOI)
SCRIPT = [
    {"respond": {"tool_use": [{"name": "submit_understanding", "input": {
        "goal_restated": "inventory crossings and their post-event status", "scope": "the synthetic AOI",
        "planned_data": ["stac", "clay", "imagery"], "known_limits": ["cloud in POST-B", "footbridge resolution"]}}]}},
    {"expect": {"contains": "r-0001"},
     "respond": {"tool_use": [{"name": "stac_search", "input": {"aoi_bbox": BBOX, "start": "2026-07-01",
                                                                "end": "2026-09-15"}}]}},
    {"expect": {"contains": ["r-0002", "SYN-POST-A"]},
     "respond": {"tool_use": [{"name": "clay_search", "input": {"aoi_bbox": BBOX, "lon": X.lon, "lat": X.lat,
                                                                "k": 5}}]}},
    {"expect": {"contains": "r-0003"},
     "respond": {"tool_use": [{"name": "imagery_window", "input": {"scene_id": "SYN-POST-A", "lon": X.lon,
                                                                   "lat": X.lat, "side_m": 60, "out_px": 128}}]}},
    {"expect": {"contains": ["r-0004", "image sha256:"]},
     "respond": {"tool_use": [{"name": "record_claim", "input": {
         "step_id": "status", "lon": X.lon, "lat": X.lat, "cls": X.cls, "status": X.status_post,
         "confidence": 0.9, "reason": "deck visible in the post window",
         "evidence_refs": [{"result_id": "r-0004", "role": "post"}]}}]}},
    {"expect": {"contains": "c-0001"}, "respond": {"text": "one crossing recorded"}},
]
CFG = RunConfig(task_ref="synth-crossings-v1@sha256:" + "0" * 64, mode="fake",
                worker=RoleConfig(provider="fake", model_key="fake", family="fake",
                                  params=InferenceParams(max_tokens=256)), seed=1, clock="logical")


class Spy:
    provider_name = "fake"

    def __init__(self, inner):
        self.inner, self.requests = inner, []

    async def complete(self, req, **kw):
        self.requests.append(req)
        return await self.inner.complete(req, **kw)


def run_sealed(root, *, zlib_level):
    store = LocalStore(root)
    tmp = store.begin_run("run-0001")
    clock, ids = LogicalClock(), IdSource(11)
    base = {"treehouse.task.hash": card().card_hash(), "treehouse.config.hash": sha256_bytes(canonical_json(CFG).encode())}
    rig = make_rig(tmp.path / "trials" / "t-0.trace.jsonl", zlib_level=zlib_level, store=store, clock=clock, ids=ids,
                   base=base)
    spy = Spy(FakeProvider(SCRIPT))
    loop = PlainLoop(model_id="fake-model", params=InferenceParams(max_tokens=256),
                     blob_sink=lambda b: store.put_blob(b, media_type="application/json", license="LicenseRef-synthetic"))

    async def go():
        async with rig.gateway as gw:
            return await loop.run(system="You are a mapping agent.", user=card().goal, provider=spy, gateway=gw,
                                  tracer=rig.tracer, budget=rig.budget, max_turns=10, role="worker", trial_index=0)
    res = asyncio.run(go())
    head = rig.tracer.close()
    claims = "".join(canonical_json(c) + "\n" for c in rig.gateway.claims).encode()
    trial = TrialHead(trial_id="t-0", role="worker", trace_file="trials/t-0.trace.jsonl", head=head,
                      claims_sha256=sha256_bytes(claims), stop=res.stop)
    backends = resolve_backends(CFG)
    m = seal(store, tmp, {"config.json": canonical_json(CFG).encode(), "trials/t-0.claims.jsonl": claims},
             manifest={"created_at": datetime(2026, 11, 4, tzinfo=UTC),
                       "task": {"id": "synth-crossings-v1", "version": "1.0.0", "hash": card().card_hash()},
                       "config_hash": sha256_bytes(canonical_json(CFG).encode()), "config": CFG, "mode": "fake",
                       "backends_resolved": backends,
                       "versions": {"treehouse": "0.1.0", "python": "3.12", "harness": "plain_loop/1"},
                       "trials": [trial], "key_isolation_statement": backends["key_isolation"].statement,
                       "license_floor": "LicenseRef-synthetic", "synthetic_data": True})
    return store, m, res, rig, spy


def test_good_mini_trajectory_seals_and_verifies(tmp_path):
    store, m, res, rig, spy = run_sealed(tmp_path / "store", zlib_level=6)
    assert res.stop == "completed" and res.turns == 6
    (claim,) = rig.gateway.claims
    assert claim.grounded and not claim.contaminated and claim.evidence_refs[0].result_id == "r-0004"
    assert rig.gateway.understanding.known_limits == ["cloud in POST-B", "footbridge resolution"]
    report = verify(store, "run-0001")
    assert report.ok, report.problems
    trace = (store.run_dir("run-0001") / "trials" / "t-0.trace.jsonl").read_text()
    assert trace.count('"op":"execute_tool"') == 5 and trace.count('"op":"chat"') == 6
    imgs = list(iter_images(spy.requests[-1].messages))
    assert len(imgs) == 1 and imgs[0][1].bytes_ is not None
    assert m.trials[0].stop == "completed" and m.synthetic_data is True


def test_reencoding_at_another_zlib_level_keeps_keys_and_heads(tmp_path):
    _, m1, _, _, spy1 = run_sealed(tmp_path / "a", zlib_level=1)
    _, m9, _, _, spy9 = run_sealed(tmp_path / "b", zlib_level=9)
    i1 = next(iter_images(spy1.requests[-1].messages))[1]
    i9 = next(iter_images(spy9.requests[-1].messages))[1]
    assert i1.bytes_ != i9.bytes_ and i1.sha256 == i9.sha256
    assert [r.key() for r in spy1.requests] == [r.key() for r in spy9.requests]
    assert m1.trials[0].head == m9.trials[0].head
