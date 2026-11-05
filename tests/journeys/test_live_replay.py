"""The committed live runs replay offline from their pixel-free cassettes (MVP-PLAN §8, Req 10.1).

No network or AWS: the worker's Bedrock responses come from the cassette; tools run in-process on the committed
fixtures. The replayed claims must equal the claims sealed during the live run.
"""
from __future__ import annotations

import json

import pytest

from treehouse.cards import load_card
from treehouse.investigation import run_investigation
from treehouse.paths import repo_root
from treehouse.providers.cassette import Cassette, ReplayProvider
from treehouse.schemas.config import RunConfig
from treehouse.store.local import LocalStore
from treehouse.store.verify import verify

ROOT = repo_root()
LIVE = ROOT / "fixtures/live"
# Task 4/5 runs (fixtures/live/runs) were recorded before the classify tool schema changed in task 5, so their
# requests no longer match current code; they are kept as sealed evidence, not replay fixtures.
CASES = [  # (run id, card, config, sealed-run evidence dir)
    ("exp-nagoya-sonnet-1", "t1-nagoya-warehouses", "t1-nagoya-sonnet-strands", LIVE / "experiments/runs"),
    ("exp-gifu-sonnet-1", "t5-gifu-warehouses", "t5-gifu-sonnet-strands", LIVE / "experiments/runs"),
    ("exp-bangladesh-sonnet-1", "t1-bangladesh-warehouses", "t1-bangladesh-sonnet-strands",
     LIVE / "experiments/runs"),
]


def _claims(lines: str) -> list[tuple]:
    rows = [json.loads(line) for line in lines.splitlines() if line.strip()]
    return [(c["cls"], c["status"], tuple(c["geometry"]["coordinates"]), c["confidence"]) for c in rows]


@pytest.mark.parametrize("run_id,card_id,config_id,evidence", CASES, ids=[c[0] for c in CASES])
def test_live_run_replays_offline_with_identical_claims(tmp_path, run_id, card_id, config_id, evidence):
    card = load_card(ROOT / "tasks" / f"{card_id}.yaml")
    live = RunConfig.model_validate_json((LIVE / "configs" / f"{config_id}.json").read_bytes())
    cassette = LIVE / "cassettes" / f"{run_id}.model.jsonl"
    config = live.model_copy(update={"mode": "replay", "worker": live.worker.model_copy(
        update={"provider": "replay", "cassette": str(cassette.relative_to(ROOT))})})
    store = LocalStore(tmp_path / "store")
    provider = ReplayProvider(Cassette(cassette))

    run_investigation(store, card, config, provider, run_id=run_id)

    assert verify(store, run_id).ok
    replayed = (store.run_dir(run_id) / "trials/t-0.claims.jsonl").read_text()
    assert _claims(replayed) == _claims((evidence / run_id / "t-0.claims.jsonl").read_text())
    assert provider.unused_keys() == []
