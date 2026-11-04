"""Run-level checking: rules, keyed match and leaks into per-claim ledgers, plus the append-only records.

Resolution order (§2): rule fail > human > key > verifier > unchecked. Contaminated (a claim that cited a
blocked result, a probable leak or a canary claim) comes first because it is excluded from grading. No human
or verifier layer exists here; they slot in between ``key`` and ``unchecked`` when they arrive.

``records`` returns one payload per evaluation kind (``rules``, ``key``, ``leak``) for the caller to hand to
``store.append_record``. Each carries its own version and the input versions it was computed from, so a
re-score with a new rule or key version is a new, different record; nothing is ever rewritten.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from treehouse.checks import keyed, leak, rules
from treehouse.checks.keyed import Key, KeyScore
from treehouse.geo.geom import Polys
from treehouse.schemas.checks import CheckLedger, CheckResult
from treehouse.schemas.claims import Claim
from treehouse.sealed import SealedRun, SealedTrial

_RULE_FAIL_FIRST = ("R1", "R2")
_RULE_FAIL_AFTER_R4 = ("R3", "R5", "R6", "R7")


@dataclass(frozen=True)
class RunChecks:
    ledgers: list[CheckLedger]
    key_scores: list[KeyScore] = field(default_factory=list)
    canary_claims: list[str] = field(default_factory=list)
    key_attempts: dict[str, int] = field(default_factory=dict)  # trial_id -> count

    @property
    def invalid_for_accuracy(self) -> bool:
        return bool(self.canary_claims)


def resolve(claim: Claim, results: list[CheckResult]) -> CheckLedger:
    by = {r.check_id: r for r in results}

    def bad(*ids: str) -> bool:
        return any(i in by and by[i].result == "fail" for i in ids)

    k = by.get("K1")
    if claim.contaminated or any(r.layer == "leak" and r.result in ("fail", "flag") for r in results):
        resolved, who = "contaminated", "claims" if claim.contaminated else "leak"
    elif bad(*_RULE_FAIL_FIRST):
        resolved, who = "incorrect", "rules"
    elif bad("R4"):
        resolved, who = by["R4"].code, "rules"
    elif bad(*_RULE_FAIL_AFTER_R4):
        resolved, who = "incorrect", "rules"
    elif k is not None and k.result in ("pass", "fail", "flag"):
        resolved, who = {"pass": "correct", "fail": "incorrect", "flag": "to_adjudicate"}[k.result], "key"
    else:
        resolved, who = "unchecked", None
    return CheckLedger(claim_id=claim.claim_id, results=results, resolved=resolved, resolved_by=who)


def _check_trial(run: SealedRun, trial: SealedTrial, keys: Mapping[str, Key]):
    """-> (extra results per claim_id, key scores, canary claim ids)."""
    extra: dict[str, list[CheckResult]] = {c.claim_id: [] for c in trial.claims}
    scores: list[KeyScore] = []
    canary: list[str] = []
    r4 = {c.claim_id: rules.r4_evidence(c, trial).result == "pass" for c in trial.claims}
    for step in run.card.steps:
        kg = step.keying
        if kg.mode == "unkeyed" or kg.status != "present" or kg.key_path not in keys:
            continue
        key = keys[kg.key_path]
        if kg.version_hash and kg.version_hash != key.version_hash:
            raise ValueError(f"key {kg.key_path}: version_hash {key.version_hash} does not match the card")
        tol = kg.match_rule.tolerance_m
        claims = [c for c in trial.claims if c.step_id == step.step_id and c.cls in tol]
        scoped = [c for c in claims if keyed.in_coverage(kg, *c.geometry.coordinates)]
        pairs = keyed.assign(scoped, key.real, tol)
        excluded: set[str] = set()
        for c in claims:
            lr = leak.leak_results(trial, c, pairs.get(c.claim_id), key.canaries, tol, r4[c.claim_id])
            extra[c.claim_id] += lr
            if any(r.result != "pass" for r in lr):
                excluded.add(c.claim_id)
            if lr[1].result == "fail":
                canary.append(c.claim_id)
        excluded |= {c.claim_id for c in claims if c.contaminated}
        kr, sc = keyed.grade_step(trial, claims, key, kg, step.question_id, pairs, excluded, step.step_id)
        for r in kr:
            extra[r.claim_id].append(r)
        scores.append(sc)
    return extra, scores, canary


def evaluate(run: SealedRun, *, keys: Mapping[str, Key] | None = None,
             footprints: Mapping[str, Polys] | None = None) -> RunChecks:
    """``keys`` maps a step's ``keying.key_path`` to its parsed key; with none, only the rules run.
    ``footprints`` (scene id -> polygons) overrides the footprints the STAC tools returned in the trace."""
    ledgers: list[CheckLedger] = []
    scores: list[KeyScore] = []
    canary: list[str] = []
    attempts: dict[str, int] = {}
    for t in run.trials:
        extra, sc, cn = _check_trial(run, t, keys or {})
        scores += sc
        canary += cn
        attempts[t.trial_id] = leak.key_attempts(t)
        for c in t.claims:
            ledgers.append(resolve(c, rules.check_claim(c, run, t, footprints) + extra[c.claim_id]))
    return RunChecks(ledgers, scores, canary, attempts)


def records(run: SealedRun, rc: RunChecks) -> dict[str, dict]:
    """Evaluation payloads by kind, for ``store.append_record(kind, run_id, payload)``."""
    base = {"manifest_ref": run.manifest_ref, "card_ref": run.card.ref()}

    def layer(name: str) -> list[dict]:
        return [{"claim_id": lg.claim_id, "results": [r.model_dump(mode="json") for r in lg.results
                                                       if r.layer == name]} for lg in rc.ledgers]

    return {
        "rules": {**base, "version": rules.VERSION, "ledgers": [
            {**row, "resolved": lg.resolved, "resolved_by": lg.resolved_by}
            for row, lg in zip(layer("rules"), rc.ledgers, strict=True)]},
        "key": {**base, "version": keyed.VERSION, "key_versions": sorted({s.key_version_hash for s in rc.key_scores}),
                "results": layer("key"), "scores": [keyed.score_dict(s) for s in rc.key_scores]},
        "leak": {**base, "version": leak.VERSION, "results": layer("leak"), "key_attempts": rc.key_attempts,
                 "canary_claims": rc.canary_claims,
                 "run_flag": leak.INVALID if rc.invalid_for_accuracy else None},
    }
