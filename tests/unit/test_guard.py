"""P0b offline-guard tests: DNS block, fake AWS env, tmp store paths, boto3 canary."""

import os
import socket
from pathlib import Path

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
    boto3 = pytest.importorskip("boto3")
    client = boto3.client("s3")
    with pytest.raises(Exception):  # noqa: B017 - any failure is fine; the call must not succeed
        client.list_buckets()
    assert any("amazonaws.com" in a for a in offline_guard.attempts)


@pytest.mark.slow
def test_slow_marker_is_deselected_by_default(request):
    assert "slow" in request.config.getoption("-m"), "slow tests must run only under -m slow"
