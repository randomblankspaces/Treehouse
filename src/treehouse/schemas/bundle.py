"""Report bundle: everything the HTML report renders, in one record."""

from __future__ import annotations

from typing import Literal

from treehouse.schemas.base import Frozen
from treehouse.schemas.checks import CheckLedger
from treehouse.schemas.claims import Claim
from treehouse.schemas.numbers import TypedNumber
from treehouse.schemas.passport import TrustPassport
from treehouse.schemas.scorecard import Scorecard
from treehouse.schemas.trace import SpanRecord


class SummaryLint(Frozen):
    ok: bool
    errors: list[str] = []


class ReportBundle(Frozen):
    schema_version: Literal["treehouse.bundle/1"] = "treehouse.bundle/1"
    manifest_ref: str
    manifest_summary: dict[str, str]
    card_ref: str
    card_summary: dict[str, str]  # title, goal, synthetic_notice, license floor
    scorecard: Scorecard
    passports: list[TrustPassport] = []
    claims: list[Claim] = []
    ledgers: list[CheckLedger] = []
    trace_rows: list[SpanRecord] = []
    facts: dict[str, TypedNumber] = {}
    summary: str
    lint: SummaryLint
    synthetic: bool
