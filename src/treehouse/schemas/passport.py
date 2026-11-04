"""Trust passport: the derived trust panel for one estimand."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from treehouse.schemas.base import Frozen
from treehouse.schemas.numbers import Tier, TypedNumber


class Estimand(Frozen):
    """``verified_precision`` is the trust headline: a lower bound on precision, since a claim
    nobody could verify never counts as correct."""

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
    schema_version: Literal["treehouse.passport/1"] = "treehouse.passport/1"
    estimand: Estimand
    headline: TypedNumber
    alternatives: list[TypedNumber] = []  # classical gold-only, B0, B1 "agent's claim", B2, RG
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
        if self.headline.tier == Tier.GOLD_ANCHORED and "width_ratio_vs_classical" not in self.headline.detail:
            raise ValueError("a GOLD-ANCHORED headline carries detail.width_ratio_vs_classical")
        return self
