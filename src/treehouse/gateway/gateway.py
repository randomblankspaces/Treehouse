"""ToolGateway (§3): the only way a harness reaches tools. Every call, in order:

1. open an ``execute_tool`` span; 2. policy (``not_allowlisted``, ``forbidden_source`` with
``key_access_attempt``, ``as_of``) - a blocked call returns an is_error result, never raises;
3. budget (one tool call; raises BudgetExceeded so the harness stops); 4. ``call_tool`` on the in-process
MCP client (bad arguments come back as is_error); 5. re-check returned hrefs against the deny-list;
6. in verify mode compare with the tool cassette (``ToolDivergence``); 7. meter and write the result
blob; 8. inject ``result_id = r-{seq:04d}``; 9. for ``imagery_window`` attach ``Image(png, sha256,
bytes_)`` with bytes from the PixelCache when present, else ``bytes_=None`` (pixel-free).
"""

from __future__ import annotations

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


class ToolGateway:
    def __init__(self, servers: dict[str, MCPServer], policy: Policy, tracer: TrialTracer, budget: BudgetGuard,
                 meter: Meter, pixels: PixelCache, tool_cassette: ToolCassette | None = None,
                 mode: Literal["live", "verify"] = "live", as_of: datetime | None = None, store: Any = None,
                 *, ledger: ClaimLedger, license: str = "unknown") -> None:
        self.servers, self.policy, self.tracer, self.budget = servers, policy, tracer, budget
        self.meter, self.pixels, self.cassette, self.mode = meter, pixels, tool_cassette, mode
        self.as_of, self.store, self.ledger, self.license = as_of or policy.as_of, store, ledger, license
        self.seq = 0
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
        self._stack = AsyncExitStack()
        for name in sorted(self.servers):
            client = await self._stack.enter_async_context(Client(self.servers[name]))
            for tool in (await client.list_tools()).tools:
                self._catalog[tool.name] = (client, tool)
        return self

    async def __aexit__(self, *exc) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack, self._catalog = None, {}

    def specs(self) -> list[ToolSpec]:
        return [ToolSpec(name=n, description=t.description or "", input_schema=t.input_schema)
                for n, (_, t) in sorted(self._catalog.items())]

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
            self.ledger.span_id = span.span_id
            decision = self.policy.check(name, args)
            if decision.blocked:
                return self._blocked(span, rid, decision)
            try:
                self.budget.commit(self.budget.reserve(tool_calls=1))
            except BudgetExceeded as e:
                span.error("budget", "BudgetExceeded", str(e))
                raise
            status, payload, text = await self._invoke(name, args)
            hrefs = [s for s in iter_strings(payload) if s.startswith(URL_PREFIXES)]
            d2 = self.policy.check_strings(hrefs)
            if d2.blocked:
                return self._blocked(span, rid, d2)
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
            self.ledger.note_result(rid, status)
            span.update({"treehouse.tool.result_ref": ref, "treehouse.tool.bytes_read": nbytes})
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
        r = await client.call_tool(name, args)
        text = "".join(getattr(c, "text", "") for c in r.content)
        sc = r.structured_content
        out_props = set((tool.output_schema or {}).get("properties", {}))
        if isinstance(sc, dict) and out_props == {"result"} and set(sc) == {"result"}:
            sc = sc["result"]
        if r.is_error or sc is None:
            return "error", {"code": "bad_args" if r.is_error else "no_structured_content", "message": text}, text
        if set(sc) == {"code", "message"}:
            return "error", sc, ""
        return "success", sc, ""

    def _image(self, payload: dict, span) -> Image:
        sha = payload["pixel_sha256"]
        span.update({"treehouse.image.sha256": sha, "treehouse.scene.id": payload["scene_id"],
                     "treehouse.license.spdx": payload["license"]})
        return Image(format="png", sha256=sha, bytes_=self.pixels.get(sha))

    def _blocked(self, span, rid: str, d: Decision) -> ToolOutcome:
        ref = self._blob({"status": "blocked", "reason": d.reason, "detail": d.detail})
        span.update({"treehouse.tool.blocked": True, "treehouse.tool.block_reason": d.reason,
                     "treehouse.key_access_attempt": d.key_access_attempt, "treehouse.tool.result_ref": ref})
        span.error("policy", d.reason, d.message)
        self.meter.record(span.attributes["gen_ai.tool.name"], "blocked")
        self.ledger.note_result(rid, "blocked")
        return ToolOutcome(result_id=rid, status="blocked", content=[Text(text=f"{d.message} [result_id {rid}]")],
                           block_reason=d.reason)
