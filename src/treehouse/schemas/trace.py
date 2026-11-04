"""Span records and the hash chain that seals a trace file."""

from __future__ import annotations

from typing import Any, Literal

from treehouse.canon import canonical_json, sha256_bytes
from treehouse.schemas.base import Frozen

Scalar = str | int | float | bool


class SpanError(Frozen):
    source: Literal["agent", "tool", "infra", "budget", "policy"]
    type: str
    message: str


class SpanEvent(Frozen):
    name: str
    ts_ns: int
    attributes: dict[str, Scalar | list[str]] = {}


class SpanRecord(Frozen):
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    name: str
    op: Literal["invoke_agent", "chat", "execute_tool"]
    start_ns: int
    end_ns: int
    status: Literal["ok", "error"]
    error: SpanError | None = None
    attributes: dict[str, Scalar | list[str]] = {}
    events: list[SpanEvent] = []


def chain_hash(prev: str, rec: dict[str, Any]) -> str:
    """h = sha256(prev + canon(rec))."""
    return sha256_bytes((prev + canonical_json(rec)).encode("utf-8"))


class ChainLine(Frozen):
    seq: int
    prev: str
    rec: dict[str, Any]
    h: str


class ChainHead(Frozen):
    head: str
    n_lines: int
    file_sha256: str
