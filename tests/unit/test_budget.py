"""BudgetGuard: reserve/commit on usd, tool_calls, bytes, tokens and wall seconds; 50/80/100 % events."""

from __future__ import annotations

import pytest

from treehouse.clock import LogicalClock
from treehouse.gateway.budget import BudgetExceeded, BudgetGuard
from treehouse.schemas.config import Budget


def test_reserve_counts_against_limit_and_names_axis():
    g = BudgetGuard(Budget(tool_calls=2))
    r1 = g.reserve(tool_calls=1)
    g.reserve(tool_calls=1)
    with pytest.raises(BudgetExceeded) as e:
        g.reserve(tool_calls=1)
    assert e.value.limit == "tool_calls" and "tool_calls" in str(e.value)
    g.release(r1)
    g.reserve(tool_calls=1)


def test_commit_uses_actuals_and_check_stops_when_exhausted():
    g = BudgetGuard(Budget(tokens=100, usd=1.0))
    r = g.reserve(tokens=50, usd=0.5)
    g.commit(r, tokens=120, usd=0.1)  # actuals may overshoot; commit never raises
    assert g.spent["tokens"] == 120 and g.remaining("usd") == pytest.approx(0.9)
    with pytest.raises(BudgetExceeded) as e:
        g.check()
    assert e.value.limit == "tokens"


def test_threshold_events_fire_once_each():
    seen = []
    g = BudgetGuard(Budget(bytes=100), on_event=lambda name, attrs: seen.append((name, attrs["axis"], attrs["pct"])))
    for _ in range(4):
        g.commit(None, bytes=30)
    assert [p for _, _, p in seen] == [50, 80, 100]
    assert {a for _, a, _ in seen} == {"bytes"} and seen[0][0] == "treehouse.budget.threshold"
    assert [e["pct"] for e in g.events] == [50, 80, 100]


def test_wall_clock_limit():
    g = BudgetGuard(Budget(wall_s=2.5), clock=LogicalClock(tick_ns=1_000_000_000))
    g.check()  # t=1s
    g.check()  # t=2s
    with pytest.raises(BudgetExceeded) as e:
        g.check()
    assert e.value.limit == "wall_s"


def test_disabled_guard_never_limits():
    g = BudgetGuard(Budget(enabled=False, tokens=1, tool_calls=0, usd=0.0, wall_s=0.0))
    for _ in range(5):
        g.commit(g.reserve(tokens=10, tool_calls=1, usd=1.0))
        g.check()
    assert g.events == [] and g.remaining("tokens") is None


def test_no_limit_axis_is_unbounded():
    g = BudgetGuard(Budget(usd=1.0))
    g.commit(g.reserve(tokens=10**9, bytes=10**12))
    g.check()
    assert g.remaining("tokens") is None
