"""Deterministic claim rules R1-R9 (IMPLEMENTATION-DESIGN §3 Rules; SYSTEM-DESIGN A5).

Pure: inputs are the frozen claims, the tool results recorded in the sealed trace, spans and the card (plus an
optional pinned-footprint mapping). Nothing the agent asserts about scenes or bboxes is used. Every rule
returns one ``CheckResult``; resolution into a ``CheckLedger`` lives in ``ledger.py``.

R4: a cited result must be an earlier successful ``imagery_window`` in the same trial whose ``bbox_read``
contains the point; no such result gives ``fabrication``, one that does not contain the point ``ungrounded``.
R5-R7 and R9 look only at the *valid* cited windows (R4's filter) that contain the point.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from treehouse.geo.geom import Polys, bbox_contains, point_in_polygons
from treehouse.schemas.checks import CheckLedger, CheckResult
from treehouse.schemas.claims import Claim
from treehouse.schemas.geo import Polygon
from treehouse.sealed import SealedRun, SealedTrial, ToolCall

VERSION = "rules-p7-v1"
OBSCURATION_MAX = 0.3  # R9
_DAMAGE = {"damaged", "destroyed"}


def _r(claim: Claim, check_id: str, result: str, code: str | None = None, **detail) -> CheckResult:
    return CheckResult(claim_id=claim.claim_id, layer="rules", check_id=check_id, version=VERSION, result=result,
                       code=code, detail=detail, record_ref=f"span:{claim.span_id}")


def cited_windows(claim: Claim, trial: SealedTrial) -> list[ToolCall]:
    """Cited results that are earlier successful ``imagery_window`` calls in this trial (R4's valid set)."""
    by_rid, by_span = trial.call_by_result(), trial.call_by_span()
    own = by_span.get(claim.span_id)
    own_seq = own.seq if own else 10**9
    return [c for r in claim.evidence_refs if (c := by_rid.get(r.result_id)) is not None
            and c.name == "imagery_window" and c.status == "success" and c.seq < own_seq]


def _covering(claim: Claim, trial: SealedTrial) -> list[ToolCall]:
    lon, lat = claim.geometry.coordinates
    return [c for c in cited_windows(claim, trial) if bbox_contains(c.payload["bbox_read"], lon, lat)]


def trace_footprints(trial: SealedTrial) -> dict[str, Polys]:
    """Scene footprints as the STAC tools returned them (the pinned fixture), keyed by scene id."""
    out: dict[str, Polys] = {}
    for c in trial.calls:
        if c.name in ("stac_search", "scene_info") and c.status == "success":
            for s in c.payload.get("scenes") or ([c.payload] if "footprint" in c.payload else []):
                if s.get("footprint") and s.get("scene_id"):
                    out[s["scene_id"]] = Polygon.model_validate(s["footprint"]).polygons()
    return out


def _step(claim: Claim, run: SealedRun):
    return next((s for s in run.card.steps if s.step_id == claim.step_id), None)


def _is_status(claim: Claim, run: SealedRun) -> bool:
    s = _step(claim, run)
    return s is not None and s.question_id == "damaged" and claim.status != "cannot_assess"


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


def r3_footprint(claim: Claim, trial: SealedTrial, footprints: Mapping[str, Polys] | None = None) -> CheckResult:
    """The point lies inside the fixture footprint of at least one cited scene."""
    fps = {**trace_footprints(trial), **(footprints or {})}
    lon, lat = claim.geometry.coordinates
    scenes = sorted({c.payload["scene_id"] for c in cited_windows(claim, trial)})
    known = [s for s in scenes if s in fps]
    if not known:
        return _r(claim, "R3", "n/a", "no_cited_scene_footprint", n_scenes=len(scenes))
    if any(point_in_polygons(lon, lat, fps[s]) for s in known):
        return _r(claim, "R3", "pass")
    return _r(claim, "R3", "fail", "outside_scene_footprint", scenes=",".join(known))


def r4_evidence(claim: Claim, trial: SealedTrial) -> CheckResult:
    valid = cited_windows(claim, trial)
    lon, lat = claim.geometry.coordinates
    if not valid:
        return _r(claim, "R4", "fail", "fabrication", n_refs=len(claim.evidence_refs))
    if not any(bbox_contains(c.payload["bbox_read"], lon, lat) for c in valid):
        return _r(claim, "R4", "fail", "ungrounded", n_refs=len(claim.evidence_refs))
    return _r(claim, "R4", "pass")


def r5_gsd(claim: Claim, run: SealedRun, trial: SealedTrial) -> CheckResult:
    """Best covering window's ``effective_gsd_m`` is within the class limit for the question. A Clay hit alone
    never suffices: no covering imagery window means fail. ``cannot_assess`` is exempt."""
    step, spec = _step(claim, run), run.card.classes.get(claim.cls)
    if step is None or spec is None or claim.status == "cannot_assess":
        return _r(claim, "R5", "n/a")
    limit = (spec.max_effective_gsd_for_status_m if step.question_id == "damaged"
             else spec.max_effective_gsd_for_existence_m)
    cov = _covering(claim, trial)
    if not cov:
        return _r(claim, "R5", "fail", "no_imagery", limit_m=limit)
    best = min(c.payload["effective_gsd_m"] for c in cov)
    return _r(claim, "R5", "pass" if best <= limit else "fail", None if best <= limit else "gsd_too_coarse",
              best_gsd_m=best, limit_m=limit)


def r6_post_coverage(claim: Claim, run: SealedRun, trial: SealedTrial,
                     footprints: Mapping[str, Polys] | None = None) -> CheckResult:
    """A status claim needs a post-event window covering the point (and its scene footprint, when known)."""
    if not _is_status(claim, run):
        return _r(claim, "R6", "n/a")
    fps = {**trace_footprints(trial), **(footprints or {})}
    lon, lat = claim.geometry.coordinates
    ok = [c for c in _covering(claim, trial) if c.payload.get("phase") == "post"
          and (c.payload["scene_id"] not in fps or point_in_polygons(lon, lat, fps[c.payload["scene_id"]]))]
    return _r(claim, "R6", "pass" if ok else "fail", None if ok else "no_post_coverage")


def r7_time(claim: Claim, run: SealedRun, trial: SealedTrial) -> CheckResult:
    """Cited scenes are <= as_of and inside the time window; damage without a pre-event window is a flag."""
    card, wins = run.card, cited_windows(claim, trial)
    for c in wins:
        dt = datetime.fromisoformat(c.payload["scene_datetime"])
        if dt > card.as_of or not card.time_window[0] <= dt.date() <= card.time_window[1]:
            return _r(claim, "R7", "fail", "scene_out_of_window", scene_id=c.payload["scene_id"])
    if claim.status in _DAMAGE and not any(c.payload.get("phase") == "pre" for c in wins):
        return _r(claim, "R7", "flag", "no_pre_evidence")
    return _r(claim, "R7", "pass")


def r8_policy_budget(claim: Claim, trial: SealedTrial) -> CheckResult:
    """From spans: a claim made after a key/forbidden-source attempt or a budget/policy error is flagged."""
    at = next((i for i, s in enumerate(trial.spans) if s.span_id == claim.span_id), len(trial.spans))
    before = trial.spans[:at]
    forbidden = sum(bool(s.attributes.get("treehouse.key_access_attempt")) for s in before)
    budget = sum(s.error is not None and s.error.source == "budget" for s in before)
    if forbidden:
        return _r(claim, "R8", "flag", "forbidden_call", n_forbidden=forbidden, n_budget=budget)
    if budget:
        return _r(claim, "R8", "flag", "over_budget", n_forbidden=0, n_budget=budget)
    return _r(claim, "R8", "pass")


def r9_obscuration(claim: Claim, run: SealedRun, trial: SealedTrial) -> CheckResult:
    """A status claim whose clearest covering post window is obscured by more than 0.3 is flagged."""
    if not _is_status(claim, run):
        return _r(claim, "R9", "n/a")
    post = [c.payload["obscuration"]["bright_lowvar_fraction"] for c in _covering(claim, trial)
            if c.payload.get("phase") == "post"]
    if post and min(post) > OBSCURATION_MAX:
        return _r(claim, "R9", "flag", "obscured", obscuration=min(post))
    return _r(claim, "R9", "pass")


def check_claim(claim: Claim, run: SealedRun, trial: SealedTrial,
                footprints: Mapping[str, Polys] | None = None) -> list[CheckResult]:
    return [r1_schema(claim, run), r2_in_aoi(claim, run), r3_footprint(claim, trial, footprints),
            r4_evidence(claim, trial), r5_gsd(claim, run, trial), r6_post_coverage(claim, run, trial, footprints),
            r7_time(claim, run, trial), r8_policy_budget(claim, trial), r9_obscuration(claim, run, trial)]


def check_run(run: SealedRun, **kw) -> list[CheckLedger]:
    """Full resolution (rules, keyed match, leaks). Kept here for ``service``; see ``ledger.evaluate``."""
    from treehouse.checks.ledger import evaluate  # lazy: ledger imports this module

    return evaluate(run, **kw).ledgers
