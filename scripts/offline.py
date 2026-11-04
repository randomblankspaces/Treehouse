"""Run a command with the network blocked in-process: ``python scripts/offline.py treehouse demo``.

Used by the clean-clone CI job (J8). Every non-loopback ``connect`` and every ``getaddrinfo`` raises, AWS
credentials are faked and point at /dev/null, and any attempt fails the run even if the caller swallowed it.
"""

from __future__ import annotations

import os
import socket
import sys

ATTEMPTS: list[str] = []


def _block(what: str):
    ATTEMPTS.append(what)
    raise OSError(f"network blocked by scripts/offline.py: {what}")


def install() -> None:
    real_connect = socket.socket.connect

    def connect(self, address):
        if isinstance(address, tuple) and address and str(address[0]) not in ("127.0.0.1", "::1", "localhost"):
            _block(f"connect {address!r}")
        return real_connect(self, address)

    socket.socket.connect = connect  # type: ignore[method-assign]
    socket.socket.connect_ex = lambda self, address: _block(f"connect_ex {address!r}")  # type: ignore[method-assign]
    socket.getaddrinfo = lambda host, *a, **k: _block(f"getaddrinfo {host!r}")  # type: ignore[assignment]
    for k in [k for k in os.environ if k.startswith("AWS_") or k.lower().endswith("_proxy")]:
        del os.environ[k]
    os.environ.update({"AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing",
                       "AWS_DEFAULT_REGION": "us-east-1", "AWS_CONFIG_FILE": os.devnull,
                       "AWS_SHARED_CREDENTIALS_FILE": os.devnull, "AWS_EC2_METADATA_DISABLED": "true"})


def main(argv: list[str]) -> int:
    if not argv or argv[0] != "treehouse":
        print("usage: python scripts/offline.py treehouse <args>", file=sys.stderr)
        return 2
    install()
    from treehouse.cli import app

    try:
        app(argv[1:], standalone_mode=False)
        code = 0
    except SystemExit as e:
        code = int(e.code or 0)
    if ATTEMPTS:
        print(f"FAIL network attempts while offline: {ATTEMPTS}", file=sys.stderr)
        return 1
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
