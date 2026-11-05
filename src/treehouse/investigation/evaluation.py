"""Post-seal measurements and class-aware catalogue comparisons; no agent calls or run writes."""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path

from pydantic import Field, model_validator
from scipy.optimize import linear_sum_assignment

from treehouse.canon import canonical_json, sha256_json
from treehouse.geo.geom import (
    bbox_ring,
    coverage_fraction,
    haversine_m,
    point_in_polygons,
    polygon_problems,
)
from treehouse.investigation.deliberation import evaluate as evaluate_deliberation
from treehouse.investigation.public import public_value
from treehouse.investigation.reporting import deliberation_scores
from treehouse.schemas.base import Frozen
from treehouse.schemas.geo import Polygon
from treehouse.schemas.numbers import TypedNumber
from treehouse.score.predicted_accuracy import deliberation_features
from treehouse.service import load_sealed

POSITIVE = {"present", "intact", "damaged", "destroyed"}


class ReferenceSource(Frozen):
    dataset: str = Field(min_length=1)
    version: str = Field(min_length=1)
    url: str = Field(min_length=1)
    license: str = Field(min_length=1)
    attribution: str = Field(min_length=1)


class ReferenceFeature(Frozen):
    id: str = Field(min_length=1)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    cls: str = Field(min_length=1)
    split: str

    @model_validator(mode="after")
    def _split(self):
        if self.split not in {"reference", "holdout"}:
            raise ValueError("reference split must be reference or holdout")
        return self


class Reference(Frozen):
    schema_version: str
    source: ReferenceSource
    quality: str
    coverage: Polygon | None
    features: list[ReferenceFeature]

    @model_validator(mode="after")
    def _rules(self):
        if self.schema_version != "treehouse.reference/1" or self.quality not in {"complete", "incomplete"}:
            raise ValueError("unsupported reference schema or quality")
        if len({f.id for f in self.features}) != len(self.features):
            raise ValueError("reference IDs must be unique and splits disjoint")
        if self.coverage and polygon_problems(self.coverage.polygons()):
            raise ValueError("reference coverage is invalid or ambiguous")
        return self


def _loaded(store, run_id):
    run = load_sealed(store, run_id)  # verification is mandatory and precedes artifact access
    ledgers = {}
    for trial in run.trials:
        p = store.run_dir(run_id) / f"trials/{trial.trial_id}.investigation.json"
        if not p.is_file():
            ledgers[trial.trial_id] = {"decisions": [], "actions": [], "legacy": True,
                                     "stop_detail": "No opt-in investigation decision records exist."}
        else:
            ledgers[trial.trial_id] = json.loads(p.read_text())
    return run, ledgers


def evaluate_investigation(store, run_id, *, reference=None):
    run, ledgers = _loaded(store, run_id)
    limitations = ["Rationale and confidence are agent self-reports; hidden reasoning quality is not assessed.",
                   "Tool counts measure activity, not reasoning quality or real-world accuracy.",
                   "No independent semantic reasoning rubric or measured human baseline is available."]

    def number(metric, value, type="count", *, tier="MEASURED", panel="process", n=None, reason=None, detail=None):
        return TypedNumber(metric=metric, value=value, type=type, tier=tier, panel=panel, n=n,
                           estimator_version="investigation/1", manifest_ref=run.manifest_ref,
                           config_hash=run.manifest.config_hash, synthetic=run.synthetic,
                           replayed=run.replayed, reasons=[reason] if reason else [], detail=detail or {}).model_dump(mode="json")

    decisions, pathways, actions = [], [], []
    successful_windows, classifier_spans = [], []
    valid_actions = 0
    legacy_actions = 0
    unsupported = poor_scale = repeated = ignored_errors = 0
    model_costs, elapsed, model_unknown = [], 0.0, False
    diagnostics = []
    deliberation, features = {}, {}
    for trial in run.trials:
        ledger = ledgers[trial.trial_id]
        if ledger.get("legacy"):
            legacy_actions += len(trial.calls)
            limitations.append(f"{trial.trial_id}: legacy run has no contemporaneous investigation decisions; none inferred.")
        calls = trial.call_by_result()
        spans = {s.span_id: s for s in trial.spans}
        trial_actions = ledger["actions"]
        for action in trial_actions:
            span = spans.get(action["span_id"])
            if (not span or span.op != "execute_tool"
                    or span.attributes.get("gen_ai.tool.call.id") != action["action_id"]
                    or span.attributes.get("treehouse.tool.args_hash") != sha256_json(action["parameters"])
                    or span.attributes.get("gen_ai.tool.name") != action["tool"]):
                raise ValueError("investigation action is inconsistent with sealed trace")
        actions.extend(trial_actions)
        for original in ledger["decisions"]:
            d = json.loads(canonical_json(original))
            span = spans.get(d["span_id"])
            if not span or span.attributes.get("gen_ai.tool.name") != "record_decision":
                raise ValueError("decision has no sealed record_decision span")
            d["trial_id"] = trial.trial_id
            if d["action"]:
                action = next((a for a in trial_actions if a["span_id"] == d["action"]["span_id"]), None)
                if (not action or action["sequence"] <= d["sequence"]
                        or action["action_id"] != d["action_id"] or action["tool"] != d["tool"]
                        or sha256_json(action["parameters"]) != sha256_json(d["parameters"])):
                    d["flags"].append("invalid_action_link")
                    d["action"] = None
                elif not d["flags"]:
                    valid_actions += 1
            decisions.append(d)
            pathways.append({"decision_id": d["decision_id"], "parent_id": d["parent_id"],
                             "action_id": d["action_id"] if d["action"] else None,
                             "result_id": d["action"]["result_id"] if d["action"] else None})
        windows = [c for c in trial.calls if c.name == "imagery_window" and c.status == "success"]
        successful_windows.extend(windows)
        classifier_spans.extend(s for s in trial.spans if s.attributes.get("treehouse.classifier.attempted"))
        boxes = [canonical_json(c.payload.get("bbox_read")) for c in windows]
        repeated += len(boxes) - len(set(boxes))
        for claim in trial.claims:
            refs = [calls.get(r.result_id) for r in claim.evidence_refs]
            images = [r for r in refs if r and r.name == "imagery_window" and r.status == "success"]
            if not claim.grounded:
                unsupported += 1
            spec = run.card.classes[claim.cls]
            threshold = (spec.max_effective_gsd_for_existence_m if claim.status in {"present", "absent"}
                         else spec.max_effective_gsd_for_status_m)
            if images and all(c.payload.get("effective_gsd_m", math.inf) > threshold for c in images):
                poor_scale += 1
                diagnostics.append({"criterion": "data_scale", "claim_id": claim.claim_id,
                                    "trial_id": trial.trial_id, "evidence_refs": [c.result_id for c in images],
                                    "observed_gsd_m": [c.payload["effective_gsd_m"] for c in images],
                                    "task_max_gsd_m": threshold,
                                    "finding": "All cited successful images exceed the task's class-specific GSD limit."})
        ignored_errors += sum("unavailable_evidence" in d["flags"] for d in ledger["decisions"])
        if trial.stop != "completed":
            limitations.append(f"{trial.trial_id} stopped with {trial.stop}: {ledger.get('stop_detail') or 'partial investigation'}")
        else:
            limitations.append(f"{trial.trial_id}: agent ended the investigation; completion does not establish exhaustive coverage.")
        if any(a["status"] != "success" for a in trial_actions):
            limitations.append(f"{trial.trial_id}: blocked, failed or budget-limited actions are not successful evidence.")
        chats = [s for s in trial.spans if s.op == "chat"]
        model_costs.extend(s.attributes.get("treehouse.cost.usd") for s in chats)
        model_unknown |= any(not any(e.name == "treehouse.investigation.model_pricing"
                                     and e.attributes.get("pricing") == "reported" for e in s.events)
                             for s in chats)
        agent = [s for s in trial.spans if s.op == "invoke_agent"]
        elapsed += sum((s.end_ns - s.start_ns) / 1e9 for s in agent)
        trial_decisions = [d for d in decisions if d["trial_id"] == trial.trial_id]
        bindings = {d["action"]["span_id"]: d["decision_id"] for d in trial_decisions if d.get("action")}
        claims = []
        for claim in trial.claims:
            action = next((a for a in trial_actions if a["span_id"] == claim.span_id), {})
            ids = [bindings[claim.span_id]] if claim.span_id in bindings else []
            for ref in claim.evidence_refs:
                call = calls.get(ref.result_id)
                if call and call.span_id in bindings:
                    ids.append(bindings[call.span_id])
            claims.append({"claim_id": claim.claim_id, "confidence": claim.confidence,
                           "decision_ids": ids, "sequence": action.get("sequence", float("inf"))})
        result = evaluate_deliberation({"decisions": trial_decisions, "actions": trial_actions, "claims": claims})
        result["scores"] = deliberation_scores(result)
        deliberation[trial.trial_id] = result
        features[trial.trial_id] = deliberation_features(result)
    cover = [[bbox_ring(w.payload["bbox_read"]) ] for w in successful_windows]
    coverage = coverage_fraction(cover, run.card.aoi.polygons()) if cover else 0
    limitations.append("Coverage is an approximate 30×30 AOI grid intersected with successful image footprints; it does not measure visibility or correct interpretation.")
    limitations.append("Reported image coverage is the union of successful footprints across trials, not coverage achieved by each individual trial.")
    if coverage < 1:
        limitations.append("Image coverage gaps remain; unseen locations have not been verified absent.")
    n_actions = len(actions) + legacy_actions
    process = {"decision_coverage": number("decision_coverage", valid_actions / n_actions if n_actions else 0,
                                           "proportion", n=n_actions),
               "action_count": number("action_count", n_actions),
               "unsupported_claims": number("unsupported_claims", unsupported),
               "scale_inappropriate_claims": number("scale_inappropriate_claims", poor_scale),
               "repeated_windows": number("repeated_windows", repeated),
               "unavailable_evidence_decisions": number("unavailable_evidence_decisions", ignored_errors),
               "image_coverage": number("image_coverage", coverage, "proportion"),
               "coverage_gap": number("coverage_gap", 1 - coverage, "proportion")}
    classifier_costs = [s.attributes.get("treehouse.classifier.cost_usd") for s in classifier_spans]
    unknown_classifier = any(c is None for c in classifier_costs)
    cost = {"numbers": {
        "classifier_usd": number("classifier_usd", None if unknown_classifier else sum(classifier_costs),
                                 "usd", panel="cost", reason="unpriced" if unknown_classifier else None),
        "model_usd": number("model_usd", None if model_unknown else sum(c or 0 for c in model_costs), "usd",
                            panel="cost", reason="unpriced" if model_unknown else None),
        "total_usd": number("total_usd", None if unknown_classifier or model_unknown else sum(classifier_costs) + sum(c or 0 for c in model_costs),
                            "usd", panel="cost", reason="unpriced" if unknown_classifier or model_unknown else None),
        "elapsed_seconds": number("elapsed_seconds", elapsed, "seconds", panel="cost")},
        "no_grade_reason": "Model or classifier cost is unpriced; totals are incomplete." if unknown_classifier or model_unknown else None}
    if run.manifest.config.clock == "logical":
        cost["numbers"]["elapsed_seconds"]["detail"]["clock"] = "logical; not measured wall time"
    predictions = [(t.trial_id, c) for t in run.trials for c in t.claims if c.status in POSITIVE]
    ref = Reference.model_validate(json.loads(Path(reference).read_text()) if isinstance(reference, str | Path)
                                   else reference) if reference is not None else None
    reason = "No grader reference supplied." if ref is None else (
        "Reference coverage is absent or ambiguous." if ref.coverage is None else None)
    output, confidence = {}, {}
    key_detail = {"key_version": ref.source.version} if ref else {}
    if ref:
        unknown_classes = {f.cls for f in ref.features} - set(run.card.classes)
        if unknown_classes:
            raise ValueError("reference contains classes outside the task")
    holdout = [f for f in ref.features if f.split == "holdout"
               and point_in_polygons(f.lon, f.lat, run.card.aoi.polygons())
               and point_in_polygons(f.lon, f.lat, ref.coverage.polygons())] if ref and ref.coverage else []
    examples = [f for f in ref.features if f.split == "reference"
                and point_in_polygons(f.lon, f.lat, run.card.aoi.polygons())
                and point_in_polygons(f.lon, f.lat, ref.coverage.polygons())] if ref and ref.coverage else []
    if any(e.cls == h.cls and haversine_m(e.lon, e.lat, h.lon, h.lat)
           <= 2 * run.card.classes[e.cls].match_tolerance_m for e in examples for h in holdout):
        reason = "Ambiguous overlap between reference-example and holdout spatial matching neighborhoods."
    all_prediction_count = len(predictions)
    if not reason:
        # Permitted examples are outside the heldout evaluation population, not heldout negatives.
        predictions = [(tid, c) for tid, c in predictions if not (
            point_in_polygons(*c.geometry.coordinates, run.card.aoi.polygons())
            and point_in_polygons(*c.geometry.coordinates, ref.coverage.polygons())
            and any(c.cls == e.cls and haversine_m(*c.geometry.coordinates, e.lon, e.lat)
                    <= run.card.classes[c.cls].match_tolerance_m for e in examples))]
    excluded_count = all_prediction_count - len(predictions)
    # Empty scoped reference cannot establish a calibrated exhaustive negative region.
    if not reason and not holdout:
        reason = "No held-out reference features in task AOI and reference coverage."
    matched_indices = set()
    tp = fn = 0
    for trial in run.trials:
        preds = [c for tid, c in predictions if tid == trial.trial_id]
        candidates = []
        for i, c in enumerate(preds):
            x, y = c.geometry.coordinates
            for j, f in enumerate(holdout):
                if (c.cls == f.cls and point_in_polygons(x, y, run.card.aoi.polygons())
                        and ref and ref.coverage and point_in_polygons(x, y, ref.coverage.polygons())):
                    dist = haversine_m(x, y, f.lon, f.lat)
                    if dist <= run.card.classes[c.cls].match_tolerance_m:
                        candidates.append((i, j, dist))
        matches = set()
        if preds and holdout:
            import numpy as np
            # Large dummy penalty first maximizes match count, then minimizes distance.
            matrix = np.full((len(preds), len(holdout) + len(preds)), 1e9)
            for i, j, dist in candidates:
                matrix[i, j] = dist
            rows, cols = linear_sum_assignment(matrix)
            matches = {int(i) for i, j in zip(rows, cols, strict=True) if j < len(holdout) and matrix[i, j] < 1e9}
        tp += len(matches)
        fn += len(holdout) - len(matches)
        matched_indices.update((trial.trial_id, preds[i].claim_id) for i in matches)
    for metric, value, typ, denom in (
        ("catalog_tp", tp, "count", len(predictions)),
        ("catalog_fp", len(predictions) - tp, "count", len(predictions)),
        ("catalog_fn", fn, "count", len(holdout) * len(run.trials)),
        ("catalog_precision", tp / len(predictions) if predictions else None, "proportion", len(predictions)),
        ("catalog_recall", tp / (tp + fn) if tp + fn else None, "proportion", tp + fn)):
        why = reason
        if not why and ref.quality == "incomplete" and metric in {"catalog_fp", "catalog_precision"}:
            why = "Incomplete catalogue: unmatched predictions require adjudication; unreviewed regions are unknown."
        if not why and value is None:
            why = "Empty denominator."
        output[metric] = number(metric, None if why else value, typ, tier="ABSTAINED" if why else "KEYED",
                                panel="output", n=denom, reason=why, detail=key_detail)
    exclusion_reason = "Known permitted reference examples are excluded from heldout precision, counts and confidence calibration; original database claims remain unchanged."
    output["reference_examples_excluded"] = number(
        "reference_examples_excluded", None if reason else excluded_count,
        tier="ABSTAINED" if reason else "KEYED", panel="output", n=all_prediction_count,
        reason=reason, detail={**key_detail, "exclusion_reason": exclusion_reason})
    confidence_reason = reason or ("Incomplete catalogue cannot establish confidence calibration." if ref.quality != "complete" else None)
    brier = sum((c.confidence - int((tid, c.claim_id) in matched_indices)) ** 2 for tid, c in predictions) / len(predictions) if predictions else None
    confidence_reason = confidence_reason or ("No positive claim confidence observations." if brier is None else None)
    confidence["brier"] = number("brier", None if confidence_reason else brier, "proportion",
                                  tier="ABSTAINED" if confidence_reason else "KEYED", panel="output",
                                  n=len(predictions), reason=confidence_reason, detail=key_detail)
    confidence["brier"]["detail"]["target"] = "catalogue presence of positive predictions; not damage status or exhaustive detection confidence"
    if ref and ref.quality == "incomplete":
        limitations.append("Catalogue match recall covers listed holdout objects only; catalogue incompleteness prevents global accuracy claims.")
    return public_value({"schema_version": "treehouse.investigation-report/1", "run_id": run_id,
            "manifest_ref": run.manifest_ref, "decisions": decisions, "pathways": pathways,
            "claims": [{"claim_id": c.claim_id, "trial_id": c.trial_id, "cls": c.cls, "status": c.status,
                        "evidence_refs": [r.model_dump(mode="json") for r in c.evidence_refs]}
                       for trial in run.trials for c in trial.claims],
            "predicted_accuracy_features": features,
            "process": {"numbers": process, "deliberation": deliberation, "limitations": limitations, "diagnostics": diagnostics,
                        "stops": [{"trial_id": t.trial_id, "reason": t.stop,
                                   "detail": ledgers[t.trial_id].get("stop_detail")} for t in run.trials]},
            "output": {"numbers": output, "no_grade_reason": reason,
                       "reference_example_exclusion_reason": exclusion_reason,
                       "reference": ref.model_dump(mode="json", exclude={"features"}) if ref else None,
                       "unmatched_to_adjudicate": len(predictions) - tp if ref and ref.quality == "incomplete" else None},
            "confidence": {"numbers": confidence, "no_grade_reason": confidence_reason}, "cost": cost,
            "summary": "Sealed decision/action observations and independent catalogue matching; semantic reasoning quality not assessed.",
            "synthetic": run.synthetic})


def _database_data(store, run_id):
    run, ledgers = _loaded(store, run_id)
    rows, features = [], []
    for trial in run.trials:
        bindings = {d["action"]["span_id"]: d["decision_id"] for d in ledgers[trial.trial_id]["decisions"]
                    if d["action"] and not d["flags"]}
        for c in trial.claims:
            lon, lat = c.geometry.coordinates
            refs = [r.model_dump(mode="json") for r in c.evidence_refs]
            decision_id = bindings.get(c.span_id)
            props = {"claim_id": c.claim_id, "trial_id": trial.trial_id, "cls": c.cls,
                     "status": c.status, "agent_confidence": c.confidence, "evidence_refs": refs,
                     "decision_id": decision_id, "synthetic": c.synthetic}
            rows.append((trial.trial_id, c.claim_id, lon, lat, c.cls, c.status, c.confidence,
                         decision_id, canonical_json(refs), int(c.synthetic)))
            if c.status in POSITIVE:
                features.append({"type": "Feature", "geometry": c.geometry.model_dump(mode="json"), "properties": props})
    return rows, {"type": "FeatureCollection", "features": features}


def database_geojson(store, run_id):
    """Verified, read-only FeatureCollection for positive sealed claims; no files are written."""
    return _database_data(store, run_id)[1]


def export_database(store, run_id, output: Path):
    rows, data = _database_data(store, run_id)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)  # refuse all existing destinations, even empty ones
    geojson, sqlite = output / "dataset.geojson", output / "dataset.sqlite"
    with sqlite3.connect(sqlite) as db:
        db.execute("CREATE TABLE detections (trial_id TEXT NOT NULL, claim_id TEXT NOT NULL, lon REAL, lat REAL, "
                   "cls TEXT, status TEXT, agent_confidence REAL, decision_id TEXT, evidence_refs_json TEXT, "
                   "synthetic INTEGER, PRIMARY KEY(trial_id,claim_id))")
        db.executemany("INSERT INTO detections VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    geojson.write_text(canonical_json(data))
    return {"geojson": str(geojson), "sqlite": str(sqlite)}
