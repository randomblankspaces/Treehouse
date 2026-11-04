"""ToolCassette: a JSONL of tool-result digests, one row per call, for ``tool_mode=verify`` (§0 row 20).

Live mode appends ``{seq, name, args_hash, digest}``; verify mode compares each call with the row at its
seq and raises ``ToolDivergence`` on any difference. Digests cover the structured result only (no pixels).
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

    def record(self, seq: int, name: str, args_hash: str, digest: str) -> None:
        row = {"seq": seq, "name": name, "args_hash": args_hash, "digest": digest}
        self.rows.append(row)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(canonical_json(row) + "\n")

    def verify(self, seq: int, name: str, args_hash: str, digest: str) -> None:
        want = next((r for r in self.rows if r["seq"] == seq), None)
        got = {"seq": seq, "name": name, "args_hash": args_hash, "digest": digest}
        if want != got:
            raise ToolDivergence(f"tool call {seq} ({name}) diverges from the cassette: want {want}, got {got}")
