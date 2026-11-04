"""BudgetGuard: per-run limits on usd, tool calls, bytes, tokens and wall seconds.

``reserve()`` refuses (``BudgetExceeded``) when spent + reserved + the request would pass a limit;
``commit()`` records actual use (it never raises; overshoot makes the next ``check()`` fail).
Threshold events fire once per axis at 50, 80 and 100 % of a limit. ``Budget.enabled=False``
removes every limit and every event. The run-wide dollar ceiling lives in ``providers/spend.py`` (P6).
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from treehouse.clock import Clock, WallClock
from treehouse.schemas.config import Budget

AXES = ("usd", "tool_calls", "bytes", "tokens")
THRESHOLDS = (50, 80, 100)


class BudgetExceeded(RuntimeError):
    def __init__(self, limit: str, limit_value: float, attempted: float) -> None:
        self.limit, self.limit_value, self.attempted = limit, limit_value, attempted
        super().__init__(f"budget limit {limit}={limit_value} would be exceeded ({attempted})")


@dataclass(frozen=True)
class Reservation:
    id: int
    amounts: dict[str, float] = field(default_factory=dict)


class BudgetGuard:
    def __init__(
        self,
        budget: Budget,
        *,
        clock: Clock | None = None,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.budget = budget
        self.clock = clock or WallClock()
        self.on_event = on_event
        self.start_ns = self.clock.now_ns()
        self.spent: dict[str, float] = dict.fromkeys(AXES, 0)
        self.events: list[dict[str, Any]] = []
        self._open: dict[int, Reservation] = {}
        self._ids = itertools.count()
        self._fired: set[tuple[str, int]] = set()

    def limit(self, axis: str) -> float | None:
        return getattr(self.budget, axis) if self.budget.enabled else None

    def _reserved(self, axis: str) -> float:
        return sum(r.amounts.get(axis, 0) for r in self._open.values())

    def remaining(self, axis: str) -> float | None:
        lim = self.limit(axis)
        return None if lim is None else lim - self.spent[axis] - self._reserved(axis)

    def _check_wall(self) -> None:
        lim = self.limit("wall_s")
        if lim is not None:
            elapsed = (self.clock.now_ns() - self.start_ns) / 1e9
            if elapsed > lim:
                raise BudgetExceeded("wall_s", lim, elapsed)

    def check(self) -> None:
        """Raise if any axis is used up or the wall-clock limit has passed."""
        self._check_wall()
        for axis in AXES:
            lim = self.limit(axis)
            if lim is not None and self.spent[axis] >= lim:
                raise BudgetExceeded(axis, lim, self.spent[axis])

    def reserve(self, **amounts: float) -> Reservation:
        unknown = set(amounts) - set(AXES)
        if unknown:
            raise ValueError(f"unknown budget axes {sorted(unknown)}")
        self._check_wall()
        for axis, amt in amounts.items():
            lim = self.limit(axis)
            if lim is not None and self.spent[axis] + self._reserved(axis) + amt > lim:
                raise BudgetExceeded(axis, lim, self.spent[axis] + self._reserved(axis) + amt)
        r = Reservation(next(self._ids), dict(amounts))
        self._open[r.id] = r
        return r

    def release(self, reservation: Reservation) -> None:
        self._open.pop(reservation.id, None)

    def commit(self, reservation: Reservation | None, **actual: float) -> None:
        """Record actual use. Axes not given default to the reserved amounts. Never raises on overshoot."""
        unknown = set(actual) - set(AXES)
        if unknown:
            raise ValueError(f"unknown budget axes {sorted(unknown)}")
        amounts = dict(reservation.amounts) if reservation else {}
        amounts.update(actual)
        if reservation:
            self.release(reservation)
        for axis, amt in amounts.items():
            self.spent[axis] += amt
            self._maybe_fire(axis)

    def _maybe_fire(self, axis: str) -> None:
        lim = self.limit(axis)
        if not lim:
            return
        pct_used = 100 * self.spent[axis] / lim
        for pct in THRESHOLDS:
            if pct_used >= pct and (axis, pct) not in self._fired:
                self._fired.add((axis, pct))
                attrs = {"axis": axis, "pct": pct, "spent": self.spent[axis], "limit": lim}
                self.events.append({"name": "treehouse.budget.threshold", **attrs})
                if self.on_event:
                    self.on_event("treehouse.budget.threshold", attrs)
