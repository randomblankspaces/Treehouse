"""ToolCassette: a JSONL of tool-result digests, one row per call, for ``tool_mode=verify`` (§0 row 20).

Live mode writes ``{seq, name, args_hash, digest}`` for every call that reaches a decision, blocked calls
included (judge D5b); verify mode compares each call with the row at its seq and raises ``ToolDivergence``
on any difference. Digests cover the structured result only (no pixels).

- The first ``record()`` of a cassette object truncates the file: re-recording never appends to stale rows.
- ``finish()`` (the gateway calls it when a verify-mode ``async with`` exits cleanly) raises
  ``ToolDivergence`` if any recorded row was never replayed, so a replay that stops early fails.
- One cassette is one trial and role: P5 keeps one file per ``(trial, role)``.
"""

from __future__ import annotations

import json
from pathlib import Path

from treehouse.canon import canonical_json


class ToolDivergence(AssertionError):
    pass


class ToolCassette:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.rows = [json.loads(x) for x in self.path.read_text().splitlines() if x.strip()] \
            if self.path.is_file() else []
        self._recording = False
        self._seen: set[int] = set()

    def record(self, seq: int, name: str, args_hash: str, digest: str) -> None:
        row = {"seq": seq, "name": name, "args_hash": args_hash, "digest": digest}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self._recording:
            self._recording, self.rows = True, []
            self.path.write_text("")
        self.rows.append(row)
        with self.path.open("a") as f:
            f.write(canonical_json(row) + "\n")

    def verify(self, seq: int, name: str, args_hash: str, digest: str) -> None:
        want = next((r for r in self.rows if r["seq"] == seq), None)
        got = {"seq": seq, "name": name, "args_hash": args_hash, "digest": digest}
        self._seen.add(seq)
        if want != got:
            raise ToolDivergence(f"tool call {seq} ({name}) diverges from the cassette: want {want}, got {got}")

    def finish(self) -> None:
        left = sorted({r["seq"] for r in self.rows} - self._seen)
        if left:
            raise ToolDivergence(f"{len(left)} recorded tool call(s) were never replayed (first seq {left[0]})")
