"""Report bundle: everything the HTML report renders, in one record.

The manifest and the card enter as text-only summaries; any number the report shows about them goes in
``facts`` as a ``TypedNumber`` (I6). ``evidence`` holds the WindowResult rows behind the claims, each with
its own ``synthetic`` flag, so every evidence row can carry its chip (I5).
"""

from __future__ import annotations

from typing import Literal

from treehouse.schemas.base import Frozen
from treehouse.schemas.checks import CheckLedger
from treehouse.schemas.claims import Claim, UnderstandingStatement
from treehouse.schemas.numbers import TypedNumber
from treehouse.schemas.passport import TrustPassport
from treehouse.schemas.scorecard import Scorecard
from treehouse.schemas.tools import WindowResult
from treehouse.schemas.trace import SpanRecord


class SummaryLint(Frozen):
    ok: bool
    errors: list[str] = []


class ManifestSummary(Frozen):
    """Text-only view of the manifest. Numbers (bytes, cost, counts) belong in ``ReportBundle.facts``."""

    run_id: str
    mode: Literal["fake", "replay", "record", "live"]
    task_ref: str
    backends: dict[str, str] = {}  # slot -> backend that ran
    key_isolation_statement: str
    license_floor: str
    license_obligations: list[str] = []
    nc_notice: str | None = None


class StepSummary(Frozen):
    step_id: str
    question_id: Literal["exists", "damaged"]
    keying_mode: Literal["keyed", "partly_keyed", "unkeyed"]
    completeness_caveat: str | None = None


class CardSummary(Frozen):
    """Text-only view of the task card the report shows."""

    id: str
    version: str
    title: str
    goal: str
    synthetic_notice: str | None = None
    license_floor: str
    license_obligations: list[str] = []
    steps: list[StepSummary] = []
    must_notice: list[str] = []  # NoticeItem ids
    known_limits: list[str] = []


class ReportBundle(Frozen):
    schema_version: Literal["treehouse.bundle/1"] = "treehouse.bundle/1"
    manifest_ref: str
    manifest_summary: ManifestSummary
    card_ref: str
    card_summary: CardSummary
    scorecard: Scorecard
    passports: list[TrustPassport] = []
    understanding: list[UnderstandingStatement] = []
    claims: list[Claim] = []
    evidence: list[WindowResult] = []
    ledgers: list[CheckLedger] = []
    trace_rows: list[SpanRecord] = []
    evidence: list[WindowResult] = []  # cited windows (metadata only, never pixels)
    facts: dict[str, TypedNumber] = {}
    summary: str
    lint: SummaryLint
    synthetic: bool
