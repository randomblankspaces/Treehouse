"""Trusted provider factories for explicit investigation sandbox runs."""

from __future__ import annotations

import os
from pathlib import Path

from treehouse.providers.bedrock import BedrockConverseProvider
from treehouse.providers.cassette import Cassette, RecordingProvider, ReplayProvider
from treehouse.providers.prices import load_default
from treehouse.providers.registry import ModelRegistry
from treehouse.providers.spend import SpendLedger


def _required_path(name: str) -> Path:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"{name} is required")
    return Path(value).expanduser().resolve()


def bedrock_recording(*, card, config) -> RecordingProvider:
    """Build the live us-east-1 Bedrock provider and record a new pixel-free cassette."""
    del card, config
    path = _required_path("TREEHOUSE_CASSETTE_OUT")
    if path.exists():
        raise ValueError(f"TREEHOUSE_CASSETTE_OUT already exists: {path}")
    registry = ModelRegistry.load()
    prices = load_default()
    ledger = SpendLedger(prices=prices, registry=registry)
    provider = BedrockConverseProvider(None, registry, prices, ledger, region="us-east-1")
    return RecordingProvider(provider, Cassette(path))


def replay(*, card, config) -> ReplayProvider:
    """Replay a required existing pixel-free cassette without constructing an AWS client."""
    del card, config
    path = _required_path("TREEHOUSE_CASSETTE_IN")
    if not path.is_file():
        raise ValueError(f"TREEHOUSE_CASSETTE_IN is not a file: {path}")
    return ReplayProvider(Cassette(path))


__all__ = ["bedrock_recording", "replay"]
