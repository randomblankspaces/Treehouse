"""Thinking is opt-in and its Converse fields come from the model registry."""

from treehouse.providers.bedrock import build_converse_kwargs
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

    assert client.kwargs["additionalModelRequestFields"] == {"thinking": {"type": "adaptive"}}
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
