"""Test-wide guards.

* Offline guarantee: every test runs with outbound sockets and DNS blocked (loopback ``connect`` is
  allowed only for tests marked ``allow_loopback``), with ``AWS_*`` replaced by fake credentials and
  ``/dev/null`` config files, and with ``TREEHOUSE_STORE`` / ``TREEHOUSE_SPEND_LEDGER`` pointed at
  the test's tmp dir; proxy variables are removed. No test can reach Bedrock, S3, IMDS or the internet by accident. Blocked
  attempts are recorded on the ``offline_guard`` fixture. Tests marked ``live`` are skipped unless
  ``TREEHOUSE_LIVE=1``.
* ``slow`` tests are deselected by default (``-m slow`` selects them).
* ``method`` tests share a session time budget of 8 s; the run fails if they exceed it.
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass, field

import pytest

_REAL_CONNECT = socket.socket.connect
_REAL_CONNECT_EX = socket.socket.connect_ex
_REAL_GETADDRINFO = socket.getaddrinfo
_LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_PROXY_VARS = {"http_proxy", "https_proxy", "all_proxy"}
METHOD_BUDGET_S = 8.0
_FAKE_AWS = {
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_CONFIG_FILE": os.devnull,
    "AWS_SHARED_CREDENTIALS_FILE": os.devnull,
    "AWS_EC2_METADATA_DISABLED": "true",
}


class NetworkBlocked(RuntimeError):
    pass


@dataclass
class OfflineGuard:
    attempts: list[str] = field(default_factory=list)

    def block(self, what: str):
        self.attempts.append(what)
        raise NetworkBlocked(f"network access blocked in tests: {what}")


def _host_of(address) -> str | None:
    if isinstance(address, tuple) and address:
        return str(address[0])
    return None  # AF_UNIX paths are local and allowed


@pytest.fixture(autouse=True)
def offline_guard(request, monkeypatch, tmp_path):
    guard = OfflineGuard()
    if os.environ.get("TREEHOUSE_LIVE") == "1" and request.node.get_closest_marker("live"):
        yield guard
        return
    allow_loopback = request.node.get_closest_marker("allow_loopback") is not None

    def connect(self, address):
        host = _host_of(address)
        if host is None or (allow_loopback and host in _LOOPBACK):
            return _REAL_CONNECT(self, address)
        guard.block(f"connect {address!r}")

    def connect_ex(self, address):
        host = _host_of(address)
        if host is None or (allow_loopback and host in _LOOPBACK):
            return _REAL_CONNECT_EX(self, address)
        guard.block(f"connect_ex {address!r}")

    def getaddrinfo(host, *args, **kwargs):
        name = host.decode() if isinstance(host, bytes) else host
        if name is None or name in _LOOPBACK:
            return _REAL_GETADDRINFO(host, *args, **kwargs)
        guard.block(f"getaddrinfo {name}")

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    for key in list(os.environ):
        if key.startswith("AWS_"):
            monkeypatch.delenv(key, raising=False)
    for key in list(os.environ):  # a loopback proxy would tunnel past the guard
        if key.lower() in _PROXY_VARS:
            monkeypatch.delenv(key, raising=False)
    for key, value in _FAKE_AWS.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("TREEHOUSE_STORE", str(tmp_path / "store"))
    monkeypatch.setenv("TREEHOUSE_SPEND_LEDGER", str(tmp_path / "spend.jsonl"))
    yield guard


def pytest_collection_modifyitems(config, items):
    if os.environ.get("TREEHOUSE_LIVE") != "1":
        skip = pytest.mark.skip(reason="live AWS test; set TREEHOUSE_LIVE=1 (run in Kiro)")
        for item in items:
            if item.get_closest_marker("live"):
                item.add_marker(skip)
    if not config.getoption("-m"):
        keep, drop = [], []
        for item in items:
            (drop if item.get_closest_marker("slow") else keep).append(item)
        if drop:
            config.hook.pytest_deselected(items=drop)
            items[:] = keep


_method_seconds = 0.0


def pytest_runtest_logreport(report):
    global _method_seconds
    if report.when == "call" and "method" in report.keywords:
        _method_seconds += report.duration


def pytest_sessionfinish(session, exitstatus):
    if _method_seconds > METHOD_BUDGET_S:
        session.config.get_terminal_writer().line(
            f"method tests took {_method_seconds:.2f} s, over the {METHOD_BUDGET_S} s budget", red=True
        )
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
