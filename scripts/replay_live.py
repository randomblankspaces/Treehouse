"""Replay a committed live warehouse run offline (no network, no AWS) and print its sealed claims.

    uv run python scripts/replay_live.py exp-nagoya-sonnet-1 --store out/replay/store

The worker's Bedrock responses come from ``fixtures/live/cassettes/<run_id>.model.jsonl``; tools run in-process
on the committed fixtures. The store must not already contain the run.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from treehouse.cards import load_card
from treehouse.investigation import run_investigation
from treehouse.paths import repo_root
from treehouse.providers.cassette import Cassette, ReplayProvider
from treehouse.schemas.config import RunConfig
from treehouse.store.local import LocalStore
from treehouse.store.verify import verify

LIVE = repo_root() / "fixtures/live"
CARDS = {"nagoya": "t1-nagoya-warehouses", "gifu": "t5-gifu-warehouses", "bangladesh": "t1-bangladesh-warehouses"}
CONFIGS = {"t1-nagoya-warehouses": "t1-nagoya", "t5-gifu-warehouses": "t5-gifu",
           "t1-bangladesh-warehouses": "t1-bangladesh"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_id", help="e.g. exp-nagoya-sonnet-1 (see fixtures/live/cassettes)")
    ap.add_argument("--store", type=Path, default=Path("out/replay/store"))
    a = ap.parse_args(argv)
    card_id = next(v for k, v in CARDS.items() if k in a.run_id)
    model = "nova" if "nova" in a.run_id else "sonnet"
    cassette = LIVE / "cassettes" / f"{a.run_id}.model.jsonl"
    live = RunConfig.model_validate_json((LIVE / "configs" / f"{CONFIGS[card_id]}-{model}-strands.json").read_bytes())
    config = live.model_copy(update={"mode": "replay", "worker": live.worker.model_copy(
        update={"provider": "replay", "cassette": str(cassette.relative_to(repo_root()))})})
    store = LocalStore(a.store)
    run_investigation(store, load_card(repo_root() / "tasks" / f"{card_id}.yaml"), config,
                      ReplayProvider(Cassette(cassette)), run_id=a.run_id)
    print("verify:", "ok" if verify(store, a.run_id).ok else "FAILED")
    for line in (store.run_dir(a.run_id) / "trials/t-0.claims.jsonl").read_text().splitlines():
        c = json.loads(line)
        print(f"{c['status']:>14}  {c['cls']}  {c['geometry']['coordinates']}  conf={c['confidence']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
