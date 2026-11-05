"""Decision graph projection for the shell: a readable tree of recorded decisions.

The investigation ledger records every decision with a ``parent_id`` (``str | None``). Live agents today
leave it ``null``, so the graph is flat. This projection exposes the recorded parent links when present and,
when they are absent, derives a readable tree from recorded ``sequence`` order: a single root (the
``submit_understanding`` decision, or the earliest decision), a spine of non-leaf decisions in order, and the
``record_claim`` decisions hung as leaves off the decision that immediately preceded them.

It also attaches, per decision, the RV verdicts that name it, and per claim a deterministic confidence
provenance (stated vs earned) derived only from recorded evidence — never from a grading key. Nothing here
reads models, writes records, or imports providers/harness/gateway.
"""
from __future__ import annotations

# Rules whose pass means an independent check along the path raised confidence in a claim.
_RAISES = {"RV7": "cited supporting evidence", "RV3": "resolution fit recorded"}
# Rules whose fail means a check along the path lowered confidence in a claim.
_LOWERS = {"RV7": "cited no supporting evidence", "RV10": "contradicts a known negative", "RV3": "resolution unfit for the object"}


def _rv_by_decision(rules_by_trial):
    """Index RV results by (trial_id, decision_id) and by (trial_id, claim_id)."""
    by_decision: dict[tuple[str, str], list[dict]] = {}
    by_claim: dict[tuple[str, str], list[dict]] = {}
    for trial_id, report in (rules_by_trial or {}).items():
        if not isinstance(report, dict):
            continue
        for result in report.get("results", []):
            entry = {"rule_id": result.get("rule_id"), "verdict": result.get("verdict"), "reason": result.get("reason")}
            if result.get("decision_id"):
                by_decision.setdefault((trial_id, result["decision_id"]), []).append(entry)
            if result.get("claim_id"):
                by_claim.setdefault((trial_id, result["claim_id"]), []).append(entry)
    return by_decision, by_claim


def _verdict(rv_entries):
    """Fold a decision's RV results into one chip: invalid if any fail, sound if any pass, else not evaluated."""
    verdicts = {entry["verdict"] for entry in rv_entries}
    if "fail" in verdicts:
        return "invalid"
    if "pass" in verdicts:
        return "sound"
    return "not_evaluated"


def _is_claim(decision):
    return decision.get("tool") == "record_claim"


def _derive_parents(ordered):
    """When recorded parent_id is absent, build a spine from sequence order with claims as leaves.

    Root = the first ``submit_understanding`` decision if present, else the earliest decision. Each later
    non-claim decision's parent is the previous non-claim decision (a spine). Each ``record_claim`` leaf's
    parent is the most recent non-claim decision recorded before it (the step that produced it).
    """
    parents: dict[str, str | None] = {}
    root = next((d for d in ordered if d.get("tool") == "submit_understanding"), ordered[0] if ordered else None)
    root_id = root["decision_id"] if root else None
    last_spine: str | None = None
    for decision in ordered:
        did = decision["decision_id"]
        if did == root_id:
            parents[did] = None
            last_spine = did
            continue
        if _is_claim(decision):
            parents[did] = last_spine if last_spine is not None else root_id
        else:
            parents[did] = last_spine if last_spine is not None else root_id
            last_spine = did
    return parents, root_id


def decision_tree(inv_decisions, trials, *, rules_by_trial=None, claim_decision_ids=None):
    """Build the public ``decisions`` array and a per-claim confidence provenance map.

    ``inv_decisions``   — ``inv["decisions"]`` from the investigation report.
    ``trials``          — ``run.trials`` (for claim membership and status).
    ``rules_by_trial``  — ``{trial_id: reasoning_rules_output}``; may be ``None``.
    ``claim_decision_ids`` — ``{(trial_id, claim_id): decision_id}`` from the marker projection.

    Returns ``(nodes, provenance_by_claim)``. ``nodes`` is a flat list the UI assembles into a tree via
    ``parent_id``; ``provenance_by_claim`` is keyed by ``(trial_id, claim_id)``.
    """
    by_decision, by_claim = _rv_by_decision(rules_by_trial)
    claim_decision_ids = claim_decision_ids or {}
    # Claims recorded per trial, and the decision that produced each.
    claims_by_decision: dict[tuple[str, str], list[dict]] = {}
    for trial in trials:
        for claim in trial.claims:
            did = claim_decision_ids.get((trial.trial_id, claim.claim_id))
            if did is not None:
                claims_by_decision.setdefault((trial.trial_id, did), []).append(claim)

    nodes: list[dict] = []
    provenance: dict[tuple[str, str], dict] = {}
    for trial in trials:
        tid = trial.trial_id
        ordered = sorted((d for d in inv_decisions if d.get("trial_id") == tid), key=lambda d: d["sequence"])
        if not ordered:
            continue
        ids = {d["decision_id"] for d in ordered}
        recorded = {d["decision_id"]: d.get("parent_id") for d in ordered}
        has_links = any(p in ids for p in recorded.values())
        derived_parents, root_id = _derive_parents(ordered)
        for decision in ordered:
            did = decision["decision_id"]
            recorded_parent = recorded.get(did)
            # Honour a real recorded link; otherwise derive one; the root keeps parent null.
            if has_links and recorded_parent in ids:
                parent_id, parent_source = recorded_parent, "recorded"
            elif has_links:
                parent_id, parent_source = None, "recorded"
            else:
                parent_id, parent_source = derived_parents.get(did), "derived"
            action = decision.get("action") or {}
            rv = by_decision.get((tid, did), [])
            claim_objs = claims_by_decision.get((tid, did), [])
            claim_ids = [c.claim_id for c in claim_objs]
            node = {
                "decision_id": did,
                "parent_id": parent_id,
                "parent_source": parent_source,
                "is_root": did == root_id and not (has_links and recorded_parent in ids),
                "trial_id": tid,
                "tool": decision.get("tool"),
                "action_id": decision.get("action_id"),
                "rationale": decision.get("rationale", ""),
                "alternatives": [{"option": a.get("option", ""), "reason": a.get("reason", "")}
                                 for a in decision.get("alternatives", [])],
                "confidence": decision.get("confidence"),
                "sequence": decision.get("sequence"),
                "status": action.get("status", "unbound"),
                "verdict": _verdict(rv),
                "rv": rv,
                "claim_ids": claim_ids,
            }
            nodes.append(node)
            for claim in claim_objs:
                provenance[(tid, claim.claim_id)] = _claim_confidence(claim, rv, by_claim.get((tid, claim.claim_id), []))
    return nodes, provenance


def _claim_confidence(claim, decision_rv, claim_rv):
    """Per-claim confidence provenance (F3 'stated vs earned'), from recorded checks only.

    'stated' is the agent's self-reported confidence. Checks that raised or lowered it come from the RV
    verdicts that name this claim's decision (RV7 evidence, RV3 resolution, RV10 negative conflict) plus
    whether any evidence was cited. 'earned' is true when the stated confidence was supported by at least one
    passed independent check and no check lowered it; high confidence with no passed check is 'unearned'.
    """
    stated = claim.confidence
    raised: list[str] = []
    lowered: list[str] = []
    for entry in [*decision_rv, *claim_rv]:
        rule, verdict = entry.get("rule_id"), entry.get("verdict")
        if verdict == "pass" and rule in _RAISES:
            raised.append(f"{rule}: {_RAISES[rule]}")
        elif verdict == "fail" and rule in _LOWERS:
            lowered.append(f"{rule}: {_LOWERS[rule]}")
    cited_evidence = bool(getattr(claim, "evidence_refs", []))
    # Earned when a check raised confidence and none lowered it; otherwise, high stated confidence is unearned.
    if raised and not lowered:
        label = "earned"
    elif stated is not None and stated >= 0.7:
        label = "unearned"
    else:
        label = "unestablished"
    return {
        "stated": stated,
        "label": label,
        "cited_evidence": cited_evidence,
        "raised": raised,
        "lowered": lowered,
    }
