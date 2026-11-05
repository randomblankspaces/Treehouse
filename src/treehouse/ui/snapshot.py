"""Read-only shell projection of verified runs. Missing evidence remains unavailable."""
from __future__ import annotations

import json

from treehouse.canon import sha256_bytes, sha256_json
from treehouse.geo.geom import point_in_polygons
from treehouse.investigation import evaluate_investigation
from treehouse.investigation.evaluation import POSITIVE, Reference
from treehouse.investigation.reasoning_rules import evaluate as reasoning_rules
from treehouse.investigation.reporting import protocol_panels
from treehouse.paths import repo_root
from treehouse.ui.projection import metadata, parameters
from treehouse.ui.scored import named_scores, thinking_summary

SECTIONS = ("reasoning_rules", "reviewer", "agentcore", "output", "calibration", "predicted_accuracy")
METHOD_LIMIT = "Reference-derived synthetic inputs demonstrate the method; they do not validate operational accuracy or generalization."


def unavailable(reason):
    return {"status": "unavailable", "value": None, "reason": reason, "scores": []}


def available(value, *, method=False):
    return {"status": "method_test_only" if method else "available", "value": value,
            "reason": METHOD_LIMIT if method else None, "scores": []}


def pending_snapshot(summary):
    return {**summary, "status": summary["status"], "started_at": None, "elapsed_ms": None,
            "cost_usd": None, "steps": [], "markers": [],
            "provenance": {"embeddings": "unknown", "reference": "unknown", "vision": "unknown",
                           "limitations": ["Run is not sealed; recorded trace and evaluation are unavailable."]},
            "evaluation": {name: unavailable("Run is not sealed yet.") for name in SECTIONS},
            "thinking_summary": {"status": "unavailable", "basis": "recorded_decisions", "text": "", "reason": "Run is not sealed; recorded decisions are unavailable."},
            "input": {"task_id": summary["task_id"], "title": summary["title"], "goal": "",
                      "aoi_bbox": None, "time_window": None, "tools_allowed": [], "data_allowlist": []},
            "context": {"model_id": "", "provider": "", "harness": "", "system_prompt": None, "items": []}}


def _bound(record, run):
    return (record.get("run_id") == run.run_id
            and record.get("manifest_ref", record.get("manifest_hash")) == run.manifest_ref)


def _optional_records(store, run, kind, directory):
    """Only ledger records or content-addressed, manifest-bound comparison receipts qualify."""
    records = [item.record for item in store.list_records(run.run_id, kind) if _bound(item.record, run)]
    location = store.root / "comparisons" / directory / run.run_id
    if location.is_dir():
        for path in sorted(location.glob("*.json")):
            body = path.read_bytes()
            if path.stem != sha256_bytes(body).removeprefix("sha256:"):
                continue
            record = json.loads(body)
            if _bound(record, run):
                records.append(record)
    return records


def snapshot(store, run, *, reference=None):
    inv = evaluate_investigation(store, run.run_id, reference=reference)
    decisions = {(d["trial_id"], d["action"]["span_id"]): d for d in inv["decisions"] if d.get("action")}
    spans = [(trial.trial_id, span) for trial in run.trials for span in trial.spans]
    t0 = min((span.start_ns for _, span in spans), default=None)
    limitations = list(inv["process"].get("limitations", []))
    # Task flags and source product names are not proof of actual input provenance.
    indices = [call.payload.get("provenance", {}) for trial in run.trials for call in trial.calls
               if call.name == "build_index" and call.status == "success"]
    embedding = "unknown"
    if indices:
        if any(str(p.get("source", "")).startswith(("synthetic-aef-v1", "synthetic-lgnd-clay-v1"))
               and p.get("synthetic") is True and p.get("access") == "fixture" for p in indices):
            embedding = "synthetic_reference_derived"
        elif all(p.get("synthetic") is True for p in indices):
            embedding = "synthetic"
    refs = [step.keying for step in run.card.steps if step.keying.mode != "unkeyed"]
    ref_state = "synthetic" if any(k.reference_quality == "synthetic" for k in refs) else "unknown" if refs or reference else "none"
    for key in refs:
        if not key.key_path:
            continue
        path = (repo_root() / key.key_path).resolve()
        if not path.is_relative_to((repo_root() / "keys").resolve()) or not path.is_file():
            continue
        if sha256_bytes(path.read_bytes()) != key.version_hash:
            continue
        provenance = path.with_name(path.stem.removesuffix("-warehouses") + "-provenance.json")
        if provenance.is_file() and json.loads(provenance.read_text()).get("synthetic_fixture") is True:
            ref_state = "synthetic"
    vision_success = any(call.status == "success" and (call.name == "classify_window" or (
        call.name == "classify" and call.payload.get("method") == "vision_subagent")) for trial in run.trials for call in trial.calls)
    vision_attempt = any(span.attributes.get("treehouse.classifier.attempted") for _, span in spans)
    vision = "used" if vision_success else "unknown" if vision_attempt else "not_used"
    if vision == "not_used":
        limitations.append("No vision model was used.")
    method = embedding.startswith("synthetic") or ref_state == "synthetic"
    if method:
        limitations.append(METHOD_LIMIT)
    if embedding == "unknown":
        limitations.append("Actual embedding provenance is unknown; source names and task flags do not establish real data.")
    if run.replayed:
        limitations.append("Replay uses recorded model responses. Recorded model costs are historical, not a new replay charge.")
    if run.replayed:
        limitations.append("Elapsed trace time measures this replay; original model latency, when recorded, is separate trace metadata.")
    if run.manifest.config.clock == "logical":
        limitations.append("Trace elapsed time uses a logical clock; it is not measured wall time or original live latency.")
    steps, markers = [], []
    for tid, span in spans:
        a = span.attributes
        kind = a.get("gen_ai.operation.name", span.op)
        if kind not in {"invoke_agent", "chat", "execute_tool"}:
            continue
        d = decisions.get((tid, span.span_id))
        row = {"span_id": span.span_id, "trial_id": tid, "parent_span_id": span.parent_span_id,
               "kind": kind, "name": span.name, "start_ms": (span.start_ns - t0) / 1e6,
               "end_ms": (span.end_ns - t0) / 1e6, "status": "error" if span.error or span.status == "error" else "ok",
               "attributes": a}
        if kind == "chat":
            priced = any(e.name == "treehouse.investigation.model_pricing" and e.attributes.get("pricing") == "reported" for e in span.events)
            cost = a.get("treehouse.cost.usd") if priced else None
            row["model"] = {"model_id": a.get("gen_ai.request.model", ""),
                            "input_tokens": a.get("gen_ai.usage.input_tokens"),
                            "output_tokens": a.get("gen_ai.usage.output_tokens"), "cost_usd": cost,
                            "thinking": None, "stop_reason": a.get("treehouse.stop_reason")}
        tool = a.get("gen_ai.tool.name")
        if tool:
            call = next((c for t in run.trials if t.trial_id == tid for c in t.calls if c.span_id == span.span_id), None)
            summary_metadata = metadata(call.payload if call else {})
            row["tool"] = {"name": tool, "args": parameters(tool, d["parameters"]) if d else {},
                           "result": a.get("treehouse.tool.result_id"), "bytes_read": a.get("treehouse.tool.bytes_read"),
                           "result_metadata": summary_metadata}
        if d:
            row["decision"] = {key: d[key] for key in ("rationale", "alternatives", "confidence")}
            row["decision_id"] = d["decision_id"]
        if span.error:
            row["error"] = {"type": span.error.type, "message": "Recorded span failed; raw error text is withheld."}
        steps.append(row)
    for trial in run.trials:
        for claim in trial.claims:
            linked = decisions.get((trial.trial_id, claim.span_id))
            markers.append({"lon": claim.geometry.coordinates[0], "lat": claim.geometry.coordinates[1],
                            "label": claim.cls, "confidence": claim.confidence, "status": claim.status,
                            "at_ms": next(((s.end_ns - t0) / 1e6 for s in trial.spans if s.span_id == claim.span_id), None), "claim_id": claim.claim_id, "trial_id": claim.trial_id,
                            "evidence_refs": [r.model_dump(mode="json") for r in claim.evidence_refs],
                            "decision_id": linked["decision_id"] if linked else None})
    evaluation = {name: unavailable(f"No recorded {name} result bound to this run.") for name in SECTIONS}
    rules = {}
    for trial in run.trials:
        path = store.run_dir(run.run_id) / f"trials/{trial.trial_id}.investigation.json"
        if path.is_file():
            # Verified by load_sealed before this projection; never infer legacy decisions.
            rules[trial.trial_id] = reasoning_rules(json.loads(path.read_text()), run.card,
                asset_class=next(iter(run.card.classes)), claims=[c.model_dump(mode="json") for c in trial.claims])
    if rules:
        evaluation["reasoning_rules"] = available(rules)
    else:
        ledgers = store.list_records(run.run_id, "rules")
        if ledgers:
            evaluation["reasoning_rules"] = available(ledgers[-1].record)
    if reference is not None:
        inv["output"]["comparison_basis"] = {"kind": "explicit_current_server_reference", "content_ref": sha256_json(reference)}
        inv["confidence"]["comparison_basis"] = inv["output"]["comparison_basis"]
        limitations.append("Output and calibration are explicit current server-reference comparisons, not historical measurements bound to the run seal.")
        current_reference = Reference.model_validate(reference)
        unknown_scope = current_reference.coverage is None or any(
            not point_in_polygons(*claim.geometry.coordinates, run.card.aoi.polygons())
            or not point_in_polygons(*claim.geometry.coordinates, current_reference.coverage.polygons())
            for trial in run.trials for claim in trial.claims if claim.status in POSITIVE)
        if unknown_scope:
            limitations.append("Positive predictions outside task AOI or current reference coverage have unknown correctness; output and calibration are withheld for this comparison.")
        for name, panel in (("output", "output"), ("calibration", "confidence")):
            if unknown_scope:
                evaluation[name] = unavailable("Comparison scope is unknown: positive predictions are outside the task AOI or supplied reference coverage, or reference coverage is absent. Their correctness is not scored.")
                continue
            values = inv[panel].get("numbers", {})
            if any(n.get("value") is not None for n in values.values()):
                evaluation[name] = available(inv[panel], method=method)
            else:
                evaluation[name] = unavailable(inv[panel].get("no_grade_reason") or "No valid independent reference population for this run.")
    else:
        panels, reason = protocol_panels(run)
        if panels:
            for name in ("output", "calibration"):
                values = {tid: {name: panel[name], "class": panel["class"], "population": panel["population"]} for tid, panel in panels.items()}
                if name == "calibration" and all(panel[name].get("brier") is None for panel in panels.values()):
                    evaluation[name] = unavailable("No valid independent claim calibration is available for this population.")
                else:
                    evaluation[name] = available(values, method=method)
        else:
            for name in ("output", "calibration"):
                evaluation[name] = unavailable(reason)
    for name, kind, directory in (("reviewer", "verifier", "reviewer"), ("agentcore", "agentcore", "agentcore")):
        records = _optional_records(store, run, kind, directory)
        records = [record for record in records if (
            record.get("schema_version") == "treehouse.process-review/1" and isinstance(record.get("findings"), list)
            if name == "reviewer" else record.get("kind") == "agentcore_comparison" and isinstance(record.get("results"), list))]
        if records:
            evaluation[name] = available(records[-1])
    evaluation = named_scores(evaluation)
    cfg = run.manifest.config
    points = [p for polygon in run.card.aoi.polygons() for ring in polygon for p in ring]
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    cost = inv["cost"]["numbers"]["total_usd"]["value"]
    return {"run_id": run.run_id, "title": run.card.title, "status": "complete", "synthetic": run.synthetic,
            "mode": "live" if run.manifest.mode in {"record", "live"} else run.manifest.mode,
            "started_at": None, "elapsed_ms": max((s["end_ms"] for s in steps), default=None), "cost_usd": cost,
            "cost_basis": "historical_recorded" if run.replayed else "reported_model_and_classifier",
            "timing_basis": cfg.clock, "provenance": {"embeddings": embedding, "reference": ref_state,
                "vision": vision, "limitations": list(dict.fromkeys(limitations))}, "evaluation": evaluation,
            "thinking_summary": thinking_summary(run, inv["decisions"]),
            "input": {"task_id": run.card.id, "title": run.card.title, "goal": run.card.goal,
                      "aoi_bbox": [min(xs), min(ys), max(xs), max(ys)], "time_window": [str(d) for d in run.card.time_window],
                      "tools_allowed": run.card.tools_allowed,
                      "data_allowlist": [{"source_id": d.source_id, "kind": d.kind, "license": d.license} for d in run.card.data_allowlist]},
            "context": {"model_id": cfg.worker.model_key, "provider": cfg.worker.provider, "harness": cfg.harness,
                        "system_prompt": None, "items": [{"label": "Execution", "tokens": None,
                        "detail": f"{run.manifest.mode}; configured model {cfg.worker.model_key}; harness {cfg.harness}"}]},
            "steps": sorted(steps, key=lambda s: s["start_ms"]), "markers": markers}
