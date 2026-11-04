"""LocalStore: the §4 layout on a local filesystem.

Every file is created with ``O_EXCL`` and made read-only (0444). Runs are assembled in
``runs/.tmp-<id>`` and become visible only by an atomic rename at seal time. ``ledger.jsonl`` is a
hash chain over every seal and every evaluation record; its seq orders events (gold draw vs verdicts).

Read evaluation records only through ``list_records`` / ``seq_of`` (ledger-driven), never by globbing
``evals/``: verify() rejects any record file without its ledger and index lines, but a glob would not.

Limits: the store is tamper-evident only against a ledger head recorded elsewhere (``verify --expect-head``);
anyone who can rewrite the whole store can recompute every hash (S3 Object Lock is W5). The ledger lock is
``fcntl.flock``, so macOS and Linux are supported; Windows is not.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

from treehouse.canon import canonical_json, sha256_bytes
from treehouse.store.base import (
    EVAL_KINDS,
    AlreadyExists,
    CorruptStore,
    RecordRef,
    StoredRecord,
    TmpRun,
    UnsealedRun,
)
from treehouse.trace.chain import append_chained, genesis_for, read_chain, verify_chain

LEDGER_GENESIS = genesis_for("treehouse/ledger")
INDEX_GENESIS = genesis_for("treehouse/evals/index")
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def check_run_id(run_id: str) -> str:
    """Run ids are one path segment: ``^[A-Za-z0-9][A-Za-z0-9._-]*$`` (no ``/``, ``..`` or leading dot)."""
    if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id) or ".." in run_id:
        raise ValueError(f"invalid run id {run_id!r}")
    return run_id


def default_store_root() -> Path:
    return Path(os.environ.get("TREEHOUSE_STORE") or ".treehouse")


class LocalStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger_path = self.root / "ledger.jsonl"
        self.index_path = self.root / "evals" / "index.jsonl"

    # --- paths -----------------------------------------------------------------------------------
    def _resolve(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if not p.is_relative_to(self.root.resolve()) or p == self.root.resolve():
            raise ValueError(f"key escapes the store root: {key!r}")
        return p

    def blob_path(self, ref: str) -> Path:
        hexd = ref.removeprefix("sha256:")
        if len(hexd) != 64 or not all(c in "0123456789abcdef" for c in hexd):
            raise ValueError(f"not a sha256 ref: {ref!r}")
        return self.root / "blobs" / "sha256" / hexd[:2] / hexd

    def run_dir(self, run_id: str) -> Path:
        return self._resolve(f"runs/{check_run_id(run_id)}")

    def is_sealed(self, run_id: str) -> bool:
        return (self.run_dir(run_id) / "SEALED").is_file()

    # --- writes ----------------------------------------------------------------------------------
    def _write_new(self, path: Path, data: bytes) -> None:
        """Create ``path`` exclusively, write ``data``, fsync, chmod 0444. Raises AlreadyExists."""
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
        except FileExistsError as e:
            raise AlreadyExists(str(path)) from e
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.chmod(path, 0o444)

    def put_once(self, key: str, data: bytes) -> None:
        self._write_new(self._resolve(key), data)

    def put_blob(self, data: bytes, *, media_type: str, license: str) -> str:
        ref = sha256_bytes(data)
        path = self.blob_path(ref)
        meta = path.with_name(path.name + ".meta.json")
        for target, body in ((meta, canonical_json({"license": license, "media_type": media_type}).encode()),
                             (path, data)):
            if target.exists():
                if target == path and sha256_bytes(path.read_bytes()) != ref:
                    raise CorruptStore(f"existing blob {path} does not match its name")
                continue
            tmp = target.with_name(f".{target.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
            self._write_new(tmp, body)
            try:
                os.link(tmp, target)  # atomic, never overwrites
            except FileExistsError:
                pass
            finally:
                tmp.unlink()
        return ref

    def get(self, ref: str) -> bytes:
        """Blob bytes (re-hashed; ``CorruptStore`` on mismatch) or the bytes of a store-relative key."""
        if ref.startswith("sha256:"):
            data = self.blob_path(ref).read_bytes()
            if sha256_bytes(data) != ref:
                raise CorruptStore(f"blob {ref} does not match its name")
            return data
        return self._resolve(ref).read_bytes()

    # --- runs ------------------------------------------------------------------------------------
    def begin_run(self, run_id: str) -> TmpRun:
        final = self.run_dir(run_id)  # validates the id
        tmp = final.with_name(".tmp-" + run_id)
        if final.exists() or tmp.exists():
            raise AlreadyExists(f"run {run_id} already exists")
        tmp.mkdir(parents=True)
        return TmpRun(run_id=run_id, path=tmp)

    def append_ledger(self, rec: dict[str, Any]) -> int:
        seq, _ = append_chained(self.ledger_path, rec, genesis=LEDGER_GENESIS)
        return seq

    def ledger_seq(self) -> int:
        """Seq of the last ledger line, or -1 when the ledger is empty."""
        return self.ledger_head()[0]

    def ledger_lines(self) -> list[dict[str, Any]]:
        """Parsed ledger lines ``{seq, prev, rec, h}`` (unverified; verify() checks the chain)."""
        return read_chain(self.ledger_path) if self.ledger_path.exists() else []

    def ledger_head(self) -> tuple[int, str]:
        """``(seq, h)`` of the last ledger line; ``(-1, LEDGER_GENESIS)`` when the ledger is empty.
        Record ``h`` somewhere outside the store and pass it to ``verify(expected_head=...)`` later."""
        lines = self.ledger_lines()
        return (lines[-1]["seq"], lines[-1]["h"]) if lines else (-1, LEDGER_GENESIS)

    def last_run_manifest_hash(self) -> str | None:
        """Manifest hash named by the last ``kind=run`` ledger line (seal() puts it in ``prev_manifest_hash``)."""
        runs = [ln["rec"]["ref"] for ln in self.ledger_lines() if ln["rec"].get("kind") == "run"]
        return runs[-1] if runs else None

    def _verified_ledger(self) -> list[dict[str, Any]]:
        if not self.ledger_path.exists():
            return []
        check = verify_chain(self.ledger_path, genesis=LEDGER_GENESIS)
        if not check.ok:
            raise CorruptStore(f"ledger seq={check.first_bad_seq}: {check.reason}")
        return read_chain(self.ledger_path)

    def _record_rel(self, kind: str, run_id: str, ref: str) -> str:
        return f"evals/{check_run_id(run_id)}/{kind}/{ref.removeprefix('sha256:')}.json"

    def seq_of(self, kind: str, run_id: str, ref: str) -> int | None:
        """Ledger seq at which record ``ref`` of ``kind`` was appended for ``run_id`` (None if never)."""
        for ln in self._verified_ledger():
            r = ln["rec"]
            if (r.get("kind"), r.get("run_id"), r.get("ref")) == (kind, run_id, ref):
                return ln["seq"]
        return None

    def list_records(self, run_id: str, kind: str) -> list[StoredRecord]:
        """Every ``kind`` record of ``run_id`` in ledger order, as ``(seq, ref, record)``. Driven by the
        (verified) ledger, so a record file dropped into ``evals/`` without a ledger line is never returned.
        Raises ``CorruptStore`` if the ledger chain is broken or a record's bytes do not match its ref."""
        if kind not in EVAL_KINDS:
            raise ValueError(f"unknown eval kind {kind!r}")
        out: list[StoredRecord] = []
        for ln in self._verified_ledger():
            r = ln["rec"]
            if r.get("kind") != kind or r.get("run_id") != run_id:
                continue
            body = self._resolve(self._record_rel(kind, run_id, r["ref"])).read_bytes()
            if sha256_bytes(body) != r["ref"]:
                raise CorruptStore(f"record {r['ref']} of run {run_id} does not match its hash")
            out.append(StoredRecord(seq=ln["seq"], ref=r["ref"], record=json.loads(body)))
        return out

    def append_record(self, kind: str, run_id: str, rec: Any) -> RecordRef:
        """Write an evaluation record for a sealed run and chain it into the ledger and evals index.

        Records are content-addressed, so appending a byte-identical record again (a deterministic
        re-score) is a no-op that returns the existing ``RecordRef`` with its original ledger seq; a
        record that differs in any byte is appended as a new record. ``RecordRef.seq`` is the ledger seq."""
        if kind not in EVAL_KINDS:
            raise ValueError(f"unknown eval kind {kind!r}")
        if not self.is_sealed(run_id):
            raise UnsealedRun(f"run {run_id} is not sealed; evaluation records are refused")
        body = canonical_json(rec).encode("utf-8")
        ref = sha256_bytes(body)
        rel = self._record_rel(kind, run_id, ref)
        path = self._resolve(rel)
        manifest_hash = json.loads((self.run_dir(run_id) / "manifest.json").read_text())["manifest_hash"]
        index_rec = {"kind": kind, "run_id": run_id, "ref": ref, "manifest_hash": manifest_hash}
        if path.exists():
            if path.read_bytes() != body:
                raise CorruptStore(f"existing record {rel} does not match its hash")
            seq = self.seq_of(kind, run_id, ref)
            if seq is not None:
                return RecordRef(kind=kind, run_id=run_id, ref=ref, path=rel, seq=seq)
            # a crash between the file write and the ledger append: finish the append
            indexed = self.index_path.exists() and any(ln["rec"] == index_rec for ln in read_chain(self.index_path))
        else:
            self.put_once(rel, body)
            indexed = False
        if not indexed:
            append_chained(self.index_path, index_rec, genesis=INDEX_GENESIS)
        seq = self.append_ledger({"kind": kind, "run_id": run_id, "ref": ref})
        return RecordRef(kind=kind, run_id=run_id, ref=ref, path=rel, seq=seq)
