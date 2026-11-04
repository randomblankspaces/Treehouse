"""The ``claims`` server: ``record_claim``, ``note_limitation``, ``submit_understanding``.

The tools write to a ``ClaimLedger`` the gateway owns. The gateway tells the ledger every result id
it issued (and which were blocked) and the span id of the current call, so a claim gets
``grounded=False`` when an evidence ref does not resolve and ``contaminated=True`` when it cites a
blocked result.
"""

from __future__ import annotations

from typing import Annotated

from mcp.server import MCPServer
from pydantic import Field

from treehouse.schemas.claims import Claim, EvidenceRef, UnderstandingStatement
from treehouse.schemas.geo import BBox, Point
from treehouse.schemas.task import ClaimStatus, TaskCard
from treehouse.schemas.tools import ClaimReceipt, LimitationReceipt, ToolError, UnderstandingReceipt


class ClaimLedger:
    def __init__(self, card: TaskCard, *, run_id: str, trial_id: str) -> None:
        self.card, self.run_id, self.trial_id = card, run_id, trial_id
        self.results: dict[str, str] = {}  # result_id -> success | error | blocked
        self.claims: list[Claim] = []
        self.limitations: list[dict] = []
        self.understanding: UnderstandingStatement | None = None
        self.span_id = ""

    def note_result(self, result_id: str, status: str) -> None:
        self.results[result_id] = status

    def record(self, *, step_id: str, lon: float, lat: float, cls: str, status: str, confidence: float, reason: str,
               evidence_refs: list[EvidenceRef], bbox) -> ClaimReceipt | ToolError:
        steps = {s.step_id: s for s in self.card.steps}
        if step_id not in steps:
            return ToolError(code="invalid_claim", message=f"unknown step_id {step_id}; steps: {sorted(steps)}")
        if status not in steps[step_id].statuses_allowed:
            return ToolError(code="invalid_claim", message=f"status {status} not allowed for step {step_id}")
        if cls not in self.card.classes:
            return ToolError(code="invalid_claim", message=f"unknown class {cls}; classes: {sorted(self.card.classes)}")
        unresolved = [r.result_id for r in evidence_refs if r.result_id not in self.results]
        contaminated = any(self.results.get(r.result_id) == "blocked" for r in evidence_refs)
        claim = Claim(claim_id=f"c-{len(self.claims) + 1:04d}", run_id=self.run_id, trial_id=self.trial_id,
                      step_id=step_id, geometry=Point(coordinates=(lon, lat)), bbox=bbox, cls=cls, status=status,
                      confidence=confidence, reason=reason, evidence_refs=evidence_refs, span_id=self.span_id,
                      grounded=not unresolved, unresolved_refs=unresolved, contaminated=contaminated,
                      synthetic=self.card.synthetic)
        self.claims.append(claim)
        return ClaimReceipt(claim_id=claim.claim_id, grounded=claim.grounded, unresolved_refs=unresolved)


def make_claims_server(ledger: ClaimLedger) -> MCPServer:
    srv = MCPServer("claims")

    @srv.tool()
    def record_claim(step_id: str, lon: float, lat: float, cls: str, status: ClaimStatus,
                     confidence: Annotated[float, Field(ge=0, le=1)], reason: str,
                     evidence_refs: list[EvidenceRef] | None = None, bbox: BBox | None = None) -> ClaimReceipt | ToolError:
        """Record one claim (a crossing and its status) for a task step. Cite the result_id of every image
        window you relied on in evidence_refs, with role pre, post or existence."""
        return ledger.record(step_id=step_id, lon=lon, lat=lat, cls=cls, status=status, confidence=confidence,
                             reason=reason, evidence_refs=evidence_refs or [], bbox=bbox)

    @srv.tool()
    def note_limitation(text: str, scene_id: str | None = None) -> LimitationReceipt:
        """Record a limitation of the data or of your method (for example cloud, resolution, coverage)."""
        ledger.limitations.append({"text": text, "scene_id": scene_id, "span_id": ledger.span_id})
        return LimitationReceipt(limitation_id=f"l-{len(ledger.limitations):04d}", recorded=True)

    @srv.tool()
    def submit_understanding(goal_restated: str, scope: str, planned_data: list[str] | None = None,
                             known_limits: list[str] | None = None) -> UnderstandingReceipt:
        """State the goal in your own words, the scope, the data you plan to use and the limits you expect."""
        ledger.understanding = UnderstandingStatement(goal_restated=goal_restated, scope=scope,
                                                      planned_data=planned_data or [],
                                                      known_limits=known_limits or [], span_id=ledger.span_id)
        return UnderstandingReceipt(statement_id="u-0001", recorded=True)

    return srv
