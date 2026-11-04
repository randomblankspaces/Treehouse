"""Amazon Bedrock AgentCore Evaluations as a *comparison signal* next to Treehouse's own checks.

A sealed run becomes one AgentCore session (``session.id`` = run id); each trial is one trace. Spans keep
their Treehouse attributes and are reshaped into the OTel span-log form AgentCore reads from ``aws/spans``.
The root span of each trial also carries the card and the trial's claims, and every tool span carries its
recorded result, so the Treehouse code-based evaluator (``lambda_evaluator``) can re-run R1/R2/R4 inside AWS.

Results are recorded append-only under ``comparisons/agentcore/`` in the store and never enter the panels.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from treehouse.aws.lambda_evaluator import CARD_ATTR, CLAIMS_ATTR, TOOL_PAYLOAD_ATTR, TOOL_STATUS_ATTR
from treehouse.canon import canonical_json, sha256_bytes
from treehouse.sealed import SealedRun
from treehouse.store.base import AlreadyExists
from treehouse.store.local import LocalStore

MAX_INPUT_BYTES = 6 * 1024 * 1024  # AgentCore truncates larger Lambda inputs; we refuse instead
SERVICE_NAME = "treehouse"


def session_spans(run: SealedRun, service_name: str = SERVICE_NAME) -> list[dict[str, Any]]:
    """OTel span-log records (``aws/spans`` shape) for every trial of ``run``.

    shortcut: span times are the run's own clock (logical in replays, so near 1970); if AgentCore rejects
    old timestamps, offset them by the manifest time.
    """
    card_json = canonical_json(run.card.model_dump(mode="json"))
    out: list[dict[str, Any]] = []
    for t in run.trials:
        calls = t.call_by_span()
        root = next((s for s in t.spans if s.parent_span_id is None), t.spans[0] if t.spans else None)
        for s in t.spans:
            attrs: dict[str, Any] = {**s.attributes, "session.id": run.run_id, "gen_ai.operation.name": s.op}
            if s is root:
                attrs[CARD_ATTR] = card_json
                attrs[CLAIMS_ATTR] = canonical_json([c.model_dump(mode="json") for c in t.claims])
            if (c := calls.get(s.span_id)) is not None:
                attrs[TOOL_STATUS_ATTR] = c.status
                attrs[TOOL_PAYLOAD_ATTR] = canonical_json(c.payload)
            out.append({
                "resource": {"attributes": {"service.name": service_name}},
                "scope": {"name": "treehouse.trace"},
                "traceId": s.trace_id, "spanId": s.span_id, "parentSpanId": s.parent_span_id or "",
                "name": s.name, "kind": "INTERNAL",
                "startTimeUnixNano": s.start_ns, "endTimeUnixNano": s.end_ns, "durationNano": s.end_ns - s.start_ns,
                "attributes": attrs,
                "status": {"code": "ERROR" if s.status == "error" else "OK"},
            })
    return out


def reference_inputs(run: SealedRun, expected_response: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Ground truth from the card. Session level: expected trajectory (``plans_tool`` items, in card order)
    and assertions (``must_notice`` and ``known_limits``). Trace level: ``expected_response`` maps trial
    trace ids to text, and is accepted only when some step is keyed (an unkeyed card has no ground truth)."""
    card = run.card
    session: dict[str, Any] = {"context": {"spanContext": {"sessionId": run.run_id}}}
    tools = [n.tool for n in card.must_notice if n.kind == "plans_tool" and n.tool]
    if tools:
        session["expectedTrajectory"] = {"toolNames": tools}
    text = {"mentions_any": "The agent mentions at least one of: {}.",
            "declares_limit": "The agent declares a limitation involving: {}."}
    assertions = [text[n.kind].format(", ".join(n.terms)) if n.kind in text else f"The agent uses the {n.tool} tool."
                  for n in card.must_notice]
    assertions += [f"The agent acknowledges this limitation: {lim}" for lim in card.known_limits]
    if assertions:
        session["assertions"] = [{"text": a} for a in assertions]
    out = [session]
    if expected_response:
        if all(s.keying.mode == "unkeyed" for s in card.steps):
            raise ValueError("expected_response given for an unkeyed card; unkeyed runs have no ground truth")
        traces = {s.trace_id for t in run.trials for s in t.spans}
        unknown = sorted(set(expected_response) - traces)
        if unknown:
            raise ValueError(f"expected_response names trace ids not in the run: {unknown}")
        out += [{"context": {"spanContext": {"sessionId": run.run_id, "traceId": tid}},
                 "expectedResponse": {"text": txt}} for tid, txt in sorted(expected_response.items())]
    return out


@dataclass(frozen=True)
class AgentCoreResult:
    """One ``evaluationResults[]`` entry; ``raw`` is AgentCore's JSON exactly as returned."""

    evaluator_id: str
    label: str | None
    value: float | None
    explanation: str | None
    error_code: str | None
    error_message: str | None
    ignored_reference_fields: list[str]
    trace_id: str | None
    raw: dict[str, Any] = field(repr=False)

    @property
    def ok(self) -> bool:
        return self.error_code is None

    @classmethod
    def from_raw(cls, r: dict[str, Any]) -> AgentCoreResult:
        return cls(evaluator_id=r["evaluatorId"], label=r.get("label"), value=r.get("value"),
                   explanation=r.get("explanation"), error_code=r.get("errorCode"),
                   error_message=r.get("errorMessage"),
                   ignored_reference_fields=list(r.get("ignoredReferenceInputFields", [])),
                   trace_id=r.get("context", {}).get("spanContext", {}).get("traceId"), raw=r)


def run_agentcore_eval(run: SealedRun, evaluators: list[str], *, client: Any = None,
                       references: list[dict[str, Any]] | None = None,
                       region: str = "us-east-1") -> list[AgentCoreResult]:
    """Call ``bedrock-agentcore`` ``Evaluate`` once per evaluator over the whole session.

    ``references`` defaults to ``reference_inputs(run)``; pass ``[]`` to run reference-free. API errors
    (throttling, access denied) propagate; per-result failures come back as results with ``error_code``."""
    spans = session_spans(run)
    size = len(json.dumps(spans).encode())
    if size > MAX_INPUT_BYTES:
        raise ValueError(f"session spans are {size} bytes; AgentCore accepts at most {MAX_INPUT_BYTES}")
    refs = reference_inputs(run) if references is None else references
    if client is None:
        import boto3  # lazy: the aws extra is optional

        client = boto3.client("bedrock-agentcore", region_name=region)
    out: list[AgentCoreResult] = []
    for ev in evaluators:
        kw: dict[str, Any] = {"evaluatorId": ev, "evaluationInput": {"sessionSpans": spans}}
        if refs:
            kw["evaluationReferenceInputs"] = refs
        resp = client.evaluate(**kw)
        out += [AgentCoreResult.from_raw(r) for r in resp["evaluationResults"]]
    return out


def record_results(store: LocalStore, run: SealedRun, evaluators: list[str], results: list[AgentCoreResult],
                   *, now: datetime | None = None) -> str:
    """Write one append-only comparison record; returns its store key. Outside ``runs/`` and ``evals/`` so
    ``treehouse verify`` and the panels never read it."""
    rec = {"kind": "agentcore_comparison", "run_id": run.run_id, "manifest_hash": run.manifest_ref,
           "evaluators": evaluators, "evaluated_at": (now or datetime.now(UTC)).isoformat(),
           "results": [r.raw for r in results]}
    body = canonical_json(rec).encode()
    key = f"comparisons/agentcore/{run.run_id}/{sha256_bytes(body).removeprefix('sha256:')}.json"
    try:
        store.put_once(key, body)
    except AlreadyExists:  # byte-identical record already there: content-addressed, so nothing to do
        pass
    return key
