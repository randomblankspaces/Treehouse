"""A tiny traced trial under LogicalClock + IdSource(7) is byte-identical to the frozen golden file.

Regenerate after an intended tracer/schema change:
    TREEHOUSE_REGEN_GOLDEN=1 uv run pytest tests/golden/test_trace_golden.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from treehouse.clock import LogicalClock
from treehouse.ids import IdSource
from treehouse.trace.chain import ChainedJsonlWriter
from treehouse.trace.tracer import CHAT_ATTRS, TOOL_ATTRS, TrialTracer

GOLDEN = Path(__file__).parent / "trace"
BASE = {
    "treehouse.task.id": "synth-crossings-v1",
    "treehouse.task.hash": "sha256:" + "0" * 64,
    "treehouse.run.id": "run-0001",
    "treehouse.trial.id": "t-0",
    "treehouse.trial.index": 0,
    "treehouse.role": "worker",
    "treehouse.config.hash": "sha256:" + "1" * 64,
}


def _build(path: Path):
    ids = IdSource(7)
    tr = TrialTracer(ChainedJsonlWriter.for_trial(path, "t-0"), trace_id=ids.trace_id(), clock=LogicalClock(),
                     ids=ids, base_attrs=BASE)
    chat = {k: "x" for k in CHAT_ATTRS} | {"gen_ai.usage.input_tokens": 10, "gen_ai.usage.output_tokens": 3}
    tool = {k: "y" for k in TOOL_ATTRS} | {"treehouse.tool.blocked": False, "treehouse.tool.bytes_read": 65536}
    with tr.span("invoke_agent worker", "invoke_agent"):
        with tr.span("chat fake-model", "chat", chat) as s:
            s.event("treehouse.budget.threshold", axis="tokens", pct=50)
        with tr.span("execute_tool imagery_window", "execute_tool", tool) as s:
            s.set("treehouse.image.sha256", "sha256:" + "d" * 64)
    return tr.close()


def test_tiny_trial_matches_golden(tmp_path):
    head = _build(tmp_path / "t-0.trace.jsonl")
    got = (tmp_path / "t-0.trace.jsonl").read_bytes()
    if os.environ.get("TREEHOUSE_REGEN_GOLDEN") == "1":
        GOLDEN.mkdir(exist_ok=True)
        (GOLDEN / "tiny-trial.trace.jsonl").write_bytes(got)
        (GOLDEN / "tiny-trial.head.json").write_text(json.dumps(head.model_dump(), indent=2, sort_keys=True) + "\n")
    assert got == (GOLDEN / "tiny-trial.trace.jsonl").read_bytes()
    assert head.model_dump() == json.loads((GOLDEN / "tiny-trial.head.json").read_text())
