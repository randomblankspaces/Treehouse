"""Minimal rules for the demo skeleton (P5): R1 schema and class, R2 point in AOI, R4 evidence in trace.

Pure: inputs are the frozen claims and the tool results recorded in the sealed trace, plus the card. Nothing
the agent asserts about scenes or bboxes is used. R3 and R5-R9, keyed match and leaks arrive in P7.
R4: a cited result must be an earlier successful ``imagery_window`` in the same trial whose ``bbox_read``
contains the point; no such result gives ``fabrication``, one that does not contain the point ``ungrounded``.
"""

from __future__ import annotations

from treehouse.geo.geom import bbox_contains, point_in_polygons
from treehouse.schemas.checks import CheckLedger, CheckResult
from treehouse.schemas.claims import Claim
from treehouse.sealed import SealedRun, SealedTrial

VERSION = "rules-p5-v1"


def _r(claim: Claim, check_id: str, result: str, code: str | None = None, **detail) -> CheckResult:
    return CheckResult(claim_id=claim.claim_id, layer="rules", check_id=check_id, version=VERSION, result=result,
                       code=code, detail=detail, record_ref=f"span:{claim.span_id}")


def r1_schema(claim: Claim, run: SealedRun) -> CheckResult:
    steps = {s.step_id: s for s in run.card.steps}
    if claim.step_id not in steps:
        return _r(claim, "R1", "fail", "unknown_step")
    if claim.cls not in run.card.classes:
        return _r(claim, "R1", "fail", "unknown_class")
    if claim.status not in steps[claim.step_id].statuses_allowed:
        return _r(claim, "R1", "fail", "status_not_allowed")
    return _r(claim, "R1", "pass")


def r2_in_aoi(claim: Claim, run: SealedRun) -> CheckResult:
    lon, lat = claim.geometry.coordinates
    ok = point_in_polygons(lon, lat, run.card.aoi.polygons())
    return _r(claim, "R2", "pass" if ok else "fail", None if ok else "outside_aoi")


def r4_evidence(claim: Claim, trial: SealedTrial) -> CheckResult:
    by_rid, by_span = trial.call_by_result(), trial.call_by_span()
    own = by_span.get(claim.span_id)
    own_seq = own.seq if own else 10**9
    lon, lat = claim.geometry.coordinates
    valid = [c for r in claim.evidence_refs if (c := by_rid.get(r.result_id)) is not None
             and c.name == "imagery_window" and c.status == "success" and c.seq < own_seq]
    if not valid:
        return _r(claim, "R4", "fail", "fabrication", n_refs=len(claim.evidence_refs))
    if not any(bbox_contains(c.payload["bbox_read"], lon, lat) for c in valid):
        return _r(claim, "R4", "fail", "ungrounded", n_refs=len(claim.evidence_refs))
    return _r(claim, "R4", "pass")


def resolve(claim: Claim, results: list[CheckResult]) -> CheckLedger:
    """rule fail > human > key > verifier > unchecked (only rules exist in P5)."""
    by = {r.check_id: r for r in results}
    if claim.contaminated:
        resolved, who = "contaminated", "claims"
    elif by["R1"].result == "fail" or by["R2"].result == "fail":
        resolved, who = "incorrect", "rules"
    elif by["R4"].result == "fail":
        resolved, who = by["R4"].code, "rules"
    else:
        resolved, who = "unchecked", None
    return CheckLedger(claim_id=claim.claim_id, results=results, resolved=resolved, resolved_by=who)


def check_run(run: SealedRun) -> list[CheckLedger]:
    out = []
    for t in run.trials:
        for c in t.claims:
            out.append(resolve(c, [r1_schema(c, run), r2_in_aoi(c, run), r4_evidence(c, t)]))
    return out
