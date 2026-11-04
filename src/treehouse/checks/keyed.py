"""Keyed match against an answer key (SYSTEM-DESIGN A2/A5; IMPLEMENTATION-DESIGN §3 Keyed match).

Pairs are feasible when the claim and key item share a class and sit within that class's ``tolerance_m``;
they are solved one-to-one with ``linear_sum_assignment`` (infeasible pairs cost ``INFEASIBLE`` and are
dropped after solving, F6; ties are broken by sorted ids). A partly keyed step is scored only inside
``key_coverage_mask``; its unmatched claims are ``to_adjudicate``, never "wrong". ``cannot_assess`` claims
take part in the assignment but leave the precision denominator and are graded against ``visible_in``.

Counts only: intervals and the cluster bootstrap belong to the panels package.
TODO(panels): precision/recall/F1 and status accuracy with cluster-bootstrap CIs from ``KeyScore``.
shortcut: dense cost matrix instead of a grid-hash component split, fine to a few thousand items per step.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import asdict, dataclass

import numpy as np
from scipy.optimize import linear_sum_assignment

from treehouse.geo.geom import haversine_m, point_in_polygons
from treehouse.schemas.checks import CheckResult
from treehouse.schemas.claims import Claim
from treehouse.schemas.task import Keying
from treehouse.sealed import SealedTrial

VERSION = "key-p7-v1"
INFEASIBLE = 1e9


@dataclass(frozen=True)
class KeyItem:
    id: str
    lon: float
    lat: float
    cls: str
    status_post: str
    visible_in: Mapping[str, bool]
    canary: bool = False


@dataclass(frozen=True)
class Key:
    version_hash: str
    items: tuple[KeyItem, ...]

    @property
    def real(self) -> list[KeyItem]:
        return [i for i in self.items if not i.canary]

    @property
    def canaries(self) -> list[KeyItem]:
        return [i for i in self.items if i.canary]


def parse_key(obj: Mapping) -> Key:
    items = tuple(KeyItem(id=c["id"], lon=c["point"][0], lat=c["point"][1], cls=c["cls"],
                          status_post=c["status_post"], visible_in=c.get("visible_in") or {},
                          canary=bool(c.get("canary"))) for c in obj["crossings"])
    return Key(version_hash=obj["version_hash"], items=items)


@dataclass(frozen=True)
class KeyScore:
    trial_id: str
    step_id: str
    key_version_hash: str
    n_claims: int          # claims in scope (inside the coverage mask)
    n_graded: int          # non-cannot_assess, not excluded, not to_adjudicate: the precision denominator
    n_correct: int
    n_to_adjudicate: int
    n_cannot_assess: int   # graded against visible_in, outside the precision denominator
    n_cannot_assess_correct: int
    n_excluded: int        # contaminated / leaked / canary claims
    n_out_of_coverage: int
    n_key_items: int       # in coverage, canaries and excluded items removed
    n_recalled: int        # key items matched by a passing claim


def assign(claims: Sequence[Claim], items: Sequence[KeyItem], tol_m: Mapping[str, float]) -> dict[str, KeyItem]:
    """claim_id -> key item, one-to-one, same class, within the per-class tolerance."""
    cs, ks = sorted(claims, key=lambda c: c.claim_id), sorted(items, key=lambda k: k.id)
    cost = np.full((len(cs), len(ks)), INFEASIBLE)
    for i, c in enumerate(cs):
        lon, lat = c.geometry.coordinates
        for j, k in enumerate(ks):
            if k.cls == c.cls and (d := haversine_m(lon, lat, k.lon, k.lat)) <= tol_m.get(c.cls, -1.0):
                cost[i, j] = d
    rows, cols = linear_sum_assignment(cost)
    return {cs[i].claim_id: ks[j] for i, j in zip(rows, cols, strict=True) if cost[i, j] < INFEASIBLE}


def in_coverage(keying: Keying, lon: float, lat: float) -> bool:
    m = keying.key_coverage_mask
    return m is None or point_in_polygons(lon, lat, m.polygons())


def post_scene_ids(trial: SealedTrial) -> set[str]:
    return {s["scene_id"] for c in trial.calls if c.name == "stac_search" and c.status == "success"
            for s in c.payload.get("scenes", []) if s.get("phase") == "post"}


def _k(claim: Claim, result: str, code: str | None = None, **detail) -> CheckResult:
    return CheckResult(claim_id=claim.claim_id, layer="key", check_id="K1", version=VERSION, result=result,
                       code=code, detail=detail, record_ref=f"span:{claim.span_id}")


def _grade(claim: Claim, item: KeyItem | None, question_id: str, partly: bool, post: set[str]) -> CheckResult:
    if claim.status == "cannot_assess":
        if item is None:
            return _k(claim, "n/a", "no_key_item")
        seen = sorted(s for s in post if item.visible_in.get(s))
        return _k(claim, "fail" if seen else "pass", "assessable_but_declined" if seen else None, item=item.id)
    if item is None:
        if claim.status == "absent":
            return _k(claim, "pass")
        return _k(claim, "flag", "to_adjudicate") if partly else _k(claim, "fail", "no_key_match")
    if claim.status == "absent":
        return _k(claim, "fail", "absent_but_keyed", item=item.id)
    if question_id == "damaged" and claim.status != item.status_post:
        return _k(claim, "fail", "wrong_status", item=item.id, key_status=item.status_post)
    return _k(claim, "pass", item=item.id)


def grade_step(trial: SealedTrial, claims: Sequence[Claim], key: Key, keying: Keying, question_id: str,
               pairs: Mapping[str, KeyItem], excluded: Collection[str], step_id: str,
               ) -> tuple[list[CheckResult], KeyScore]:
    """K1 per claim in ``claims`` (this step, this trial), then the counts."""
    post, partly = post_scene_ids(trial), keying.mode == "partly_keyed"
    out: list[CheckResult] = []
    gone = {pairs[c].id for c in excluded if c in pairs}  # the touched item leaves the grading too
    n = dict(claims=0, graded=0, correct=0, adj=0, ca=0, ca_ok=0, excl=0, oob=0)
    recalled: set[str] = set()
    for c in claims:
        if not in_coverage(keying, *c.geometry.coordinates):
            out.append(_k(c, "n/a", "outside_key_coverage"))
            n["oob"] += 1
            continue
        n["claims"] += 1
        if c.claim_id in excluded:
            out.append(_k(c, "n/a", "excluded_contaminated"))
            n["excl"] += 1
            continue
        r = _grade(c, pairs.get(c.claim_id), question_id, partly, post)
        out.append(r)
        if c.status == "cannot_assess":
            n["ca"] += 1
            n["ca_ok"] += r.result == "pass"
        elif r.result == "flag":
            n["adj"] += 1
        else:
            n["graded"] += 1
            n["correct"] += r.result == "pass"
            if r.result == "pass" and c.claim_id in pairs:
                recalled.add(pairs[c.claim_id].id)
    items = [k for k in key.real if in_coverage(keying, k.lon, k.lat) and k.id not in gone]
    score = KeyScore(trial_id=trial.trial_id, step_id=step_id, key_version_hash=key.version_hash,
                     n_claims=n["claims"], n_graded=n["graded"], n_correct=n["correct"], n_to_adjudicate=n["adj"],
                     n_cannot_assess=n["ca"], n_cannot_assess_correct=n["ca_ok"], n_excluded=n["excl"],
                     n_out_of_coverage=n["oob"], n_key_items=len(items), n_recalled=len(recalled & {k.id for k in items}))
    return out, score


def score_dict(s: KeyScore) -> dict:
    return asdict(s)
