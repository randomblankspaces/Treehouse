"""Score panels. There is deliberately no composite score field."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from treehouse.schemas.base import Frozen
from treehouse.schemas.numbers import PanelName, Tier, TypedNumber


class Panel(Frozen):
    """A score panel. Every number in it belongs to it (``number.panel == name``); output and trust
    panels never hold MEASURED numbers (the container half of the MEASURED fence)."""

    name: PanelName
    version: str
    numbers: dict[str, TypedNumber] = {}
    evidence_span_ids: dict[str, list[str]] = {}
    no_grade_reason: str | None = None

    @model_validator(mode="after")
    def _fence(self) -> Panel:
        for key, x in self.numbers.items():
            if x.panel != self.name:
                raise ValueError(f"numbers.{key}: number on panel {x.panel!r} inside panel {self.name!r}")
            if self.name in ("output", "trust") and x.tier == Tier.MEASURED:
                raise ValueError(f"numbers.{key}: MEASURED numbers never sit on the {self.name} panel")
        return self


class Scorecard(Frozen):
    schema_version: Literal["treehouse.scorecard/1"] = "treehouse.scorecard/1"
    run_ref: str
    process: Panel
    understanding: Panel
    output: Panel
    cost: Panel
    trust_ref: str | None = None
    versions: dict[str, str] = {}

    @model_validator(mode="after")
    def _slots(self) -> Scorecard:
        for slot in ("process", "understanding", "output", "cost"):
            if getattr(self, slot).name != slot:
                raise ValueError(f"{slot}: panel in the {slot} slot is named {getattr(self, slot).name!r}")
        return self
