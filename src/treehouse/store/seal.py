"""seal(): hash every file of a temporary run, write the manifest LAST, then SEALED, then rename."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from treehouse.canon import canonical_json, sha256_bytes
from treehouse.schemas.manifest import Manifest
from treehouse.store.base import AlreadyExists, SealError, TmpRun
from treehouse.store.local import LocalStore
from treehouse.trace.chain import trial_genesis, verify_chain

RESERVED = {"manifest.json", "SEALED"}


def seal(store: LocalStore, tmp_run: TmpRun, parts: Mapping[str, bytes], *, manifest: Mapping[str, Any]) -> Manifest:
    """``parts`` are extra files (relative path -> bytes) written into the run before hashing.
    ``manifest`` holds every Manifest field except ``run_id``, ``files`` and ``manifest_hash``."""
    tmp = tmp_run.path
    if not tmp.is_dir() or not tmp.name.startswith(".tmp-"):
        raise SealError(f"not a temporary run directory: {tmp}")
    final = tmp.with_name(tmp_run.run_id)
    if final.exists():
        raise AlreadyExists(f"run {tmp_run.run_id} is already sealed")
    for rel, data in sorted(parts.items()):
        if rel in RESERVED:
            raise SealError(f"{rel} is written by seal()")
        store._write_new(store._resolve(f"runs/{tmp.name}/{rel}"), data)

    draft = Manifest.model_validate({**manifest, "run_id": tmp_run.run_id, "files": {}, "manifest_hash": ""})
    for th in draft.trials:
        check = verify_chain(tmp / th.trace_file, genesis=trial_genesis(th.trial_id), expected=th.head)
        if not check.ok:
            raise SealError(f"{th.trace_file} seq={check.first_bad_seq}: {check.reason}")

    files: dict[str, str] = {}
    for p in sorted(tmp.rglob("*")):
        if p.is_file():
            rel = p.relative_to(tmp).as_posix()
            if rel in RESERVED:
                raise SealError(f"{rel} already present before seal")
            files[rel] = sha256_bytes(p.read_bytes())
            os.chmod(p, 0o444)

    m = draft.model_copy(update={"files": files})
    m = Manifest.model_validate({**m.model_dump(mode="json"), "manifest_hash": m.compute_hash()})
    store._write_new(tmp / "manifest.json", canonical_json(m).encode("utf-8"))  # manifest LAST
    store._write_new(tmp / "SEALED", (m.manifest_hash + "\n").encode())
    os.rename(tmp, final)
    store.append_ledger({"kind": "run", "run_id": m.run_id, "ref": m.manifest_hash})
    return m
