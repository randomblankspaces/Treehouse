#!/usr/bin/env python3
"""Analyze every sealed LocalStore run without combining run or trial panels.

Keyed grading uses only the held-out IDs when a ``*-split.json`` file exists. Training examples may have
been shown to the worker, so including them in grading would leak training performance into evaluation.
Claim-level calibration calls the public grader once per claim; a claim is correct when its flagged 160 m
cell touches a held-out asset under the grader's own any-touch and 1 m edge-tolerance rules.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from treehouse.cards import load_card
from treehouse.checks.protocol_grader import (
    Asset,
    GradeReport,
    PredictedClaim,
    exclude_example_claims,
    grade,
    transfer_gap,
)
from treehouse.investigation.reasoning_rules import evaluate
from treehouse.paths import repo_root
from treehouse.schemas.tools import ToolError
from treehouse.score.calibration import calibrate
from treehouse.score.predicted_accuracy import fit, leave_one_config_out, predict, validate_transfer
from treehouse.service import load_sealed
from treehouse.store.local import LocalStore
from treehouse.tools.retrieval import retrieval_for_card

CELL_SIZE_M = 160.0
BOOTSTRAP_SEED = 20261105
BOOTSTRAP_RESAMPLES = 2000
UNKEYED_REFERENCES = {
    "t1-bangladesh-warehouses": "keys/osm/chattogram-warehouses.geojson",
}
NOTE = (
    "Embeddings and references are committed synthetic fixtures (see docs/KIRO-STATUS.md); "
    "metrics measure the pipeline, not real-world accuracy."
)
HELDOUT_NOTE = (
    "Keyed grading uses only the held-out split where a split file exists; training examples may have "
    "been shown to the agent."
)
CALIBRATION_METHOD = (
    "Each claim is graded alone with the public protocol grader; correct means its 160 m flagged cell "
    "touches a held-out reference asset under the grader's any-touch rule."
)
OFFLINE_LABEL = "offline, synthetic fixture embeddings, not a live agent run"
NO_INTERVAL = "95% bootstrap interval requires at least 2 trials"

SCALAR_PATHS = {
    "output.recall": ("output", "recall"),
    "output.precision": ("output", "precision"),
    "output.lift": ("output", "lift"),
    "output.count_ratio": ("output", "count_ratio"),
    "output.auroc": ("output", "auroc"),
    "output.ap": ("output", "ap"),
    "output.recall_at_10": ("output", "recall_at_k", "10"),
    "output.recall_at_20": ("output", "recall_at_k", "20"),
    "output.recall_at_50": ("output", "recall_at_k", "50"),
    "output.review_effort_50": ("output", "review_effort", "50"),
    "output.review_effort_80": ("output", "review_effort", "80"),
    "output.review_effort_90": ("output", "review_effort", "90"),
    "output.n_assets": ("output", "n_assets"),
    "output.n_found": ("output", "n_found"),
    "output.n_claims": ("output", "n_claims"),
    "output.n_predicted_sites": ("output", "n_predicted_sites"),
    "output.n_flagged_cells": ("output", "n_flagged_cells"),
    "output.n_grid_cells": ("output", "n_grid_cells"),
    "output.n_asset_cells": ("output", "n_asset_cells"),
    "reasoning.rv_pass_rate": ("reasoning", "rv_pass_rate"),
    "calibration.brier": ("calibration", "brier"),
    "calibration.ece": ("calibration", "ece"),
    "cost.usd": ("cost", "usd"),
    "cost.model_calls": ("cost", "model_calls"),
    "cost.input_tokens": ("cost", "input_tokens"),
    "cost.output_tokens": ("cost", "output_tokens"),
    "cost.tool_calls": ("cost", "tool_calls"),
    "cost.wall_seconds": ("cost", "wall_seconds"),
}


def _aoi_bbox(card) -> tuple[float, float, float, float]:
    def points(value):
        if isinstance(value[0], (int, float)):
            return [value]
        return [point for child in value for point in points(child)]

    coordinates = points(card.aoi.coordinates)
    xs, ys = (point[0] for point in coordinates), (point[1] for point in coordinates)
    xs, ys = list(xs), list(ys)
    return min(xs), min(ys), max(xs), max(ys)


def _assets(path: Path, heldout: set[str] | None = None) -> list[Asset]:
    collection = json.loads(path.read_text())
    assets = []
    for feature in collection["features"]:
        feature_id = str(feature.get("id") or feature.get("properties", {}).get("id"))
        if heldout is not None and feature_id not in heldout:
            continue
        geometry = feature["geometry"]
        if geometry["type"] != "Point":
            raise ValueError(f"reference {path} contains non-Point geometry {geometry['type']!r}")
        lon, lat = geometry["coordinates"][:2]
        assets.append(Asset(lon=float(lon), lat=float(lat), id=feature_id))
    return assets


def _validated_split(reference_path):
    split_path = reference_path.with_name(reference_path.stem.removesuffix("-warehouses") + "-split.json")
    try:
        split = json.loads(split_path.read_text())
        groups = [split[name] for name in ("train", "heldout")]
        if any(not isinstance(group, list) or not all(isinstance(x, str) for x in group)
               or len(group) != len(set(group)) for group in groups):
            raise ValueError("split populations must be unique ID lists")
        train, heldout = map(set, groups)
        identifiers = {str(f.get("id") or f.get("properties", {}).get("id"))
                       for f in json.loads(reference_path.read_text())["features"]}
        if not heldout or train & heldout or not (train | heldout) <= identifiers:
            raise ValueError("split populations must be nonempty, disjoint and contain known reference IDs")
        return train, heldout, split_path
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError("Reference split population is missing or invalid; held-out grading refused.") from exc


def _reference(card) -> tuple[list[Asset], str, bool, str]:
    keyed_step = next((step for step in card.steps if step.keying.mode == "keyed"), None)
    if keyed_step is None:
        relative = UNKEYED_REFERENCES.get(card.id)
        if relative is None:
            return [], "incomplete", False, "unkeyed card has no mapped precision pool"
        return _assets(repo_root() / relative), "incomplete", False, f"precision pool: {relative}"

    relative = keyed_step.keying.key_path
    if relative is None:
        raise ValueError(f"keyed card {card.id} has no key_path")
    reference_path = repo_root() / relative
    _, heldout, split_path = _validated_split(reference_path)
    note = f"current reference: {relative}; current held-out split {split_path.relative_to(repo_root())}; not a sealed historical population"
    quality = keyed_step.keying.reference_quality
    completeness = "incomplete" if quality == "incomplete" else "complete"
    return _assets(reference_path, heldout), completeness, True, note


def _examples(card):
    step = next((s for s in card.steps if s.keying.mode == "keyed"), None)
    if step is None or step.keying.key_path is None:
        return []
    path = repo_root() / step.keying.key_path
    train, _, _ = _validated_split(path)
    return _assets(path, train)


def _claims(trial) -> list[PredictedClaim]:
    return [
        PredictedClaim(
            lon=float(claim.geometry.coordinates[0]),
            lat=float(claim.geometry.coordinates[1]),
            score=float(claim.confidence),
        )
        for claim in trial.claims
        if claim.status == "present"
    ]


def _claim_correctness(
    claims: list[PredictedClaim], assets: list[Asset], aoi_bbox: tuple[float, float, float, float], examples=()
) -> list[bool]:
    return [
        grade([claim], assets, aoi_bbox, completeness="complete", cell_size_m=CELL_SIZE_M, excluded_assets=examples).precision == 1.0
        for claim in claims
    ]


def _cost(trial) -> dict[str, int | float]:
    chats = [span for span in trial.spans if span.op == "chat"]
    if trial.spans:
        wall_seconds = (max(span.end_ns for span in trial.spans) - min(span.start_ns for span in trial.spans)) / 1e9
    else:
        wall_seconds = 0.0
    return {
        "usd": sum(float(span.attributes.get("treehouse.cost.usd", 0.0)) for span in chats),
        "model_calls": len(chats),
        "input_tokens": sum(int(span.attributes.get("gen_ai.usage.input_tokens", 0)) for span in chats),
        "output_tokens": sum(int(span.attributes.get("gen_ai.usage.output_tokens", 0)) for span in chats),
        "tool_calls": len(trial.calls),
        "wall_seconds": wall_seconds,
    }


def _features(ledger: dict, claims: list[PredictedClaim], rv_pass_rate: float) -> dict[str, float]:
    decisions = ledger.get("decisions", [])
    cell_size = next(
        (
            float(decision.get("parameters", {}).get("cell_size_m", 0))
            for decision in decisions
            if decision.get("tool") == "build_index"
        ),
        0.0,
    )
    used_vision = any(
        decision.get("tool") == "classify"
        and decision.get("parameters", {}).get("method") == "vision_subagent"
        for decision in decisions
    )
    return {
        "rv_pass_rate": rv_pass_rate,
        "n_present_claims": float(len(claims)),
        "mean_confidence": float(np.mean([claim.score for claim in claims])) if claims else 0.0,
        "used_vision": float(used_vision),
        "cell_size_m": cell_size,
    }


def _trial_panels(store: LocalStore, run, trial, assets, completeness, keyed, aoi_bbox):
    examples = _examples(run.card)
    claims = exclude_example_claims(_claims(trial), examples, aoi_bbox, assets=assets, cell_size_m=CELL_SIZE_M)
    output_report = grade(claims, assets, aoi_bbox, completeness=completeness, cell_size_m=CELL_SIZE_M, excluded_assets=examples)
    ledger_path = store.run_dir(run.run_id) / "trials" / f"{trial.trial_id}.investigation.json"
    ledger = json.loads(ledger_path.read_text())
    claim_rows = [claim.model_dump(mode="json") for claim in trial.claims]
    reasoning_report = evaluate(ledger, run.card, asset_class="warehouse", claims=claim_rows)
    summary = reasoning_report["summary"]
    passed, failed = len(summary["passed_rules"]), len(summary["failed_rules"])
    rv_pass_rate = passed / (passed + failed) if passed + failed else 0.0
    reasoning = {
        "rules_version": reasoning_report["rules_version"],
        "verdict_by_rule": summary["verdict_by_rule"],
        "failed_rules": summary["failed_rules"],
        "rv_pass_rate": rv_pass_rate,
    }
    if keyed and output_report.n_assets:
        correct = _claim_correctness(claims, assets, aoi_bbox, examples)
        calibration = calibrate([claim.score for claim in claims], correct, n_bins=5) | {
            "correctness_method": CALIBRATION_METHOD
        }
    else:
        correct = []
        calibration = {"no_grade_reason": "No valid held-out population" if keyed else "unkeyed"}
    panels = {
        "output": output_report.model_dump(mode="json"),
        "reasoning": reasoning,
        "calibration": calibration,
        "cost": _cost(trial),
    }
    return panels, _features(ledger, claims, rv_pass_rate), correct, output_report, claims


def _value(panel: dict, path: tuple[str, ...]) -> float | None:
    value: Any = panel
    for part in path:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _summary(values: list[float], *, seed: int = BOOTSTRAP_SEED) -> dict[str, Any]:
    result = {"n": len(values), "mean": float(np.mean(values)) if values else None}
    if len(values) < 2:
        return result | {"interval_95": None, "interval_reason": NO_INTERVAL}
    rng = np.random.default_rng(seed)
    sample = np.asarray(values, float)
    means = rng.choice(sample, size=(BOOTSTRAP_RESAMPLES, len(sample)), replace=True).mean(axis=1)
    lo, hi = np.quantile(means, [0.025, 0.975])
    return result | {
        "interval_95": [float(lo), float(hi)],
        "interval_reason": None,
        "bootstrap": {"seed": seed, "resamples": BOOTSTRAP_RESAMPLES},
    }


def _difference(left: list[float], right: list[float], *, paired: bool = False) -> dict[str, Any]:
    result = {
        "n_left": len(left),
        "n_right": len(right),
        "difference_of_means": float(np.mean(left) - np.mean(right)) if left and right else None,
    }
    if len(left) < 2 or len(right) < 2 or (paired and len(left) != len(right)):
        return result | {"interval_95": None, "interval_reason": NO_INTERVAL}
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    if paired:
        differences = np.asarray(left) - np.asarray(right)
        samples = rng.choice(differences, size=(BOOTSTRAP_RESAMPLES, len(differences)), replace=True).mean(axis=1)
    else:
        a = rng.choice(np.asarray(left), size=(BOOTSTRAP_RESAMPLES, len(left)), replace=True).mean(axis=1)
        b = rng.choice(np.asarray(right), size=(BOOTSTRAP_RESAMPLES, len(right)), replace=True).mean(axis=1)
        samples = a - b
    lo, hi = np.quantile(samples, [0.025, 0.975])
    return result | {
        "interval_95": [float(lo), float(hi)],
        "interval_reason": None,
        "bootstrap": {"seed": BOOTSTRAP_SEED, "resamples": BOOTSTRAP_RESAMPLES},
    }


def _config_panels(rows: list[dict]) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["config_label"]].append(row)
    output = {}
    for label, trials in sorted(grouped.items()):
        metrics = {}
        for name, path in SCALAR_PATHS.items():
            values = [value for trial in trials if (value := _value(trial["panels"], path)) is not None]
            metrics[name] = _summary(values)
        if trials[0]["keyed"]:
            valid = [trial for trial in trials if len(trial["claims"]) == len(trial["correct"])]
            confidences = [claim.score for trial in valid for claim in trial["claims"]]
            correct = [outcome for trial in valid for outcome in trial["correct"]]
            pooled = calibrate(confidences, correct, n_bins=5) | {"correctness_method": CALIBRATION_METHOD}
        else:
            pooled = {"no_grade_reason": "unkeyed"}
        output[label] = {
            "n": len(trials),
            "n_trials": len(trials),
            "trial_refs": [f"{trial['run_id']}/{trial['trial_id']}" for trial in trials],
            "metrics": metrics,
            "pooled_calibration": pooled,
        }
    return output


def _find_rows(rows: list[dict], card_id: str, model_key: str, harness: str) -> list[dict]:
    return [
        row
        for row in rows
        if row["card_id"] == card_id and row["model_key"] == model_key and row["harness"] == harness
    ]


def _model_comparison(rows: list[dict]) -> dict:
    sonnet = _find_rows(rows, "t1-nagoya-warehouses", "claude-sonnet-5-5", "strands")
    nova = _find_rows(rows, "t1-nagoya-warehouses", "nova-pro", "strands")
    metrics = {}
    for name, path in SCALAR_PATHS.items():
        left = [value for row in sonnet if (value := _value(row["panels"], path)) is not None]
        right = [value for row in nova if (value := _value(row["panels"], path)) is not None]
        metrics[name] = _difference(left, right)
    return {
        "factor": "model",
        "held_constant": {"card_id": "t1-nagoya-warehouses", "harness": "strands"},
        "left": "claude-sonnet-5-5",
        "right": "nova-pro",
        "difference": "left mean minus right mean",
        "metrics": metrics,
    }


def _mean_grade(rows: list[dict]) -> GradeReport | None:
    if not rows:
        return None
    updates = {}
    for name in ("recall", "precision", "lift", "count_ratio", "auroc", "ap"):
        values = [getattr(row["grade"], name) for row in rows if getattr(row["grade"], name) is not None]
        updates[name] = float(np.mean(values)) if values else None
    return rows[0]["grade"].model_copy(update=updates)


def _transfer_comparison(rows: list[dict]) -> dict:
    nagoya = _find_rows(rows, "t1-nagoya-warehouses", "claude-sonnet-5-5", "strands")
    gifu = _find_rows(rows, "t5-gifu-warehouses", "claude-sonnet-5-5", "strands")
    home, away = _mean_grade(nagoya), _mean_grade(gifu)
    if home is None or away is None:
        gap, reason = {}, "requires Sonnet/Strands trials for both Nagoya and Gifu"
    else:
        gap, reason = transfer_gap(home, away), None
    return {
        "factor": "city transfer",
        "model_key": "claude-sonnet-5-5",
        "harness": "strands",
        "direction": "Nagoya mean minus Gifu mean",
        "metrics": gap,
        "reason": reason,
    }


def _predicted_accuracy(rows: list[dict]) -> dict:
    nagoya = [row for row in rows if row["keyed"] and row["card_id"] == "t1-nagoya-warehouses"]
    gifu = [row for row in rows if row["keyed"] and row["card_id"] == "t5-gifu-warehouses"]
    bangladesh = [row for row in rows if row["card_id"] == "t1-bangladesh-warehouses"]
    targets = {"site_recall": "recall", "cell_precision": "precision"}
    output = {}
    for target, grade_name in targets.items():
        training = [row for row in nagoya if getattr(row["grade"], grade_name) is not None]
        if not training:
            output[target] = {
                "verdict": "insufficient validation",
                "reason": "no keyed Nagoya target values",
                "bangladesh_predictions": [],
            }
            continue
        features = [row["features"] for row in training]
        values = [float(getattr(row["grade"], grade_name)) for row in training]
        configs = [row["config_label"] for row in training]
        model = fit(features, values, configs, target=target)
        transfer_rows = [row for row in gifu if getattr(row["grade"], grade_name) is not None]
        transfer = validate_transfer(
            model,
            [row["features"] for row in transfer_rows],
            [float(getattr(row["grade"], grade_name)) for row in transfer_rows],
        )
        predictions = predict(model, [row["features"] for row in bangladesh])
        output[target] = {
            "model": asdict(model),
            "leave_one_config_out": leave_one_config_out(features, values, configs),
            "gifu_transfer": transfer,
            "bangladesh_predictions": [
                prediction | {"run_id": row["run_id"], "trial_id": row["trial_id"]}
                for row, prediction in zip(bangladesh, predictions, strict=True)
            ],
        }
    return {
        "label": "MODEL-ESTIMATED",
        "status": "method_test_only",
        "reason": "Reference-derived synthetic fixtures demonstrate this estimator; they cannot validate operational accuracy or generalization.",
        "training_scope": "keyed Nagoya runs; None targets are skipped",
        "validation_scope": "leave-one-config-out on Nagoya and transfer to Gifu",
        "targets": output,
    }


def _classifier_comparison() -> dict:
    card = load_card(repo_root() / "tasks/t1-nagoya-warehouses.yaml")
    tools = retrieval_for_card(card)
    built = tools.build_index("aef-10m-annual", CELL_SIZE_M, 2024)
    if isinstance(built, ToolError):
        raise RuntimeError(built.message)
    index_id = built["index_id"]
    example_ids = [example["example_id"] for example in tools.examples.train_examples()]
    assets, _, _, reference_note = _reference(card)
    aoi_bbox = _aoi_bbox(card)
    seeds = [BOOTSTRAP_SEED + offset for offset in range(3)]
    trials = []
    for seed in seeds:
        subset = sorted(np.random.default_rng(seed).choice(example_ids, size=12, replace=False).tolist())
        methods = {}
        for method in ("linear_probe", "linear_svm"):
            classified = tools.classify(index_id, method, example_ids=subset, k=1000)
            if isinstance(classified, ToolError):
                raise RuntimeError(classified.message)
            aggregated = tools.aggregate(index_id, classified["scores"], threshold=0.5)
            if isinstance(aggregated, ToolError):
                raise RuntimeError(aggregated.message)
            claims = [
                PredictedClaim(lon=site["lon"], lat=site["lat"], score=site["max_score"])
                for site in aggregated["sites"]
            ]
            report = grade(claims, assets, aoi_bbox, completeness="complete", cell_size_m=CELL_SIZE_M, excluded_assets=_examples(card))
            methods[method] = report.model_dump(mode="json")
        trials.append({"seed": seed, "training_example_ids": subset, "methods": methods})

    summary = {}
    for method in ("linear_probe", "linear_svm"):
        summary[method] = {
            metric: _summary([trial["methods"][method][metric] for trial in trials])
            for metric in ("recall", "precision")
        }
    differences = {
        metric: _difference(
            [trial["methods"]["linear_probe"][metric] for trial in trials],
            [trial["methods"]["linear_svm"][metric] for trial in trials],
            paired=True,
        )
        for metric in ("recall", "precision")
    }
    return {
        "label": OFFLINE_LABEL,
        "setup": {
            "source_id": "aef-10m-annual",
            "cell_size_m": CELL_SIZE_M,
            "year": 2024,
            "threshold": 0.5,
            "classifier_k": 1000,
            "training_subset": "random 12 of 16 Nagoya training examples per seed",
            "reference": reference_note,
        },
        "trials": trials,
        "methods": summary,
        "difference": {
            "direction": "linear_probe mean minus linear_svm mean",
            "metrics": differences,
        },
        "gifu_transfer": {
            "status": "not applicable: no training examples (transfer requires a cross-index classifier, not built)"
        },
    }


def _git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root(), check=True, capture_output=True, text=True
    ).stdout.strip()


def analyze(store_path: Path | str) -> dict:
    store = LocalStore(store_path)
    run_ids = sorted(
        {
            line["rec"]["run_id"]
            for line in store.ledger_lines()
            if line["rec"].get("kind") == "run" and store.is_sealed(line["rec"]["run_id"])
        }
    )
    runs, rows = {}, []
    for run_id in run_ids:
        run = load_sealed(store, run_id)
        config = run.manifest.config
        config_label = f"{run.card.id}|{config.worker.model_key}|{config.harness}"
        assets, completeness, keyed, reference_note = _reference(run.card)
        aoi_bbox = _aoi_bbox(run.card)
        trial_panels = {}
        for trial in run.trials:
            panels, features, correct, report, claims = _trial_panels(
                store, run, trial, assets, completeness, keyed, aoi_bbox
            )
            trial_panels[trial.trial_id] = panels
            rows.append(
                {
                    "run_id": run_id,
                    "trial_id": trial.trial_id,
                    "card_id": run.card.id,
                    "model_key": config.worker.model_key,
                    "harness": config.harness,
                    "config_label": config_label,
                    "keyed": keyed,
                    "panels": panels,
                    "features": features,
                    "correct": correct,
                    "grade": report,
                    "claims": claims,
                }
            )
        runs[run_id] = {
            "card_id": run.card.id,
            "config_label": config_label,
            "model_key": config.worker.model_key,
            "harness": config.harness,
            "reference": reference_note,
            "grading_split_note": HELDOUT_NOTE,
            "panels_by_trial": trial_panels,
        }

    return {
        "metadata": {
            "generated_at": datetime.now(UTC).isoformat(),
            "store": str(Path(store_path)),
            "run_ids": run_ids,
            "git_commit": _git_commit(),
            "note": NOTE,
            "grading_split_note": HELDOUT_NOTE,
            "bootstrap": {"seed": BOOTSTRAP_SEED, "resamples": BOOTSTRAP_RESAMPLES, "confidence": 0.95},
        },
        "runs": runs,
        "configs": _config_panels(rows),
        "comparisons": {
            "model": _model_comparison(rows),
            "transfer_gap": _transfer_comparison(rows),
            "classifier": _classifier_comparison(),
        },
        "predicted_accuracy": _predicted_accuracy(rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True, help="LocalStore root")
    parser.add_argument("--out", type=Path, required=True, help="metrics JSON destination")
    args = parser.parse_args()
    metrics = analyze(args.store)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
