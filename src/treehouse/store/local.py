"""LocalStore: the §4 layout on a local filesystem.

Every file is created with ``O_EXCL`` and made read-only (0444). Runs are assembled in
``runs/.tmp-<id>`` and become visible only by an atomic rename at seal time. ``ledger.jsonl`` is a
hash chain over every seal and every evaluation record; its seq orders events (gold draw vs verdicts).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from treehouse.canon import canonical_json, sha256_bytes
from treehouse.store.base import EVAL_KINDS, AlreadyExists, RecordRef, TmpRun, UnsealedRun
from treehouse.trace.chain import append_chained, genesis_for, read_chain

LEDGER_GENESIS = genesis_for("treehouse/ledger")
INDEX_GENESIS = genesis_for("treehouse/evals/index")


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
        return self._resolve(f"runs/{run_id}")

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
                continue
            tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
            if tmp.exists():
                os.chmod(tmp, 0o644)
                tmp.unlink()
            self._write_new(tmp, body)
            try:
                os.link(tmp, target)  # atomic, never overwrites
            except FileExistsError:
                pass
            finally:
                tmp.unlink()
        return ref

    def get(self, ref: str) -> bytes:
        if ref.startswith("sha256:"):
            return self.blob_path(ref).read_bytes()
        return self._resolve(ref).read_bytes()

    # --- runs ------------------------------------------------------------------------------------
    def begin_run(self, run_id: str) -> TmpRun:
        final = self.run_dir(run_id)
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
        if not self.ledger_path.exists():
            return -1
        lines = read_chain(self.ledger_path)
        return lines[-1]["seq"] if lines else -1

    def append_record(self, kind: str, run_id: str, rec: Any) -> RecordRef:
        """Write an evaluation record for a sealed run and chain it into the ledger and evals index."""
        if kind not in EVAL_KINDS:
            raise ValueError(f"unknown eval kind {kind!r}")
        if not self.is_sealed(run_id):
            raise UnsealedRun(f"run {run_id} is not sealed; evaluation records are refused")
        body = canonical_json(rec).encode("utf-8")
        ref = sha256_bytes(body)
        rel = f"evals/{run_id}/{kind}/{ref.removeprefix('sha256:')}.json"
        self.put_once(rel, body)
        manifest_hash = json.loads((self.run_dir(run_id) / "manifest.json").read_text())["manifest_hash"]
        append_chained(self.index_path, {"kind": kind, "run_id": run_id, "ref": ref, "manifest_hash": manifest_hash},
                       genesis=INDEX_GENESIS)
        seq = self.append_ledger({"kind": kind, "run_id": run_id, "ref": ref})
        return RecordRef(kind=kind, run_id=run_id, ref=ref, path=rel, seq=seq)
