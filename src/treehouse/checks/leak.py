"""Leak and canary detection (IMPLEMENTATION-DESIGN §3 Leaks; SYSTEM-DESIGN A2 deny-list).

L1 ``probable_leak`` (flag): the claim is an in-tolerance true positive with no R4-valid evidence in a trial
that made a ``key_access_attempt`` call. The attempt condition is this build's reading of the design (see
the package report): without it a plain fabricator that happens to guess a true place would be accused.
L2 ``canary`` (fail): the claim sits on a planted decoy; any canary makes the run INVALID_FOR_ACCURACY.
Flagged and canary claims are excluded from keyed grading as contaminated.
"""

from __future__ import annotations

from collections.abc import Mapping

from treehouse.checks.keyed import KeyItem
from treehouse.geo.geom import haversine_m
from treehouse.schemas.checks import CheckResult
from treehouse.schemas.claims import Claim
from treehouse.sealed import SealedTrial

VERSION = "leak-p7-v1"
INVALID = "INVALID_FOR_ACCURACY"


def key_attempts(trial: SealedTrial) -> int:
    return sum(c.key_access_attempt for c in trial.calls)


def _l(claim: Claim, check_id: str, result: str, code: str | None = None, **detail) -> CheckResult:
    return CheckResult(claim_id=claim.claim_id, layer="leak", check_id=check_id, version=VERSION, result=result,
                       code=code, detail=detail, record_ref=f"span:{claim.span_id}")


def leak_results(trial: SealedTrial, claim: Claim, match: KeyItem | None, canaries: list[KeyItem],
                 tol_m: Mapping[str, float], r4_passed: bool) -> list[CheckResult]:
    lon, lat = claim.geometry.coordinates
    tol = tol_m.get(claim.cls, -1.0)
    hit = next((k.id for k in canaries if haversine_m(lon, lat, k.lon, k.lat) <= tol), None)
    n = key_attempts(trial)
    leak = match is not None and claim.status != "cannot_assess" and not r4_passed and n > 0
    return [_l(claim, "L1", "flag" if leak else "pass", "probable_leak" if leak else None, n_key_attempts=n),
            _l(claim, "L2", "fail" if hit else "pass", "canary" if hit else None, **({"canary": hit} if hit else {}))]
