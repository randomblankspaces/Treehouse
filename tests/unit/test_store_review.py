"""Regression tests for the judged P2 review doubts (B1, B2, M1, M2, M4, M5, M6, m3-m8, m23, m25).
Each test is the doubter's exploit script turned into an assertion (scratchpad/doubt-p3/scripts)."""

from __future__ import annotations

import json
import os
import shutil

import pytest
from typer.testing import CliRunner

from treehouse.canon import canonical_json, sha256_bytes
from treehouse.cli import app
from treehouse.schemas.manifest import TrialHead
from treehouse.store.base import CorruptStore, SealError
from treehouse.store.local import LEDGER_GENESIS, LocalStore
from treehouse.store.seal import seal
from treehouse.store.verify import verify
from treehouse.trace.chain import ChainedJsonlWriter, append_chained

from .test_store import CFG, _manifest_fields, make_sealed_run


@pytest.fixture
def store(tmp_path):
    return LocalStore(tmp_path / "store")


def _chmod_all(p):
    for q in [p, *p.rglob("*")]:
        os.chmod(q, 0o755 if q.is_dir() else 0o644)


def _seal_with(store, rid="run-0001", recs=({"span": "FORGED"},), parts=None, claims=b'{"claim_id":"c-f"}\n'):
    tmp = store.begin_run(rid)
    w = ChainedJsonlWriter.for_trial(tmp.path / "trials" / "t-0.trace.jsonl", "t-0")
    for r in recs:
        w.append(r)
    head = w.close()
    th = TrialHead(trial_id="t-0", role="worker", trace_file="trials/t-0.trace.jsonl", head=head,
                   claims_sha256=sha256_bytes(claims), stop="completed")
    allparts = {"config.json": canonical_json(CFG).encode(), "trials/t-0.claims.jsonl": claims, **(parts or {})}
    return seal(store, tmp, allparts, manifest=_manifest_fields([th]))


def _reseal(store, rid="run-0001"):
    run = store.root / "runs" / rid
    _chmod_all(run)
    shutil.rmtree(run)
    return _seal_with(store, rid)


def _problems(store, *a, **kw):
    return [str(p) for p in verify(store, *a, **kw).problems]


# --- B1: every sealed run needs exactly one ledger run line --------------------------------------


def test_b1_reseal_with_ledger_intact_fails(store):
    make_sealed_run(store)
    _reseal(store)
    assert any("2 ledger run lines" in p for p in _problems(store))


def test_b1_reseal_then_delete_ledger_fails(store):
    make_sealed_run(store)
    _reseal(store)
    os.remove(store.ledger_path)
    assert any("no ledger" in p for p in _problems(store))


def test_b1_reseal_and_rebuild_ledger_without_old_line_fails(store):
    make_sealed_run(store)
    _reseal(store)
    recs = [json.loads(x)["rec"] for x in store.ledger_path.read_text().splitlines()][1:]
    os.remove(store.ledger_path)
    for r in recs:
        append_chained(store.ledger_path, r, genesis=LEDGER_GENESIS)
    assert any("prev_manifest_hash" in p for p in _problems(store))


def test_b1_ledger_tail_truncated_fails(store):
    make_sealed_run(store, "run-0001")
    make_sealed_run(store, "run-0002")
    lines = store.ledger_path.read_bytes().split(b"\n")
    store.ledger_path.write_bytes(lines[0] + b"\n")  # drop run-0002's line
    probs = _problems(store)
    assert any("run run-0002 has 0 ledger run lines" in p for p in probs)


def test_b1_run_copied_into_store_without_ledger_fails(tmp_path):
    s1, s2 = LocalStore(tmp_path / "a"), LocalStore(tmp_path / "b")
    make_sealed_run(s1)
    shutil.copytree(s1.root / "runs", s2.root / "runs")
    assert not verify(s2).ok


def test_b1_run_copied_into_store_with_other_ledger_fails(tmp_path):
    s1, s2 = LocalStore(tmp_path / "a"), LocalStore(tmp_path / "b")
    make_sealed_run(s1, "run-0001")
    make_sealed_run(s2, "run-0002")
    shutil.copytree(s1.root / "runs" / "run-0001", s2.root / "runs" / "run-0001")
    assert any("run run-0001 has 0 ledger run lines" in p for p in _problems(s2))


# --- M1: prev_manifest_hash and the ledger head -------------------------------------------------


def test_m1_seal_chains_prev_manifest_hash(store):
    a = make_sealed_run(store, "run-0001")
    b = make_sealed_run(store, "run-0002")
    assert a.prev_manifest_hash is None and b.prev_manifest_hash == a.manifest_hash
    rep = verify(store)
    assert rep.ok, rep.problems
    assert (rep.ledger_n_lines, rep.ledger_head) == (2, store.ledger_head()[1])


def test_m1_expected_head_detects_full_rewrite(store):
    make_sealed_run(store)
    head = verify(store).ledger_head
    store.append_record("score", "run-0001", {"v": 1})
    assert verify(store, expected_head=head).ok  # an append keeps the old head as a line
    os.remove(store.ledger_path)  # forger rebuilds the whole store consistently
    evals = store.root / "evals"
    _chmod_all(evals)
    shutil.rmtree(evals)
    _reseal(store)
    assert verify(store).ok  # undetectable without an external anchor...
    assert any("recorded head" in p for p in _problems(store, expected_head=head))  # ...and caught with one


def test_m1_cli_prints_ledger_head_and_checks_expect_head(store):
    make_sealed_run(store)
    head = store.ledger_head()[1]
    r = CliRunner().invoke(app, ["verify", "--store", str(store.root)])
    assert r.exit_code == 0 and f"ledger head: {head} (1 line(s))" in r.output
    r = CliRunner().invoke(app, ["verify", "--store", str(store.root), "--expect-head", "sha256:" + "f" * 64])
    assert r.exit_code == 1 and "recorded head" in r.output


# --- B2 / M6: eval records only through the ledger ------------------------------------------------


def _drop_forged_record(store, kind="gold"):
    body = canonical_json({"label": "yes", "forged": True}).encode()
    ref = sha256_bytes(body)
    p = store.root / "evals" / "run-0001" / kind / (ref.removeprefix("sha256:") + ".json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body)
    return ref


def test_b2_forged_record_without_ledger_line_fails_and_is_not_listed(store):
    make_sealed_run(store)
    real = store.append_record("gold", "run-0001", {"label": "no"})
    forged = _drop_forged_record(store)
    probs = _problems(store)
    assert any("no ledger line" in p for p in probs) and any("no evals index line" in p for p in probs)
    listed = store.list_records("run-0001", "gold")
    assert [(r.seq, r.ref, r.record) for r in listed] == [(real.seq, real.ref, {"label": "no"})]
    assert store.seq_of("gold", "run-0001", forged) is None and store.seq_of("gold", "run-0001", real.ref) == 1


def test_b2_stray_files_and_unknown_kinds_fail(store):
    make_sealed_run(store)
    store.append_record("score", "run-0001", {"v": 1})
    d = store.root / "evals" / "run-0001"
    (d / "bogus").mkdir()
    (d / "score" / "notes.txt").write_text("x")
    probs = _problems(store)
    assert any("unknown eval kind 'bogus'" in p for p in probs)
    assert any("notes.txt" in p and "stray" in p for p in probs)


def test_b2_index_line_without_ledger_line_fails(store):
    from treehouse.store.local import INDEX_GENESIS

    m = make_sealed_run(store)
    append_chained(store.index_path, {"kind": "score", "run_id": "run-0001", "ref": "sha256:" + "a" * 64,
                                      "manifest_hash": m.manifest_hash}, genesis=INDEX_GENESIS)
    assert any("with no ledger line" in p for p in _problems(store))


def test_m6_list_records_in_ledger_order_with_seq(store):
    make_sealed_run(store)
    r1 = store.append_record("verifier", "run-0001", {"v": 1})
    store.append_record("score", "run-0001", {"s": 1})
    r3 = store.append_record("verifier", "run-0001", {"v": 2})
    got = store.list_records("run-0001", "verifier")
    assert [(g.seq, g.ref, g.record) for g in got] == [(r1.seq, r1.ref, {"v": 1}), (r3.seq, r3.ref, {"v": 2})]
    assert (r1.seq, r3.seq) == (1, 3)


def test_m6_list_records_refuses_corrupt_ledger(store):
    make_sealed_run(store)
    store.append_record("score", "run-0001", {"v": 1})
    lines = store.ledger_path.read_text().splitlines()
    store.ledger_path.write_text("\n".join([lines[1], lines[0]]) + "\n")
    with pytest.raises(CorruptStore):
        store.list_records("run-0001", "score")


# --- M5: identical re-score is idempotent, a different record appends ----------------------------


def test_m5_identical_rescore_is_a_noop_different_appends(store):
    make_sealed_run(store)
    r1 = store.append_record("score", "run-0001", {"v": 1})
    again = store.append_record("score", "run-0001", {"v": 1})
    assert again == r1 and store.ledger_seq() == 1
    r2 = store.append_record("score", "run-0001", {"v": 1, "scorer": "v2"})
    assert r2.seq == 2 and r2.ref != r1.ref
    assert [r.seq for r in store.list_records("run-0001", "score")] == [1, 2]
    assert verify(store).ok


def test_m5_append_completes_after_crash_between_file_and_ledger(store):
    make_sealed_run(store)
    body = canonical_json({"v": 1}).encode()
    store.put_once(f"evals/run-0001/score/{sha256_bytes(body).removeprefix('sha256:')}.json", body)
    assert not verify(store).ok
    r = store.append_record("score", "run-0001", {"v": 1})
    assert r.seq == 1 and verify(store).ok


# --- M2: referenced blobs must exist; spans bind to the manifest (m8) ----------------------------


def _span(ref=None, run_id="run-0001", trial_id="t-0"):
    attrs = {"treehouse.run.id": run_id, "treehouse.trial.id": trial_id,
             "treehouse.config.hash": sha256_bytes(canonical_json(CFG).encode())}
    if ref:
        attrs["treehouse.input.messages_ref"] = ref
    return {"attributes": attrs, "name": "chat m", "op": "chat"}


def test_m2_missing_referenced_blob_fails(store):
    ref = store.put_blob(b'{"messages":[]}', media_type="application/json", license="CC0-1.0")
    _seal_with(store, recs=[_span(ref)])
    assert verify(store).ok
    hexd = ref.removeprefix("sha256:")
    for q in (store.root / "blobs/sha256" / hexd[:2]).iterdir():
        os.chmod(q, 0o644)
        q.unlink()
    assert any(f"references blob {ref}" in p for p in _problems(store))


def test_m8_span_from_another_run_fails(store):
    _seal_with(store, recs=[_span(run_id="run-9999")])
    assert any("treehouse.run.id='run-9999'" in p for p in _problems(store))


# --- M4 / m5 / m25: seal refuses paths outside the run and bad claims ----------------------------


@pytest.mark.parametrize("rel", ["../run-y/SEALED", "../../evil.txt", "/abs/x", "a/../b", "a\\b", "./x"])
def test_m4_seal_refuses_unsafe_part_paths(store, rel):
    with pytest.raises(SealError):
        _seal_with(store, parts={rel: b"x"})
    assert not (store.root / "evil.txt").exists() and not (store.root / "runs" / "run-y").exists()


def test_m4_seal_refuses_trace_file_outside_run(store, tmp_path):
    tmp = store.begin_run("r")
    outside = tmp_path / "elsewhere" / "t-0.trace.jsonl"
    w = ChainedJsonlWriter.for_trial(outside, "t-0")
    w.append({"a": 1})
    th = TrialHead(trial_id="t-0", role="worker", trace_file=str(outside), head=w.close(),
                   claims_sha256=sha256_bytes(b""), stop="completed")
    with pytest.raises(SealError, match="relative"):
        seal(store, tmp, {}, manifest=_manifest_fields([th]))


def test_m25_seal_refuses_symlinks(store, tmp_path):
    target = tmp_path / "outside.txt"
    target.write_text("outside")
    tmp = store.begin_run("run-0001")
    os.symlink(target, tmp.path / "link.txt")
    w = ChainedJsonlWriter.for_trial(tmp.path / "trials" / "t-0.trace.jsonl", "t-0")
    w.append({"a": 1})
    claims = b"\n"
    th = TrialHead(trial_id="t-0", role="worker", trace_file="trials/t-0.trace.jsonl", head=w.close(),
                   claims_sha256=sha256_bytes(claims), stop="completed")
    with pytest.raises(SealError, match="symlink"):
        seal(store, tmp, {"trials/t-0.claims.jsonl": claims}, manifest=_manifest_fields([th]))
    assert os.stat(target).st_mode & 0o200  # target was not chmodded read-only


def test_m5_seal_checks_claims_file_and_sha(store):
    with pytest.raises(SealError, match="claims_sha256"):
        _seal_with(store, claims=b"{}\n", parts={"trials/t-0.claims.jsonl": b"other\n"})
    tmp = store.begin_run("run-0002")
    w = ChainedJsonlWriter.for_trial(tmp.path / "trials" / "t-0.trace.jsonl", "t-0")
    w.append({"a": 1})
    th = TrialHead(trial_id="t-0", role="worker", trace_file="trials/t-0.trace.jsonl", head=w.close(),
                   claims_sha256=sha256_bytes(b""), stop="completed")
    with pytest.raises(SealError, match="claims file"):
        seal(store, tmp, {}, manifest=_manifest_fields([th]))


# --- m3 / m4 / m6 / m23 ---------------------------------------------------------------------------


def test_m3_traversal_ids_report_fail_not_crash(store):
    make_sealed_run(store)
    assert any("invalid run id" in p for p in _problems(store, "../../etc"))
    r = CliRunner().invoke(app, ["verify", "../../etc", "--store", str(store.root)])
    assert r.exit_code == 1 and "FAIL" in r.output and r.exception is None or isinstance(r.exception, SystemExit)
    append_chained(store.ledger_path, {"kind": "run", "run_id": "../../x", "ref": "y"}, genesis=LEDGER_GENESIS)
    assert any("invalid run id" in p for p in _problems(store))


@pytest.mark.parametrize("rid", ["a/b", "x/..", "..", ".hidden", ""])
def test_m4_invalid_run_ids_refused(store, rid):
    with pytest.raises(ValueError):
        store.begin_run(rid)


def test_m6_non_canonical_manifest_bytes_fail(store):
    make_sealed_run(store)
    mp = store.root / "runs/run-0001/manifest.json"
    os.chmod(mp, 0o644)
    mp.write_text(json.dumps(json.loads(mp.read_text()), indent=4))
    assert any("not canonical" in p for p in _problems(store))


def test_m23_get_rehashes_blobs(store):
    ref = store.put_blob(b"payload", media_type="text/plain", license="CC0-1.0")
    p = store.blob_path(ref)
    os.chmod(p, 0o644)
    p.write_bytes(b"tampered")
    with pytest.raises(CorruptStore):
        store.get(ref)
    with pytest.raises(CorruptStore):
        store.put_blob(b"payload", media_type="text/plain", license="CC0-1.0")
