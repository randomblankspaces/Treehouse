"""Live server configuration reaches the sandbox runner with CLI precedence."""

import json
import runpy
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from treehouse.canon import canonical_json
from treehouse.paths import repo_root
from treehouse.schemas.config import RunConfig


def test_live_config_without_gsi_keeps_default_servers(tmp_path):
    output = tmp_path / "config.json"
    main = runpy.run_path(str(repo_root() / "scripts/make_live_config.py"))["main"]
    assert main(["tasks/t1-bangladesh-warehouses.yaml", "claude-sonnet-5-5", "strands",
                 "--output", str(output)]) == 0
    assert "servers" not in json.loads(output.read_text())


def test_existing_config_serialization_is_unchanged():
    data = json.loads((repo_root() / "fixtures/live/configs/t1-nagoya-sonnet-strands.json").read_text())
    assert json.loads(canonical_json(RunConfig.model_validate(data))) == data


@pytest.mark.parametrize("configured,flag", [("plugins:configured", None),
                                           ("plugins:configured", "plugins:override"),
                                           (None, "plugins:override"), (None, None)])
def test_sandbox_server_factory_uses_config_unless_cli_overrides(tmp_path, monkeypatch, configured, flag):
    from treehouse import investigation
    from treehouse.investigation import commands

    data = json.loads((repo_root() / "fixtures/live/configs/t1-nagoya-sonnet-strands.json").read_text())
    if configured:
        data["servers"] = configured
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data))
    selected = []
    server_factory = object()

    def factory(spec):
        selected.append(spec)
        return (lambda **kwargs: object()) if spec == "plugins:provider" else server_factory

    def run(*args, **kwargs):
        assert kwargs["server_factory"] is (server_factory if configured or flag else None)
        return SimpleNamespace(manifest=SimpleNamespace(manifest_hash="test"), trials=[])

    monkeypatch.setattr(commands, "_factory", factory)
    monkeypatch.setattr(investigation, "run_investigation", run)
    args = ["run", "--task", "tasks/t1-nagoya-warehouses.yaml", "--config", str(path),
            "--provider", "plugins:provider", "--run-id", "server-config", "--store", str(tmp_path / "store"),
            "--no-bundle"]
    if flag:
        args.extend(["--servers", flag])
    result = CliRunner().invoke(commands.sandbox_app, args)
    assert result.exit_code == 0, result.exception
    assert selected == ["plugins:provider", *([flag or configured] if flag or configured else [])]
