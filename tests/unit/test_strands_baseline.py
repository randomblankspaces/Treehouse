"""``baseline: no_tool``: the gateway lists only the claim tools, refuses imagery calls (traced), and the
claims still record; ``baseline_gap`` reads the difference."""

from __future__ import annotations

import asyncio

import pytest

from treehouse.cards import load_card
from treehouse.clock import LogicalClock
from treehouse.gateway.budget import BudgetGuard
from treehouse.gateway.gateway import ToolGateway
from treehouse.gateway.meter import Meter
from treehouse.gateway.pixel_cache import PixelCache
from treehouse.gateway.policy import Policy
from treehouse.harness.baseline import NO_TOOL_TOOLS, baseline_gap
from treehouse.harness.plain_loop import PlainLoop
from treehouse.ids import IdSource
from treehouse.paths import tasks_root
from treehouse.providers.fake import FakeProvider
from treehouse.schemas.config import Budget, InferenceParams
from treehouse.synth import world
from treehouse.tools.claims import ClaimLedger
from treehouse.tools.servers import build_servers
from treehouse.trace.chain import ChainedJsonlWriter, read_chain
from treehouse.trace.tracer import TrialTracer

X = world.crossings()[0]


@pytest.mark.parametrize("harness", ["plain_loop", "strands"])
def test_no_tool_baseline_removes_imagery_but_keeps_claims(tmp_path, harness):
    if harness == "strands":
        pytest.importorskip("strands")
        from treehouse.harness.strands_harness import StrandsHarness as H
    else:
        H = PlainLoop
    card = load_card(tasks_root() / "synth-crossings-v1.yaml")
    ids, clock = IdSource(4), LogicalClock()
    base = {"treehouse.task.id": card.id, "treehouse.task.hash": card.card_hash(), "treehouse.run.id": "run-b",
            "treehouse.trial.id": "t-0", "treehouse.trial.index": 0, "treehouse.role": "worker",
            "treehouse.config.hash": "sha256:" + "4" * 64}
    tracer = TrialTracer(ChainedJsonlWriter.for_trial(tmp_path / "b.jsonl", "t-0"), trace_id=ids.trace_id(),
                         clock=clock, ids=ids, base_attrs=base)
    pixels, ledger, guard = PixelCache(), ClaimLedger(card, run_id="run-b", trial_id="t-0"), BudgetGuard(Budget(),
                                                                                                       clock=clock)
    gw = ToolGateway(build_servers(card, ledger=ledger, pixels=pixels), Policy(card), tracer, guard, Meter(), pixels,
                     ledger=ledger, tools=NO_TOOL_TOOLS)
    script = [
        {"respond": {"tool_use": [{"name": "imagery_window", "input": {"scene_id": "SYN-POST-A", "lon": X.lon,
                                                                       "lat": X.lat, "side_m": 60}}]}},
        {"expect": {"contains": "not_allowlisted"}, "respond": {"tool_use": [{"name": "record_claim", "input": {
            "step_id": "status", "lon": X.lon, "lat": X.lat, "cls": X.cls, "status": X.status_post,
            "confidence": 0.5, "reason": "from memory", "evidence_refs": []}}]}},
        {"respond": {"text": "done"}}]

    async def go():
        async with gw:
            assert {s.name for s in gw.specs()} <= NO_TOOL_TOOLS and "imagery_window" not in gw.visible_tools()
            return await H(model_id="fake", params=InferenceParams(max_tokens=64)).run(
                system="sys", user=card.goal, provider=FakeProvider(script), gateway=gw, tracer=tracer,
                budget=guard, max_turns=5, role="worker", trial_index=0)
    res = asyncio.run(go())
    tracer.close()
    assert res.stop == "completed" and len(ledger.claims) == 1
    tools = [x["rec"]["attributes"] for x in read_chain(tmp_path / "b.jsonl") if x["rec"]["op"] == "execute_tool"]
    assert tools[0]["treehouse.tool.block_reason"] == "not_allowlisted"


def test_baseline_gap_reading():
    assert baseline_gap(0.8, 0.3)["gap"] == pytest.approx(0.5)
    assert "not tool-grounded" in baseline_gap(0.4, 0.45)["reading"]
