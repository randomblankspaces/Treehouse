"""Evidence bundle, tier ladder, disagreement rule and gate (IMPLEMENTATION-DESIGN §3)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import combinations

from treehouse.schemas.config import TrustConfig
from treehouse.schemas.numbers import Tier, TypedNumber
from treehouse.schemas.passport import ControlsReport
from treehouse.schemas.sampling import GoldDraw, SampleDesign
from treehouse.schemas.verdicts import GoldLabel, VerifierVerdict
from treehouse.trust.adjudication import ADJ_PREFIX
from treehouse.trust.baselines import KeyedRun

DISAGREE_SET = {"keyed", "ppi", "classical", "b2", "b0"}  # B1 and the upper bound never enter the check
DISAGREE_REASON = "estimators disagree: treat as unverified"


@dataclass(frozen=True)
class EvidenceBundle:
    """Everything the trust engine reads for one estimand, already loaded by ``service``.
    ``claimed``: claim unit id -> the worker's answer to the step question (yes/no/cannot_assess)."""

    step_id: str
    question_id: str
    design: SampleDesign
    claimed: dict[str, str]
    verdicts: Sequence[VerifierVerdict]
    family: str
    model: str
    harness: str
    toolset: str
    threshold: float  # card.thresholds.rely_lo
    manifest_ref: str
    synthetic: bool
    replayed: bool = False
    gold_draw: GoldDraw | None = None
    gold: Sequence[GoldLabel] = ()
    confidences: dict[str, float] = field(default_factory=dict)
    keyed: TypedNumber | None = None  # a KEYED number whose key covers the estimand
    keyed_runs: Sequence[KeyedRun] = ()
    same_family_verifier: bool = False
    code_sha: str = "unknown"


@dataclass(frozen=True)
class TierDecision:
    tier: Tier
    rung: str | None
    reasons: list[str]
    gold: dict[str, str]  # accepted gold: unit id -> label (empty unless gold passed every check)


def accepted_gold(ev: EvidenceBundle) -> tuple[dict[str, str], list[str]]:
    """First-pass labels that belong to the committed draw. Adjudication-queue labels are never PPI gold."""
    drawn = set(ev.gold_draw.unit_ids) if ev.gold_draw else set()
    ok, reasons = {}, []
    for lab in ev.gold:
        if lab.is_relabel:
            continue
        r = ("adjudication-gold-refused" if lab.sealed_ref.startswith(ADJ_PREFIX)
             else "gold-not-in-draw" if lab.unit_id not in drawn else None)
        if r:
            reasons += [r] if r not in reasons else []
        else:
            ok[lab.unit_id] = lab.label
    return ok, reasons


def select_tier(ev: EvidenceBundle, cfg: TrustConfig) -> TierDecision:
    gold, reasons = accepted_gold(ev)
    if gold and not all(ev.gold_draw.committed_seq < v.created_seq for v in ev.verdicts):
        gold, reasons = {}, [*reasons, "gold-not-precommitted"]
    if gold and not all(lab.blind_protocol_hash for lab in ev.gold if lab.unit_id in gold):
        gold, reasons = {}, [*reasons, "no-blind-protocol"]
    if ev.keyed is not None:
        return TierDecision(Tier.KEYED, "L1", reasons, gold)
    if gold:
        if len(gold) < ev.gold_draw.n_gold:
            reasons.append(f"gold-incomplete: {len(gold)} of {ev.gold_draw.n_gold} labelled")
        if len(gold) < cfg.g_min_label:
            reasons.append("anecdotal")
        return TierDecision(Tier.GOLD_ANCHORED, "L2" if ev.same_family_verifier else "L3", reasons, gold)
    # CALIBRATED-TRANSFER (Rogan-Gladen) is W4 and not built.
    if any(r.family == ev.family and not r.synthetic for r in ev.keyed_runs):
        return TierDecision(Tier.MODEL_ESTIMATED, None, reasons, {})
    return TierDecision(Tier.ABSTAINED, None, [*reasons, f"no gold and no keyed runs for family {ev.family}"], {})


def disagreements(nums: Sequence[TypedNumber]) -> list[tuple[str, str]]:
    xs = [x for x in nums if x.interval is not None and x.detail.get("estimator") in DISAGREE_SET]
    return [(a.metric, b.metric) for a, b in combinations(xs, 2)
            if a.interval.hi < b.interval.lo or b.interval.hi < a.interval.lo]


def gate(headline: TypedNumber, threshold: float, disagree: Sequence, controls: ControlsReport,
         cfg: TrustConfig) -> tuple[str, list[str]]:
    """Rely needs KEYED or GOLD-ANCHORED, lo >= threshold, no disagreement, abstention <= max and a placebo
    false-alarm upper bound <= max where measured. Spot-check needs hi >= threshold."""
    if headline.value is None:
        return "Do not rely", ["no estimate issued"]
    if disagree:
        return "Do not rely", [DISAGREE_REASON]
    lo, hi = (headline.interval.lo, headline.interval.hi) if headline.interval else (headline.value,) * 2
    reasons = []
    if headline.tier not in (Tier.KEYED, Tier.GOLD_ANCHORED):
        reasons.append(f"tier {headline.tier.value} cannot be relied on")
    if lo < threshold:
        reasons.append("lower bound below threshold")
    if (headline.abstention_rate or 0.0) > cfg.max_abstention_for_rely:
        reasons.append("abstention above maximum")
    if controls.placebo_far is not None and controls.placebo_far.interval.hi > cfg.placebo_far_max:
        reasons.append("verifier-fails-placebo")
    if not reasons:
        return "Rely", []
    return ("Spot-check" if hi >= threshold else "Do not rely"), reasons
