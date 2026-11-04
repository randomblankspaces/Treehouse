"""P5 acceptance (IMPLEMENTATION-DESIGN §7 P5, §6 J2/J8/I5/I6): `treehouse demo` replays every cassette through
the plain loop, the gateway and live in-process MCP servers under the offline guard, in under 60 s; golden trace
heads hold across two runs; every number is chipped and synthetic; `treehouse verify` exits 0 on the store."""

from __future__ import annotations

import base64
import json
import re
import shutil
import socket
import time
from html.parser import HTMLParser

import pytest
from typer.testing import CliRunner

from treehouse.canon import stable_view
from treehouse.cli import app
from treehouse.service import demo, golden_heads_path, trace_heads

DIGIT = re.compile(r"\d")
DATE = re.compile(r"^\s*\d{4}-\d{2}-\d{2}")
NOTE = "illustrative, not surveyed bridges"
# image magic numbers and their base64 forms, built at runtime so this file itself passes the licence scan
_MAGIC = [b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"II*\x00", b"MM\x00*"]
IMAGE_MARKERS = [*_MAGIC, *(base64.b64encode(m)[:6] for m in _MAGIC), b"data:" + b"image/"]


class _Blocked(RuntimeError):
    pass


@pytest.fixture(scope="module")
def first(tmp_path_factory):
    """Demo run #1, under a module-level socket block (the autouse guard is per test)."""
    attempts: list[str] = []

    def block(*a, **k):
        attempts.append(repr(a[:2]))
        raise _Blocked("network blocked")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(socket.socket, "connect", block)
        mp.setattr(socket, "getaddrinfo", block)
        out = tmp_path_factory.mktemp("demo1")
        results = demo(out, echo=lambda *_: None)
    assert attempts == []
    return out, results


def _scores(results):
    return {rid: stable_view(ev.scorecard) for rid, ev in results.items()}


def test_j2_j8_demo_offline_under_guard_fast_and_deterministic(first, tmp_path, offline_guard):
    """J2: no network/Bedrock while the demo runs; J8: under 60 s; scores and heads identical across runs."""
    out1, r1 = first
    lines: list[str] = []
    t0 = time.perf_counter()
    r2 = demo(tmp_path / "demo2", echo=lines.append)
    elapsed = time.perf_counter() - t0
    assert offline_guard.attempts == []
    assert elapsed < 60, elapsed
    assert _scores(r1) == _scores(r2)
    assert any(ln.startswith("golden trace heads: match") for ln in lines)
    assert any(ln.startswith("verify: ok") for ln in lines)
    assert all(ev.run.manifest.mode == "replay" and ev.run.manifest.backends_resolved["model.worker"].ran == "replay"
               for ev in r2.values())


def test_golden_heads_stable(first):
    _, results = first
    heads = {rid: {t.trial_id: t.head.head for t in ev.run.manifest.trials} for rid, ev in results.items()}
    assert heads == json.loads(golden_heads_path().read_text())
    assert len(heads) == 9


def test_verify_cli_exits_zero_on_demo_store(first):
    out, _ = first
    r = CliRunner().invoke(app, ["verify", "--store", str(out / "store")])
    assert r.exit_code == 0, r.output
    assert "9 run(s)" in r.output


def test_planted_behaviours_show_in_the_demo(first):
    _, res = first
    led = {rid: [lg.resolved for lg in ev.ledgers] for rid, ev in res.items()}
    assert led["synth-fabricator"].count("fabrication") == 10 and led["synth-fabricator"].count("ungrounded") == 10
    assert res["synth-key-peeker"].scorecard.process.numbers["forbidden_attempts"].value == 2
    assert res["synth-budget-stop"].run.trials[0].stop == "budget"
    assert res["synth-good"].scorecard.process.numbers["grounding_rate"].value == 1.0
    looper = [c.name for c in res["synth-looper"].run.trials[0].calls]
    assert looper.count("stac_search") == 6 and "find_bridges" in looper
    assert len(res["nepal-good"].run.trials[0].claims) == 30
    assert sum(c.status == "cannot_assess" for c in res["nepal-good"].run.trials[0].claims) == 8
    assert sum(c.status == "cannot_assess" for c in res["nepal-guesser"].run.trials[0].claims) == 0
    used = {c.payload.get("scene_id") for c in res["nepal-good"].run.trials[0].calls if c.name == "imagery_window"}
    assert used == {"B1300011011E5610"}  # never a cloud-trap scene


def test_cost_panel_is_measured_replayed_and_modelled_bytes(first):
    _, res = first
    for ev in res.values():
        cost = ev.scorecard.cost
        assert cost.numbers and all(n.tier.value == "MEASURED" and n.replayed for n in cost.numbers.values())
        assert "not measured in replay" in (cost.no_grade_reason or "")
    b = res["synth-good"].scorecard.cost.numbers["bytes_read"]
    assert b.value > 0 and b.chip() == "Measured from trace · SYNTHETIC · recorded · modelled bytes"
    assert 'title="declared overview-block model, not measured"' in res["synth-good"].html


def test_trust_is_a_stub_that_abstains(first):
    _, res = first
    for ev in res.values():
        h = ev.passport.headline
        assert h.tier.value == "ABSTAINED" and h.value is None and h.reasons == ["trust engine not yet built"]
        assert ev.passport.gate == "Do not rely"


def _walk_numbers(obj, path=""):
    if isinstance(obj, dict):
        if {"metric", "tier", "synthetic"} <= set(obj):
            yield path, obj
        for k, v in obj.items():
            yield from _walk_numbers(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_numbers(v, f"{path}[{i}]")


def test_i5_every_number_synthetic_and_every_nepal_row_chipped(first):
    out, res = first
    for rid in res:
        bundle = json.loads((out / "store" / "bundles" / rid / "bundle.json").read_text())
        nums = list(_walk_numbers(bundle))
        assert nums and all(n["synthetic"] is True for _, n in nums), rid
        assert bundle["synthetic"] is True
        html = (out / "store" / "bundles" / rid / "report.html").read_text()
        assert "SYNTHETIC DEMO DATA" in html
    for rid in ("nepal-good", "nepal-guesser"):
        html = res[rid].html
        rows = re.findall(r'<tr data-row="(claim|evidence)"[^>]*>(.*?)</tr>', html, re.S)
        kinds = [k for k, _ in rows]
        assert kinds.count("claim") == 30 and kinds.count("evidence") == 30
        for _, body in rows:
            assert "SYNTHETIC" in body and NOTE in body
    assert "SYNTHETIC DEMO DATA" in (out / "index.html").read_text()


class _TierWalker(HTMLParser):
    VOID = {"meta", "br", "img", "hr", "link", "input"}

    def __init__(self):
        super().__init__()
        self.stack: list[tuple[str, dict]] = []
        self.bad: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append((tag, dict(attrs)))

    def handle_endtag(self, tag):
        while self.stack:
            if self.stack.pop()[0] == tag:
                break

    def handle_data(self, data):
        if not DIGIT.search(data) or any(t in ("style", "title") for t, _ in self.stack):
            return
        if DATE.match(data):
            return
        if any({"data-tier", "data-id", "data-card"} & set(a) for _, a in self.stack):
            return
        self.bad.append(data.strip()[:80])


def test_i6_every_digit_has_a_tier_ancestor(first):
    out, _ = first
    pages = sorted((out / "store" / "bundles").glob("*/report.html")) + [out / "index.html"]
    assert len(pages) == 10
    for p in pages:
        w = _TierWalker()
        w.feed(p.read_text())
        assert w.bad == [], (p.parent.name, w.bad[:5])


def test_i6_walker_catches_a_bare_number():
    w = _TierWalker()
    w.feed("<p>grounding 0.95</p><p data-tier='MEASURED'>0.5</p><code data-id='1'>r-0001</code>")
    assert w.bad == ["grounding 0.95"]


def test_reports_have_no_js_and_no_image_bytes(first):
    """Inline CSS, no JS, never image bytes (the licence-scan patterns) in any page or bundle."""
    out, _ = first
    for p in [*sorted((out / "store" / "bundles").rglob("*.*")), out / "index.html"]:
        data = p.read_bytes()
        assert b"<script" not in data, p
        assert not any(m in data for m in IMAGE_MARKERS), p
        if p.suffix == ".html":
            assert b"<style>" in data and b"<link" not in data


def test_heads_helper_matches_manifest(first):
    _, res = first
    assert trace_heads({}) == {}
    assert all(ev.run.manifest.trials[0].head.head.startswith("sha256:") for ev in res.values())


@pytest.mark.parametrize("damage", ["seal", "claims", "trace"])
def test_loading_tampered_demo_run_is_refused(first, tmp_path, damage):
    from treehouse.service import DemoError, load_sealed
    from treehouse.store.local import LocalStore

    out, _ = first
    root = tmp_path / "store"
    shutil.copytree(out / "store", root)
    run = root / "runs" / "synth-good"
    if damage == "seal":
        (run / "SEALED").unlink()
    else:
        path = run / "trials" / f"t-0.{damage}.jsonl"
        path.chmod(0o644)
        path.write_bytes(b" " + path.read_bytes())
    with pytest.raises(DemoError, match="verif"):
        load_sealed(LocalStore(root), "synth-good")


def _output_snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() if p.is_file() else None
            for p in root.rglob("*")}


@pytest.mark.parametrize("occupied", ["store", "index.html", "both", "store-link", "index-link"])
def test_demo_refuses_existing_output_before_mutation(tmp_path, monkeypatch, occupied):
    import treehouse.service as service

    out = tmp_path / "demo"
    out.mkdir()
    if occupied in ("store", "both"):
        (out / "store").mkdir()
        (out / "store" / "personal.txt").write_text("keep my data")
    if occupied in ("index.html", "both"):
        (out / "index.html").write_text("keep my index")
    if occupied.endswith("-link"):
        target = "store" if occupied == "store-link" else "index.html"
        (out / target).symlink_to(tmp_path / "missing-personal-target")
    before = _output_snapshot(tmp_path)

    def replay_started():
        pytest.fail("demo started before refusing occupied output")

    monkeypatch.setattr(service, "load_runs", replay_started)
    with pytest.raises(service.DemoError, match="already exists.*fresh"):
        service.demo(out)
    result = CliRunner().invoke(app, ["demo", "--out", str(out)])
    assert result.exit_code == 1 and "already exists" in result.output, result.output
    assert _output_snapshot(tmp_path) == before


def test_demo_preserves_existing_sealed_non_demo_store(tmp_path):
    from treehouse.schemas.config import RunConfig
    from treehouse.service import DemoError, demo_root, run
    from treehouse.store.local import LocalStore
    from treehouse.store.verify import verify

    out = tmp_path / "personal"
    store = LocalStore(out / "store")
    cfg = RunConfig.model_validate_json((demo_root() / "configs" / "synth-looper.json").read_bytes())
    run(store, cfg, run_id="personal-run", mode="fake")
    assert verify(store).ok
    before = _output_snapshot(tmp_path)
    with pytest.raises(DemoError, match="already exists.*fresh"):
        demo(out)
    assert _output_snapshot(tmp_path) == before
    assert verify(store).ok


@pytest.mark.parametrize("existing", ["model", "tool-first", "tool-last", "all"])
def test_record_refuses_all_existing_cassettes_before_mutation(tmp_path, monkeypatch, existing):
    import treehouse.service as service
    from treehouse.runner import tool_cassette_path
    from treehouse.schemas.config import RunConfig
    from treehouse.store.local import LocalStore

    cfg = RunConfig.model_validate_json((service.demo_root() / "configs" / "synth-looper.json").read_bytes())
    cfg = cfg.model_copy(update={"trials": 2})
    cas = tmp_path / "cassettes"
    cas.mkdir()
    model = cas / "personal-run.model.jsonl"
    paths = [model, tool_cassette_path(model, 0), tool_cassette_path(model, 1)]
    chosen = {"model": paths[:1], "tool-first": paths[1:2], "tool-last": paths[2:], "all": paths}[existing]
    for path in chosen:
        path.write_text("keep my cassette")
    store = LocalStore(tmp_path / "store")
    before = _output_snapshot(tmp_path)

    def recording_started(*args):
        pytest.fail("recording started before refusing occupied cassettes")

    monkeypatch.setattr(service, "execute", recording_started)
    with pytest.raises(service.DemoError, match="already exists.*fresh"):
        service.run(store, cfg, run_id="personal-run", mode="record", cassette_out=cas)
    assert _output_snapshot(tmp_path) == before


@pytest.mark.parametrize("existing", ["model", "tool"])
def test_record_cli_refusal_does_not_create_store(tmp_path, existing):
    from treehouse.service import demo_root

    cas = tmp_path / "cassettes"
    cas.mkdir()
    suffix = "model" if existing == "model" else "t0.tool"
    (cas / f"personal-run.{suffix}.jsonl").write_text("keep my cassette")
    store = tmp_path / "new-store"
    before = _output_snapshot(tmp_path)
    result = CliRunner().invoke(app, ["run", str(demo_root() / "configs" / "synth-looper.json"),
                                      "--mode", "record", "--run-id", "personal-run",
                                      "--store", str(store), "--cassette-out", str(cas)])
    assert result.exit_code == 1 and "already exists" in result.output, result.output
    assert not store.exists()
    assert _output_snapshot(tmp_path) == before


def test_record_cli_rejects_unsafe_run_id_before_creating_outputs(tmp_path):
    from treehouse.service import demo_root

    before = _output_snapshot(tmp_path)
    result = CliRunner().invoke(app, ["run", str(demo_root() / "configs" / "synth-looper.json"),
                                      "--mode", "record", "--run-id", "../personal",
                                      "--store", str(tmp_path / "new-store"),
                                      "--cassette-out", str(tmp_path / "new-cassettes")])
    assert result.exit_code == 1 and "invalid run id" in result.output, result.output
    assert _output_snapshot(tmp_path) == before
