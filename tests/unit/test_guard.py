"""P0b offline-guard tests: DNS block, fake AWS env, tmp store paths, boto3 canary, loopback marker,
session-scope and subprocess coverage."""

import os
import socket
import subprocess
import sys
from pathlib import Path

import boto3  # a pinned dev dependency: the canary must never be skipped
import pytest

BLOCKED = "network access blocked"


def test_getaddrinfo_blocked_for_public_host(offline_guard):
    with pytest.raises(RuntimeError, match=BLOCKED):
        socket.getaddrinfo("example.com", 443)
    assert any("example.com" in a for a in offline_guard.attempts)


def test_getaddrinfo_allows_loopback():
    assert socket.getaddrinfo("127.0.0.1", 80)


def test_connect_blocked_and_recorded(offline_guard):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(RuntimeError, match=BLOCKED):
            s.connect_ex(("10.0.0.1", 80))
    finally:
        s.close()
    assert offline_guard.attempts


def test_fake_aws_environment():
    assert os.environ["AWS_ACCESS_KEY_ID"] == "testing"
    assert os.environ["AWS_SECRET_ACCESS_KEY"] == "testing"
    assert os.environ["AWS_DEFAULT_REGION"] == "us-east-1"
    assert os.environ["AWS_CONFIG_FILE"] == os.devnull
    assert os.environ["AWS_SHARED_CREDENTIALS_FILE"] == os.devnull
    assert os.environ["AWS_EC2_METADATA_DISABLED"] == "true"
    allowed = {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_DEFAULT_REGION",
        "AWS_CONFIG_FILE",
        "AWS_SHARED_CREDENTIALS_FILE",
        "AWS_EC2_METADATA_DISABLED",
    }
    assert {k for k in os.environ if k.startswith("AWS_")} == allowed


def test_store_and_spend_ledger_point_at_tmp(tmp_path):
    store = Path(os.environ["TREEHOUSE_STORE"])
    ledger = Path(os.environ["TREEHOUSE_SPEND_LEDGER"])
    assert store.parent == tmp_path and ledger.parent == tmp_path


def test_boto3_canary(offline_guard):
    client = boto3.client("s3")
    with pytest.raises(Exception):  # noqa: B017 - any failure is fine; the call must not succeed
        client.list_buckets()
    assert any("amazonaws.com" in a for a in offline_guard.attempts)


@pytest.mark.slow
def test_slow_marker_is_deselected_by_default(request):
    assert "slow" in request.config.getoption("-m"), "slow tests must run only under -m slow"


@pytest.mark.parametrize("call", [
    lambda: socket.gethostbyname("example.com"),
    lambda: socket.gethostbyname_ex("example.com"),
    lambda: socket.gethostbyaddr("8.8.8.8"),
])
def test_other_name_lookups_blocked(offline_guard, call):
    with pytest.raises(RuntimeError, match=BLOCKED):
        call()
    assert offline_guard.attempts


def test_udp_sendto_blocked(offline_guard):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        with pytest.raises(RuntimeError, match=BLOCKED):
            s.sendto(b"x", ("8.8.8.8", 53))
    finally:
        s.close()
    assert any("sendto" in a for a in offline_guard.attempts)


def _loopback_server() -> socket.socket:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    return srv


def test_loopback_blocked_without_marker(offline_guard):
    srv, cli = _loopback_server(), socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(RuntimeError, match=BLOCKED):
            cli.connect(srv.getsockname())
    finally:
        cli.close()
        srv.close()


@pytest.mark.allow_loopback
def test_loopback_allowed_with_marker(offline_guard):
    srv, cli = _loopback_server(), socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        cli.connect(srv.getsockname())
    finally:
        cli.close()
        srv.close()
    assert offline_guard.attempts == []


@pytest.fixture(scope="session")
def session_lookup():
    """Runs before any function-scoped fixture: the guard must already be installed."""
    try:
        socket.getaddrinfo("example.com", 443)
    except Exception as e:  # noqa: BLE001
        return e
    return None


def test_session_scoped_fixture_is_guarded(session_lookup):
    assert type(session_lookup).__name__ == "NetworkBlocked", session_lookup
    assert os.environ["AWS_ACCESS_KEY_ID"] == "testing"


@pytest.mark.parametrize("code", [
    "import socket; socket.getaddrinfo('example.com', 443)",
    "import socket; socket.gethostbyname('example.com')",
    "import socket; s = socket.socket(); s.connect(('10.0.0.1', 80))",
])
def test_subprocess_python_is_guarded(code):
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and BLOCKED in r.stderr, r.stderr


def test_subprocess_env_is_scrubbed():
    code = "import os, json; print(json.dumps({k: v for k, v in os.environ.items() if k.startswith('AWS_') or 'proxy' in k.lower()}))"
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    import json

    env = json.loads(r.stdout)
    assert env["AWS_ACCESS_KEY_ID"] == "testing" and not [k for k in env if "proxy" in k.lower()]
