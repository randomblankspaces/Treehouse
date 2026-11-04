"""Score panels. There is deliberately no composite score field."""

from __future__ import annotations

from typing import Literal

from treehouse.schemas.base import Frozen
from treehouse.schemas.numbers import PanelName, TypedNumber


class Panel(Frozen):
    name: PanelName
    version: str
    numbers: dict[str, TypedNumber] = {}
    evidence_span_ids: dict[str, list[str]] = {}
    no_grade_reason: str | None = None


class Scorecard(Frozen):
    schema_version: Literal["treehouse.scorecard/1"] = "treehouse.scorecard/1"
    run_ref: str
    process: Panel
    understanding: Panel
    output: Panel
    cost: Panel
    trust_ref: str | None = None
    versions: dict[str, str] = {}
