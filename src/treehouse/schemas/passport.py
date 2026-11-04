"""Trust passport: the derived trust panel for one estimand."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from treehouse.schemas.base import Frozen
from treehouse.schemas.numbers import Tier, TypedNumber


class Estimand(Frozen):
    """``verified_precision`` is the trust headline whenever any gold label is ``cannot_assess``: a lower
    bound on precision, since a claim nobody could verify never counts as correct. ``precision`` is used
    only when ``n_gold_cannot_assess == 0`` (the passport validator enforces both directions)."""

    name: str
    kind: Literal["precision", "verified_precision", "count", "miss_rate"]
    step_id: str
    question_id: Literal["exists", "damaged"]
    population: Literal["claim_table", "unreported_frame"]


class ControlsReport(Frozen):
    se: TypedNumber | None = None
    sp: TypedNumber | None = None
    placebo_far: TypedNumber | None = None
    retest_kappa: TypedNumber | None = None
    relabel_kappa: TypedNumber | None = None
    unavailable: list[str] = []


class TrustPassport(Frozen):
    """The trust panel for one estimand.

    Container fence (§2): ``headline``, ``alternatives`` and ``truth_reveal`` are trust-panel numbers and
    are never MEASURED; every ``controls`` number sits on the controls panel. ``narrowing_note`` is plain
    text rendered inside the headline's chip element; any count it mentions repeats ``headline.n_gold``.
    Golden comparisons use ``canon.stable_view`` (``code_sha`` and ``manifest_ref`` are volatile)."""

    schema_version: Literal["treehouse.passport/1"] = "treehouse.passport/1"
    estimand: Estimand
    headline: TypedNumber
    alternatives: list[TypedNumber] = []  # classical gold-only, B0, B1 "agent's claim", B2, RG,
    # precision_upper_if_unassessable_correct (y=1; not in the disagreement check)
    n_gold_cannot_assess: int = Field(ge=0)
    narrowing_note: str | None = None  # "the verifier did not narrow the interval at n_gold=k"
    disagreement: list[tuple[str, str]] = []
    gate: Literal["Rely", "Spot-check", "Do not rely"]
    gate_reasons: list[str] = []
    controls: ControlsReport
    shift: dict[str, TypedNumber] = {}
    beat_baseline: str
    process_facts: dict[str, TypedNumber] = {}
    truth_reveal: TypedNumber | None = None
    sample_design_id: str
    gold_draw_id: str | None = None
    trust_config_hash: str
    estimator_version: str
    code_sha: str
    manifest_ref: str
    synthetic: bool

    @model_validator(mode="after")
    def _rules(self) -> TrustPassport:
        if self.truth_reveal is not None and not self.synthetic:
            raise ValueError("truth_reveal exists only for synthetic tasks")
        h = self.headline
        if h.tier == Tier.GOLD_ANCHORED and "width_ratio_vs_classical" not in h.detail:
            raise ValueError("headline: a GOLD-ANCHORED headline carries detail.width_ratio_vs_classical")
        for where, x in [("headline", h), *((f"alternatives.{i}", a) for i, a in enumerate(self.alternatives)),
                         ("truth_reveal", self.truth_reveal)]:
            if x is not None and (x.panel != "trust" or x.tier == Tier.MEASURED):
                raise ValueError(f"{where}: a passport number sits on the trust panel and is never MEASURED")
        for name in ("se", "sp", "placebo_far", "retest_kappa", "relabel_kappa"):
            x = getattr(self.controls, name)
            if x is not None and x.panel != "controls":
                raise ValueError(f"controls.{name}: a control number sits on the controls panel")
        k, n_ca = self.estimand.kind, self.n_gold_cannot_assess
        if k == "precision" and n_ca > 0:
            raise ValueError("estimand.kind: 'precision' requires n_gold_cannot_assess == 0; use 'verified_precision'")
        if k == "verified_precision" and n_ca == 0:
            raise ValueError("estimand.kind: 'verified_precision' is used only when some gold label is cannot_assess")
        if h.n_gold is not None and n_ca > h.n_gold:
            raise ValueError("n_gold_cannot_assess: cannot exceed headline.n_gold")
        ratio = h.detail.get("width_ratio_vs_classical")
        if isinstance(ratio, int | float) and not isinstance(ratio, bool) and ratio >= 1 and not self.narrowing_note:
            raise ValueError("narrowing_note: required when headline width_ratio_vs_classical >= 1")
        return self
