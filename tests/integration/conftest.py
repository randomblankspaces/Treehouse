"""Fixtures for the integration tests (builders live in gwrig.py)."""

from __future__ import annotations

import pytest
from gwrig import make_rig


@pytest.fixture
def rig(tmp_path):
    return make_rig(tmp_path / "t-0.trace.jsonl")
