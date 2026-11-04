"""Harness protocol and result. Claims are recorded by the gateway's claims tools, never by a harness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

Stop = Literal["completed", "max_turns", "budget", "error"]


@dataclass(frozen=True)
class HarnessResult:
    final_text: str
    stop: Stop
    turns: int
    detail: str | None = None  # e.g. which budget limit was hit


class Harness(Protocol):
    name: str
    version: str

    async def run(
        self,
        *,
        system: str,
        user: str,
        provider: Any,
        gateway: Any,
        tracer: Any,
        budget: Any,
        max_turns: int,
        role: str,
        trial_index: int,
    ) -> HarnessResult: ...
