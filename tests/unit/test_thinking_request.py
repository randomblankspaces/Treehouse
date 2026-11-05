"""Thinking is opt-in and its Converse fields come from the model registry."""

import pytest

from treehouse.providers.bedrock import BedrockValidationError, build_converse_kwargs
from treehouse.providers.registry import ModelRegistry
from treehouse.schemas.config import InferenceParams
from treehouse.schemas.model_io import Message, ModelRequest, Text


class FakeConverseClient:
    def __init__(self):
        self.kwargs = None

    def converse(self, **kwargs):
        self.kwargs = kwargs


def test_thinking_on_sends_configured_fields_and_omits_temperature():
    registry = ModelRegistry.load()
    entry = registry.get("claude-sonnet-5-5")
    request = ModelRequest(
        model_id=entry.key, system="", messages=[Message(role="user", content=[Text(text="hi")])],
        params=InferenceParams(max_tokens=64, temperature=0.2),
    )
    client = FakeConverseClient()

    kwargs = build_converse_kwargs(request, entry, thinking=True)
    client.converse(**kwargs)

    assert client.kwargs["additionalModelRequestFields"] == {"thinking": {"type": "adaptive", "display": "summarized"}}
    assert client.kwargs["inferenceConfig"] == {"maxTokens": 64}


def test_thinking_is_off_by_default_and_leaves_existing_request_shape_unchanged():
    registry = ModelRegistry.load()
    entry = registry.get("claude-sonnet-5-5")
    request = ModelRequest(
        model_id=entry.key, system="", messages=[Message(role="user", content=[Text(text="hi")])],
        params=InferenceParams(max_tokens=64, temperature=0.2),
    )

    kwargs = build_converse_kwargs(request, entry)

    assert "additionalModelRequestFields" not in kwargs
    assert kwargs["inferenceConfig"] == {"maxTokens": 64, "temperature": 0.2}


def test_thinking_without_model_configuration_fails_cleanly():
    entry = ModelRegistry.load().get("nova-pro")
    request = ModelRequest(
        model_id=entry.key, system="", messages=[Message(role="user", content=[Text(text="hi")])],
        params=InferenceParams(max_tokens=64),
    )
    with pytest.raises(BedrockValidationError, match="no thinking request_fields configured"):
        build_converse_kwargs(request, entry, thinking=True)


def test_run_config_thinking_is_opt_in_and_preserves_existing_serialization():
    from treehouse.canon import canonical_json
    from treehouse.paths import repo_root
    from treehouse.schemas.config import RunConfig

    original = (repo_root() / "fixtures/demo/configs/synth-good.json").read_text().strip()
    config = RunConfig.model_validate_json(original)
    assert config.thinking is False
    assert canonical_json(config) == original
    assert canonical_json(RunConfig.model_validate({**config.model_dump(), "thinking": False})) == original
    enabled = RunConfig.model_validate({**config.model_dump(), "thinking": True})
    assert enabled.thinking is True
    assert enabled.model_dump(mode="json")["thinking"] is True


def test_registry_request_fields_are_optional_and_validated():
    from pydantic import ValidationError

    from treehouse.providers.registry import ModelEntry

    entry = ModelRegistry.load().get("nova-pro")
    assert entry.request_fields == {}
    with pytest.raises(ValidationError):
        ModelEntry.model_validate({**entry.model_dump(), "request_fields": ["thinking"]})


@pytest.mark.parametrize("thinking", [False, True])
def test_live_config_script_supports_thinking_switch(tmp_path, thinking):
    import runpy

    from treehouse.paths import repo_root
    from treehouse.schemas.config import RunConfig

    root = repo_root()
    script = runpy.run_path(str(root / "scripts/make_live_config.py"))
    output = tmp_path / "live.json"
    args = [str(root / "tasks/synth-crossings-v1.yaml"), "claude-sonnet-5-5", "strands",
            "--output", str(output)]
    if thinking:
        args.append("--thinking")
    assert script["main"](args) == 0
    assert RunConfig.model_validate_json(output.read_bytes()).thinking is thinking


@pytest.mark.parametrize("thinking", [False, True])
def test_recording_factory_propagates_run_thinking_to_bedrock(tmp_path, monkeypatch, thinking):
    from treehouse.paths import repo_root
    from treehouse.providers.factories import bedrock_recording
    from treehouse.schemas.config import RunConfig

    config = RunConfig.model_validate_json(
        (repo_root() / "fixtures/live/configs/t1-nagoya-sonnet-strands.json").read_bytes())
    config = RunConfig.model_validate({**config.model_dump(), "thinking": thinking})
    monkeypatch.setenv("TREEHOUSE_CASSETTE_OUT", str(tmp_path / "record.jsonl"))
    monkeypatch.setenv("TREEHOUSE_SPEND_LEDGER", str(tmp_path / "spend.jsonl"))

    provider = bedrock_recording(card=None, config=config).inner
    entry = provider.registry.get(config.worker.model_key)
    request = ModelRequest(model_id=entry.key, system="", messages=[],
                           params=InferenceParams(max_tokens=64, temperature=0.2))
    _, kwargs = provider.prepare(request)

    assert provider.thinking is thinking
    assert ("additionalModelRequestFields" in kwargs) is thinking
    assert ("temperature" in kwargs["inferenceConfig"]) is not thinking
