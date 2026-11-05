"""Deterministic reasoning-validity checks for investigation ledgers."""

from __future__ import annotations

import copy
import fnmatch
import re
from collections.abc import Iterable, Mapping
from typing import Any

from treehouse.assets import AssetClasses, UnknownAssetClass
from treehouse.cards import LICENSE_RANK

# rv-v2 (2026-11-05, from live runs): an omitted get_examples split is the server default "train" (RV4);
# no stated_count is not_applicable, because note_limitation takes free text only (RV7).
RULES_VERSION = "rv-v2"
RULE_IDS = tuple(f"RV{i}" for i in range(1, 11))

# Kept public and versioned with the rules so wording changes are reviewable.
LIMITATION_PHRASES = (
    "cannot",
    "can't",
    "could not",
    "limitation",
    "may be missed",
    "not reliable",
    "too coarse",
    "unreliable",
)
NEGATION_PHRASES = (
    "exclude",
    "excluding",
    "is not",
    "isn't",
    "not",
    "without",
)
RECALL_TERMS = ("recall", "complete", "completeness", "found every", "all instances")

_SEARCH_TOOLS = frozenset({"build_index", "retrieve", "search", "query", "scan"})
_LABEL_REVEALING_TOOLS = frozenset({"get_examples", "read_labels", "key_lookup"})
_JUSTIFICATION_PHRASES = ("because", "due to", "reason", "transient", "already complete", "claim set is complete")
_GAP_PHRASES = ("gap", "not reviewed", "not searched", "unable to review", "unreviewed")


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _all_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _all_strings(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _all_strings(item)


def _decision_text(decision: Mapping[str, Any]) -> str:
    parameters = decision.get("parameters", {})
    return " ".join([_text(decision.get("rationale")), *_all_strings(parameters)]).lower()


def _has_phrase(text: str, phrases: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in phrases)


def _has_limitation(text: str) -> bool:
    return _has_phrase(text, LIMITATION_PHRASES)


def _result(
    rule_id: str,
    verdict: str,
    reason: str,
    decision: Mapping[str, Any] | None = None,
    *,
    claim_id: str | None = None,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "decision_id": decision.get("decision_id") if decision else None,
        "action_id": decision.get("action_id") if decision else None,
        "claim_id": claim_id,
        "verdict": verdict,
        "reason": reason,
    }


def _not_applicable(rule_id: str, reason: str) -> list[dict[str, Any]]:
    return [_result(rule_id, "not_applicable", reason)]


def _valid_ledger(ledger: Any) -> tuple[bool, str]:
    if not isinstance(ledger, Mapping):
        return False, "ledger is not an object"
    if ledger.get("schema_version") != "treehouse.investigation-ledger/1":
        return False, "ledger schema_version is missing or unsupported"
    decisions, actions = ledger.get("decisions"), ledger.get("actions")
    if not isinstance(decisions, list) or not isinstance(actions, list):
        return False, "ledger decisions and actions must be lists"
    for i, decision in enumerate(decisions):
        if not isinstance(decision, Mapping):
            return False, f"decision {i} is not an object"
        if not isinstance(decision.get("tool"), str) or not isinstance(decision.get("parameters"), Mapping):
            return False, f"decision {i} has malformed tool or parameters"
        if not isinstance(decision.get("rationale"), str):
            return False, f"decision {i} has malformed rationale"
    for i, action in enumerate(actions):
        if not isinstance(action, Mapping):
            return False, f"action {i} is not an object"
        if not isinstance(action.get("result_id"), str) or not isinstance(action.get("status"), str):
            return False, f"action {i} has malformed result_id or status"
    return True, ""


def _rule_rv1(decisions: list[dict[str, Any]], registry: Any, asset_class: str) -> list[dict[str, Any]]:
    checked = []
    for decision in decisions:
        parameters = decision["parameters"]
        for name, size in parameters.items():
            if name not in {"cell_size_m", "chip_size_m"}:
                continue
            if not isinstance(size, int | float) or isinstance(size, bool) or size <= 0:
                checked.append(_result("RV1", "fail", f"{name} is not a positive size", decision))
            elif registry.cell_fits(asset_class, float(size)):
                checked.append(_result("RV1", "pass", f"{name}={size:g} m fits the registry scale", decision))
            elif _has_limitation(_decision_text(decision)):
                checked.append(_result("RV1", "pass", f"{name}={size:g} m is coarse, but its limitation and consequence are stated", decision))
            else:
                checked.append(_result("RV1", "fail", f"{name}={size:g} m does not fit the registry scale and no consequence is stated", decision))
    return checked or _not_applicable("RV1", "no cell or chip size was recorded")


def _rule_rv2(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checked = []
    non_commercial_rank = LICENSE_RANK["CC-BY-NC-4.0"]
    for decision in decisions:
        parameters = decision["parameters"]
        sources = [value for key, value in parameters.items() if key in {"source", "source_id", "imagery_source"}]
        source_text = " ".join(_all_strings(sources)).lower()
        licenses = [value for key, value in parameters.items() if "license" in key.lower() and isinstance(value, str)]
        prohibited_source = next((name for name in ("maxar", "vantor") if name in source_text), None)
        prohibited_license = next(
            (
                license_id
                for license_id in licenses
                if "non-commercial" in license_id.lower()
                or "-nc-" in license_id.lower()
                or LICENSE_RANK.get(license_id, -1) >= non_commercial_rank
            ),
            None,
        )
        if prohibited_source:
            checked.append(_result("RV2", "fail", f"{prohibited_source} imagery is not reusable for this purpose", decision))
        elif prohibited_license:
            checked.append(_result("RV2", "fail", f"licence {prohibited_license} is non-commercial", decision))
        elif sources or licenses:
            checked.append(_result("RV2", "pass", "the recorded source and licence do not impose a non-commercial restriction", decision))
    return checked or _not_applicable("RV2", "no imagery or embedding source was recorded")


def _rule_rv3(
    decisions: list[dict[str, Any]], registry: Any, asset_class: str, asset: Any
) -> list[dict[str, Any]]:
    checked = []
    coarse_gsd = max(asset.suitable_gsd_m)
    for decision in decisions:
        parameters = decision["parameters"]
        gsd, object_size = parameters.get("gsd_m"), parameters.get("object_size_m")
        if not all(isinstance(value, int | float) and not isinstance(value, bool) for value in (gsd, object_size)):
            continue
        if gsd >= coarse_gsd and object_size < asset.min_size_m:
            if _has_limitation(_decision_text(decision)):
                checked.append(_result("RV3", "pass", "the below-minimum object claim states the coarse-resolution limitation", decision))
            else:
                checked.append(_result("RV3", "fail", f"a {object_size:g} m object is below the registry minimum at {gsd:g} m GSD", decision))
        elif registry.resolvable_at(asset_class, float(gsd)):
            checked.append(_result("RV3", "pass", f"{gsd:g} m GSD is suitable according to the registry", decision))
        else:
            verdict = "pass" if _has_limitation(_decision_text(decision)) else "fail"
            reason = "the unsuitable resolution is explicitly limited" if verdict == "pass" else "the registry marks this resolution unsuitable"
            checked.append(_result("RV3", verdict, reason, decision))
    return checked or _not_applicable("RV3", "no claim recorded both object size and GSD")


def _matches_forbidden(kind: str, pattern: str, decision: Mapping[str, Any]) -> bool:
    parameters = decision["parameters"]
    if kind == "tool":
        return fnmatch.fnmatchcase(decision["tool"].lower(), pattern.lower())
    keys_for_kind = {
        "path": {"path", "file", "filename"},
        "dataset_id": {"dataset_id"},
        "host": {"host", "hostname"},
        "url_prefix": {"url", "uri"},
        "s3_prefix": {"s3_uri", "uri"},
    }.get(kind, set())
    values = [value for key, value in parameters.items() if key.lower() in keys_for_kind]
    for value in _all_strings(values):
        candidate, wanted = value.lower(), pattern.lower()
        if kind in {"url_prefix", "s3_prefix", "path"} and candidate.startswith(wanted):
            return True
        if fnmatch.fnmatchcase(candidate, wanted):
            return True
    return False


def _rule_rv4(decisions: list[dict[str, Any]], card: Any) -> list[dict[str, Any]]:
    checked = []
    forbidden = _get(card, "forbidden_sources", []) or []
    for decision in decisions:
        text_values = " ".join(_all_strings(decision["parameters"])).lower()
        failures = []
        if "keys/" in text_values or "keys\\" in text_values:
            failures.append("a keys/ grading path was accessed")
        if decision["tool"] == "get_examples" and str(decision["parameters"].get("split", "train")).lower() != "train":
            failures.append("few-shot examples did not use the training split")
        for source in forbidden:
            kind, pattern = _text(_get(source, "kind")), _text(_get(source, "pattern"))
            if kind and pattern and _matches_forbidden(kind, pattern, decision):
                failures.append(f"forbidden {kind} {pattern!r} was used")
        if failures:
            checked.append(_result("RV4", "fail", "; ".join(dict.fromkeys(failures)), decision))
        else:
            checked.append(_result("RV4", "pass", "the decision does not access held-out grading data", decision))
    return checked or _not_applicable("RV4", "no decisions were recorded")


def _rule_rv5(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(enumerate(decisions), key=lambda item: (item[1].get("sequence", item[0]), item[0]))
    reveal_position = next((i for i, (_, d) in enumerate(ordered) if d["tool"] in _LABEL_REVEALING_TOOLS), None)
    prompts: list[tuple[int, dict[str, Any], str]] = []
    for i, (_, decision) in enumerate(ordered):
        prompt = decision["parameters"].get("prompt")
        if isinstance(prompt, str) and prompt.strip():
            prompts.append((i, decision, prompt.strip()))
    if not prompts:
        return _not_applicable("RV5", "no zero-shot prompt was recorded")
    baseline = prompts[0][2]
    changed = [item for item in prompts[1:] if item[2] != baseline and reveal_position is not None and item[0] > reveal_position]
    results = [_result("RV5", "fail", "the zero-shot prompt changed after label-revealing examples", d) for _, d, _ in changed]
    if results:
        return results
    return [_result("RV5", "pass", "the zero-shot prompt remained fixed after any label-revealing step", prompts[0][1])]


def _aoi_bounds(card: Any) -> tuple[float, float, float, float] | None:
    aoi = _get(card, "aoi")
    coordinates = _get(aoi, "coordinates")
    positions: list[tuple[float, float]] = []

    def visit(value: Any) -> None:
        if isinstance(value, (list, tuple)) and len(value) >= 2 and all(
            isinstance(x, int | float) and not isinstance(x, bool) for x in value[:2]
        ):
            positions.append((float(value[0]), float(value[1])))
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item)

    visit(coordinates)
    if not positions:
        return None
    xs, ys = zip(*positions, strict=True)
    return min(xs), min(ys), max(xs), max(ys)


def _valid_bbox(value: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    if not all(isinstance(x, int | float) and not isinstance(x, bool) for x in value):
        return None
    bbox = tuple(float(x) for x in value)
    return bbox if bbox[0] <= bbox[2] and bbox[1] <= bbox[3] else None


def _rectangles_cover(target: tuple[float, float, float, float], boxes: list[tuple[float, float, float, float]]) -> bool:
    min_x, min_y, max_x, max_y = target
    clipped = [
        (max(min_x, a), max(min_y, b), min(max_x, c), min(max_y, d))
        for a, b, c, d in boxes
        if c >= min_x and a <= max_x and d >= min_y and b <= max_y
    ]
    cuts = sorted({min_x, max_x, *(x for box in clipped for x in (box[0], box[2]))})
    for left, right in zip(cuts, cuts[1:], strict=False):
        if right <= left:
            continue
        middle = (left + right) / 2
        intervals = sorted((b, d) for a, b, c, d in clipped if a <= middle <= c)
        covered_to = min_y
        for bottom, top in intervals:
            if bottom > covered_to:
                break
            covered_to = max(covered_to, top)
        if covered_to < max_y:
            return False
    return bool(clipped)


def _declared_gap(decisions: list[dict[str, Any]]) -> bool:
    return any(_has_phrase(_decision_text(decision), _GAP_PHRASES) for decision in decisions)


def _rule_rv6(decisions: list[dict[str, Any]], card: Any) -> list[dict[str, Any]]:
    target = _aoi_bounds(card)
    if target is None:
        return _not_applicable("RV6", "the task card has no usable AOI")
    search_decisions = [d for d in decisions if d["tool"] in _SEARCH_TOOLS]
    boxes = []
    for d in search_decisions:
        params = d["parameters"]
        raw = params.get("bbox", params.get("aoi_bbox"))
        bbox = _valid_bbox(raw)
        if bbox is not None:
            boxes.append(bbox)
        elif d["tool"] == "build_index" and raw is None:
            boxes.append(target)  # the retrieval server's build_index defaults to the card AOI
    if boxes and _rectangles_cover(target, boxes):
        return [_result("RV6", "pass", "recorded search bounds cover the card AOI", search_decisions[0])]
    if _declared_gap(decisions):
        return [_result("RV6", "pass", "the recorded search does not cover the full AOI, and the gap is declared")]
    reason = "recorded search bounds do not cover the card AOI and no gap is declared" if boxes else "no usable searched bounds or declared gap were recorded"
    return [_result("RV6", "fail", reason, search_decisions[0] if search_decisions else None)]


def _evidence_index(actions: list[dict[str, Any]], tool_results: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    index = {
        action["result_id"]: {
            "status": action.get("status"),
            "parameters": action.get("parameters", {}),
            "tool": action.get("tool"),
        }
        for action in actions
    }
    for result_id, result in tool_results.items():
        if isinstance(result_id, str) and isinstance(result, Mapping):
            existing = index.setdefault(result_id, {})
            existing.update(result)
    return index


def _claim_refs(claim: Mapping[str, Any]) -> list[str]:
    parameters = claim.get("parameters", {})
    values = [claim.get("evidence_refs", []), parameters.get("evidence_refs", [])]
    return list(dict.fromkeys(ref for ref in _all_strings(values) if ref))


def _evidence_covers_claim(evidence: Mapping[str, Any], claim: Mapping[str, Any]) -> bool:
    parameters = claim.get("parameters", {})
    lon, lat = parameters.get("lon"), parameters.get("lat")
    if not all(isinstance(x, int | float) and not isinstance(x, bool) for x in (lon, lat)):
        return True
    bbox = _valid_bbox(_get(evidence.get("parameters", {}), "bbox"))
    return bbox is None or bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


def _rule_rv7(
    decisions: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    claims: list[Any],
    tool_results: Mapping[str, Any],
) -> list[dict[str, Any]]:
    evidence = _evidence_index(actions, tool_results)
    ledger_claims = [decision for decision in decisions if decision["tool"] == "record_claim"]
    results = []
    for claim in ledger_claims:
        refs = _claim_refs(claim)
        invalid = [ref for ref in refs if ref not in evidence or evidence[ref].get("status") != "success"]
        uncovered = [ref for ref in refs if ref in evidence and not _evidence_covers_claim(evidence[ref], claim)]
        if not refs:
            results.append(_result("RV7", "fail", "claim cites no evidence", claim))
        elif invalid or uncovered:
            details = []
            if invalid:
                details.append(f"unavailable evidence: {', '.join(invalid)}")
            if uncovered:
                details.append(f"evidence does not cover claim: {', '.join(uncovered)}")
            results.append(_result("RV7", "fail", "; ".join(details), claim))
        else:
            results.append(_result("RV7", "pass", "claim cites available evidence that covers it", claim))
    for i, external in enumerate(claims):
        if not isinstance(external, Mapping):
            results.append(_result("RV7", "fail", "external claim is malformed", claim_id=f"external-{i + 1}"))
            continue
        claim_id = _text(external.get("claim_id")) or f"external-{i + 1}"
        refs = list(dict.fromkeys(_all_strings(external.get("evidence_refs", []))))
        invalid = [ref for ref in refs if ref not in evidence or evidence[ref].get("status") != "success"]
        if not refs:
            results.append(_result("RV7", "fail", "external claim cites no evidence", claim_id=claim_id))
        elif invalid:
            results.append(_result("RV7", "fail", f"external claim cites unavailable evidence: {', '.join(invalid)}", claim_id=claim_id))
        else:
            results.append(_result("RV7", "pass", "external claim cites available evidence", claim_id=claim_id))
    stated = [
        d["parameters"].get("stated_count")
        for d in decisions
        if d["tool"] == "note_limitation" and "stated_count" in d["parameters"]
    ]
    if not stated:
        results.append(_result("RV7", "not_applicable", "no numeric stated count was recorded"))
    elif not isinstance(stated[-1], int) or isinstance(stated[-1], bool) or stated[-1] != len(ledger_claims):
        results.append(_result("RV7", "fail", f"stated count {stated[-1]!r} does not equal {len(ledger_claims)} recorded claims"))
    else:
        results.append(_result("RV7", "pass", "stated count equals the number of recorded claims"))
    return results


def _is_negated(text: str, position: int) -> bool:
    prefix = text[max(0, position - 32) : position]
    return any(re.search(rf"\b{re.escape(phrase)}(?:\s+(?:a|an|any))?\s*$", prefix) for phrase in NEGATION_PHRASES)


def _asserts_recall(text: str) -> bool:
    lowered = text.lower()
    for term in RECALL_TERMS:
        for match in re.finditer(rf"\b{re.escape(term)}\b", lowered):
            if not _is_negated(lowered, match.start()) and not _has_phrase(
                lowered[max(0, match.start() - 24) : match.start()], ("cannot claim", "never", "no complete")
            ):
                return True
    return False


def _rule_rv8(decisions: list[dict[str, Any]], card: Any) -> list[dict[str, Any]]:
    texts = [_decision_text(decision) for decision in decisions]
    declarations = []
    for decision in decisions:
        parameters = decision["parameters"]
        if decision["tool"] == "submit_understanding":
            declarations.extend(_all_strings(parameters.get("known_limits", [])))
        elif decision["tool"] == "note_limitation":
            declarations.extend(_all_strings(parameters.get("text", "")))
    declared_text = " ".join(declarations).lower()
    has_limits = bool(declarations) and (
        any(d["tool"] == "submit_understanding" and d["parameters"].get("known_limits") for d in decisions)
        or _has_phrase(declared_text, LIMITATION_PHRASES)
    )
    has_unreviewed = _has_phrase(declared_text, _GAP_PHRASES)
    has_count_range = "count range" in declared_text or bool(
        re.search(r"\b\d[\d,]*\s*(?:-|–|to)\s*\d[\d,]*\b", declared_text)
    )
    steps = _get(card, "steps", []) or []
    incomplete = any(
        _get(_get(step, "keying"), "mode") == "unkeyed"
        or _get(_get(step, "keying"), "reference_quality") in {"incomplete", "synthetic"}
        for step in steps
    )
    recall_claimed = incomplete and any(_asserts_recall(text) for text in texts)
    problems = []
    if not has_limits:
        problems.append("limits are not stated")
    if not has_unreviewed:
        problems.append("unreviewed areas are not stated")
    if not has_count_range:
        problems.append("count range is not stated")
    if recall_claimed:
        problems.append("recall is claimed against an unkeyed or incomplete reference")
    if problems:
        return [_result("RV8", "fail", "; ".join(problems))]
    return [_result("RV8", "pass", "limits, unreviewed areas, and a count range are stated without unsupported recall")]


def _rule_rv9(
    decisions: list[dict[str, Any]], actions: list[dict[str, Any]], tool_results: Mapping[str, Any]
) -> list[dict[str, Any]]:
    by_action = {action.get("action_id"): action for action in actions}
    contradictions = []
    for decision in decisions:
        action = by_action.get(decision.get("action_id"), {})
        status, result_id = action.get("status"), action.get("result_id")
        result = tool_results.get(result_id, {}) if isinstance(result_id, str) else {}
        payload = _get(result, "payload", {})
        empty_candidates = (
            status == "success"
            and isinstance(payload, Mapping)
            and "candidates" in payload
            and payload.get("candidates") == []
        )
        if status in {"error", "budget", "blocked"} or empty_candidates:
            contradictions.append(decision)
    if not contradictions:
        return _not_applicable("RV9", "no contradictory result or failed action was recorded")
    results = []
    for contradiction in contradictions:
        sequence = contradiction.get("sequence", -1)
        later = [d for d in decisions if d.get("sequence", -1) > sequence]
        revised = any(d.get("parent_id") == contradiction.get("decision_id") for d in later)
        justified = any(
            "not revis" in _decision_text(d) and _has_phrase(_decision_text(d), _JUSTIFICATION_PHRASES)
            for d in later
        )
        if revised:
            results.append(_result("RV9", "pass", "a later decision revises the contradicted decision", contradiction))
        elif justified:
            results.append(_result("RV9", "pass", "a later decision gives a reason for not revising", contradiction))
        else:
            results.append(_result("RV9", "fail", "contradictory evidence was neither revised nor explicitly justified", contradiction))
    return results


def _negative_variants(negative: str) -> set[str]:
    phrase = negative.lower().strip()
    words = phrase.split()
    last = words[-1] if words else ""
    variants = {phrase}
    if last.endswith("ies") and len(last) > 3:
        variants.add(" ".join([*words[:-1], last[:-3] + "y"]))
    elif last.endswith("s") and not last.endswith("ss"):
        variants.add(" ".join([*words[:-1], last[:-1]]))
    return variants


def _rule_rv10(decisions: list[dict[str, Any]], asset: Any) -> list[dict[str, Any]]:
    claims = [d for d in decisions if d["tool"] == "record_claim" and d["parameters"].get("status") == "present"]
    if not claims:
        return _not_applicable("RV10", "no present claim was recorded")
    negatives = sorted({variant for negative in asset.negative for variant in _negative_variants(negative)}, key=len, reverse=True)
    results = []
    for claim in claims:
        text = _decision_text(claim)
        bad = []
        for negative in negatives:
            for match in re.finditer(rf"\b{re.escape(negative)}\b", text):
                if not _is_negated(text, match.start()):
                    bad.append(negative)
        if bad:
            results.append(_result("RV10", "fail", f"present claim is labelled as a registry negative: {bad[0]}", claim))
        else:
            results.append(_result("RV10", "pass", "present claim is not labelled as a registry negative", claim))
    return results


def _summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    verdict_by_rule = {}
    for rule_id in RULE_IDS:
        verdicts = [result["verdict"] for result in results if result["rule_id"] == rule_id]
        verdict_by_rule[rule_id] = "fail" if "fail" in verdicts else "pass" if "pass" in verdicts else "not_applicable"
    return {
        "verdict_by_rule": verdict_by_rule,
        "failed_rules": [rule_id for rule_id in RULE_IDS if verdict_by_rule[rule_id] == "fail"],
        "passed_rules": [rule_id for rule_id in RULE_IDS if verdict_by_rule[rule_id] == "pass"],
        "not_applicable_rules": [rule_id for rule_id in RULE_IDS if verdict_by_rule[rule_id] == "not_applicable"],
    }


def evaluate(
    ledger: dict,
    card: Any,
    *,
    asset_class: str,
    registry: Any = None,
    claims: list[dict[str, Any]] | None = None,
    tool_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate RV1-RV10 without mutating the ledger, card, claims, or tool results."""
    ledger_copy = copy.deepcopy(ledger)
    card_copy = copy.deepcopy(card)
    claims_copy = copy.deepcopy(claims) if claims is not None else []
    results_copy = copy.deepcopy(tool_results) if tool_results is not None else {}

    valid, problem = _valid_ledger(ledger_copy)
    if not valid or card_copy is None or not isinstance(claims_copy, list) or not isinstance(results_copy, Mapping):
        reason = problem if not valid else "task card or supplemental inputs are malformed"
        results = [_result(rule_id, "not_applicable", reason) for rule_id in RULE_IDS]
        return {"rules_version": RULES_VERSION, "results": results, "summary": _summary(results)}

    active_registry = registry if registry is not None else AssetClasses.load()
    try:
        asset = active_registry.get(asset_class)
    except (UnknownAssetClass, KeyError, AttributeError, TypeError, ValueError):
        asset = None

    decisions = [dict(decision) for decision in ledger_copy["decisions"]]
    actions = [dict(action) for action in ledger_copy["actions"]]
    results: list[dict[str, Any]] = []
    if asset is None:
        results += _not_applicable("RV1", f"unknown asset class {asset_class!r}")
    else:
        results += _rule_rv1(decisions, active_registry, asset_class)
    results += _rule_rv2(decisions)
    if asset is None:
        results += _not_applicable("RV3", f"unknown asset class {asset_class!r}")
    else:
        results += _rule_rv3(decisions, active_registry, asset_class, asset)
    results += _rule_rv4(decisions, card_copy)
    results += _rule_rv5(decisions)
    results += _rule_rv6(decisions, card_copy)
    results += _rule_rv7(decisions, actions, claims_copy, results_copy)
    results += _rule_rv8(decisions, card_copy)
    results += _rule_rv9(decisions, actions, results_copy)
    if asset is None:
        results += _not_applicable("RV10", f"unknown asset class {asset_class!r}")
    else:
        results += _rule_rv10(decisions, asset)
    return {"rules_version": RULES_VERSION, "results": results, "summary": _summary(results)}


__all__ = ["LIMITATION_PHRASES", "NEGATION_PHRASES", "RECALL_TERMS", "RULES_VERSION", "evaluate"]
