"""AgentCore code-based evaluator: Treehouse's deterministic checks as one Lambda handler.

``evaluationLevel`` picks the check:
* ``TRACE``: R1 schema, R2 in-AOI and R4 evidence-in-trace over the claims of each target trace (trial).
* ``SESSION``: forbidden-source access (key-access attempts or ``forbidden_source`` blocks) and the card's
  cost, tool-call and byte limits over the whole session.

Input spans are the ones ``treehouse.aws.agentcore.session_spans`` writes; the card and claims ride on each
trial's root span. Import-light on purpose (pydantic plus pure Treehouse modules; no boto3, rasterio or
strands), so the Lambda bundle is ``src/treehouse`` plus pydantic.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from treehouse.checks.rules import r1_schema, r2_in_aoi, r4_evidence
from treehouse.schemas.claims import Claim
from treehouse.schemas.task import TaskCard
from treehouse.sealed import SealedRun, SealedTrial, ToolCall

CARD_ATTR, CLAIMS_ATTR = "treehouse.card", "treehouse.claims"
TOOL_STATUS_ATTR, TOOL_PAYLOAD_ATTR = "treehouse.tool.status", "treehouse.tool.payload"


class InvalidInput(ValueError):
    pass


def _err(code: str, msg: str) -> dict[str, str]:
    return {"errorCode": code, "errorMessage": msg}


def _spans_by_trace(event: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    spans = (event.get("evaluationInput") or {}).get("sessionSpans")
    if not isinstance(spans, list):
        raise InvalidInput("evaluationInput.sessionSpans must be a list")
    out: dict[str, list[dict[str, Any]]] = {}
    for s in spans:  # real sessions also hold log events; only records with a spanId are spans
        if isinstance(s, dict) and s.get("spanId") and s.get("traceId"):
            out.setdefault(s["traceId"], []).append(s)
    if not out:
        raise InvalidInput("no spans in evaluationInput.sessionSpans")
    return out


def _attrs(span: dict[str, Any]) -> dict[str, Any]:
    return span.get("attributes") or {}


def _card(by_trace: dict[str, list[dict[str, Any]]]) -> TaskCard:
    raw = next((_attrs(s)[CARD_ATTR] for spans in by_trace.values() for s in spans if CARD_ATTR in _attrs(s)), None)
    if raw is None:
        raise InvalidInput(f"no span carries {CARD_ATTR}; spans must come from treehouse.aws.agentcore")
    card = TaskCard.model_validate_json(raw)
    hashes = {_attrs(s).get("treehouse.task.hash") for spans in by_trace.values() for s in spans} - {None}
    if hashes and hashes != {card.card_hash()}:
        raise InvalidInput("treehouse.task.hash on the spans does not match the card they carry")
    return card


def _trial(trace_id: str, spans: list[dict[str, Any]]) -> SealedTrial:
    claims: list[Claim] = []
    calls: list[ToolCall] = []
    for s in spans:
        a = _attrs(s)
        if CLAIMS_ATTR in a:
            claims += [Claim.model_validate(c) for c in json.loads(a[CLAIMS_ATTR])]
        if a.get("gen_ai.operation.name") == "execute_tool" and TOOL_PAYLOAD_ATTR in a:
            rid = str(a.get("treehouse.tool.result_id", ""))
            calls.append(ToolCall(seq=int(rid[2:]) if rid.startswith("r-") else 0, result_id=rid,
                                  name=str(a.get("gen_ai.tool.name", "")), status=str(a.get(TOOL_STATUS_ATTR, "")),
                                  span_id=s["spanId"], payload=json.loads(a[TOOL_PAYLOAD_ATTR]),
                                  key_access_attempt=bool(a.get("treehouse.key_access_attempt"))))
    return SealedTrial(trial_id=trace_id, stop="", spans=[], claims=claims, calls=calls)


def rules_eval(by_trace: dict[str, list[dict[str, Any]]], targets: list[str] | None) -> dict[str, Any]:
    card = _card(by_trace)
    run = SealedRun(run_id="", manifest=None, card=card)  # R1/R2 read only run.card  # type: ignore[arg-type]
    fails: Counter[str] = Counter()
    n = n_pass = 0
    for tid in targets or sorted(by_trace):
        trial = _trial(tid, by_trace.get(tid, []))
        for c in trial.claims:
            res = [r1_schema(c, run), r2_in_aoi(c, run), r4_evidence(c, trial)]
            n += 1
            n_pass += all(r.result == "pass" for r in res)
            fails.update(f"{r.check_id}:{r.code}" for r in res if r.result == "fail")
    if n == 0:
        return {"label": "NO_CLAIMS", "explanation": "no claims in the target traces"}
    detail = ", ".join(f"{k}={v}" for k, v in sorted(fails.items())) or "none"
    return {"label": "PASS" if n_pass == n else "FAIL", "value": n_pass / n,
            "explanation": f"{n_pass}/{n} claims pass R1, R2 and R4; failures: {detail}"}


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def guard_eval(by_trace: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    card = _card(by_trace)
    spans = [s for ss in by_trace.values() for s in ss]
    tools = [_attrs(s) for s in spans if _attrs(s).get("gen_ai.operation.name") == "execute_tool"]
    forbidden = sum(bool(a.get("treehouse.key_access_attempt")) or a.get("treehouse.tool.block_reason")
                    == "forbidden_source" for a in tools)
    used = {"usd": sum(_num(_attrs(s).get("treehouse.cost.usd")) for s in spans),
            "tool_calls": len(tools), "bytes": sum(int(_num(a.get("treehouse.tool.bytes_read"))) for a in tools)}
    b = card.budget
    limits: dict[str, float] = {"bytes": card.windows.max_bytes_per_run}
    for k in ("usd", "tool_calls", "bytes") if b.enabled else ():
        if (lim := getattr(b, k)) is not None:
            limits[k] = min(lim, limits.get(k, lim))
    over = sorted(k for k, lim in limits.items() if used[k] > lim)
    ok = forbidden == 0 and not over
    return {"label": "PASS" if ok else "FAIL", "value": 1.0 if ok else 0.0,
            "explanation": f"forbidden-source accesses={forbidden}; usd={used['usd']:.4f}; "
                           f"tool_calls={used['tool_calls']}; bytes={used['bytes']}; over limit: "
                           f"{', '.join(over) or 'none'}"}


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Lambda entry point; returns ``{label, value?, explanation?}`` or ``{errorCode, errorMessage}``."""
    try:
        if not isinstance(event, dict) or event.get("schemaVersion") != "1.0":
            raise InvalidInput(f"unsupported schemaVersion {event.get('schemaVersion') if isinstance(event, dict) else None!r}")
        level = event.get("evaluationLevel")
        by_trace = _spans_by_trace(event)
        if level == "TRACE":
            return rules_eval(by_trace, (event.get("evaluationTarget") or {}).get("traceIds"))
        if level == "SESSION":
            return guard_eval(by_trace)
        raise InvalidInput(f"evaluationLevel {level!r} is not supported (TRACE or SESSION)")
    except (InvalidInput, ValueError, KeyError, TypeError) as e:  # pydantic ValidationError is a ValueError
        return _err("VALIDATION_FAILED", f"{type(e).__name__}: {e}"[:1000])
