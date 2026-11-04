"""Store protocol, record references and errors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple, Protocol

EVAL_KINDS = frozenset({"rules", "key", "leak", "sample", "gold_draw", "verifier", "gold", "score", "trust", "summary", "agentcore"})


class AlreadyExists(FileExistsError):
    """A put-once key, a sealed run or an eval record already exists."""


class UnsealedRun(PermissionError):
    """Evaluation records may only be appended to sealed runs."""


class SealError(RuntimeError):
    """A run could not be sealed (its trace does not verify, or it is already sealed)."""


class CorruptStore(RuntimeError):
    """A read found the ledger chain broken or a record/blob whose bytes do not match its hash."""


@dataclass(frozen=True)
class RecordRef:
    kind: str
    run_id: str
    ref: str  # sha256:<hex> of the record's canonical JSON
    path: str  # relative to the store root
    seq: int  # ledger seq of the append


class StoredRecord(NamedTuple):
    """One evaluation record as the ledger names it (``LocalStore.list_records``)."""

    seq: int  # ledger seq of the append: use it for GoldDraw.committed_seq / VerifierVerdict.created_seq
    ref: str  # sha256:<hex> of the record's canonical JSON
    record: Any  # the parsed record


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
