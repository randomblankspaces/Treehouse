"""Builders for gateway tests: a synth-card ToolGateway with a chained tracer under LogicalClock."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from treehouse.cards import load_card
from treehouse.clock import LogicalClock
from treehouse.gateway.budget import BudgetGuard
from treehouse.gateway.gateway import ToolGateway
from treehouse.gateway.meter import Meter
from treehouse.gateway.pixel_cache import PixelCache
from treehouse.gateway.policy import Policy
from treehouse.ids import IdSource
from treehouse.paths import tasks_root
from treehouse.schemas.config import Budget
from treehouse.schemas.trace import SpanRecord
from treehouse.tools.claims import ClaimLedger
from treehouse.tools.servers import build_servers
from treehouse.trace.chain import ChainedJsonlWriter, read_chain
from treehouse.trace.tracer import TrialTracer

BASE = {
    "treehouse.task.id": "synth-crossings-v1",
    "treehouse.task.hash": "sha256:" + "0" * 64,
    "treehouse.run.id": "run-0001",
    "treehouse.trial.id": "t-0",
    "treehouse.trial.index": 0,
    "treehouse.role": "worker",
    "treehouse.config.hash": "sha256:" + "1" * 64,
}


def card(name: str = "synth-crossings-v1"):
    return load_card(tasks_root() / f"{name}.yaml")


@dataclass
class Rig:
    gateway: ToolGateway
    tracer: TrialTracer
    ledger: ClaimLedger
    trace_path: Path
    budget: BudgetGuard
    pixels: PixelCache

    def spans(self) -> list[SpanRecord]:
        return [SpanRecord.model_validate(x["rec"]) for x in read_chain(self.trace_path)]


def make_rig(trace_path: Path, *, task=None, as_of=None, budget: Budget | None = None, zlib_level: int = 6,
             store=None, clock=None, ids=None, base: dict | None = None) -> Rig:
    task = task or card()
    ids = ids or IdSource(7)
    clock = clock or LogicalClock()
    tracer = TrialTracer(ChainedJsonlWriter.for_trial(trace_path, "t-0"), trace_id=ids.trace_id(), clock=clock,
                         ids=ids, base_attrs={**BASE, "treehouse.task.id": task.id, **(base or {})})
    pixels = PixelCache(zlib_level=zlib_level)
    ledger = ClaimLedger(task, run_id="run-0001", trial_id="t-0")
    guard = BudgetGuard(budget or Budget(), clock=clock)
    servers = build_servers(task, ledger=ledger, pixels=pixels, as_of=as_of)
    gw = ToolGateway(servers, Policy(task, as_of=as_of), tracer, guard, Meter(), pixels, as_of=as_of, store=store,
                     ledger=ledger, license="LicenseRef-synthetic")
    return Rig(gw, tracer, ledger, trace_path, guard, pixels)
