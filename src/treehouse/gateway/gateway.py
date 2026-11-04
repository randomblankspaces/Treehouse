"""ToolGateway (§3): the only way a harness reaches tools. Every call, in order:

1. open an ``execute_tool`` span; 2. policy (``not_allowlisted``, ``forbidden_source`` with
``key_access_attempt``, ``as_of``) - a blocked call returns an is_error result, never raises;
3. budget (one tool call; raises BudgetExceeded so the harness stops); 4. ``call_tool`` on the in-process
MCP client (bad arguments come back as is_error); 5. re-check returned hrefs against the deny-list;
6. in verify mode compare with the tool cassette (``ToolDivergence``); 7. meter and write the result
blob; 8. inject ``result_id = r-{seq:04d}``; 9. for ``imagery_window`` attach ``Image(png, sha256,
bytes_)`` with bytes from the PixelCache when present, else ``bytes_=None`` (pixel-free).

Judged review additions (P4 judge):
- Any exception from ``call_tool`` (transport, output-schema validation, a server bug) becomes an
  ``is_error`` outcome with code ``tool_crash`` and a ``tool`` span error; it never ends the trial (D1).
  MCP ``is_error`` results are ``bad_args`` only when they are argument-validation errors, else
  ``tool_crash`` (D10). Pydantic's doc URLs are stripped from those messages so digests and request keys do
  not move with a pydantic upgrade (D5f).
- ``Budget.bytes``: before each ``imagery_window`` the gateway refuses (BudgetExceeded) when bytes already
  spent reach the limit, so the overshoot is at most one window; bytes are committed after the call.
  Threshold events fired during a call are attached to its ``execute_tool`` span (D6).
- ``specs()`` lists only the card's ``tools_allowed`` plus *bait*: catalog tools that a ``tool``
  forbidden source names (the decoy ``key_lookup``), so a key-peeker can find it and be caught. A
  role-scoped ``tools=`` list replaces both (no bait) and blocks anything outside it as ``not_allowlisted``
  (D9). ``as_of`` given to the gateway is the policy's ``as_of`` (D8).
- Server-side ``not_available_as_of`` refusals are recorded as policy blocks (``block_reason="as_of"``),
  like policy ``as_of`` blocks (D13). Step 5 scans every returned string; a hit there sets
  ``treehouse.tool.result_tainted`` and not ``key_access_attempt`` (the agent did not ask for it) (D14).
- The tool cassette records and verifies blocked calls too, and a verify-mode exit checks it was fully
  consumed (D5). ``record_claim`` spans carry ``treehouse.claim.id`` and ``treehouse.evidence.refs`` (D22).
  A gateway serves one trial: entering it a second time raises (D24).
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Iterable
from contextlib import AsyncExitStack
from datetime import datetime
from typing import Any, Literal

from mcp.client import Client
from mcp.server import MCPServer

from treehouse.canon import canonical_json, sha256_bytes, sha256_json
from treehouse.gateway.base import ToolOutcome
from treehouse.gateway.budget import BudgetExceeded, BudgetGuard
from treehouse.gateway.meter import Meter
from treehouse.gateway.pixel_cache import PixelCache
from treehouse.gateway.policy import Decision, Policy, iter_strings
from treehouse.gateway.tool_cassette import ToolCassette
from treehouse.schemas.model_io import Image, Json, Text, ToolSpec
from treehouse.tools.claims import ClaimLedger
from treehouse.trace.tracer import TrialTracer

CLAIM_TOOLS = {"record_claim", "note_limitation", "submit_understanding"}
URL_PREFIXES = ("http://", "https://", "s3://", "file://")
_PYDANTIC_URL = re.compile(r"\s*For further information visit https?://errors\.pydantic\.dev/\S*")


def normalize_error_text(text: str) -> str:
    """Drop pydantic's version-bearing doc URLs from validation messages."""
    return _PYDANTIC_URL.sub("", text)


class ToolGateway:
    def __init__(self, servers: dict[str, MCPServer], policy: Policy, tracer: TrialTracer, budget: BudgetGuard,
                 meter: Meter, pixels: PixelCache, tool_cassette: ToolCassette | None = None,
                 mode: Literal["live", "verify"] = "live", as_of: datetime | None = None, store: Any = None,
                 *, ledger: ClaimLedger, license: str = "unknown", tools: Iterable[str] | None = None,
                 investigation: Any = None) -> None:
        if mode == "verify" and tool_cassette is None:
            raise ValueError("mode='verify' needs a tool_cassette")
        if as_of is not None:
            policy.as_of = as_of  # one as_of for policy date args (D8); servers get the same value from the runner
        self.servers, self.policy, self.tracer, self.budget = servers, policy, tracer, budget
        self.meter, self.pixels, self.cassette, self.mode = meter, pixels, tool_cassette, mode
        self.as_of, self.store, self.ledger, self.license = policy.as_of, store, ledger, license
        self.tools = None if tools is None else set(tools)
        self.seq = 0
        self.investigation = investigation
        self._entered = False
        self._stack: AsyncExitStack | None = None
        self._catalog: dict[str, tuple[Client, Any]] = {}

    @property
    def claims(self):
        return self.ledger.claims

    @property
    def limitations(self):
        return self.ledger.limitations

    @property
    def understanding(self):
        return self.ledger.understanding

    async def __aenter__(self) -> ToolGateway:
        if self._entered:
            raise RuntimeError("a ToolGateway serves one trial; build a new one (seq and ledger would carry over)")
        self._entered = True
        self._stack = AsyncExitStack()
        for name in sorted(self.servers):
            client = await self._stack.enter_async_context(Client(self.servers[name]))
            for tool in (await client.list_tools()).tools:
                self._catalog[tool.name] = (client, tool)
        return self

    async def __aexit__(self, exc_type, *exc) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack, self._catalog = None, {}
        if exc_type is None and self.mode == "verify" and self.cassette is not None:
            self.cassette.finish()

    def _bait(self, name: str) -> bool:
        return any(fs.kind == "tool" and fnmatch.fnmatchcase(name.casefold(), fs.pattern.casefold())
                   for fs in self.policy.forbidden)

    def visible_tools(self) -> list[str]:
        if self.tools is not None:
            return sorted(n for n in self._catalog if n in self.tools)
        return sorted(n for n in self._catalog if n in self.policy.allowed or self._bait(n))

    def specs(self) -> list[ToolSpec]:
        return [ToolSpec(name=n, description=t.description or "", input_schema=t.input_schema)
                for n in self.visible_tools() for t in [self._catalog[n][1]]]

    def _blob(self, payload: dict) -> str:
        data = canonical_json(payload).encode()
        if self.store is None:
            return sha256_bytes(data)
        return self.store.put_blob(data, media_type="application/json", license=self.license)

    async def call(self, name: str, args: dict[str, Any], *, call_id: str) -> ToolOutcome:
        self.seq += 1
        rid = f"r-{self.seq:04d}"
        args_hash = sha256_json(args)
        t0 = self.tracer.clock.now_ns()
        attrs = {"gen_ai.tool.name": name, "gen_ai.tool.call.id": call_id, "treehouse.tool.args_hash": args_hash,
                 "treehouse.tool.result_id": rid, "treehouse.tool.result_ref": "", "treehouse.tool.bytes_read": 0,
                 "treehouse.tool.blocked": False, "treehouse.tool.block_reason": "",
                 "treehouse.key_access_attempt": False}
        with self.tracer.span(f"execute_tool {name}", "execute_tool", attrs) as span:
            n_events = len(self.budget.events)
            outcome = None
            try:
                outcome = await self._call(span, name, args, rid, args_hash, t0)
                return outcome
            finally:
                if self.investigation is not None:
                    self.investigation.observe(span, name, args, call_id, rid, self.seq, outcome)
                for e in self.budget.events[n_events:]:
                    span.event(e["name"], axis=e["axis"], pct=e["pct"])

    async def _call(self, span, name: str, args: dict[str, Any], rid: str, args_hash: str, t0: int) -> ToolOutcome:
        self.ledger.span_id = span.span_id
        if self.investigation is not None:
            refused = self.investigation.before(span, name, args, rid, self.seq)
            if refused is not None:
                return self._blocked(span, rid, refused, args_hash)
        decision = self.policy.check(name, args)
        if not decision.blocked and self.tools is not None and name not in self.tools:
            decision = Decision(True, "not_allowlisted", name)
        if decision.blocked:
            return self._blocked(span, rid, decision, args_hash)
        try:
            if name == "imagery_window":
                lim = self.budget.limit("bytes")
                if lim is not None and self.budget.spent["bytes"] >= lim:
                    raise BudgetExceeded("bytes", lim, self.budget.spent["bytes"])
            self.budget.commit(self.budget.reserve(tool_calls=1))
        except BudgetExceeded as e:
            span.error("budget", "BudgetExceeded", str(e))
            raise
        status, payload, text = await self._invoke(name, args)
        d2 = self.policy.check_strings(list(iter_strings(payload)))
        if d2.blocked:
            span.set("treehouse.tool.result_tainted", True)
            return self._blocked(span, rid, Decision(True, d2.reason, f"returned by the tool: {d2.detail}"),
                                 args_hash)
        if status == "error" and payload.get("code") == "not_available_as_of":
            return self._blocked(span, rid, Decision(True, "as_of", payload.get("message", "")), args_hash)
        payload = {**payload, "result_id": rid}  # step 8 (fills WindowResult.result_id too)
        ref = self._blob({"status": status, "result": payload, "text": text})
        if self.cassette is not None:
            digest = sha256_json({"status": status, "result": payload, "text": text})
            (self.cassette.verify if self.mode == "verify" else self.cassette.record)(
                self.seq, name, args_hash, digest)
        nbytes = int(payload.get("bytes_read", 0)) if status == "success" else 0
        if nbytes:
            self.budget.commit(None, bytes=nbytes)
        latency = (self.tracer.clock.now_ns() - t0) // 1_000_000
        self.meter.record(name, status, bytes_read=nbytes, latency_ms=latency)
        self.ledger.note_result(rid, status, name)
        span.update({"treehouse.tool.result_ref": ref, "treehouse.tool.bytes_read": nbytes})
        if name == "record_claim" and status == "success":
            span.update({"treehouse.claim.id": payload.get("claim_id", ""),
                         "treehouse.evidence.refs": [r.get("result_id", "") for r in args.get("evidence_refs") or []
                                                     if isinstance(r, dict)]})
        content: list = [Json(json_=payload)]
        if status == "error":
            code = payload.get("code", "tool_error")
            msg = payload.get("message", text)
            content = [Text(text=f"error {code}: {msg}"), *content]
            span.error("tool", code, msg)
        if name == "imagery_window" and status == "success":
            content.append(self._image(payload, span))
        return ToolOutcome(result_id=rid, status=status, content=content, bytes_read=nbytes, latency_ms=latency)

    async def _invoke(self, name: str, args: dict[str, Any]) -> tuple[str, dict, str]:
        """(status, structured payload, text). Typed ToolErrors and MCP is_error both map to status error."""
        entry = self._catalog.get(name)
        if entry is None:
            return "error", {"code": "unknown_tool", "message": f"no tool named {name}"}, ""
        client, tool = entry
        try:
            r = await client.call_tool(name, args)
        except Exception as e:  # noqa: BLE001 - any tool/MCP failure is a typed tool error, never a crash (D1)
            msg = normalize_error_text(f"{type(e).__name__}: {e}")
            return "error", {"code": "tool_crash", "message": msg}, msg
        text = normalize_error_text("".join(getattr(c, "text", "") for c in r.content))
        sc = r.structured_content
        out_props = set((tool.output_schema or {}).get("properties", {}))
        if isinstance(sc, dict) and out_props == {"result"} and set(sc) == {"result"}:
            sc = sc["result"]
        if r.is_error:
            code = "bad_args" if re.search(r"validation errors? for \w+Arguments", text) else "tool_crash"
            return "error", {"code": code, "message": text}, text
        if sc is None:
            return "error", {"code": "no_structured_content", "message": text}, text
        if set(sc) == {"code", "message"}:
            return "error", sc, ""
        return "success", sc, ""

    def _image(self, payload: dict, span) -> Image:
        sha = payload["pixel_sha256"]
        span.update({"treehouse.image.sha256": sha, "treehouse.scene.id": payload["scene_id"],
                     "treehouse.license.spdx": payload["license"]})
        return Image(format="png", sha256=sha, bytes_=self.pixels.get(sha))

    def _blocked(self, span, rid: str, d: Decision, args_hash: str) -> ToolOutcome:
        body = {"status": "blocked", "reason": d.reason, "detail": d.detail}
        ref = self._blob(body)
        name = span.attributes["gen_ai.tool.name"]
        if self.cassette is not None:
            (self.cassette.verify if self.mode == "verify" else self.cassette.record)(
                self.seq, name, args_hash, sha256_json(body))
        span.update({"treehouse.tool.blocked": True, "treehouse.tool.block_reason": d.reason,
                     "treehouse.key_access_attempt": d.key_access_attempt, "treehouse.tool.result_ref": ref})
        span.error("policy", d.reason, d.message)
        self.meter.record(name, "blocked")
        self.ledger.note_result(rid, "blocked", name)
        return ToolOutcome(result_id=rid, status="blocked", content=[Text(text=f"{d.message} [result_id {rid}]")],
                           block_reason=d.reason)
