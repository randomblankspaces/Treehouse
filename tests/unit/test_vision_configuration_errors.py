"""Vision errors identify missing wiring before attempting any imagery reads."""

import pytest

from treehouse.cards import load_card
from treehouse.tools.retrieval import retrieval_for_card


@pytest.mark.parametrize("missing", ["vision", "gsi", "allowlist"])
def test_vision_error_names_missing_component_and_server_factory(missing):
    tools = retrieval_for_card(load_card("tasks/t1-nagoya-warehouses.yaml"), vision=object(), gsi=object())
    if missing == "allowlist":
        tools.vision_allowed = False
    else:
        setattr(tools, missing, None)
    error = tools.classify("unused", "vision_subagent", ["r000c000"])
    assert error.code == "not_configured"
    assert {"vision": "vision model", "gsi": "GSI imagery source", "allowlist": "task allow-list"}[missing] in error.message
    assert "--servers treehouse.providers.factories:vision_servers" in error.message
    assert "TREEHOUSE_VISION_MODE" in error.message
