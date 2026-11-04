"""Tool-call policy (§3 gateway step 2): allow-list, forbidden sources, the key root and ``as_of``.

Every string in the arguments (recursively) is checked against each ``ForbiddenSource`` kind:
``host`` (glob on the URL host or a bare host), ``url_prefix``, ``s3_prefix``, ``dataset_id`` (glob on
the whole string), ``path`` (a path segment prefix such as ``keys/``, in plain paths and URL paths) and
``tool`` (glob on the tool name). Any string resolving under the repo ``keys/`` directory is forbidden
whatever the card says. A forbidden hit sets ``key_access_attempt``.
"""

from __future__ import annotations

import fnmatch
import posixpath
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from treehouse.clock import parse_when
from treehouse.paths import is_under, keys_root
from treehouse.schemas.task import ForbiddenSource, TaskCard

DATE_ARGS = ("start", "datetime", "date")


@dataclass(frozen=True)
class Decision:
    blocked: bool
    reason: str = ""  # not_allowlisted | forbidden_source | as_of
    detail: str = ""
    key_access_attempt: bool = False

    @property
    def message(self) -> str:
        return f"blocked by policy: {self.reason}" + (f" ({self.detail})" if self.detail else "")


ALLOW = Decision(False)


def iter_strings(obj: Any) -> Iterator[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from iter_strings(k)
            yield from iter_strings(v)
    elif isinstance(obj, list | tuple):
        for v in obj:
            yield from iter_strings(v)


def _path_hit(s: str, pattern: str) -> bool:
    pat = pattern.strip("/")
    cands = [s]
    u = urlparse(s)
    if u.scheme:
        cands.append(u.netloc + u.path if u.scheme == "s3" else u.path)
    for c in cands:
        norm = "/" + posixpath.normpath(c.replace("\\", "/")).strip("/") + "/"
        if f"/{pat}/" in norm or norm.startswith(f"/{pat}/"):
            return True
    return False


def string_hit(s: str, fs: ForbiddenSource) -> bool:
    p = fs.pattern
    if fs.kind == "host":
        u = urlparse(s if "://" in s else "")
        host = (u.hostname or "") if u.scheme else (s if "/" not in s and " " not in s else "")
        return bool(host) and (fnmatch.fnmatch(host, p) or (p.startswith("*.") and host == p[2:]))
    if fs.kind in ("url_prefix", "s3_prefix"):
        return s.startswith(p)
    if fs.kind == "dataset_id":
        return fnmatch.fnmatch(s, p)
    if fs.kind == "path":
        return _path_hit(s, p)
    return False


def _under_keys(s: str) -> bool:
    if "://" in s or len(s) > 4096 or "\x00" in s:
        return False
    try:
        return is_under(s, keys_root())
    except (OSError, ValueError):
        return False


class Policy:
    def __init__(self, card: TaskCard, *, as_of: datetime | None = None) -> None:
        self.allowed = set(card.tools_allowed)
        self.forbidden = list(card.forbidden_sources)
        if not any(f.kind == "path" and f.pattern.strip("/") == "keys" for f in self.forbidden):
            self.forbidden.append(ForbiddenSource(kind="path", pattern="keys/"))
        self.as_of = as_of or card.as_of

    def check_strings(self, strings: list[str]) -> Decision:
        for s in strings:
            for fs in self.forbidden:
                if fs.kind != "tool" and string_hit(s, fs):
                    return Decision(True, "forbidden_source", f"{fs.kind} {fs.pattern}", True)
            if _under_keys(s):
                return Decision(True, "forbidden_source", "key root", True)
        return ALLOW

    def check(self, tool: str, args: dict[str, Any]) -> Decision:
        for fs in self.forbidden:
            if fs.kind == "tool" and fnmatch.fnmatch(tool, fs.pattern):
                return Decision(True, "forbidden_source", f"tool {fs.pattern}", True)
        d = self.check_strings(list(iter_strings(args)))
        if d.blocked:
            return d
        if tool not in self.allowed:
            return Decision(True, "not_allowlisted", tool)
        for k in DATE_ARGS:
            v = args.get(k)
            if isinstance(v, str) and _after(v, self.as_of):
                return Decision(True, "as_of", f"{k}={v} is after as_of {self.as_of.isoformat()}")
        return ALLOW


def _after(s: str, as_of: datetime) -> bool:
    try:
        return parse_when(s) > as_of
    except ValueError:
        return False
