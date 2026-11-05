"""Versioned, deterministic observations of exploration; never evidence of hidden cognition."""
from __future__ import annotations

import re

VERSION = "deliberation/1"
BASIS = "self-reported rationale and model thinking text; not proof of internal computation"
CHOICES = {"model", "model_id", "source", "source_id", "cell_size_m", "chip_size_m", "method", "threshold"}
UNCERTAIN = re.compile(r"\b(guess(?:ing)?|uncertain|not sure|unsure)\b", re.I)


def _normal(value):
    return " ".join(str(value).casefold().replace(",", "").split())


def _contains(text, value):
    return re.search(r"(?<![\w.-])" + re.escape(_normal(value)) + r"(?![\w.-])", _normal(text)) is not None


def _option_matches(option, key, value):
    value = _normal(int(value) if isinstance(value, float) and value.is_integer() else value)
    return option == value or (key in {"cell_size_m", "chip_size_m"} and option == f"{value} m")


def _alternatives(decision):
    return sorted({_normal(a.get("option", "") if isinstance(a, dict) else a)
                   for a in decision.get("alternatives", [])} - {""})


def _parameters(decision):
    return decision.get("parameters", (decision.get("action") or {}).get("parameters", {}))


def _tool(decision):
    return decision.get("tool", (decision.get("action") or {}).get("tool", ""))


def _values(parameters):
    for key, value in parameters.items():
        if isinstance(value, dict):
            yield from _values(value)
        elif key in CHOICES:
            yield key, value


def _success(action):
    return action is not None and action.get("status", "success") == "success"


def evaluate(ledger):
    """Summarise one trial. Sequence and evidence links constrain attribution, never proximity."""
    decisions = [d for d in ledger.get("decisions", []) if not d.get("flags")]
    actions, claims = ledger.get("actions", []), ledger.get("claims", [])
    by_id = {d["decision_id"]: d for d in decisions}
    results = {a["result_id"]: a for a in actions if a.get("result_id")}
    metrics = {}

    def metric(name, numerator, denominator, *, recorded=True):
        metrics[name] = {"numerator": numerator, "denominator": denominator,
                         "value": numerator / denominator if denominator else 0.0,
                         "status": "available" if recorded else "unavailable"}
        if not recorded:
            metrics[name].update(value=None, reason="not recorded")

    alternatives = [(d, _alternatives(d)) for d in decisions]
    metric("alternatives_per_decision", sum(len(a) for _, a in alternatives), len(decisions))
    tried = compared = choice_count = 0
    agreement = linked = revisions = 0
    uncertain = []
    for d, options in alternatives:
        chosen = list(_values(_parameters(d)))
        later = [a for a in actions if _success(a) and
                 (a.get("sequence", float("inf")) > d.get("sequence", -1))]
        tried += sum(any(key == other_key and value != other_value and
                         _option_matches(option, key, other_value)
                         for key, value in chosen for a in later
                         for other_key, other_value in _values(a.get("parameters", {}))) for option in options)
        choice_count += len(chosen) if options else 0
        compared += sum(any(key == other_key and value != other_value and
                            any(_option_matches(option, key, other_value) for option in options)
                            for action in later for other_key, other_value in _values(action.get("parameters", {})))
                        for key, value in chosen)
        text = d.get("thinking_text", "")
        if d.get("thinking_ref"):
            linked += 1
            guessing = bool(UNCERTAIN.search(text)) and d.get("confidence", 0) >= .7
            if guessing:
                uncertain.append(d["decision_id"])
            agreement += bool(chosen and options and not guessing and
                              all(_contains(text, v) for _, v in chosen) and
                              any(_contains(text, a) for a in options))
        parent = by_id.get(d.get("parent_id"))
        new_refs = set(d.get("evidence_refs", [])) - set((parent or {}).get("evidence_refs", []))
        if "sequence" in d:
            new_refs = {ref for ref in new_refs if ref in results and _success(results[ref])
                        and (parent or {}).get("sequence", -1) < results[ref].get("sequence", float("inf")) < d["sequence"]}
        if new_refs and ((parent and _parameters(parent) != _parameters(d)) or _tool(d) == "revise"):
            revisions += 1
    metric("alternatives_tried", tried, sum(len(a) for _, a in alternatives))
    metric("key_choices_compared", compared, choice_count)
    metric("revisions_after_evidence", revisions, len(decisions))
    metric("thinking_coverage", linked, len(decisions), recorded=bool(linked))
    metric("thinking_rationale_agreement", agreement, linked, recorded=bool(linked))

    earned, checked_count = {}, 0
    for claim in claims:
        chain, seen = [], set()
        pending = list(claim.get("decision_ids", []))
        while pending:
            did = pending.pop()
            if did in seen or did not in by_id:
                continue
            seen.add(did)
            d = by_id[did]
            if d.get("sequence", -1) >= claim.get("sequence", float("inf")):
                continue
            chain.append(d)
            if d.get("parent_id"):
                pending.append(d["parent_id"])
            for ref in d.get("evidence_refs", []):
                action = results.get(ref, {})
                if _success(action) and action.get("decision_id"):
                    pending.append(action["decision_id"])
        sources = set()
        checked = False
        for d in chain:
            action = d.get("action")
            if not _success(action):
                continue
            executed = results.get(action.get("result_id"), action)
            if not _success(executed) or executed.get("sequence", -1) >= claim.get("sequence", float("inf")):
                continue
            params = _parameters(d)
            tool = _tool(d)
            checked |= tool == "classify_window" or (tool == "classify" and params.get("method") == "vision_subagent")
            source = params.get("source_id", params.get("source"))
            if source and tool in {"imagery_window", "build_index"}:
                sources.add(str(source))
        checked |= len(sources) > 1
        checked_count += checked
        explored = any(_alternatives(d) for d in chain)
        confidence = claim.get("confidence", 0.5)
        earned[claim["claim_id"]] = ("unearned" if confidence >= .7 and not explored and not checked else
                                     "under-confident" if confidence <= .3 and checked else "supported")
    metric("claims_independently_checked", checked_count, len(claims))
    return {"version": VERSION, "status": "available" if decisions else "unavailable",
            "basis": BASIS, "metrics": metrics, "earned_confidence": earned,
            "thinking_confidence_flags": uncertain}
