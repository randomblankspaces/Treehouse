"""Claims the agent records, and its understanding statement."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from treehouse.schemas.base import Frozen
from treehouse.schemas.geo import BBox, Point
from treehouse.schemas.task import ClaimStatus


class EvidenceRef(Frozen):
    result_id: str
    role: Literal["pre", "post", "existence"]


class Claim(Frozen):
    claim_id: str
    run_id: str
    trial_id: str
    step_id: str
    geometry: Point
    bbox: BBox | None = None
    cls: str
    status: ClaimStatus
    confidence: float = Field(ge=0, le=1)  # the agent's own figure; shown as "agent's claim", never as a Treehouse number
    reason: str
    evidence_refs: list[EvidenceRef] = []
    span_id: str
    grounded: bool
    unresolved_refs: list[str] = []
    contaminated: bool = False
    synthetic: bool


class UnderstandingStatement(Frozen):
    goal_restated: str
    scope: str
    planned_data: list[str] = []
    known_limits: list[str] = []
    span_id: str
