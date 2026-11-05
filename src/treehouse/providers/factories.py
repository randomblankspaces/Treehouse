"""Trusted provider factories for explicit investigation sandbox runs."""

from __future__ import annotations

import os
from pathlib import Path

from treehouse.providers.bedrock import BedrockConverseProvider
from treehouse.providers.cassette import Cassette, RecordingProvider, ReplayProvider
from treehouse.providers.prices import load_default
from treehouse.providers.registry import ModelRegistry
from treehouse.providers.spend import SpendLedger
from treehouse.tools.retrieval import make_retrieval_server, retrieval_for_card
from treehouse.tools.sources.gsi import RecordingGsiSeamlessPhotoSource, ReplayGsiSeamlessPhotoSource
from treehouse.verifier.vision_classifier_agent import VisionSubagent


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


def vision_servers(*, card, ledger, pixels, default_servers):
    """Inject a recorded or replayed GSI vision classifier into Japan retrieval tasks."""
    del ledger, pixels
    if not any(source.source_id == "gsi-seamless-aerial-japan" for source in card.data_allowlist):
        return default_servers

    mode = os.environ.get("TREEHOUSE_VISION_MODE")
    if not mode:
        raise ValueError("TREEHOUSE_VISION_MODE is required")
    if mode not in {"record", "replay"}:
        raise ValueError("TREEHOUSE_VISION_MODE must be record or replay")

    cassette_path = _required_path("TREEHOUSE_VISION_CASSETTE")
    gsi_log_path = _required_path("TREEHOUSE_GSI_LOG")
    registry = ModelRegistry.load()
    model_key = os.environ.get("TREEHOUSE_VISION_MODEL", "claude-sonnet-5-5")
    if model_key not in registry.keys():
        raise ValueError(f"TREEHOUSE_VISION_MODEL must be a registry key: {model_key!r}")
    model = registry.get(model_key)
    if not model.vision:
        raise ValueError(f"TREEHOUSE_VISION_MODEL does not support vision: {model_key}")

    if mode == "record":
        if cassette_path.exists():
            raise ValueError(f"TREEHOUSE_VISION_CASSETTE already exists: {cassette_path}")
        if gsi_log_path.exists():
            raise ValueError(f"TREEHOUSE_GSI_LOG already exists: {gsi_log_path}")
        prices = load_default()
        spend = SpendLedger(prices=prices, registry=registry)
        live = BedrockConverseProvider(None, registry, prices, spend, region=model.region)
        provider = RecordingProvider(live, Cassette(cassette_path))
        gsi = RecordingGsiSeamlessPhotoSource(gsi_log_path)
    else:
        if not cassette_path.is_file():
            raise ValueError(f"TREEHOUSE_VISION_CASSETTE is not a file: {cassette_path}")
        if not gsi_log_path.is_file():
            raise ValueError(f"TREEHOUSE_GSI_LOG is not a file: {gsi_log_path}")
        provider = ReplayProvider(Cassette(cassette_path))
        gsi = ReplayGsiSeamlessPhotoSource(gsi_log_path)

    servers = dict(default_servers)
    tools = retrieval_for_card(card, vision=VisionSubagent(provider, model.invoke_id), gsi=gsi)
    servers["retrieval"] = make_retrieval_server(tools)
    return servers


__all__ = ["bedrock_recording", "replay", "vision_servers"]
