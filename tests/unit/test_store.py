"""LocalStore, seal, verify and resolve_backends (IMPLEMENTATION-DESIGN §3 Store, §4 layout, §7 P2)."""

from __future__ import annotations

import json
import os
import stat
from datetime import UTC, datetime

import pytest
from typer.testing import CliRunner

from treehouse.canon import canonical_json, sha256_bytes
from treehouse.cli import app
from treehouse.schemas.config import Backends, InferenceParams, RoleConfig, RunConfig
from treehouse.schemas.manifest import Manifest, TrialHead
from treehouse.store.backends import KEY_ISOLATION_LOCAL, BackendUnavailable, resolve_backends
from treehouse.store.base import AlreadyExists, SealError, UnsealedRun
from treehouse.store.local import LocalStore
from treehouse.store.seal import seal
from treehouse.store.verify import verify
from treehouse.trace.chain import ChainedJsonlWriter

CFG = RunConfig(
    task_ref="synth-crossings-v1@sha256:" + "0" * 64,
    mode="fake",
    worker=RoleConfig(provider="fake", model_key="fake", family="fake", params=InferenceParams(max_tokens=64)),
    seed=1,
    clock="logical",
)


def _manifest_fields(trials, cfg=CFG):
    res = resolve_backends(cfg)
    return {
        "created_at": datetime(2026, 11, 4, tzinfo=UTC),
        "task": {"id": "synth-crossings-v1", "version": "1", "hash": "sha256:" + "0" * 64},
        "config_hash": sha256_bytes(canonical_json(cfg).encode()),
        "config": cfg,
        "mode": "fake",
        "backends_resolved": res,
        "versions": {"treehouse": "0.1.0", "python": "3.12", "harness": "plain_loop/1"},
        "trials": trials,
        "key_isolation_statement": res["key_isolation"].statement,
        "license_floor": "CC-BY-4.0",
        "synthetic_data": True,
    }


def make_sealed_run(store: LocalStore, run_id="run-0001", n_spans=3) -> Manifest:
    tmp = store.begin_run(run_id)
    w = ChainedJsonlWriter.for_trial(tmp.path / "trials" / "t-0.trace.jsonl", "t-0")
    for i in range(n_spans):
        w.append({"span": i})
    head = w.close()
    claims = b'{"claim_id":"c-1"}\n'
    trial = TrialHead(trial_id="t-0", role="worker", trace_file="trials/t-0.trace.jsonl", head=head,
                      claims_sha256=sha256_bytes(claims), stop="completed")
    parts = {"config.json": canonical_json(CFG).encode(), "trials/t-0.claims.jsonl": claims}
    return seal(store, tmp, parts, manifest=_manifest_fields([trial]))


@pytest.fixture
def store(tmp_path):
    return LocalStore(tmp_path / "store")


# --- blobs and put_once ---------------------------------------------------------------------------


def test_put_blob_is_content_addressed_idempotent_and_licensed(store):
    ref = store.put_blob(b"hello", media_type="text/plain", license="CC-BY-4.0")
    assert ref == sha256_bytes(b"hello")
    assert store.put_blob(b"hello", media_type="text/plain", license="CC-BY-4.0") == ref
    assert store.get(ref) == b"hello"
    hexd = ref.split(":")[1]
    blob = store.root / "blobs" / "sha256" / hexd[:2] / hexd
    meta = json.loads(blob.with_name(hexd + ".meta.json").read_text())
    assert meta == {"license": "CC-BY-4.0", "media_type": "text/plain"}
    assert stat.S_IMODE(blob.stat().st_mode) == 0o444


def test_put_once_twice_raises(store):
    store.put_once("misc/a.json", b"1")
    with pytest.raises(AlreadyExists):
        store.put_once("misc/a.json", b"2")
    assert store.get("misc/a.json") == b"1"
    assert stat.S_IMODE((store.root / "misc/a.json").stat().st_mode) == 0o444


@pytest.mark.parametrize("first_only", [True, False], ids=["first-short-write", "repeated-short-writes"])
def test_put_once_completes_short_writes_before_sync(store, monkeypatch, first_only):
    payload = b"complete payload\x00\xff"
    real_write, real_fsync = os.write, os.fsync
    calls = 0

    def short_write(fd, data):
        nonlocal calls
        calls += 1
        return real_write(fd, data if first_only and calls > 1 else data[:3])

    def sync_complete_file(fd):
        assert store.get("misc/payload") == payload
        real_fsync(fd)

    monkeypatch.setattr(os, "write", short_write)
    monkeypatch.setattr(os, "fsync", sync_complete_file)
    store.put_once("misc/payload", payload)
    assert store.get("misc/payload") == payload
    assert stat.S_IMODE((store.root / "misc/payload").stat().st_mode) == 0o444


@pytest.mark.parametrize("prefix", [0, 3], ids=["initially", "after-short-write"])
def test_put_once_raises_on_zero_write_progress(store, monkeypatch, prefix):
    real_write = os.write
    calls = 0

    def stalled_write(fd, data):
        nonlocal calls
        calls += 1
        if prefix and calls == 1:
            return real_write(fd, data[:prefix])
        assert calls == (2 if prefix else 1), "retried a write that made no progress"
        return 0

    monkeypatch.setattr(os, "write", stalled_write)
    with pytest.raises(OSError):
        store.put_once("misc/stalled", b"payload")
    assert calls == (2 if prefix else 1)


def test_put_once_accepts_empty_payload(store):
    store.put_once("misc/empty", b"")
    assert store.get("misc/empty") == b""
    assert stat.S_IMODE((store.root / "misc/empty").stat().st_mode) == 0o444


@pytest.mark.parametrize("operation", ["write", "fsync"])
def test_put_once_propagates_io_errors(store, monkeypatch, operation):
    error = OSError("simulated I/O failure")

    def fail(*args):
        raise error

    monkeypatch.setattr(os, operation, fail)
    with pytest.raises(OSError) as exc:
        store.put_once("misc/failed", b"payload")
    assert exc.value is error


def test_put_once_refuses_escape(store):
    with pytest.raises(ValueError):
        store.put_once("../outside", b"x")


# --- seal -----------------------------------------------------------------------------------------


def test_seal_moves_tmp_writes_manifest_last_and_ledger(store, monkeypatch):
    order: list[str] = []
    real = LocalStore._write_new

    def spy(self, path, data):
        order.append(path.name)
        return real(self, path, data)

    monkeypatch.setattr(LocalStore, "_write_new", spy)
    m = make_sealed_run(store)
    assert order[-2:] == ["manifest.json", "SEALED"]
    run = store.root / "runs" / "run-0001"
    assert run.is_dir() and not (store.root / "runs" / ".tmp-run-0001").exists()
    assert (run / "SEALED").read_text().strip() == m.manifest_hash
    assert m.manifest_hash == m.compute_hash()
    assert set(m.files) == {"config.json", "trials/t-0.claims.jsonl", "trials/t-0.trace.jsonl"}
    assert store.is_sealed("run-0001")
    assert store.ledger_seq() == 0
    for p in run.rglob("*"):
        if p.is_file():
            assert stat.S_IMODE(p.stat().st_mode) == 0o444


def test_seal_refuses_broken_trace(store):
    tmp = store.begin_run("run-0002")
    w = ChainedJsonlWriter.for_trial(tmp.path / "trials" / "t-0.trace.jsonl", "t-0")
    w.append({"a": 1})
    w.append({"a": 2})
    head = w.close()
    p = tmp.path / "trials" / "t-0.trace.jsonl"
    p.write_bytes(p.read_bytes().split(b"\n")[0] + b"\n")
    trial = TrialHead(trial_id="t-0", role="worker", trace_file="trials/t-0.trace.jsonl", head=head,
                      claims_sha256=sha256_bytes(b""), stop="completed")
    with pytest.raises(SealError, match="seq=1"):
        seal(store, tmp, {}, manifest=_manifest_fields([trial]))
    assert not store.is_sealed("run-0002")


def test_seal_twice_refused(store):
    make_sealed_run(store)
    with pytest.raises(AlreadyExists):
        store.begin_run("run-0001")


# --- append_record --------------------------------------------------------------------------------


def test_eval_on_unsealed_run_refused(store):
    store.begin_run("run-0003")
    with pytest.raises(UnsealedRun):
        store.append_record("score", "run-0003", {"x": 1})
    with pytest.raises(UnsealedRun):
        store.append_record("score", "never-existed", {"x": 1})


def test_append_record_chains_ledger_and_index(store):
    m = make_sealed_run(store)
    r1 = store.append_record("score", "run-0001", {"v": 1})
    r2 = store.append_record("trust", "run-0001", {"v": 2})
    assert (r1.seq, r2.seq) == (1, 2) and store.ledger_seq() == 2
    assert store.get(r1.path) == canonical_json({"v": 1}).encode()
    idx = [json.loads(x)["rec"] for x in (store.root / "evals" / "index.jsonl").read_text().splitlines()]
    assert idx[0]["manifest_hash"] == m.manifest_hash and idx[1]["kind"] == "trust"
    with pytest.raises(ValueError):
        store.append_record("bogus", "run-0001", {})
    assert verify(store).ok


# --- verify ---------------------------------------------------------------------------------------


def _writable(p):
    os.chmod(p, 0o644)
    return p


def test_verify_clean_store(store):
    make_sealed_run(store)
    store.put_blob(b"x", media_type="text/plain", license="CC0-1.0")
    rep = verify(store)
    assert rep.ok, rep.problems


def test_verify_reports_trace_tamper_with_path_and_seq(store):
    make_sealed_run(store, n_spans=4)
    p = _writable(store.root / "runs/run-0001/trials/t-0.trace.jsonl")
    lines = p.read_bytes().split(b"\n")
    lines[2] = lines[2].replace(b'"span":2', b'"span":9')
    p.write_bytes(b"\n".join(lines))
    rep = verify(store, "run-0001")
    assert not rep.ok
    bad = [x for x in rep.problems if x.seq is not None]
    assert bad[0].path.endswith("runs/run-0001/trials/t-0.trace.jsonl") and bad[0].seq == 2


def test_verify_reports_manifest_file_and_ledger_tamper(store):
    make_sealed_run(store)
    store.append_record("score", "run-0001", {"v": 1})
    c = _writable(store.root / "runs/run-0001/config.json")
    c.write_bytes(c.read_bytes() + b" ")
    led = store.root / "ledger.jsonl"
    lines = led.read_text().splitlines()
    led.write_text("\n".join([lines[1], lines[0]]) + "\n")
    rep = verify(store)
    msgs = {(p.path.split("store/")[-1], p.seq) for p in rep.problems}
    assert ("runs/run-0001/config.json", None) in msgs
    assert ("ledger.jsonl", 0) in msgs


def test_verify_detects_manifest_edit_blob_corruption_and_orphan_eval(store):
    make_sealed_run(store)
    ref = store.put_blob(b"payload", media_type="text/plain", license="CC0-1.0")
    mp = _writable(store.root / "runs/run-0001/manifest.json")
    mp.write_text(mp.read_text().replace("CC-BY-4.0", "CC0-1.0"))
    hexd = ref.split(":")[1]
    bp = _writable(store.root / "blobs/sha256" / hexd[:2] / hexd)
    bp.write_bytes(b"other")
    orphan = store.root / "evals" / "run-9999" / "score"
    orphan.mkdir(parents=True)
    (orphan / "deadbeef.json").write_text("{}")
    paths = {p.path.split("store/")[-1] for p in verify(store).problems}
    assert "runs/run-0001/manifest.json" in paths
    assert f"blobs/sha256/{hexd[:2]}/{hexd}" in paths
    assert "evals/run-9999" in paths


def test_verify_cli_exit_codes(store):
    make_sealed_run(store)
    r = CliRunner().invoke(app, ["verify", "--store", str(store.root)])
    assert r.exit_code == 0, r.output
    assert "ok" in r.output
    p = _writable(store.root / "runs/run-0001/trials/t-0.trace.jsonl")
    p.write_bytes(p.read_bytes()[:-5])
    r = CliRunner().invoke(app, ["verify", "run-0001", "--store", str(store.root)])
    assert r.exit_code == 1
    assert "runs/run-0001/trials/t-0.trace.jsonl" in r.output and "seq=2" in r.output


# --- backends -------------------------------------------------------------------------------------


def test_resolve_backends_local_with_isolation_statement():
    res = resolve_backends(CFG)
    assert res["store"].ran == "local" and res["key_isolation"].ran == "local"
    assert res["key_isolation"].statement == KEY_ISOLATION_LOCAL == "local convention, not IAM-enforced"
    assert res["tracer"].ran == "jsonl" and res["model.worker"].ran == "fake"
    assert "model.verifier" not in res


def test_resolve_backends_degrades_or_refuses_s3_and_iam():
    cfg = CFG.model_copy(update={"backends": Backends(store="s3", key_isolation="iam", tracer=["jsonl", "otlp"])})
    res = resolve_backends(cfg)
    assert res["store"].ran == "local" and res["store"].degraded_from == "s3" and res["store"].reason
    assert res["key_isolation"].ran == "local" and res["key_isolation"].statement == KEY_ISOLATION_LOCAL
    assert res["tracer"].ran == "jsonl" and res["tracer"].degraded_from == "jsonl,otlp"
    strict = cfg.model_copy(update={"backends": Backends(store="s3", allow_degrade=False)})
    with pytest.raises(BackendUnavailable):
        resolve_backends(strict)
