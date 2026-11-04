"""Verifier verdicts and gold labels."""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime

from treehouse.schemas.base import Frozen

Answer = Literal["yes", "no", "cannot_assess"]


class VerifierVerdict(Frozen):
    unit_id: str
    question_id: Literal["exists", "damaged"]
    answer: Answer
    verifier_config_hash: str
    request_hash: str
    span_ref: str | None = None
    recorded: bool
    synthetic: bool
    created_seq: int


class GoldLabel(Frozen):
    """A human ``cannot_assess`` counts as y=0 for precision and is reported as a count."""

    unit_id: str
    question_id: Literal["exists", "damaged"]
    label: Answer
    labeller: str
    labeller_kind: Literal["human", "synthetic"]
    blind_protocol_hash: str
    ts: AwareDatetime
    sealed_ref: str
    is_relabel: bool = False
    synthetic: bool
