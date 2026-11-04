"""Seeded trace and span ids (W3C / OpenTelemetry widths), deterministic for a given seed."""

from __future__ import annotations

import hashlib


class IdSource:
    """The n-th id of each kind is ``sha256("<seed>:<kind>:<n>")`` truncated: stable across machines."""

    def __init__(self, seed: int) -> None:
        self._seed = seed
        self._n = {"trace": 0, "span": 0}

    def _next(self, kind: str, hex_len: int) -> str:
        while True:
            n = self._n[kind]
            self._n[kind] = n + 1
            h = hashlib.sha256(f"{self._seed}:{kind}:{n}".encode()).hexdigest()[:hex_len]
            if int(h, 16):  # all-zero ids are invalid in OpenTelemetry
                return h

    def trace_id(self) -> str:
        return self._next("trace", 32)

    def span_id(self) -> str:
        return self._next("span", 16)
