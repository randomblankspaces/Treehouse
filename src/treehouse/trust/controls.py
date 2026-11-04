"""Same-batch controls (V5): verifier sensitivity/specificity on keyed controls, placebo false-alarm rate,
test-retest and blind-relabel kappa. Rates exclude ``cannot_assess`` answers from the denominator."""

from __future__ import annotations

from collections.abc import Sequence

from treehouse.schemas.config import TrustConfig
from treehouse.schemas.numbers import Interval, Tier, TypedNumber
from treehouse.schemas.passport import ControlsReport
from treehouse.schemas.sampling import SampleDesign
from treehouse.schemas.verdicts import GoldLabel, VerifierVerdict
from treehouse.stats.agreement import cohen_kappa
from treehouse.stats.intervals import clopper_pearson
from treehouse.trust.config import ESTIMATOR_VERSION

# control -> (unit kind, the answer counted as a hit)
RATES = {"se": ("control_pos", "yes"), "sp": ("control_neg", "no"), "placebo_far": ("placebo", "yes")}


def _num(metric, value, type_, lo, hi, n, method, over, cfg, meta, reasons=()):
    return TypedNumber(metric=metric, value=value, type=type_, tier=Tier.MEASURED, panel="controls", n=n,
                       interval=Interval(lo=lo, hi=hi, level=cfg.level, method=method),
                       estimator_version=ESTIMATOR_VERSION, reasons=list(reasons),
                       detail={"aggregate_over": over}, **meta)


def _kappa(name, pairs, over, cfg, seed, meta):
    if not pairs:
        return None
    e = cohen_kappa([a for a, _ in pairs], [b for _, b in pairs], B=cfg.B, seed=seed, level=cfg.level)
    reasons = ["anecdotal"] if len(pairs) < cfg.anecdotal_below else []
    return _num(name, e.point, "kappa", e.lo, e.hi, len(pairs), "kappa-bootstrap", over, cfg, meta, reasons)


def controls_report(design: SampleDesign, verdicts: Sequence[VerifierVerdict], cfg: TrustConfig, *,
                    gold: Sequence[GoldLabel] = (), seed: int = 0, meta: dict) -> ControlsReport:
    ans = {v.unit_id: v.answer for v in verdicts}
    out, unavailable = {}, []
    for name, (kind, hit) in RATES.items():
        a = [ans[u.unit_id] for u in design.units if u.kind == kind and ans.get(u.unit_id, "cannot_assess") != "cannot_assess"]
        if not a:
            unavailable.append(f"{name}: no answered {kind} units")
            continue
        e = clopper_pearson(sum(x == hit for x in a), len(a), cfg.level)
        out[name] = _num(name, e.point, "proportion", e.lo, e.hi, len(a), "clopper-pearson", kind, cfg, meta)
    retest = [(ans[u.ref], ans[u.unit_id]) for u in design.units
              if u.kind == "retest" and u.unit_id in ans and u.ref in ans]
    first = {g.unit_id: g.label for g in gold if not g.is_relabel}
    relabel = [(first[g.unit_id], g.label) for g in gold if g.is_relabel and g.unit_id in first]
    out["retest_kappa"] = _kappa("retest_kappa", retest, "retest", cfg, seed, meta)
    out["relabel_kappa"] = _kappa("relabel_kappa", relabel, "relabel", cfg, seed + 1, meta)
    unavailable += [f"{k}: no pairs" for k in ("retest_kappa", "relabel_kappa") if out[k] is None]
    return ControlsReport(**out, unavailable=unavailable)
