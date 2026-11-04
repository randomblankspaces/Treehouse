import socket

import pytest

from treehouse import __version__
from treehouse.canon import canonical_json, sha256_json


def test_version():
    assert __version__ == "0.1.0"


def test_canonical_json_is_order_independent():
    assert canonical_json({"b": 1, "a": [1, 2]}) == canonical_json({"a": [1, 2], "b": 1})
    assert sha256_json({"b": 1, "a": 2}) == sha256_json({"a": 2, "b": 1})


def test_canonical_json_rejects_nan():
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})


def test_network_is_blocked():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(RuntimeError):
        s.connect(("93.184.216.34", 80))
    s.close()


def test_aws_env_is_cleared():
    import os

    assert not [k for k in os.environ if k.startswith("AWS_") and k != "AWS_EC2_METADATA_DISABLED"]


def test_cli_version():
    from typer.testing import CliRunner

    from treehouse.cli import app

    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0 and "0.1.0" in result.output
