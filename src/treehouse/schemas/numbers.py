"""Typed numbers. Every number Treehouse reports is a ``TypedNumber`` carrying its tier and provenance."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from treehouse.schemas.base import Frozen


class Tier(StrEnum):
    KEYED = "KEYED"
    GOLD_ANCHORED = "GOLD-ANCHORED"
    CALIBRATED_TRANSFER = "CALIBRATED-TRANSFER"
    MODEL_ESTIMATED = "MODEL-ESTIMATED"
    ABSTAINED = "ABSTAINED"
    MEASURED = "MEASURED"


NumType = Literal["proportion", "count", "flag", "usd", "seconds", "bytes", "tokens", "ratio", "kappa"]
PanelName = Literal["process", "understanding", "output", "trust", "controls", "cost"]
MEASURED_PANELS = {"process", "understanding", "cost", "controls"}
IntervalMethod = Literal[
    "wilson",
    "clopper-pearson",
    "hypergeom-exact",
    "ppi-2phase-rbs-v1",
    "cluster-bootstrap",
    "betabinom-predictive",
    "poisson-binomial",
    "kappa-bootstrap",
    "rg-bootstrap-inflated-v1",
]

CHIP_LABELS = {
    Tier.KEYED: "Checked",
    Tier.GOLD_ANCHORED: "Estimated from a random check",
    Tier.CALIBRATED_TRANSFER: "Estimated from track record",
    Tier.MODEL_ESTIMATED: "Rough model guess",
    Tier.ABSTAINED: "Not issued",
    Tier.MEASURED: "Measured from trace",
}
BYTES_MODEL_SYNTHETIC = "synthetic-overview-block-v1"
BYTES_MODELS = {BYTES_MODEL_SYNTHETIC, "measured"}
MODELLED_BYTES_CHIP = "modelled bytes"
MODELLED_BYTES_HOVER = "declared overview-block model, not measured"

# Allowed range of ``value`` (and of an interval's endpoints) per number type, and whether it is integral.
TYPE_RANGE: dict[str, tuple[float | None, float | None, bool]] = {
    "proportion": (0.0, 1.0, False),
    "count": (0.0, None, True),
    "flag": (0.0, 1.0, True),
    "usd": (0.0, None, False),
    "seconds": (0.0, None, False),
    "bytes": (0.0, None, True),
    "tokens": (0.0, None, True),
    "ratio": (0.0, None, False),
    "kappa": (-1.0, 1.0, False),
}


class Interval(Frozen):
    lo: float
    hi: float
    level: float
    method: IntervalMethod
    B: int | None = None
    seed: int | None = None
    fpc: bool = False

    @model_validator(mode="after")
    def _ordered(self) -> Interval:
        if self.lo > self.hi:
            raise ValueError("interval lo must be <= hi")
        if not 0 < self.level < 1:
            raise ValueError("interval level must be in (0, 1)")
        return self


class TypedNumber(Frozen):
    """A reported number. ``detail`` may carry e.g. ``key_version``, ``aggregate_over``,
    ``width_ratio_vs_classical`` or ``bytes_model`` (modelled, not measured, bytes)."""

    metric: str
    value: float | None
    type: NumType
    tier: Tier
    panel: PanelName
    rung: Literal["L1", "L2", "L3", "L4"] | None = None
    n: int | None = Field(ge=0)
    n_gold: int | None = Field(default=None, ge=0)
    n_verified: int | None = Field(default=None, ge=0)
    abstention_rate: float | None = Field(default=None, ge=0, le=1)
    interval: Interval | None = None
    estimator_version: str
    config_hash: str | None = None
    manifest_ref: str
    reasons: list[str] = []
    synthetic: bool
    replayed: bool = False
    detail: dict[str, str | int | float | bool] = {}

    @model_validator(mode="after")
    def _rules(self) -> TypedNumber:
        t = self.tier
        if self.value is None:
            abstained = t == Tier.ABSTAINED and self.reasons
            unpriced = t == Tier.MEASURED and "unpriced" in self.reasons
            if not (abstained or unpriced):
                raise ValueError("value may be None only when ABSTAINED with reasons, or MEASURED and unpriced")
        if t == Tier.ABSTAINED and not self.reasons:
            raise ValueError("ABSTAINED requires non-empty reasons")
        if t == Tier.ABSTAINED and self.value is not None:
            raise ValueError("an ABSTAINED number carries no value")
        if t == Tier.KEYED and ("key_version" not in self.detail or self.n is None):
            raise ValueError("KEYED requires detail.key_version and n")
        if t == Tier.GOLD_ANCHORED and (
            self.n_gold is None or self.n_gold < 1 or self.abstention_rate is None or self.interval is None
        ):
            raise ValueError("GOLD-ANCHORED requires n_gold >= 1, abstention_rate and interval")
        if t in (Tier.CALIBRATED_TRANSFER, Tier.MODEL_ESTIMATED) and self.interval is None:
            raise ValueError(f"{t.value} requires interval")
        if t == Tier.MEASURED:
            if self.panel not in MEASURED_PANELS:
                raise ValueError("MEASURED numbers belong only to process, understanding, cost or controls")
            if self.interval is not None and "aggregate_over" not in self.detail:
                raise ValueError("a MEASURED interval requires detail.aggregate_over")
        lo, hi, integral = TYPE_RANGE[self.type]
        if self.value is not None:
            if (lo is not None and self.value < lo) or (hi is not None and self.value > hi):
                raise ValueError(f"a {self.type} must lie in [{lo}, {hi if hi is not None else 'inf'}]")
            if integral and not float(self.value).is_integer():
                raise ValueError(f"a {self.type} must be integral")
            if self.type == "flag" and self.value not in (0, 1):
                raise ValueError("a flag is 0 or 1")
        if self.interval is not None and (
            (lo is not None and self.interval.lo < lo) or (hi is not None and self.interval.hi > hi)
        ):
            raise ValueError(f"the interval of a {self.type} must lie within its range")
        bm = self.detail.get("bytes_model")
        if bm is not None and bm not in BYTES_MODELS:
            raise ValueError(f"detail.bytes_model must be one of {sorted(BYTES_MODELS)}")
        return self

    @property
    def modelled_bytes(self) -> bool:
        return self.detail.get("bytes_model") == BYTES_MODEL_SYNTHETIC

    def chip(self) -> str:
        """Plain-English chip, e.g. "Measured from trace · SYNTHETIC · modelled bytes"."""
        parts = [CHIP_LABELS[self.tier]]
        if self.synthetic:
            parts.append("SYNTHETIC")
        if self.replayed:
            parts.append("recorded")
        if self.modelled_bytes:
            parts.append(MODELLED_BYTES_CHIP)
        return " · ".join(parts)

    def chip_hover(self) -> str | None:
        """Hover text for the chip, or None (RS-B1: modelled bytes are declared, not measured)."""
        return MODELLED_BYTES_HOVER if self.modelled_bytes else None
