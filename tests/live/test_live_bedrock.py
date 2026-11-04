"""@live twins of the offline P6 tests. Skipped unless TREEHOUSE_LIVE=1 (run in Kiro, never in CI).

K1:  TREEHOUSE_LIVE=1 uv run pytest tests/live -k probe     (at most $3, via the spend ledger)
K3:  TREEHOUSE_LIVE=1 uv run pytest tests/live -k converse  (needs a filled price table, K2a; ~$0.01)
"""

from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.live
REGION = "us-east-1"  # one default everywhere: the price table and registry are us-east-1 (minor 17)


def test_live_probe_k1(tmp_path):
    from treehouse.probe import Probe, default_client_factory
    from treehouse.providers.registry import ModelRegistry
    from treehouse.providers.spend import SpendLedger

    ledger = SpendLedger()
    assert ledger.initialized, f"{ledger.path} missing: run `uv run treehouse budget init` first"
    report = Probe(default_client_factory(REGION), region=REGION, registry=ModelRegistry.load(),
                   ledger=ledger, log_group=None).run()
    assert report.spend.reserved_usd <= 3.0
    assert report.summary["ok"] >= 1
    assert any(m.user_turn_image == "ok" for m in report.models)


def test_live_converse_text_turn_k3():
    from treehouse.providers.bedrock import BedrockConverseProvider
    from treehouse.providers.prices import load_default
    from treehouse.providers.registry import ModelRegistry
    from treehouse.providers.spend import SpendLedger
    from treehouse.schemas.config import InferenceParams
    from treehouse.schemas.model_io import Message, ModelRequest, Text

    reg, prices = ModelRegistry.load(), load_default()
    if not prices.is_priced(reg.get(reg.defaults["worker"]).price_ref):
        pytest.skip("price table is null; run K2a first")
    p = BedrockConverseProvider(None, reg, prices, SpendLedger(prices=prices, registry=reg), REGION)
    req = ModelRequest(model_id=reg.defaults["worker"], system="Be brief.",
                       messages=[Message(role="user", content=[Text(text="Say OK.")])],
                       params=InferenceParams(max_tokens=16))
    r = asyncio.run(p.complete(req, role="worker", trial_index=0, turn=0))
    assert r.cost_usd is not None and r.cost_usd > 0 and r.usage.output_tokens > 0
