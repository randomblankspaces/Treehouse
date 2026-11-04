"""Meter: per-tool counts, statuses, bytes and latency for the cost panel and the span attributes."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field


@dataclass
class Meter:
    calls: Counter = field(default_factory=Counter)
    statuses: Counter = field(default_factory=Counter)
    bytes_read: defaultdict = field(default_factory=lambda: defaultdict(int))
    latency_ms: defaultdict = field(default_factory=lambda: defaultdict(int))

    def record(self, tool: str, status: str, *, bytes_read: int = 0, latency_ms: int = 0) -> None:
        self.calls[tool] += 1
        self.statuses[status] += 1
        self.bytes_read[tool] += bytes_read
        self.latency_ms[tool] += latency_ms

    @property
    def total_bytes(self) -> int:
        return sum(self.bytes_read.values())

    def summary(self) -> dict:
        return {"calls": dict(sorted(self.calls.items())), "statuses": dict(sorted(self.statuses.items())),
                "bytes_read": dict(sorted(self.bytes_read.items())), "total_bytes": self.total_bytes}
