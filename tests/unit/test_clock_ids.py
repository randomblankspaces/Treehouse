from hypothesis import given
from hypothesis import strategies as st

from treehouse.clock import Clock, LogicalClock, WallClock
from treehouse.ids import IdSource


def test_wall_clock_is_a_clock():
    c = WallClock()
    assert isinstance(c, Clock)
    a, b = c.now_ns(), c.now_ns()
    assert a > 1_600_000_000 * 10**9 and b >= a


@given(st.integers(min_value=0, max_value=2**62), st.integers(min_value=1, max_value=10**9))
def test_logical_clock_is_deterministic(start, tick):
    a, b = LogicalClock(start, tick), LogicalClock(start, tick)
    xs = [a.now_ns() for _ in range(5)]
    assert xs == [b.now_ns() for _ in range(5)]
    assert xs == [start + i * tick for i in range(5)]
    assert isinstance(a, Clock)


def test_logical_clock_default_ticks():
    c = LogicalClock()
    assert [c.now_ns(), c.now_ns()] == [0, 1_000_000]


@given(st.integers(min_value=0, max_value=2**63))
def test_id_source_is_deterministic(seed):
    a, b = IdSource(seed), IdSource(seed)
    ta, sa = [a.trace_id() for _ in range(3)], [a.span_id() for _ in range(3)]
    assert ta == [b.trace_id() for _ in range(3)]
    assert sa == [b.span_id() for _ in range(3)]
    for t in ta:
        assert len(t) == 32 and int(t, 16) != 0
    for s in sa:
        assert len(s) == 16 and int(s, 16) != 0
    assert len(set(ta)) == 3 and len(set(sa)) == 3


def test_id_source_seeds_differ():
    assert IdSource(1).trace_id() != IdSource(2).trace_id()
