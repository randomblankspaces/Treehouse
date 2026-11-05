"""Generate a live one-trial run config for a task card, model, and harness."""

from __future__ import annotations

import argparse
from pathlib import Path

from treehouse.canon import canonical_json
from treehouse.cards import load_card
from treehouse.providers.registry import ModelRegistry
from treehouse.schemas.config import InferenceParams, RoleConfig, RunConfig


def make_live_config(card_path: Path, model_key: str, harness: str) -> RunConfig:
    card = load_card(card_path)
    model = ModelRegistry.load().get(model_key)
    return RunConfig(
        task_ref=card.ref(),
        mode="live",
        worker=RoleConfig(
            provider="bedrock",
            model_key=model.key,
            family=model.family,
            params=InferenceParams(max_tokens=4096),
            tools=list(card.tools_allowed),
        ),
        harness=harness,
        servers=("treehouse.providers.factories:vision_servers"
                 if any(source.source_id == "gsi-seamless-aerial-japan" for source in card.data_allowlist)
                 else None),
        max_turns=40,
        trials=1,
        seed=1,
        clock="wall",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("card", type=Path)
    parser.add_argument("model_key")
    parser.add_argument("harness", choices=("plain_loop", "strands"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    config = make_live_config(args.card, args.model_key, args.harness)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(canonical_json(config) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
