"""Hash-chained JSONL files.

Each line is the canonical JSON of ``{seq, prev, rec, h}`` with ``h = sha256(prev + canon(rec))`` and
``prev`` the previous line's ``h`` (the genesis value for line 0). A trial's genesis is
``sha256("treehouse/trial/" + trial_id)``. ``verify_chain`` reports the seq of the first bad line.

Files are written in binary with ``\n`` line ends on every platform (no ``\r\n`` from text mode). Shared
chains are locked with ``fcntl.flock``: macOS and Linux are supported, Windows is not.
"""

from __future__ import annotations

import fcntl
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from treehouse.canon import canonical_json, sha256_bytes
from treehouse.schemas.trace import ChainHead, chain_hash


def genesis_for(label: str) -> str:
    return sha256_bytes(label.encode("utf-8"))


def trial_genesis(trial_id: str) -> str:
    return genesis_for("treehouse/trial/" + trial_id)


def _line(seq: int, prev: str, rec: dict[str, Any]) -> tuple[str, str]:
    h = chain_hash(prev, rec)
    return canonical_json({"seq": seq, "prev": prev, "rec": rec, "h": h}) + "\n", h


class ChainedJsonlWriter:
    """Writes one new chained file. Refuses to overwrite an existing file."""

    def __init__(self, path: Path | str, *, genesis: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._f = open(self.path, "xb")  # noqa: SIM115 - closed in close()
        self._prev = genesis
        self._seq = 0

    @classmethod
    def for_trial(cls, path: Path | str, trial_id: str) -> ChainedJsonlWriter:
        return cls(path, genesis=trial_genesis(trial_id))

    def append(self, rec: dict[str, Any]) -> str:
        if self._f.closed:
            raise ValueError(f"chain {self.path} is closed")
        line, h = _line(self._seq, self._prev, rec)
        self._f.write(line.encode("utf-8"))
        self._f.flush()
        self._prev, self._seq = h, self._seq + 1
        return h

    def close(self) -> ChainHead:
        if not self._f.closed:
            self._f.close()
        return ChainHead(head=self._prev, n_lines=self._seq, file_sha256=sha256_bytes(self.path.read_bytes()))


def append_chained(path: Path | str, rec: dict[str, Any], *, genesis: str) -> tuple[int, str]:
    """Append one record to a shared chained file (e.g. the store ledger) under an exclusive lock.

    Returns ``(seq, h)``. The tail is re-read under the lock so concurrent appenders stay chained."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "ab+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            last = None
            for raw in f:
                if raw.strip():
                    last = raw
            seq, prev = (0, genesis) if last is None else (json.loads(last)["seq"] + 1, json.loads(last)["h"])
            line, h = _line(seq, prev, rec)
            f.write(line.encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    return seq, h


@dataclass(frozen=True)
class ChainCheck:
    ok: bool
    n_lines: int  # lines that verified before the first problem
    head: str  # h of the last good line (genesis if none)
    first_bad_seq: int | None = None
    reason: str | None = None


def read_chain(path: Path | str) -> list[dict[str, Any]]:
    """Parsed lines, without verification."""
    return [json.loads(x) for x in Path(path).read_bytes().split(b"\n") if x]


def verify_chain(path: Path | str, *, genesis: str, expected: ChainHead | None = None) -> ChainCheck:
    """Check every line; with ``expected`` also check length, head and file sha (truncation, rewrite)."""
    path = Path(path)
    if not path.is_file():
        return ChainCheck(False, 0, genesis, 0, "file missing")
    raw = path.read_bytes()
    pieces = raw.split(b"\n")
    tail = pieces.pop()  # b"" when the file ends with a newline
    prev = genesis
    for seq, piece in enumerate(pieces):
        bad = _check_line(piece, seq, prev)
        if bad:
            return ChainCheck(False, seq, prev, seq, bad)
        prev = json.loads(piece)["h"]
    n = len(pieces)
    if tail:
        return ChainCheck(False, n, prev, n, "truncated line (no newline)")
    if expected is not None:
        if n < expected.n_lines:
            return ChainCheck(False, n, prev, n, f"truncated: {n} of {expected.n_lines} lines")
        if n > expected.n_lines:
            return ChainCheck(False, expected.n_lines, prev, expected.n_lines, "lines after the sealed head")
        if prev != expected.head:
            return ChainCheck(False, n, prev, max(n - 1, 0), "head mismatch: chain rewritten")
        if sha256_bytes(raw) != expected.file_sha256:
            return ChainCheck(False, n, prev, max(n - 1, 0), "file sha256 mismatch")
    return ChainCheck(True, n, prev)


def _check_line(piece: bytes, seq: int, prev: str) -> str | None:
    try:
        obj = json.loads(piece.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return "unparseable line"
    if not isinstance(obj, dict) or set(obj) != {"seq", "prev", "rec", "h"} or not isinstance(obj["rec"], dict):
        return "malformed line"
    try:
        if canonical_json(obj).encode("utf-8") != piece:
            return "non-canonical line"
    except ValueError:
        return "non-canonical line"
    if obj["seq"] != seq or isinstance(obj["seq"], bool):
        return f"seq {obj['seq']!r} where {seq} expected (deleted or reordered line)"
    if obj["prev"] != prev:
        return "prev does not match the previous line's h"
    if chain_hash(prev, obj["rec"]) != obj["h"]:
        return "h does not match sha256(prev + canon(rec))"
    return None
