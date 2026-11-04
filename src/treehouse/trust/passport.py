"""build_passport: evidence bundle -> TrustPassport. Pure and deterministic given ``seed``."""

from __future__ import annotations

from treehouse.schemas.config import TrustConfig
from treehouse.schemas.numbers import Interval, Tier, TypedNumber
from treehouse.schemas.passport import Estimand, TrustPassport
from treehouse.trust.baselines import baseline_b0, baseline_b1, baseline_b2
from treehouse.trust.config import ESTIMATOR_VERSION, trust_config_hash
from treehouse.trust.controls import controls_report
from treehouse.trust.ppi import PPIResult, classical_gold_only, ppi_mean, predictor_values
from treehouse.trust.tiers import EvidenceBundle, disagreements, gate, select_tier

UPPER = "precision_upper_if_unassessable_correct"


def _gold_number(metric, estimator, r: PPIResult, abst, rung, reasons, meta, **detail) -> TypedNumber:
    return TypedNumber(metric=metric, value=r.theta, type="proportion", tier=Tier.GOLD_ANCHORED, panel="trust",
                       rung=rung, n=r.n, n_gold=r.g, n_verified=abst[0], abstention_rate=abst[1],
                       interval=Interval(lo=r.lo, hi=r.hi, level=r.level, method=r.method, B=r.B, seed=r.seed,
                                         fpc=True),
                       estimator_version=ESTIMATOR_VERSION, reasons=list(reasons), **meta,
                       detail={"estimator": estimator, "lambda": r.lam, **detail})


def _relabel(x: TypedNumber, **upd) -> TypedNumber:
    return TypedNumber.model_validate({**x.model_dump(), **upd})


def build_passport(ev: EvidenceBundle, cfg: TrustConfig, *, seed: int) -> TrustPassport:
    meta = {"manifest_ref": ev.manifest_ref, "synthetic": ev.synthetic, "replayed": ev.replayed,
            "config_hash": trust_config_hash(cfg)}
    claims = [u for u in ev.design.units if u.kind == "claim"]
    strata = {u.unit_id: u.stratum for u in claims}
    answers = {v.unit_id: v.answer for v in ev.verdicts}
    f, abstain = predictor_values(answers, ev.claimed, strata)
    n_abst = sum(abstain.values())
    abst = (len(claims) - n_abst, n_abst / len(claims))
    dec = select_tier(ev, cfg)
    n_ca = sum(lab == "cannot_assess" for lab in dec.gold.values())
    kind = "verified_precision" if n_ca else "precision"

    alts: list[TypedNumber] = []
    headline = None
    note = None
    if dec.gold:  # PPI is valid evidence whenever gold passed its checks, even under a KEYED headline
        y_lo = {u: float(lab == ev.claimed[u]) for u, lab in dec.gold.items()}
        y_hi = {u: float(lab == ev.claimed[u] or lab == "cannot_assess") for u, lab in dec.gold.items()}
        p = ppi_mean(ev.design, ev.gold_draw, f, abstain, y_lo, cfg=cfg, seed=seed)
        c = classical_gold_only(ev.design, ev.gold_draw, y_lo, cfg=cfg, seed=seed)
        ratio = (p.hi - p.lo) / (c.hi - c.lo) if c.hi > c.lo else 1.0
        ppi_num = _gold_number(kind, "ppi", p, abst, dec.rung, dec.reasons, meta, width_ratio_vs_classical=ratio)
        if dec.tier == Tier.GOLD_ANCHORED:
            headline = ppi_num
            if ratio >= 1:
                note = f"the verifier did not narrow the interval at n_gold={p.g}"
        else:
            alts.append(ppi_num)
        alts.append(_gold_number("classical_gold_only", "classical", c, abst, dec.rung, [], meta))
        if n_ca:
            u = ppi_mean(ev.design, ev.gold_draw, f, abstain, y_hi, cfg=cfg, seed=seed)
            alts.append(_gold_number(UPPER, "upper", u, abst, dec.rung, ["not in the disagreement check"], meta))

    n_new = len(ev.claimed)
    b0 = baseline_b0(ev.keyed_runs, ev.family, ev.model, ev.harness, ev.toolset, n_new, cfg, meta=meta)
    b1 = baseline_b1([ev.confidences[u] for u in sorted(ev.confidences)], cfg.level, meta=meta)
    b2 = baseline_b2(ev.keyed_runs, ev.model, ev.harness, n_new, cfg, meta=meta)
    if dec.tier == Tier.KEYED:
        headline = _relabel(ev.keyed, metric=kind, panel="trust", rung="L1",
                            detail={**ev.keyed.detail, "estimator": "keyed"})
    elif dec.tier == Tier.MODEL_ESTIMATED:
        headline, b2 = _relabel(b2, metric=kind, reasons=[*dec.reasons, *b2.reasons]), None
    elif dec.tier == Tier.ABSTAINED:
        headline = TypedNumber(metric=kind, value=None, type="proportion", tier=Tier.ABSTAINED, panel="trust",
                               n=len(claims), estimator_version=ESTIMATOR_VERSION, reasons=dec.reasons, **meta)
    alts += [b for b in (b0, b1, b2) if b is not None]

    disagree = disagreements([headline, *alts])
    controls = controls_report(ev.design, ev.verdicts, cfg, gold=ev.gold, seed=seed, meta=meta)
    gate_, gate_reasons = gate(headline, ev.threshold, disagree, controls, cfg)
    regimes = {r.regime for r in ev.keyed_runs if r.family == ev.family and not r.synthetic}
    beat = (f"not computable: {len(regimes)} keyed regime{'s' if len(regimes) != 1 else ''}"
            if len(regimes) < 3 else f"not computed: LORO not built ({len(regimes)} keyed regimes)")
    return TrustPassport(
        estimand=Estimand(name=kind, kind=kind, step_id=ev.step_id, question_id=ev.question_id,
                          population="claim_table"),
        headline=headline, alternatives=alts, n_gold_cannot_assess=n_ca, narrowing_note=note,
        disagreement=disagree, gate=gate_, gate_reasons=gate_reasons, controls=controls, beat_baseline=beat,
        sample_design_id=ev.design.design_id, gold_draw_id=ev.gold_draw.draw_id if ev.gold_draw else None,
        trust_config_hash=meta["config_hash"], estimator_version=ESTIMATOR_VERSION, code_sha=ev.code_sha,
        manifest_ref=ev.manifest_ref, synthetic=ev.synthetic)
