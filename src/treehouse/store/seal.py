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
TRACE_SUFFIX, CLAIMS_SUFFIX = ".trace.jsonl", ".claims.jsonl"


def safe_run_path(rel: str) -> str | None:
    """Why ``rel`` is not a safe run-relative POSIX path (None when it is): no absolute paths, no ``..``,
    no backslashes, no empty or ``.`` segments."""
    if not rel or rel.startswith("/") or "\\" in rel or ":" in rel.split("/")[0]:
        return f"{rel!r} is not a relative POSIX path"
    if any(seg in ("", ".", "..") for seg in rel.split("/")):
        return f"{rel!r} has an empty, '.' or '..' segment"
    return None


def claims_file_for(trace_file: str) -> str | None:
    """The trial's claims file: the trace file's sibling ``<tid>.claims.jsonl`` (§4 layout)."""
    return trace_file[: -len(TRACE_SUFFIX)] + CLAIMS_SUFFIX if trace_file.endswith(TRACE_SUFFIX) else None


def seal(store: LocalStore, tmp_run: TmpRun, parts: Mapping[str, bytes], *, manifest: Mapping[str, Any]) -> Manifest:
    """``parts`` are extra files (relative path -> bytes) written into the run before hashing.
    ``manifest`` holds every Manifest field except ``run_id``, ``files`` and ``manifest_hash``.

    seal() sets ``prev_manifest_hash`` to the manifest hash of the last ``kind=run`` ledger line (None for
    the first run), refuses unsafe paths and symlinks, and requires every trial's trace and claims files
    (``trials/<tid>.trace.jsonl`` + ``trials/<tid>.claims.jsonl``) to be inside the run and to match the
    trial head and ``claims_sha256``."""
    tmp = tmp_run.path
    if not tmp.is_dir() or not tmp.name.startswith(".tmp-"):
        raise SealError(f"not a temporary run directory: {tmp}")
    final = tmp.with_name(tmp_run.run_id)
    if final.exists():
        raise AlreadyExists(f"run {tmp_run.run_id} is already sealed")
    root = tmp.resolve()
    for rel, data in sorted(parts.items()):
        if rel in RESERVED:
            raise SealError(f"{rel} is written by seal()")
        bad = safe_run_path(rel)
        if bad:
            raise SealError(bad)
        target = (tmp / rel).resolve()
        if not target.is_relative_to(root):
            raise SealError(f"{rel!r} escapes the run directory")
        store._write_new(target, data)

    prev = store.last_run_manifest_hash()
    if manifest.get("prev_manifest_hash") not in (None, prev):
        raise SealError(f"prev_manifest_hash {manifest['prev_manifest_hash']} != last sealed run {prev}")
    draft = Manifest.model_validate({**manifest, "run_id": tmp_run.run_id, "files": {}, "manifest_hash": "",
                                     "prev_manifest_hash": prev})
    for th in draft.trials:
        claims = claims_file_for(th.trace_file)
        bad = safe_run_path(th.trace_file) or (None if claims else f"{th.trace_file!r} must end in {TRACE_SUFFIX}")
        if bad:
            raise SealError(f"trial {th.trial_id}: {bad}")
        check = verify_chain(tmp / th.trace_file, genesis=trial_genesis(th.trial_id), expected=th.head)
        if not check.ok:
            raise SealError(f"{th.trace_file} seq={check.first_bad_seq}: {check.reason}")
        cp = tmp / str(claims)
        if not cp.is_file() or cp.is_symlink():
            raise SealError(f"trial {th.trial_id}: claims file {claims} missing")
        if sha256_bytes(cp.read_bytes()) != th.claims_sha256:
            raise SealError(f"trial {th.trial_id}: {claims} does not match claims_sha256")

    files: dict[str, str] = {}
    for p in sorted(tmp.rglob("*")):
        if p.is_symlink():
            raise SealError(f"{p.relative_to(tmp).as_posix()} is a symlink; seal refuses symlinks")
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


__all__ = ["RESERVED", "claims_file_for", "safe_run_path", "seal"]
