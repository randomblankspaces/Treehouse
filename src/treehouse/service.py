"""service: the single code path behind the CLI (and later the MCP server and API).

``run`` executes one config (fake, record or replay) and seals it; ``load_sealed`` builds the frozen
``SealedRun`` the pure layers receive; ``check``, ``score``, ``trust`` and ``report`` append versioned eval
records and write the static report; ``demo`` replays every run in ``fixtures/demo/runs.yaml`` into a fresh
store and writes ``out/demo/index.html``. Everything here works offline.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from treehouse.canon import canonical_json, sha256_bytes, sha256_json
from treehouse.cards import load_card
from treehouse.checks.rules import check_run
from treehouse.paths import fixtures_root, repo_root, tasks_root
from treehouse.providers.cassette import Cassette, RecordingProvider, ReplayProvider
from treehouse.providers.fake import FakeProvider
from treehouse.report.html import ident, num_html, page, render
from treehouse.runner import RunOutcome, RunSpec, execute, tool_cassette_path
from treehouse.schemas.bundle import CardSummary, ManifestSummary, ReportBundle, StepSummary, SummaryLint
from treehouse.schemas.checks import CheckLedger
from treehouse.schemas.claims import Claim, UnderstandingStatement
from treehouse.schemas.config import Budget, InferenceParams, RoleConfig, RunConfig, TrustConfig
from treehouse.schemas.manifest import Manifest
from treehouse.schemas.passport import TrustPassport
from treehouse.schemas.scorecard import Scorecard
from treehouse.schemas.task import TaskCard
from treehouse.schemas.tools import WindowResult
from treehouse.schemas.trace import SpanRecord
from treehouse.score.scorecard import build_scorecard
from treehouse.sealed import SealedRun, SealedTrial, ToolCall
from treehouse.store.local import LocalStore
from treehouse.store.verify import verify
from treehouse.synth import policies
from treehouse.trace.chain import read_chain
from treehouse.trust.stub import stub_passport

Mode = Literal["fake", "replay", "record"]
DEMO_DIR = "demo"


class DemoError(RuntimeError):
    pass


# --- demo fixtures ---------------------------------------------------------------------------------------

def demo_root() -> Path:
    return fixtures_root() / DEMO_DIR


def golden_heads_path() -> Path:
    return fixtures_root() / "golden" / "heads.json"


def load_runs(root: Path | None = None) -> list[dict[str, Any]]:
    return yaml.safe_load(((root or demo_root()) / "runs.yaml").read_text())["runs"]


def card_path(task_id: str) -> Path:
    return tasks_root() / f"{task_id}.yaml"


def recorded_windows_for(card: TaskCard) -> list[dict] | None:
    img = next((d for d in card.data_allowlist if d.kind == "imagery"), None)
    if img is None or img.access != "recorded" or not img.fixture_path:
        return None
    p = repo_root() / img.fixture_path
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.is_file() else []


def demo_config(entry: dict[str, Any], card: TaskCard, *, mode: Mode = "replay",
                cassette_dir: str = "fixtures/demo/cassettes") -> RunConfig:
    """The committed config of a demo run (``mode`` replay); record and fake differ only in mode/provider."""
    return RunConfig(
        task_ref=card.ref(), mode=mode,
        worker=RoleConfig(provider="replay" if mode == "replay" else "fake", model_key=f"fake-{entry['policy']}",
                          family="fake", params=InferenceParams(max_tokens=4096), script=entry["policy"],
                          cassette=f"{cassette_dir}/{entry['run_id']}.model.jsonl"),
        trials=1, seed=int(entry.get("seed", 1)), clock="logical",
        budget=Budget(**entry["budget"]) if entry.get("budget") else Budget(),
        tool_mode="verify" if mode == "replay" else "live")


# --- run -------------------------------------------------------------------------------------------------

def _card_for(cfg: RunConfig) -> tuple[TaskCard, bytes]:
    task_id, _, want = cfg.task_ref.partition("@")
    path = card_path(task_id)
    card = load_card(path)
    if card.card_hash() != want:
        raise DemoError(f"task {task_id}: card hash {card.card_hash()} != config task_ref {want}; "
                        "regenerate fixtures with scripts/make_demo_fixtures.py")
    return card, path.read_bytes()


def run(store: LocalStore, cfg: RunConfig, *, run_id: str, mode: Mode | None = None,
        cassette_out: Path | None = None, cassette_root: Path | None = None) -> RunOutcome:
    """Execute ``cfg`` (mode overridden by ``mode``) and seal it into ``store``."""
    mode = mode or cfg.mode  # type: ignore[assignment]
    if mode not in ("fake", "replay", "record"):
        raise DemoError(f"mode {mode!r} is not available offline (live runs need the Bedrock adapter, P6)")
    if mode != cfg.mode:
        cfg = cfg.model_copy(update={"mode": mode, "tool_mode": "verify" if mode == "replay" else "live",
                                     "worker": cfg.worker.model_copy(update={
                                         "provider": "replay" if mode == "replay" else "fake"})})
    card, card_bytes = _card_for(cfg)
    rows = recorded_windows_for(card)
    tool_paths: list[Path | None] = []
    model_cassette: Path | None = None
    if mode == "replay":
        if not cfg.worker.cassette:
            raise DemoError("replay needs worker.cassette")
        model_cassette = (cassette_root or repo_root()) / cfg.worker.cassette
        provider: Any = ReplayProvider(Cassette(model_cassette))
        tool_paths = [tool_cassette_path(model_cassette, i) for i in range(cfg.trials)]
    else:
        fake = FakeProvider(policies.build(cfg.worker.script or "", card, recorded_windows=rows))
        provider = fake
        if mode == "record":
            out = Path(cassette_out or "out/cassettes")
            model_cassette = out / f"{run_id}.model.jsonl"
            for p in [model_cassette, *(tool_cassette_path(model_cassette, i) for i in range(cfg.trials))]:
                if p.exists():
                    p.unlink()
            provider = RecordingProvider(fake, Cassette(model_cassette))
            tool_paths = [tool_cassette_path(model_cassette, i) for i in range(cfg.trials)]
    return execute(store, RunSpec(run_id=run_id, config=cfg, card=card, card_bytes=card_bytes, provider=provider,
                                  tool_cassettes=tool_paths, model_cassette=model_cassette, recorded_windows=rows))


# --- load ------------------------------------------------------------------------------------------------

def load_sealed(store: LocalStore, run_id: str) -> SealedRun:
    d = store.run_dir(run_id)
    m = Manifest.model_validate_json((d / "manifest.json").read_bytes())
    card = TaskCard.model_validate(yaml.safe_load((d / "task.yaml").read_text()))
    trials = []
    for th in m.trials:
        spans = [SpanRecord.model_validate(x["rec"]) for x in read_chain(d / th.trace_file)]
        claims_p = d / th.trace_file.replace(".trace.jsonl", ".claims.jsonl")
        claims = [Claim.model_validate_json(x) for x in claims_p.read_text().splitlines() if x.strip()]
        und_p = d / th.trace_file.replace(".trace.jsonl", ".understanding.json")
        und = json.loads(und_p.read_text()).get("understanding") if und_p.is_file() else None
        calls = []
        for s in spans:
            if s.op != "execute_tool":
                continue
            a = s.attributes
            rid, ref = str(a.get("treehouse.tool.result_id", "")), str(a.get("treehouse.tool.result_ref", ""))
            body = json.loads(store.get(ref)) if ref.startswith("sha256:") else {"status": "error"}
            status = "blocked" if a.get("treehouse.tool.blocked") else body.get("status", "error")
            payload = body.get("result") or {k: v for k, v in body.items() if k != "status"}
            calls.append(ToolCall(seq=int(rid[2:]) if rid.startswith("r-") else 0, result_id=rid,
                                  name=str(a.get("gen_ai.tool.name", "")), status=status, span_id=s.span_id,
                                  payload=payload, key_access_attempt=bool(a.get("treehouse.key_access_attempt"))))
        trials.append(SealedTrial(trial_id=th.trial_id, stop=th.stop, spans=spans, claims=claims, calls=calls,
                                  understanding=UnderstandingStatement.model_validate(und) if und else None))
    return SealedRun(run_id=run_id, manifest=m, card=card, trials=trials)


# --- check / score / trust / report ---------------------------------------------------------------------

def trust_config_hash() -> str:
    data = yaml.safe_load((repo_root() / "prereg" / "trust-config.yaml").read_text())
    return sha256_json(TrustConfig(**data))


@dataclass
class Evaluated:
    run: SealedRun
    ledgers: list[CheckLedger]
    scorecard: Scorecard
    passport: TrustPassport
    bundle: ReportBundle
    html: str


def check(store: LocalStore, run: SealedRun) -> list[CheckLedger]:
    ledgers = check_run(run)
    store.append_record("rules", run.run_id, {"version": "rules-p5-v1", "ledgers": [lg.model_dump(mode="json")
                                                                                     for lg in ledgers]})
    return ledgers


def score(store: LocalStore, run: SealedRun, ledgers: list[CheckLedger]) -> Scorecard:
    sc = build_scorecard(run, ledgers)
    store.append_record("score", run.run_id, sc)
    return sc


def trust(store: LocalStore, run: SealedRun) -> TrustPassport:
    p = stub_passport(run, trust_config_hash=trust_config_hash())
    store.append_record("trust", run.run_id, p)
    return p


def build_bundle(run: SealedRun, ledgers: list[CheckLedger], sc: Scorecard, passport: TrustPassport) -> ReportBundle:
    m, card = run.manifest, run.card
    cited = {r.result_id for t in run.trials for c in t.claims for r in c.evidence_refs}
    evidence = [WindowResult.model_validate(c.payload) for t in run.trials for c in t.calls
                if c.name == "imagery_window" and c.status == "success" and c.result_id in cited]
    facts = {**sc.process.numbers, **sc.cost.numbers}
    summary = (f"Run {run.run_id}: {facts['claims'].value:.0f} claims; stop {run.trials[0].stop}; trust: "
               f"{passport.headline.chip()} ({'; '.join(passport.headline.reasons)}).")
    return ReportBundle(
        manifest_ref=m.manifest_hash,
        manifest_summary=ManifestSummary(run_id=run.run_id, mode=m.mode, task_ref=card.ref(),
                                         backends={k: v.ran for k, v in m.backends_resolved.items()},
                                         key_isolation_statement=m.key_isolation_statement,
                                         license_floor=m.license_floor, license_obligations=m.license_obligations,
                                         nc_notice=m.nc_notice),
        card_ref=card.ref(),
        card_summary=CardSummary(id=card.id, version=card.version, title=card.title, goal=card.goal,
                                 synthetic_notice=card.synthetic_notice, license_floor=m.license_floor,
                                 license_obligations=m.license_obligations,
                                 steps=[StepSummary(step_id=s.step_id, question_id=s.question_id,
                                                    keying_mode=s.keying.mode,
                                                    completeness_caveat=s.keying.completeness_caveat)
                                        for s in card.steps],
                                 must_notice=[n.id for n in card.must_notice], known_limits=card.known_limits),
        scorecard=sc, passports=[passport],
        understanding=[t.understanding for t in run.trials if t.understanding],
        claims=[c for t in run.trials for c in t.claims], evidence=evidence, ledgers=ledgers,
        trace_rows=[s for t in run.trials for s in t.spans], facts=facts, summary=summary,
        lint=SummaryLint(ok=True), synthetic=run.synthetic)


def report(store: LocalStore, run: SealedRun, ledgers, sc, passport) -> Evaluated:
    bundle = build_bundle(run, ledgers, sc, passport)
    html = render(bundle)
    store.put_once(f"bundles/{run.run_id}/bundle.json", canonical_json(bundle).encode())
    store.put_once(f"bundles/{run.run_id}/report.html", html.encode())
    return Evaluated(run, ledgers, sc, passport, bundle, html)


def evaluate(store: LocalStore, run_id: str) -> Evaluated:
    run_ = load_sealed(store, run_id)
    ledgers = check(store, run_)
    sc = score(store, run_, ledgers)
    p = trust(store, run_)
    return report(store, run_, ledgers, sc, p)


# --- demo ------------------------------------------------------------------------------------------------

def _rmtree(p: Path) -> None:
    if p.exists():
        shutil.rmtree(p)


def trace_heads(outcomes: dict[str, RunOutcome]) -> dict[str, dict[str, str]]:
    return {rid: {t.trial_id: t.head for t in o.trials} for rid, o in sorted(outcomes.items())}


def demo(out: Path | str = "out/demo", *, echo=print, check_heads: bool = True) -> dict[str, Evaluated]:
    """§5.3: replay every demo run into a fresh store, assert golden heads, check, score, trust stub, report,
    index, verify. Raises DemoError on any mismatch."""
    t0 = time.perf_counter()
    out = Path(out)
    store_root = out / "store"
    _rmtree(store_root)
    (out / "index.html").unlink(missing_ok=True)
    store = LocalStore(store_root)
    entries = load_runs()
    echo(f"treehouse demo: SYNTHETIC DEMO DATA; {len(entries)} runs replayed offline (mode=replay, "
         "clock=logical, tool_mode=verify)")
    outcomes: dict[str, RunOutcome] = {}
    for e in entries:
        cfg = RunConfig.model_validate_json((demo_root() / "configs" / f"{e['run_id']}.json").read_bytes())
        o = run(store, cfg, run_id=e["run_id"], mode="replay")
        outcomes[e["run_id"]] = o
        t = o.trials[0]
        echo(f"  replayed {e['run_id']:<22} policy={e['policy']:<14} stop={t.stop:<9} claims={t.n_claims:<3} "
             f"head={t.head[7:19]}")
    heads = trace_heads(outcomes)
    if check_heads:
        want = json.loads(golden_heads_path().read_text())
        if heads != want:
            bad = sorted(k for k in set(heads) | set(want) if heads.get(k) != want.get(k))
            raise DemoError(f"trace heads differ from fixtures/golden/heads.json for {bad}")
        echo(f"golden trace heads: match ({len(heads)} runs)")
    results = {rid: evaluate(store, rid) for rid in outcomes}
    for rid, ev in results.items():
        led = [lg.resolved for lg in ev.ledgers]
        counts = ", ".join(f"{k}={led.count(k)}" for k in sorted(set(led)))
        echo(f"  checked  {rid:<22} R1/R2/R4 -> {counts or 'no claims'}")
    echo(f"trust: {next(iter(results.values())).passport.headline.chip()} "
         f"({'; '.join(next(iter(results.values())).passport.headline.reasons)}) for every run (stub until P8)")
    (out / "index.html").write_text(index_html(results))
    rep = verify(store)
    if not rep.ok:
        for p in rep.problems:
            echo(str(p))
        raise DemoError("treehouse verify failed on the demo store")
    echo(f"verify: ok {store_root}: {rep.runs} run(s), {rep.records} record(s), {rep.blobs} blob(s)")
    echo(f"wrote {out / 'index.html'} ({time.perf_counter() - t0:.1f} s)")
    return results


def index_html(results: dict[str, Evaluated]) -> str:
    rows = []
    for rid, ev in results.items():
        f, card = ev.bundle.facts, ev.run.card
        rows.append(
            f"<tr><td><a href='store/bundles/{rid}/report.html'>{ident(rid)}</a></td><td>{ident(card.id)}</td>"
            f"<td>{ident(ev.run.trials[0].stop)}</td><td>{num_html(f['claims'])}</td>"
            f"<td>{num_html(f['grounding_rate']) if 'grounding_rate' in f else '-'}</td>"
            f"<td>{num_html(f['forbidden_attempts'])}</td><td>{num_html(f['bytes_read'])}</td>"
            f"<td>{num_html(ev.passport.headline)}</td>"
            f"<td>{'<span class=\"chip syn\">SYNTHETIC</span>' if ev.run.synthetic else ''}</td></tr>")
    body = ("<div class='banner'>SYNTHETIC DEMO DATA: every run below replays a scripted fake agent on synthetic "
            "or illustrative data.</div><h1>Treehouse demo</h1>"
            "<p>Each run was replayed offline through the plain loop, the tool gateway and live in-process MCP "
            "servers, sealed into a fresh store, checked (<code data-id='1'>R1, R2, R4</code>), scored and verified. Trust passport: stub "
            "(not yet built). Points on the corridor task are illustrative, not surveyed bridges.</p>"
            "<table><tr><th>run</th><th>task</th><th>stop</th><th>claims</th><th>grounding rate (<code data-id='1'>R4</code>)</th>"
            "<th>forbidden attempts</th><th>bytes read</th><th>trust</th><th>data</th></tr>"
            + "".join(rows) + "</table>")
    return page("Treehouse demo", body)


def fixture_bytes_digest(paths: list[Path]) -> str:
    return sha256_bytes(b"".join(p.read_bytes() for p in sorted(paths)))
