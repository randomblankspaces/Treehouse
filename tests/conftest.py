"""Test-wide guards.

* Offline guarantee, installed process-wide in ``pytest_configure`` (so session- and module-scoped
  fixtures and collection-time code are covered too, not just test bodies):
  - outbound ``connect``/``connect_ex``/``sendto``/``sendmsg`` to non-loopback hosts, and DNS
    (``getaddrinfo``, ``gethostbyname[_ex]``, ``gethostbyaddr``) for non-loopback names, raise
    ``NetworkBlocked``; loopback ``connect`` is allowed only inside tests marked ``allow_loopback``;
  - ``AWS_*`` is replaced by fake credentials and ``/dev/null`` config files, every variable whose name contains "proxy" is removed
    (a loopback proxy would tunnel past the guard), and ``TREEHOUSE_STORE`` / ``TREEHOUSE_SPEND_LEDGER``
    point at a session tmp dir (each test then gets its own tmp_path);
  - child Python processes inherit ``TREEHOUSE_OFFLINE_GUARD=1`` and ``PYTHONPATH=tests/_offline``, whose
    ``sitecustomize`` installs the same block. Non-Python children (``uv``, curl) are covered only by the
    scrubbed environment, not by a socket block.
  Blocked attempts are recorded on the ``offline_guard`` fixture (inside a test) or on ``SESSION_GUARD``.
  Tests marked ``live`` are skipped unless ``TREEHOUSE_LIVE=1``; when they run, they get the real
  network and the original environment back.
* ``slow`` tests are deselected unless the ``-m`` expression mentions ``slow``.
* ``method`` tests share a session time budget of 8 s; the run fails if they exceed it.
"""

from __future__ import annotations

import os
import shutil
import socket
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest

_REAL = {
    "connect": socket.socket.connect,
    "connect_ex": socket.socket.connect_ex,
    "sendto": socket.socket.sendto,
    "sendmsg": getattr(socket.socket, "sendmsg", None),
}
_REAL_DNS = {n: getattr(socket, n) for n in ("getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr")}
_LOOPBACK = {"127.0.0.1", "::1", "localhost"}
SUBPROCESS_GUARD_DIR = Path(__file__).parent / "_offline"
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


SESSION_GUARD = OfflineGuard()


@dataclass
class _State:
    guard: OfflineGuard = field(default_factory=lambda: SESSION_GUARD)
    allow_loopback: bool = False
    live: bool = False
    original_env: dict[str, str] = field(default_factory=dict)
    session_dir: str | None = None


_STATE = _State()


def _host_of(address) -> str | None:
    if isinstance(address, tuple) and address:
        return str(address[0])
    return None  # AF_UNIX paths are local and allowed


def _permitted(address) -> bool:
    host = _host_of(address)
    return _STATE.live or host is None or (_STATE.allow_loopback and host in _LOOPBACK)


def _connect(self, address):
    if _permitted(address):
        return _REAL["connect"](self, address)
    _STATE.guard.block(f"connect {address!r}")


def _connect_ex(self, address):
    if _permitted(address):
        return _REAL["connect_ex"](self, address)
    _STATE.guard.block(f"connect_ex {address!r}")


def _sendto(self, data, *args):
    if _permitted(args[-1]):
        return _REAL["sendto"](self, data, *args)
    _STATE.guard.block(f"sendto {args[-1]!r}")


def _sendmsg(self, buffers, *args):
    address = args[2] if len(args) > 2 else None
    if _permitted(address):
        return _REAL["sendmsg"](self, buffers, *args)
    _STATE.guard.block(f"sendmsg {address!r}")


def _dns(name_of_fn: str):
    real = _REAL_DNS[name_of_fn]

    def lookup(host, *args, **kwargs):
        name = host.decode() if isinstance(host, bytes) else host
        if _STATE.live or name is None or name in _LOOPBACK:
            return real(host, *args, **kwargs)
        _STATE.guard.block(f"{name_of_fn} {name}")

    return lookup


def _guarded_env(store_dir: str) -> dict[str, str | None]:
    """Environment changes for offline tests (None = remove)."""
    env: dict[str, str | None] = {k: None for k in os.environ if k.startswith("AWS_") or "proxy" in k.lower()}
    env.update(_FAKE_AWS)
    pp = os.environ.get("PYTHONPATH", "")
    guard_dir = str(SUBPROCESS_GUARD_DIR)
    env["PYTHONPATH"] = pp if guard_dir in pp.split(os.pathsep) else os.pathsep.join(x for x in (guard_dir, pp) if x)
    env["TREEHOUSE_OFFLINE_GUARD"] = "1"
    env["TREEHOUSE_STORE"] = str(Path(store_dir) / "store")
    env["TREEHOUSE_SPEND_LEDGER"] = str(Path(store_dir) / "spend.jsonl")
    return env


def pytest_configure(config):
    _STATE.original_env = dict(os.environ)
    _STATE.session_dir = tempfile.mkdtemp(prefix="treehouse-tests-")
    for k, v in _guarded_env(_STATE.session_dir).items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    socket.socket.connect = _connect
    socket.socket.connect_ex = _connect_ex
    socket.socket.sendto = _sendto
    if _REAL["sendmsg"] is not None:
        socket.socket.sendmsg = _sendmsg
    for n in _REAL_DNS:
        setattr(socket, n, _dns(n))


def pytest_unconfigure(config):
    for n in ("connect", "connect_ex", "sendto", "sendmsg"):
        if _REAL[n] is not None:
            setattr(socket.socket, n, _REAL[n])
    for n, fn in _REAL_DNS.items():
        setattr(socket, n, fn)
    if _STATE.original_env:
        os.environ.clear()
        os.environ.update(_STATE.original_env)
    if _STATE.session_dir:
        shutil.rmtree(_STATE.session_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def offline_guard(request, monkeypatch, tmp_path):
    guard = OfflineGuard()
    if os.environ.get("TREEHOUSE_LIVE") == "1" and request.node.get_closest_marker("live"):
        for k in set(os.environ) | set(_STATE.original_env):
            if k in _STATE.original_env:
                monkeypatch.setenv(k, _STATE.original_env[k])
            else:
                monkeypatch.delenv(k, raising=False)
        _STATE.live = True
        try:
            yield guard
        finally:
            _STATE.live = False
        return
    allow_loopback = request.node.get_closest_marker("allow_loopback") is not None
    for k, v in _guarded_env(str(tmp_path)).items():  # re-scrub: a session fixture may have changed env
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)
    if allow_loopback:
        monkeypatch.setenv("TREEHOUSE_OFFLINE_ALLOW_LOOPBACK", "1")
    _STATE.guard, _STATE.allow_loopback = guard, allow_loopback
    try:
        yield guard
    finally:
        _STATE.guard, _STATE.allow_loopback = SESSION_GUARD, False


def pytest_collection_modifyitems(config, items):
    if os.environ.get("TREEHOUSE_LIVE") != "1":
        skip = pytest.mark.skip(reason="live AWS test; set TREEHOUSE_LIVE=1 (run in Kiro)")
        for item in items:
            if item.get_closest_marker("live"):
                item.add_marker(skip)
    if "slow" not in (config.getoption("-m") or ""):
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


@pytest.fixture
def unpriced_table_path():
    """Immutable missing-price scenario, independent of the real dated price table."""
    return Path(__file__).parent / "fixtures" / "prices" / "unpriced.yaml"


@pytest.fixture
def unpriced_prices(unpriced_table_path):
    from treehouse.providers.prices import PriceTable

    return PriceTable.load(unpriced_table_path)


@pytest.fixture
def isolated_repo_ledger(tmp_path, monkeypatch):
    """CLI scenarios must compare against a test repo ledger, never real account spend."""
    path = tmp_path / "repo" / ".spend" / "spend.jsonl"
    monkeypatch.setattr("treehouse.providers.spend.repo_ledger_path", lambda: path)
    return path
