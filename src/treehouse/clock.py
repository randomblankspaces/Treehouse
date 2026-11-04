"""Clocks. Traces take time from a ``Clock`` so replayed runs can use deterministic logical time."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def now_ns(self) -> int: ...


class WallClock:
    """Real time, nanoseconds since the Unix epoch."""

    def now_ns(self) -> int:
        return time.time_ns()


class LogicalClock:
    """Deterministic time: ``start_ns``, then one ``tick_ns`` later on every call."""

    def __init__(self, start_ns: int = 0, tick_ns: int = 1_000_000) -> None:
        if tick_ns <= 0:
            raise ValueError("tick_ns must be positive")
        self._next = start_ns
        self._tick = tick_ns

    def now_ns(self) -> int:
        t = self._next
        self._next += self._tick
        return t


def parse_when(s: str, *, end: bool = False) -> datetime:
    """ISO date or datetime; naive means UTC; a bare date as ``end`` means the end of that day."""
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if len(s) == 10 and end:
        t = t.replace(hour=23, minute=59, second=59)
    return t if t.tzinfo else t.replace(tzinfo=UTC)
