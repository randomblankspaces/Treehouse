"""Vision errors retain the byte-exact message used by recorded model requests."""

import pytest

from treehouse.cards import load_card
from treehouse.tools.retrieval import retrieval_for_card


@pytest.mark.parametrize("missing", ["vision", "gsi", "allowlist"])
def test_vision_error_preserves_recorded_message(missing):
    tools = retrieval_for_card(load_card("tasks/t1-nagoya-warehouses.yaml"), vision=object(), gsi=object())
    if missing == "allowlist":
        tools.vision_allowed = False
    else:
        setattr(tools, missing, None)
    error = tools.classify("unused", "vision_subagent", ["r000c000"])
    assert error.code == "not_configured"
    assert error.message == (
        "vision_subagent needs an injected vision model and "
        "the gsi-seamless-aerial-japan source on the task allow-list"
    )
