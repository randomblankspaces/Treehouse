"""Named measurements and deterministic prose from recorded evidence; no models or writes."""
from __future__ import annotations


def score(metric, value, unit, numerator, denominator, basis, section, *, trial_id=None, reason=None):
    missing = value is None or denominator is None or denominator <= 0
    result = {"metric": metric, "value": None if missing else value, "unit": unit,
              "numerator": numerator, "denominator": denominator, "basis": basis,
              "status": "unavailable" if missing else section["status"],
              "reason": (reason or "No assessed population or recorded numeric scale.") if missing else section["reason"]}
    if trial_id is not None:
        result["trial_id"] = trial_id
    return result


def named_scores(evaluation):
    """Keep incompatible catalogue, cell and assessed-rule denominators explicitly separate."""
    for name, section in evaluation.items():
        section["scores"] = []
        if section["status"] == "unavailable":
            continue
        value = section["value"]
        if name == "reasoning_rules":
            for tid, report in value.items():
                if not isinstance(report, dict) or "summary" not in report:
                    continue
                summary = report["summary"]
                passed, failed = len(summary["passed_rules"]), len(summary["failed_rules"])
                total = passed + failed
                section["scores"].append(score("rules_pass_rate", 100 * passed / total if total else None,
                    "percent", passed, total, "passed / assessed workflow rule criteria; not applicable criteria excluded; not intrinsic cognition", section, trial_id=tid))
        elif name in {"output", "calibration"} and "numbers" in value:
            numbers = value["numbers"]
            if name == "output":
                for metric in ("precision", "recall"):
                    number = numbers.get(f"catalog_{metric}", {})
                    fraction = number.get("value")
                    tp = numbers.get("catalog_tp", {}).get("value")
                    section["scores"].append(score(metric, None if fraction is None else fraction * 100,
                        "percent", tp, number.get("n"),
                        "explicit current server-reference catalogue comparison: matched predictions / scoped predictions" if metric == "precision" else
                        "explicit current server-reference catalogue comparison: matched holdout objects / scoped catalogue holdout objects across trials",
                        section, reason="; ".join(number.get("reasons", [])) or None))
            else:
                number = numbers.get("brier", {})
                section["scores"].append(score("brier", number.get("value"), "raw", None, number.get("n"),
                    "explicit current catalogue comparison; mean squared probability error over graded positive predictions; lower is better; not accuracy",
                    section, reason="; ".join(number.get("reasons", [])) or None))
        if not section["scores"] and not section["reason"]:
            section["reason"] = "A numeric rubric or recorded scale is unavailable; the separate raw result is retained."
    return evaluation


def thinking_summary(run, decisions):
    if not decisions:
        return {"status": "unavailable", "basis": "recorded_decisions", "text": "",
                "reason": "No contemporaneous decisions were recorded; hidden reasoning cannot be recovered."}
    cfg = run.manifest.config
    models = sorted({str(span.attributes[key]) for trial in run.trials for span in trial.spans
                     for key in ("gen_ai.request.model", "gen_ai.response.model")
                     if span.op == "chat" and span.attributes.get(key)})
    text = [f"Recorded rationale summary: observed model(s) {', '.join(models) or 'unavailable'}; configured model {cfg.worker.model_key}; harness {cfg.harness}."]
    # Keep the report below the public text limit; the complete decision trace remains inspectable.
    selected = decisions if len(decisions) <= 8 else decisions[:5] + decisions[-3:]
    selected_ids = {(d.get("trial_id"), d["decision_id"]) for d in selected}
    if len(selected) < len(decisions):
        text.append(f"Summary coverage: {len(selected)} of {len(decisions)} recorded decisions shown; intervening decisions remain in the full trace.")
    def clip(value, limit):
        return value if len(value) <= limit else value[:limit] + "…"
    for trial in run.trials[:8]:
        ordered = sorted((d for d in decisions if d.get("trial_id") == trial.trial_id), key=lambda d: d["sequence"])
        text.append(f"Trial {trial.trial_id}: {len(ordered)} recorded decisions.")
        previous = set()
        for d in ordered:
            if (d.get("trial_id"), d["decision_id"]) not in selected_ids:
                continue
            action = d.get("action")
            outcome = action.get("status", "unknown") if action else "no linked action"
            repeat = " Revisited this tool; the record does not establish a change of plan." if d["tool"] in previous else ""
            previous.add(d["tool"])
            refs = ", ".join(clip(ref, 48) for ref in d.get("evidence_refs", [])[:2]) or "none recorded"
            alternatives = "; ".join(f"{clip(a['option'], 48)}: {clip(a['reason'], 64)}" for a in d.get("alternatives", [])[:2]) or "none recorded"
            text.append(f"{d['decision_id']}: {d['tool']} ({outcome}). Recorded rationale: {clip(d['rationale'], 200)}. Alternatives: {alternatives}. Support: {refs}.{repeat}")
        counts = {status: sum(c.status == status for c in trial.claims) for status in ("present", "absent", "cannot_assess")}
        text.append(f"Recorded stop: {trial.stop}. Output: {counts['present']} predicted present, {counts['absent']} absent, {counts['cannot_assess']} cannot assess; these are agent reports, not ground truth.")
    if len(run.trials) > 8:
        text.append("Additional trials are omitted from this bounded summary; inspect the full trace for their stops and outcomes.")
    text.append("This deterministic local summary describes recorded explanations and actions, not hidden reasoning. Exploration and revisions beyond the recorded decisions are unavailable.")
    return {"status": "available", "basis": "recorded_decisions", "text": "\n\n".join(text), "reason": None}
