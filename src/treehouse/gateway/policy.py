"""Tool-call policy (§3 gateway step 2): allow-list, forbidden sources, the key root and ``as_of``.

Every string in the arguments (recursively) is checked against each ``ForbiddenSource`` kind:
``host`` (glob on the URL host or a bare host), ``url_prefix``, ``s3_prefix``, ``dataset_id`` (glob on
the whole string), ``path`` (a path segment prefix such as ``keys/``, in plain paths and URL paths) and
``tool`` (glob on the tool name). Any string resolving under the repo ``keys/`` directory is forbidden
whatever the card says. A forbidden hit sets ``key_access_attempt``.

Matching is on normalised strings (judge D7): percent-decoded until stable and case-folded; every URL
embedded anywhere in a string, plus its query values and fragment, is checked too; hosts come from
URLs, scheme-relative ``//host`` and scheme-less ``host/path`` forms, with trailing dots stripped;
``dataset_id`` matches the whole string or any ``/ : ? & = #``-separated token, as a glob or (for a
pattern with no glob characters) as a prefix; ``s3_prefix`` maps ``s3://``, virtual-host and path-style
S3 URLs to ``(bucket, key)``; tool names compare case-insensitively.
"""

from __future__ import annotations

import fnmatch
import posixpath
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit

from treehouse.clock import parse_when
from treehouse.paths import keys_root, may_be_under
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


_URL_RE = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\"'<>]+|(?<![:\w])//[^\s\"'<>/]+[^\s\"'<>]*", re.I)
_HOST_RE = re.compile(r"^[a-z0-9_-]+(\.[a-z0-9_-]+)+\.?(:\d+)?$")
_S3_VHOST = re.compile(r"^(?P<b>[a-z0-9.-]+)\.s3([.-][a-z0-9-]+)*\.amazonaws\.com$")
_S3_PATH = re.compile(r"^s3([.-][a-z0-9-]+)*\.amazonaws\.com$")
_TOKEN_SPLIT = re.compile(r"[/:\s?&=#@,;]+")


def _unquote_all(s: str) -> str:
    for _ in range(5):
        u = unquote(s)
        if u == s:
            break
        s = u
    return s


def _variants(s: str) -> list[str]:
    """The string, percent-decoded until stable and case-folded, plus every URL embedded in it and the
    query values and fragment of each URL (judge D7)."""
    base = _unquote_all(s).casefold()
    out, seen = [], set()

    def add(x: str) -> None:
        if x and x not in seen and len(seen) < 64:
            seen.add(x)
            out.append(x)

    add(base)
    for m in _URL_RE.finditer(base):
        u = m.group(0)
        add(u)
        try:
            pu = urlsplit(u)
        except ValueError:
            continue
        for _, v in parse_qsl(pu.query, keep_blank_values=True):
            add(v)
        add(pu.fragment)
    return out


def _host_path(s: str) -> tuple[str, str, str] | None:
    """(scheme, host, path) for a URL, a scheme-relative ``//host/...`` or a scheme-less ``host/path`` /
    bare host. Hosts are lower-cased with trailing dots stripped."""
    try:
        if "://" in s:
            u = urlsplit(s)
            return u.scheme, (u.hostname or "").rstrip("."), u.path
        if s.startswith("//"):
            u = urlsplit("http:" + s)
            return "", (u.hostname or "").rstrip("."), u.path
    except ValueError:
        return None
    head, _, rest = s.partition("/")
    if _HOST_RE.match(head) and " " not in s:
        return "", head.split(":")[0].rstrip("."), "/" + rest
    return None


def _segments_hit(path: str, pat: str) -> bool:
    norm = "/" + posixpath.normpath(path.replace("\\", "/")).strip("/") + "/"
    return f"/{pat}/" in norm


def _path_hit(v: str, pattern: str) -> bool:
    pat = pattern.strip("/").casefold()
    cands = [v]
    hp = _host_path(v)
    if hp is not None:
        scheme, host, path = hp
        cands += [path, host + path]
    return any(_segments_hit(c, pat) for c in cands)


def _s3_parts(v: str) -> tuple[str, str] | None:
    """(bucket, key) for ``s3://b/k``, virtual-host ``https://b.s3.<region>.amazonaws.com/k`` and
    path-style ``https://s3.<region>.amazonaws.com/b/k``."""
    if v.startswith("s3://"):
        b, _, k = v[5:].partition("/")
        return b, k
    hp = _host_path(v)
    if hp is None:
        return None
    _, host, path = hp
    m = _S3_VHOST.match(host)
    if m and not _S3_PATH.match(host):
        return m.group("b"), path.lstrip("/")
    if _S3_PATH.match(host):
        b, _, k = path.lstrip("/").partition("/")
        return b, k
    return None


def _canon_url(v: str) -> str:
    hp = _host_path(v)
    if hp is None or "://" not in v:
        return v
    scheme, host, path = hp
    return f"{scheme}://{host}{path}"


def _variant_hit(v: str, fs: ForbiddenSource) -> bool:
    p = fs.pattern.casefold()
    if fs.kind == "host":
        hp = _host_path(v)
        host = hp[1] if hp else ""
        pat = p.rstrip(".")
        return bool(host) and (fnmatch.fnmatchcase(host, pat) or (pat.startswith("*.") and host == pat[2:]))
    if fs.kind == "url_prefix":
        return v.startswith(p) or _canon_url(v).startswith(_canon_url(p))
    if fs.kind == "s3_prefix":
        want, got = _s3_parts(p), _s3_parts(v)
        if want is None:
            return v.startswith(p)
        return got is not None and got[0] == want[0] and got[1].startswith(want[1])
    if fs.kind == "dataset_id":
        glob = any(ch in p for ch in "*?[")
        for t in [v, *(x for x in _TOKEN_SPLIT.split(v) if x)]:
            if fnmatch.fnmatchcase(t, p) or (not glob and t.startswith(p)):
                return True
        return False
    if fs.kind == "path":
        return _path_hit(v, p)
    return False


def string_hit(s: str, fs: ForbiddenSource) -> bool:
    """Does ``s`` (after normalisation: percent-decoding, case-folding, embedded URLs, query values and
    fragments, scheme-less and scheme-relative hosts, trailing dots, all three S3 URL forms) match ``fs``?"""
    return any(_variant_hit(v, fs) for v in _variants(s))


def _under_keys(s: str) -> bool:
    if len(s) > 4096 or "\x00" in s:
        return False
    cands = [s, _unquote_all(s)]
    if s.casefold().startswith("file://"):
        cands.append(urlsplit(_unquote_all(s)).path)
    for c in cands:
        if "://" in c:
            continue
        try:
            if may_be_under(c, keys_root()):
                return True
        except (OSError, ValueError):
            continue
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
            if fs.kind == "tool" and fnmatch.fnmatchcase(tool.casefold(), fs.pattern.casefold()):
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
