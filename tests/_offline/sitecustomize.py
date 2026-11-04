"""Offline guard for Python subprocesses started by tests.

``tests/conftest.py`` puts this directory first on ``PYTHONPATH`` and sets ``TREEHOUSE_OFFLINE_GUARD=1``
for the whole session, so any child Python interpreter imports this module at startup and blocks
non-loopback ``connect``/``connect_ex``/``sendto``/``sendmsg`` and name lookups. Loopback ``connect`` is
allowed only when ``TREEHOUSE_OFFLINE_ALLOW_LOOPBACK=1`` (set for tests marked ``allow_loopback``).
Children that are not Python (``uv`` itself, curl) are covered only by the scrubbed environment.
"""

from __future__ import annotations

import os
import socket

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def _install() -> None:
    real = {n: getattr(socket.socket, n, None) for n in ("connect", "connect_ex", "sendto", "sendmsg")}
    real_gai = socket.getaddrinfo
    allow_loop = os.environ.get("TREEHOUSE_OFFLINE_ALLOW_LOOPBACK") == "1"

    def blocked(what):
        raise OSError(f"network access blocked in tests (subprocess): {what}")

    def ok(address, loopback_ok):
        if not (isinstance(address, tuple) and address):
            return True
        return loopback_ok and str(address[0]) in _LOOPBACK

    def connect(self, address):
        return real["connect"](self, address) if ok(address, allow_loop) else blocked(f"connect {address!r}")

    def connect_ex(self, address):
        return real["connect_ex"](self, address) if ok(address, allow_loop) else blocked(f"connect_ex {address!r}")

    def sendto(self, data, *args):
        address = args[-1]
        return real["sendto"](self, data, *args) if ok(address, True) else blocked(f"sendto {address!r}")

    def sendmsg(self, buffers, *args):
        address = args[2] if len(args) > 2 else None
        return real["sendmsg"](self, buffers, *args) if ok(address, True) else blocked(f"sendmsg {address!r}")

    def getaddrinfo(host, *a, **k):
        name = host.decode() if isinstance(host, bytes) else host
        return real_gai(host, *a, **k) if name is None or name in _LOOPBACK else blocked(f"getaddrinfo {name}")

    def by_name(host, *a):
        return blocked(f"name lookup {host}") if host not in _LOOPBACK else "127.0.0.1"

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.socket.sendto = sendto
    if real["sendmsg"] is not None:
        socket.socket.sendmsg = sendmsg
    socket.getaddrinfo = getaddrinfo
    socket.gethostbyname = by_name
    socket.gethostbyname_ex = lambda host: blocked(f"name lookup {host}")
    socket.gethostbyaddr = lambda host: blocked(f"name lookup {host}")


if os.environ.get("TREEHOUSE_OFFLINE_GUARD") == "1":
    _install()
