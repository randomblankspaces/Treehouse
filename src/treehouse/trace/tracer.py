"""TrialTracer: one hash-chained span file per trial.

Time comes from an injected ``Clock`` and ids from an injected ``IdSource``, so a run under
``LogicalClock`` with ``IdSource(seed)`` writes byte-identical traces. A span is written when it ends.
Attribute names follow IMPLEMENTATION-DESIGN §3 with fact-check F10 (``treehouse.input.messages_ref``,
not ``gen_ai.input.messages_ref``).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any, Literal

from treehouse.clock import Clock
from treehouse.ids import IdSource
from treehouse.schemas.trace import ChainHead, SpanError, SpanEvent, SpanRecord
from treehouse.trace.chain import ChainedJsonlWriter

Op = Literal["invoke_agent", "chat", "execute_tool"]

RUN_CONTEXT_ATTRS = (
    "treehouse.task.id",
    "treehouse.task.hash",
    "treehouse.run.id",
    "treehouse.trial.id",
    "treehouse.trial.index",
    "treehouse.role",
    "treehouse.config.hash",
)
CHAT_ATTRS = (
    "gen_ai.provider.name",
    "gen_ai.request.model",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens",
    "treehouse.input.messages_ref",
    "treehouse.output.messages_ref",
    "treehouse.cost.usd",
    "treehouse.price_table.version",
    "treehouse.cassette",
    "treehouse.recorded_latency_ms",
)
TOOL_ATTRS = (
    "treehouse.tool.args_hash",
    "treehouse.tool.result_id",
    "treehouse.tool.result_ref",
    "treehouse.tool.bytes_read",
    "treehouse.tool.blocked",
    "treehouse.tool.block_reason",
    "treehouse.key_access_attempt",
)
REQUIRED_BY_OP: dict[str, tuple[str, ...]] = {"invoke_agent": (), "chat": CHAT_ATTRS, "execute_tool": TOOL_ATTRS}


class MissingSpanAttributes(ValueError):
    pass


class Span:
    """Mutable while open; frozen into a ``SpanRecord`` on end."""

    def __init__(self, tracer: TrialTracer, name: str, op: Op, parent: str | None, attrs: dict[str, Any]) -> None:
        self._t = tracer
        self.name, self.op, self.parent_span_id = name, op, parent
        self.span_id = tracer.ids.span_id()
        self.start_ns = tracer.clock.now_ns()
        self.attributes: dict[str, Any] = {**tracer.base_attrs, "gen_ai.operation.name": op, **attrs}
        self.events: list[SpanEvent] = []
        self.err: SpanError | None = None

    def set(self, key: str, value: Any) -> Span:
        self.attributes[key] = value
        return self

    def update(self, attrs: Mapping[str, Any]) -> Span:
        self.attributes.update(attrs)
        return self

    def event(self, name: str, attrs: Mapping[str, Any] | None = None, **kw: Any) -> Span:
        self.events.append(SpanEvent(name=name, ts_ns=self._t.clock.now_ns(), attributes={**(attrs or {}), **kw}))
        return self

    def error(self, source: str, type: str, message: str) -> Span:
        self.err = SpanError(source=source, type=type, message=message)
        return self


class TrialTracer:
    def __init__(
        self,
        writer: ChainedJsonlWriter,
        *,
        trace_id: str,
        clock: Clock,
        ids: IdSource,
        base_attrs: Mapping[str, Any],
    ) -> None:
        missing = [a for a in RUN_CONTEXT_ATTRS if a not in base_attrs]
        if missing:
            raise MissingSpanAttributes(f"base_attrs missing {missing}")
        self.writer, self.trace_id, self.clock, self.ids = writer, trace_id, clock, ids
        self.base_attrs = dict(base_attrs)
        self._stack: list[Span] = []

    @contextmanager
    def span(self, name: str, op: Op, attrs: Mapping[str, Any] | None = None, **kw: Any) -> Iterator[Span]:
        parent = self._stack[-1].span_id if self._stack else None
        s = Span(self, name, op, parent, {**(attrs or {}), **kw})
        self._stack.append(s)
        try:
            yield s
        except BaseException as e:
            if s.err is None:
                # exceptions may name their error source (BudgetExceeded -> "budget"); default "infra"
                s.error(getattr(e, "span_error_source", "infra"), type(e).__name__, str(e))
            self._end(s, check=False)
            raise
        self._end(s, check=True)

    def _end(self, s: Span, *, check: bool) -> None:
        self._stack.remove(s)
        missing = [a for a in REQUIRED_BY_OP[s.op] if a not in s.attributes] if check else []
        if missing:  # write the span as an error (no hole in the trace), then raise
            s.error("infra", "MissingSpanAttributes", f"missing {missing}")
        rec = SpanRecord(
            trace_id=self.trace_id,
            span_id=s.span_id,
            parent_span_id=s.parent_span_id,
            name=s.name,
            op=s.op,
            start_ns=s.start_ns,
            end_ns=self.clock.now_ns(),
            status="error" if s.err else "ok",
            error=s.err,
            attributes=s.attributes,
            events=s.events,
        )
        self.writer.append(rec.model_dump(mode="json"))
        if missing:
            raise MissingSpanAttributes(f"{s.op} span {s.name!r} missing {missing}")

    def close(self) -> ChainHead:
        if self._stack:
            raise RuntimeError(f"open spans at close: {[s.name for s in self._stack]}")
        return self.writer.close()
