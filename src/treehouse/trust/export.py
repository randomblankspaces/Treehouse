"""Raw-statistics export: every number behind a passport as tidy tables (lists of dicts), so developers can
run their own inference. ``write_tables`` uses the stdlib only (csv or jsonl)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from treehouse.schemas.passport import TrustPassport
from treehouse.trust.tiers import EvidenceBundle

DATA_DICTIONARY: dict[str, dict[str, str]] = {
    "units": {
        "unit_id": "sampled unit id (sealed id, not the blind id the verifier saw)",
        "kind": "claim | control_pos | control_neg | placebo | retest | unreported",
        "stratum": "sampling stratum label",
        "pi": "phase-1 inclusion probability n_h/N_h (unitless, 0-1]",
        "weight": "design weight 1/pi (frame units represented by this unit)",
        "worker_claim": "worker's answer to the step question: yes | no | cannot_assess; null for controls",
        "verifier_verdict": "verifier answer: yes | no | cannot_assess (abstain); null when no verdict",
        "gold_label": "first-pass human gold label: yes | no | cannot_assess; null when not labelled",
        "sampled_for_gold": "true when the unit is in the committed random gold draw",
    },
    "estimates": {
        "metric": "number name (headline uses the estimand name)",
        "estimator": "keyed | ppi | classical | upper | b0 | b1 | b2",
        "method": "interval method (e.g. ppi-2phase-rbs-v1, hypergeom-exact, betabinom-predictive)",
        "point": "point estimate (proportion 0-1); null when abstained",
        "lo": "interval lower bound (proportion 0-1)",
        "hi": "interval upper bound (proportion 0-1)",
        "level": "interval confidence level (e.g. 0.9)",
        "n": "units in the estimate (sampled claims, or n_new for baselines)",
        "n_gold": "gold labels used (null when none)",
        "lambda": "PPI power-tuning lambda (fixed 1 below lam_fixed_below); null for non-PPI",
        "tier": "evidence tier (KEYED, GOLD-ANCHORED, MODEL-ESTIMATED, ABSTAINED, ...)",
        "estimator_version": "trust-engine version that produced the row",
        "is_headline": "true for the passport headline",
    },
    "baselines": {
        "baseline": "b0 | b1 | b2",
        "point": "predicted precision of this run (proportion 0-1)",
        "lo": "predictive interval lower bound (proportion 0-1)",
        "hi": "predictive interval upper bound (proportion 0-1)",
        "level": "interval level",
        "mu": "beta-binomial mean (null for b1)",
        "kappa": "beta-binomial concentration a+b (null for b1)",
        "fit": "mle | kappa0 | prior (null for b1)",
        "n_runs": "keyed runs pooled (null for b1)",
        "n_new": "claims in this run the prediction is for",
    },
    "controls": {
        "control": "se | sp | placebo_far | retest_kappa | relabel_kappa",
        "point": "rate (proportion) or Cohen's kappa",
        "lo": "interval lower bound",
        "hi": "interval upper bound",
        "level": "interval level",
        "n": "answered control units or pairs",
        "method": "clopper-pearson | kappa-bootstrap",
        "reasons": "semicolon-separated flags (e.g. anecdotal)",
    },
}


def tables(ev: EvidenceBundle, passport: TrustPassport) -> dict[str, list[dict]]:
    verdict = {v.unit_id: v.answer for v in ev.verdicts}
    gold = {g.unit_id: g.label for g in ev.gold if not g.is_relabel}
    drawn = set(ev.gold_draw.unit_ids) if ev.gold_draw else set()
    units = [{"unit_id": u.unit_id, "kind": u.kind, "stratum": u.stratum, "pi": u.pi, "weight": 1 / u.pi,
              "worker_claim": ev.claimed.get(u.unit_id), "verifier_verdict": verdict.get(u.unit_id),
              "gold_label": gold.get(u.unit_id), "sampled_for_gold": u.unit_id in drawn}
             for u in sorted(ev.design.units, key=lambda u: u.order)]
    nums = [passport.headline, *passport.alternatives]
    iv = lambda x, k: getattr(x.interval, k) if x.interval else None  # noqa: E731
    estimates = [{"metric": x.metric, "estimator": x.detail.get("estimator"), "method": iv(x, "method"),
                  "point": x.value, "lo": iv(x, "lo"), "hi": iv(x, "hi"), "level": iv(x, "level"), "n": x.n,
                  "n_gold": x.n_gold, "lambda": x.detail.get("lambda"), "tier": x.tier.value,
                  "estimator_version": x.estimator_version, "is_headline": i == 0} for i, x in enumerate(nums)]
    baselines = [{"baseline": x.detail["estimator"], "point": x.value, "lo": iv(x, "lo"), "hi": iv(x, "hi"),
                  "level": iv(x, "level"), "mu": x.detail.get("mu"), "kappa": x.detail.get("kappa"),
                  "fit": x.detail.get("fit"), "n_runs": x.detail.get("n_runs"), "n_new": x.n}
                 for x in nums if x.detail.get("estimator") in ("b0", "b1", "b2")]
    c = passport.controls
    controls = [{"control": k, "point": x.value, "lo": iv(x, "lo"), "hi": iv(x, "hi"), "level": iv(x, "level"),
                 "n": x.n, "method": iv(x, "method"), "reasons": ";".join(x.reasons)}
                for k in ("se", "sp", "placebo_far", "retest_kappa", "relabel_kappa") if (x := getattr(c, k))]
    return {"units": units, "estimates": estimates, "baselines": baselines, "controls": controls}


def write_tables(dir: Path, tbls: dict[str, list[dict]], fmt: str = "csv") -> list[Path]:
    """Write ``<table>.<fmt>`` per table plus ``data_dictionary.<fmt>`` (table, column, meaning).
    CSV writes null as an empty cell and booleans as True/False."""
    if fmt not in ("csv", "jsonl"):
        raise ValueError("fmt must be csv or jsonl")
    dir = Path(dir)
    dir.mkdir(parents=True, exist_ok=True)
    dd = [{"table": t, "column": c, "meaning": m} for t, cols in DATA_DICTIONARY.items() for c, m in cols.items()]
    out = []
    for name, rows, cols in [*((t, tbls[t], list(DATA_DICTIONARY[t])) for t in DATA_DICTIONARY),
                             ("data_dictionary", dd, ["table", "column", "meaning"])]:
        path = dir / f"{name}.{fmt}"
        with path.open("w", newline="", encoding="utf-8") as fh:
            if fmt == "csv":
                w = csv.DictWriter(fh, fieldnames=cols, extrasaction="raise")
                w.writeheader()
                w.writerows(rows)
            else:
                fh.writelines(json.dumps({c: r[c] for c in cols}, allow_nan=False) + "\n" for r in rows)
        out.append(path)
    return out
