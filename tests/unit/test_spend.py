"""SpendLedger (§3, AWS-B1): thresholds, unpriced refusal, persistence, and the $450 property."""

from __future__ import annotations

import tempfile
import warnings
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from treehouse.paths import repo_root
from treehouse.providers.prices import Price, PriceTable, load_default, load_fixture, load_probe_ceiling
from treehouse.providers.spend import (
    BudgetAlarm,
    BudgetHardStop,
    SpendLedger,
    SpendWarning,
    UnpricedModel,
    default_ledger_path,
)
from treehouse.schemas.model_io import Usage

BIG = PriceTable(version="big-test", region="any", synthetic=True,
                 models={"m": Price(input=1.0, output=5.0)})  # $1 / $5 per 1k tokens

def new_ledger(*a, **kw):
    """A test ledger: synthetic tables allowed, genesis written (B1: reserve refuses an un-initialised file)."""
    kw.setdefault("allow_synthetic", True)
    led = SpendLedger(*a, **kw)
    if not led.initialized:
        led.init(note="test")
    return led



def test_default_path_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TREEHOUSE_SPEND_LEDGER", str(tmp_path / "x.jsonl"))
    assert default_ledger_path() == tmp_path / "x.jsonl"
    monkeypatch.delenv("TREEHOUSE_SPEND_LEDGER")
    # B1: inside a checkout the default is the repo's committed .spend/spend.jsonl
    assert default_ledger_path() == repo_root() / ".spend" / "spend.jsonl"
    monkeypatch.setenv("TREEHOUSE_SPEND_LEDGER", "rel/x.jsonl")
    assert default_ledger_path().is_absolute()  # a relative env path is resolved once, not per cwd


def test_worst_case_and_commit(tmp_path):
    led = new_ledger(tmp_path / "s.jsonl", prices=load_fixture())
    r = led.reserve("claude-sonnet-5-5", 1000, 100)
    assert r.worst_usd == pytest.approx((1000 * 0.003 + 100 * 0.015) / 1000)
    assert led.status().reserved_usd == pytest.approx(r.worst_usd)
    usd = led.commit(r, Usage(input_tokens=500, output_tokens=10))
    st_ = led.status()
    assert usd == pytest.approx((500 * 0.003 + 10 * 0.015) / 1000)
    assert st_.spent_usd == pytest.approx(usd) and st_.reserved_usd == 0 and st_.estimated_usd == 0


def test_thresholds(tmp_path):
    led = new_ledger(tmp_path / "s.jsonl", prices=BIG)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        led.commit(led.reserve("m", 0, 50_000), Usage(input_tokens=0, output_tokens=50_000))  # $250
    assert led.status().level == "ok"
    with pytest.warns(SpendWarning):
        led.commit(led.reserve("m", 0, 10_000), Usage(input_tokens=0, output_tokens=10_000))  # $300
    assert led.status().level == "over_planned"
    with pytest.raises(BudgetAlarm):
        led.reserve("m", 0, 12_000)  # -> $360
    with pytest.raises(BudgetAlarm):
        led.reserve("m", 0, 12_000, allow_over_alarm=True)  # flag without reason
    with pytest.warns(SpendWarning):
        r = led.reserve("m", 0, 12_000, allow_over_alarm=True, reason="K4 Nepal run approved")
    assert led.status().over_alarm_reasons == ["K4 Nepal run approved"]
    led.commit(r, Usage(input_tokens=0, output_tokens=12_000))
    with pytest.raises(BudgetHardStop):
        led.reserve("m", 0, 20_000, allow_over_alarm=True, reason="x")  # -> $460
    assert led.status().level == "over_alarm"


def test_unpriced_refused_unless_capped(tmp_path):
    led = new_ledger(tmp_path / "s.jsonl", prices=load_default())
    with pytest.raises(UnpricedModel):
        led.reserve("nova-pro", 10, 10)
    r = led.reserve("nova-pro", 10, 32, unpriced_cap_usd=0.25)
    assert r.unpriced and r.worst_usd == 0.25
    usd = led.commit(r, Usage(input_tokens=100, output_tokens=32), price_override=load_probe_ceiling())
    assert usd == pytest.approx((100 * 0.05 + 32 * 0.25) / 1000)
    st_ = led.status()
    assert st_.estimated_usd == pytest.approx(usd) and st_.spent_usd == pytest.approx(usd)
    r2 = led.reserve("nova-pro", 10, 32, unpriced_cap_usd=0.25)
    assert led.commit(r2, Usage(input_tokens=1, output_tokens=1)) == 0.25  # no override: the cap is committed


def test_persists_across_instances_and_release(tmp_path):
    p = tmp_path / "s.jsonl"
    a = new_ledger(p, prices=load_fixture())
    r = a.reserve("nova-pro", 1000, 1000)
    b = new_ledger(p, prices=load_fixture())
    assert b.status().reserved_usd == pytest.approx(r.worst_usd) and b.status().open_reservations == [r.id]
    b.release(r, "failed")
    assert a.status().reserved_usd == 0


ops = st.lists(st.tuples(st.integers(0, 40_000), st.integers(0, 40_000), st.floats(0, 1), st.floats(0, 1),
                         st.booleans()), min_size=1, max_size=40)


@settings(max_examples=60, deadline=None)
@given(ops)
def test_property_never_passes_hard_stop(seq):
    """Whatever the sequence of reserves and commits (usage within the reservation), spent never passes $450,
    and a reserve is refused exactly when spent + reserved + worst case would."""
    with tempfile.TemporaryDirectory() as d, warnings.catch_warnings():
        warnings.simplefilter("ignore", SpendWarning)
        led = new_ledger(Path(d) / "s.jsonl", prices=BIG)
        for est, mx, fin, fout, release in seq:
            before = led.status()
            worst = (est * 1.0 + mx * 5.0) / 1000
            try:
                r = led.reserve("m", est, mx, allow_over_alarm=True, reason="property")
            except BudgetHardStop:
                assert before.total_usd + worst > 450 - 1e-6
                continue
            assert before.total_usd + worst <= 450 + 1e-6
            if release:
                led.release(r)
            else:
                led.commit(r, Usage(input_tokens=int(est * fin), output_tokens=int(mx * fout)))
            now = led.status()
            assert now.spent_usd <= 450 + 1e-6 and now.total_usd <= 450 + 1e-6
