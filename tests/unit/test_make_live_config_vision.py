"""The live config generator must retain the Nagoya vision server wiring."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from treehouse.paths import repo_root


def test_nagoya_live_config_output_includes_vision_servers(tmp_path: Path) -> None:
    root = repo_root()
    output = tmp_path / "live-config.json"
    subprocess.run(
        [
            sys.executable,
            str(root / "scripts/make_live_config.py"),
            str(root / "tasks/t1-nagoya-warehouses.yaml"),
            "claude-sonnet-5-5",
            "strands",
            "--output",
            str(output),
        ],
        check=True,
        cwd=root,
    )

    config = json.loads(output.read_text(encoding="utf-8"))
    assert config["servers"] == "treehouse.providers.factories:vision_servers"
