"""Test-wide guards.

* Offline guarantee: every test runs with outbound sockets blocked (loopback is allowed only for
  tests marked ``allow_loopback``) and with all ``AWS_*`` variables cleared, so no test can reach
  Bedrock, S3 or the internet by accident. Tests marked ``live`` are skipped unless
  ``TREEHOUSE_LIVE=1``.
"""

from __future__ import annotations

import os
import socket

import pytest

_REAL_CONNECT = socket.socket.connect
_REAL_CONNECT_EX = socket.socket.connect_ex
_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


class NetworkBlocked(RuntimeError):
    pass


def _host_of(address) -> str | None:
    if isinstance(address, tuple) and address:
        return str(address[0])
    return None  # AF_UNIX paths are local and allowed


@pytest.fixture(autouse=True)
def _offline(request, monkeypatch):
    if os.environ.get("TREEHOUSE_LIVE") == "1" and request.node.get_closest_marker("live"):
        yield
        return
    allow_loopback = request.node.get_closest_marker("allow_loopback") is not None

    def guard(self, address):
        host = _host_of(address)
        if host is None or (allow_loopback and host in _LOOPBACK):
            return _REAL_CONNECT(self, address)
        raise NetworkBlocked(f"network access blocked in tests: {address!r}")

    def guard_ex(self, address):
        host = _host_of(address)
        if host is None or (allow_loopback and host in _LOOPBACK):
            return _REAL_CONNECT_EX(self, address)
        raise NetworkBlocked(f"network access blocked in tests: {address!r}")

    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(socket.socket, "connect_ex", guard_ex)
    for key in list(os.environ):
        if key.startswith("AWS_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    yield


def pytest_collection_modifyitems(config, items):
    if os.environ.get("TREEHOUSE_LIVE") == "1":
        return
    skip = pytest.mark.skip(reason="live AWS test; set TREEHOUSE_LIVE=1 (run in Kiro)")
    for item in items:
        if item.get_closest_marker("live"):
            item.add_marker(skip)
