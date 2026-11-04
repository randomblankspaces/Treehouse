"""`treehouse schema <name>` exports JSON Schema; the export is diffed against tests/golden/schema/.

Regenerate after an intended schema change:
    for n in $(uv run treehouse schema --list); do uv run treehouse schema $n > tests/golden/schema/$n.json; done
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from treehouse.cli import app
from treehouse.schemas.registry import SCHEMAS

GOLDEN = Path(__file__).parent / "schema"


def test_every_schema_has_a_golden_file():
    assert sorted(p.stem for p in GOLDEN.glob("*.json")) == sorted(SCHEMAS)


@pytest.mark.parametrize("name", sorted(SCHEMAS))
def test_schema_export_matches_golden(name):
    r = CliRunner().invoke(app, ["schema", name])
    assert r.exit_code == 0, r.output
    assert json.loads(r.output) == json.loads((GOLDEN / f"{name}.json").read_text())


def test_schema_list_and_unknown():
    r = CliRunner().invoke(app, ["schema", "--list"])
    assert r.exit_code == 0 and "task" in r.output.split()
    r = CliRunner().invoke(app, ["schema", "nope"])
    assert r.exit_code != 0
