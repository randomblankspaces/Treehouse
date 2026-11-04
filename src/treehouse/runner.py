"""runner: task x config x K trials -> PlainLoop -> ToolGateway (live in-process MCP servers) -> TrialTracer -> seal.

One code path for fake, record and replay. Under ``clock=logical`` with ids from ``IdSource(seed)`` a replay
writes byte-identical traces, so trace heads are golden (``fixtures/golden/heads.json``).
"""

from __future__ import annotations

import asyncio
import json
import platform
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from treehouse import __version__
from treehouse.canon import canonical_json, sha256_bytes
from treehouse.cards import license_floor
from treehouse.clock import LogicalClock, WallClock
from treehouse.gateway.budget import BudgetGuard
from treehouse.gateway.gateway import ToolGateway
from treehouse.gateway.meter import Meter
from treehouse.gateway.pixel_cache import PixelCache
from treehouse.gateway.policy import Policy
from treehouse.gateway.tool_cassette import ToolCassette
from treehouse.harness.plain_loop import PlainLoop
from treehouse.ids import IdSource
from treehouse.providers.base import ModelProvider
from treehouse.schemas.config import RunConfig
from treehouse.schemas.manifest import Manifest, TrialHead
from treehouse.schemas.task import TaskCard
from treehouse.store.backends import resolve_backends
from treehouse.store.local import LocalStore
from treehouse.store.seal import seal
from treehouse.tools.claims import ClaimLedger
from treehouse.tools.servers import build_servers
from treehouse.trace.chain import ChainedJsonlWriter
from treehouse.trace.tracer import TrialTracer

SYSTEM = ("You are a geospatial mapping agent. Use only the tools you are given. Record every claim with "
          "record_claim and cite the result_id of each image window you relied on.")
LOGICAL_CREATED_AT = datetime(2026, 11, 4, tzinfo=UTC)
NC_LICENSES = {"CC-BY-NC-4.0"}


def tool_cassette_path(model_cassette: Path | str, trial_index: int) -> Path:
    p = Path(model_cassette)
    return p.with_name(p.name.replace(".model.jsonl", f".t{trial_index}.tool.jsonl"))


@dataclass
class RunSpec:
    run_id: str
    config: RunConfig
    card: TaskCard
    card_bytes: bytes
    provider: ModelProvider
    tool_cassettes: list[Path | None] = field(default_factory=list)  # one per trial (verify or record)
    model_cassette: Path | None = None  # copied into the sealed run
    recorded_windows: list[dict] | None = None


@dataclass
class TrialOutcome:
    trial_id: str
    stop: str
    detail: str | None
    n_claims: int
    head: str


@dataclass
class RunOutcome:
    manifest: Manifest
    trials: list[TrialOutcome]


def _licenses(card: TaskCard) -> list[str]:
    out = [d.license for d in card.data_allowlist]
    out += [s.keying.license for s in card.steps if s.keying.license]
    return out


async def _trial(spec: RunSpec, store: LocalStore, tmp: Path, i: int, floor: str):
    cfg, card = spec.config, spec.card
    tid = f"t-{i}"
    clock = LogicalClock() if cfg.clock == "logical" else WallClock()
    ids = IdSource(cfg.seed * 1000 + i)
    base = {"treehouse.task.id": card.id, "treehouse.task.hash": card.card_hash(), "treehouse.run.id": spec.run_id,
            "treehouse.trial.id": tid, "treehouse.trial.index": i, "treehouse.role": "worker",
            "treehouse.config.hash": sha256_bytes(canonical_json(cfg).encode())}
    tracer = TrialTracer(ChainedJsonlWriter.for_trial(tmp / "trials" / f"{tid}.trace.jsonl", tid),
                         trace_id=ids.trace_id(), clock=clock, ids=ids, base_attrs=base)
    pixels = PixelCache()
    ledger = ClaimLedger(card, run_id=spec.run_id, trial_id=tid)
    guard = BudgetGuard(cfg.budget, clock=clock)
    servers = build_servers(card, ledger=ledger, pixels=pixels, recorded_windows=spec.recorded_windows)
    tc_path = spec.tool_cassettes[i] if i < len(spec.tool_cassettes) else None
    tcas = ToolCassette(tc_path) if tc_path is not None else None
    gw = ToolGateway(servers, Policy(card), tracer, guard, Meter(), pixels, tool_cassette=tcas,
                     mode=cfg.tool_mode, store=store, ledger=ledger, license=floor)
    loop = PlainLoop(model_id=cfg.worker.model_key, params=cfg.worker.params)
    async with gw:
        res = await loop.run(system=SYSTEM, user=card.goal, provider=spec.provider, gateway=gw, tracer=tracer,
                             budget=guard, max_turns=cfg.max_turns, role="worker", trial_index=i)
    head = tracer.close()
    claims = "".join(canonical_json(c) + "\n" for c in ledger.claims).encode()
    parts = {f"trials/{tid}.claims.jsonl": claims}
    extra = {"understanding": ledger.understanding.model_dump(mode="json") if ledger.understanding else None,
             "limitations": ledger.limitations}
    parts[f"trials/{tid}.understanding.json"] = canonical_json(extra).encode()
    th = TrialHead(trial_id=tid, role="worker", trace_file=f"trials/{tid}.trace.jsonl", head=head,
                   claims_sha256=sha256_bytes(claims), stop=res.stop)
    return th, parts, TrialOutcome(tid, res.stop, res.detail, len(ledger.claims), head.head), tc_path


def execute(store: LocalStore, spec: RunSpec) -> RunOutcome:
    """Run every trial of ``spec`` and seal the run into ``store``."""
    cfg, card = spec.config, spec.card
    floor = license_floor(_licenses(card))
    tmp_run = store.begin_run(spec.run_id)
    heads, parts, outcomes, tool_paths = [], {}, [], []
    for i in range(cfg.trials):
        th, p, out, tc = asyncio.run(_trial(spec, store, tmp_run.path, i, floor))
        heads.append(th)
        parts.update(p)
        outcomes.append(out)
        tool_paths.append(tc)
    parts["task.yaml"] = spec.card_bytes
    parts["config.json"] = canonical_json(cfg).encode()
    model_sha = tool_sha = None
    if spec.model_cassette is not None and Path(spec.model_cassette).is_file():
        data = Path(spec.model_cassette).read_bytes()
        parts["cassette/model.jsonl"] = data
        model_sha = sha256_bytes(data)
    tool_data = b"".join(Path(p).read_bytes() for p in tool_paths if p is not None and Path(p).is_file())
    if tool_data:
        parts["cassette/tool.jsonl"] = tool_data
        tool_sha = sha256_bytes(tool_data)
    backends = resolve_backends(cfg)
    nc = sorted(set(_licenses(card)) & NC_LICENSES)
    m = seal(store, tmp_run, parts, manifest={
        "created_at": LOGICAL_CREATED_AT if cfg.clock == "logical" else datetime.now(UTC),
        "task": {"id": card.id, "version": card.version, "hash": card.card_hash()},
        "config_hash": sha256_bytes(canonical_json(cfg).encode()), "config": cfg, "mode": cfg.mode,
        "backends_resolved": backends,
        "versions": {"treehouse": __version__, "python": platform.python_version(), "harness": "plain_loop/1"},
        "trials": heads, "cassettes": {"model_sha": model_sha, "tool_sha": tool_sha},
        "key_isolation_statement": backends["key_isolation"].statement, "license_floor": floor,
        "nc_notice": (f"Non-commercial: inputs are {', '.join(nc)}; derived data is non-commercial."
                      if nc else None),
        "synthetic_data": card.synthetic})
    return RunOutcome(m, outcomes)


def copy_cassette(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
