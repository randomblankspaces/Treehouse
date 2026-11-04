"""Per-claim check results and the resolved ledger."""

from __future__ import annotations

from typing import Literal

from treehouse.schemas.base import Frozen


class CheckResult(Frozen):
    claim_id: str
    layer: Literal["rules", "key", "verifier", "human", "overlap", "leak"]
    check_id: str
    version: str
    result: Literal["pass", "fail", "flag", "n/a"]
    code: str | None = None
    detail: dict[str, str | int | float | bool] = {}
    record_ref: str | None = None


class CheckLedger(Frozen):
    """Resolution order: rule fail > human > key > verifier > unchecked."""

    claim_id: str
    results: list[CheckResult]
    resolved: Literal[
        "correct", "incorrect", "fabrication", "ungrounded", "contaminated", "to_adjudicate", "unchecked"
    ]
    resolved_by: str | None = None
