"""SealedRun: the frozen, already-loaded view of a sealed run that the pure layers (checks, score, trust,
report) receive from ``service``. Loading (store, blobs) happens in ``service``; nothing here does I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from treehouse.schemas.claims import Claim, UnderstandingStatement
from treehouse.schemas.manifest import Manifest
from treehouse.schemas.task import TaskCard
from treehouse.schemas.trace import SpanRecord


@dataclass(frozen=True)
class ToolCall:
    seq: int  # gateway call order within the trial (r-{seq:04d})
    result_id: str
    name: str
    status: str  # success | error | blocked
    span_id: str
    payload: dict[str, Any]  # the structured result (success/error) or {reason, detail} (blocked)
    key_access_attempt: bool = False


@dataclass(frozen=True)
class SealedTrial:
    trial_id: str
    stop: str
    spans: list[SpanRecord]
    claims: list[Claim]
    calls: list[ToolCall]
    understanding: UnderstandingStatement | None = None

    def call_by_result(self) -> dict[str, ToolCall]:
        return {c.result_id: c for c in self.calls}

    def call_by_span(self) -> dict[str, ToolCall]:
        return {c.span_id: c for c in self.calls}


@dataclass(frozen=True)
class SealedRun:
    run_id: str
    manifest: Manifest
    card: TaskCard
    trials: list[SealedTrial] = field(default_factory=list)

    @property
    def replayed(self) -> bool:
        return self.manifest.mode == "replay"

    @property
    def synthetic(self) -> bool:
        return self.manifest.synthetic_data

    @property
    def manifest_ref(self) -> str:
        return self.manifest.manifest_hash
