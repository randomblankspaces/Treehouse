"""Store protocol, record references and errors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

EVAL_KINDS = frozenset({"rules", "key", "leak", "sample", "gold_draw", "verifier", "gold", "score", "trust", "summary"})


class AlreadyExists(FileExistsError):
    """A put-once key, a sealed run or an eval record already exists."""


class UnsealedRun(PermissionError):
    """Evaluation records may only be appended to sealed runs."""


class SealError(RuntimeError):
    """A run could not be sealed (its trace does not verify, or it is already sealed)."""


@dataclass(frozen=True)
class RecordRef:
    kind: str
    run_id: str
    ref: str  # sha256:<hex> of the record's canonical JSON
    path: str  # relative to the store root
    seq: int  # ledger seq of the append


@dataclass(frozen=True)
class TmpRun:
    run_id: str
    path: Path  # runs/.tmp-<run_id>


class Store(Protocol):
    def put_blob(self, data: bytes, *, media_type: str, license: str) -> str: ...
    def put_once(self, key: str, data: bytes) -> None: ...
    def get(self, ref: str) -> bytes: ...
    def append_record(self, kind: str, run_id: str, rec: Any) -> RecordRef: ...
    def ledger_seq(self) -> int: ...
