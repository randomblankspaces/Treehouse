"""Opt-in causal decisions around the existing gateway, never a replacement tool backend."""

from __future__ import annotations

import math
from typing import Annotated, Any, TypedDict

from mcp.server import MCPServer
from pydantic import Field

from treehouse.canon import canonical_json, sha256_bytes, sha256_json
from treehouse.gateway.policy import Decision
from treehouse.providers.base import pixel_free_json
from treehouse.schemas.base import Frozen
from treehouse.schemas.model_io import Image, Json, Reasoning, ToolUse
from treehouse.schemas.tools import ToolError, WindowResult


class DecisionReceipt(Frozen):
    decision_id: str
class Alternative(TypedDict):
    """Typed so the tool schema shows the model the required keys (live runs guessed e.g. "why_not")."""
    option: str
    reason: str


class ClassifierPrediction(Frozen):
    label: str
    confidence: float
    explanation: str
    model_id: str
    usage: dict | None
    cost_usd: float | None
    pricing: str
    usage_status: str
    cls: str
    evidence_refs: list[str]
    evidence_ref: str
    source: str = "model_estimated"
    tier: str = "MODEL-ESTIMATED"
    synthetic: bool


class InvestigationSession:
    system = ("You are a geospatial investigation agent. Choose your own strategy using the task and observations. "
              "Before each tool action, call record_decision with a new unique action_id label, the exact tool "
              "and the exact parameters you will then send, concise rationale, alternatives actually "
              "considered, and confidence; the decision binds to your next call with identical tool and "
              "parameters. "
              "Cite only prior successful result IDs. A decision is consumed by one action. "
              "Use record_claim to build the database; confidence is your own estimate. "
              "Explain uncertainty, data scale, gaps, revisions and stopping with note_limitation. "
              "Decision explanations are self-reports, not proof of hidden internal reasoning.")

    def __init__(self, card, ledger, pixels, budget, tracer, *, classifier=None, server_factory=None,
                 model_turns=None):
        self.card, self.ledger, self.pixels = card, ledger, pixels
        self.budget, self.tracer, self.classifier = budget, tracer, classifier
        self.server_factory = server_factory
        self.model_turns = model_turns if model_turns is not None else {}
        self.thinking_recorded = False
        self.decisions: list[dict] = []
        self.actions: list[dict] = []
        self.results: dict[str, dict] = {}
        self.windows: dict[str, tuple[WindowResult, Image]] = {}
        self.sequence = 0
        self.current_span = None
        self.attempted: set[str] = set()

    def task(self):
        c = self.card
        # Deliberate allowlist: no keying, key paths, grader notes or completeness masks.
        return canonical_json({"goal": c.goal, "aoi": c.aoi.model_dump(mode="json"),
                               "classes": {k: v.model_dump(mode="json") for k, v in c.classes.items()},
                               "steps": [{"step_id": s.step_id, "question_id": s.question_id,
                                          "statuses_allowed": s.statuses_allowed} for s in c.steps],
                               "time_window": [str(x) for x in c.time_window], "as_of": c.as_of.isoformat(),
                               "data": [{"source_id": d.source_id, "kind": d.kind,
                                         "item_ids": d.item_ids, "license": d.license} for d in c.data_allowlist],
                               "windows": c.windows.model_dump(mode="json"),
                               "budget": self.budget.budget.model_dump(mode="json"),
                               "synthetic": c.synthetic})

    def _account_classifier(self, usage, cost):
        """Validate each reported axis before committing it; invalid statistics never reduce spend."""
        if hasattr(usage, "model_dump"):
            usage = usage.model_dump(mode="json")
        axes = ("input_tokens", "output_tokens", "cache_read", "cache_write")
        valid_usage = usage is None or (isinstance(usage, dict) and all(
            isinstance(usage.get(k, 0), int) and not isinstance(usage.get(k, 0), bool)
            and usage.get(k, 0) >= 0 for k in axes))
        valid_cost = cost is None or (isinstance(cost, int | float) and not isinstance(cost, bool)
                                     and math.isfinite(cost) and cost >= 0)
        if valid_usage and usage is not None:
            tokens = sum(usage.get(k, 0) for k in axes)
            self.budget.commit(None, tokens=tokens)
            self.current_span.set("treehouse.classifier.tokens", tokens)
        if valid_cost and cost is not None:
            self.budget.commit(None, usd=cost)
            self.current_span.update({"treehouse.classifier.cost_usd": cost,
                                      "treehouse.classifier.pricing": "reported"})
        valid = valid_usage and valid_cost
        self.current_span.set("treehouse.classifier.accounting", "valid" if valid else "invalid")
        return usage, valid

    def before(self, span, name, args, rid, sequence):
        self.sequence, self.current_span = sequence, span
        if name == "record_decision":
            return None
        call_id = span.attributes["gen_ai.tool.call.id"]
        candidates = [d for d in self.decisions if d["action_id"] == call_id and not d["flags"]
                      and d["action"] is None]
        if not candidates:
            # Live models cannot know the ToolUse id Bedrock will assign, so an unused prior decision with the
            # identical tool and parameters binds instead (still one decision per action, before dispatch).
            want = sha256_json(args)
            candidates = [d for d in self.decisions if d["action"] is None and not d["flags"]
                          and d["tool"] == name and sha256_json(d["parameters"]) == want][:1]
        prior = call_id in self.attempted
        self.attempted.add(call_id)
        if prior or not candidates:
            return Decision(True, "missing_decision", "action requires an unused prior decision")
        d = candidates[0]
        if d["tool"] != name or sha256_json(d["parameters"]) != sha256_json(args):
            d["flags"].append("action_mismatch")
            return Decision(True, "decision_mismatch", "action tool or parameters differ from decision")
        span.set("treehouse.investigation.decision_id", d["decision_id"])
        # Binding occurs before dispatch, including budget and tool failures.
        d["action"] = {"span_id": span.span_id, "result_id": rid, "status": "pending", "tool": name}
        return None

    def observe(self, span, name, args, call_id, rid, sequence, outcome):
        status = outcome.status if outcome else ("budget" if span.err and span.err.source == "budget" else "error")
        payload = next((b.json_ for b in outcome.content if isinstance(b, Json)), {}) if outcome else {}
        action = {"action_id": call_id, "tool": name, "parameters": args, "span_id": span.span_id,
                  "result_id": rid, "sequence": sequence, "status": status,
                  "decision_id": span.attributes.get("treehouse.investigation.decision_id"),
                  "block_reason": outcome.block_reason if outcome else None}
        if name != "record_decision":
            self.attempted.add(call_id)
            self.actions.append(action)
        for d in self.decisions:
            if d["action"] and d["action"]["span_id"] == span.span_id:
                d["action"]["status"] = status
        self.results[rid] = {"status": status, "tool": name, "payload": payload, "sequence": sequence}
        if name == "imagery_window" and status == "success":
            image = next((b for b in outcome.content if isinstance(b, Image)), None)
            if image is not None:
                self.windows[rid] = (WindowResult.model_validate(payload), image)

    def servers(self, servers):
        if self.server_factory is not None:
            servers = self.server_factory(card=self.card, ledger=self.ledger, pixels=self.pixels,
                                          default_servers=servers)
        srv = MCPServer("investigation")

        @srv.tool()
        def record_decision(action_id: str, tool: str, parameters: dict[str, Any], rationale: str,
                            alternatives: list[Alternative],
                            confidence: Annotated[float, Field(ge=0, le=1)],
                            parent_id: str | None = None,
                            evidence_refs: list[str] | None = None) -> DecisionReceipt | ToolError:
            """Record a contemporaneous explanation and exact plan for one future tool action."""
            refs = evidence_refs or []
            flags = []
            if not action_id.strip() or not rationale.strip() or tool == "record_decision":
                flags.append("invalid_decision")
            if any(set(a) != {"option", "reason"} or not all(a.values()) for a in alternatives):
                flags.append("invalid_alternatives")
            if action_id in self.attempted or any(d["action_id"] == action_id for d in self.decisions):
                flags.append("reused_or_posthoc_action_id")
            if parent_id and not any(d["decision_id"] == parent_id and not d["flags"] for d in self.decisions):
                flags.append("unknown_parent")
            if any(r not in self.results or self.results[r]["status"] != "success" for r in refs):
                flags.append("unavailable_evidence")
            if self.tracer and self.current_span:
                span_id = self.current_span.span_id
            else:
                span_id = self.ledger.span_id
            response = self.model_turns.get(self.ledger.trial_id)
            reasoning = []
            if response is not None and self.current_span and any(
                    isinstance(b, ToolUse) and b.id == self.current_span.attributes["gen_ai.tool.call.id"]
                    for b in response.message.content):
                reasoning = [b.text for b in response.message.content if isinstance(b, Reasoning)]
            self.thinking_recorded |= bool(reasoning)
            d = {"decision_id": f"{self.ledger.trial_id}:d-{len(self.decisions) + 1:04d}",
                 "trial_id": self.ledger.trial_id, "action_id": action_id, "tool": tool,
                 "parameters": parameters, "rationale": rationale, "alternatives": alternatives,
                 "confidence": confidence, "parent_id": parent_id, "evidence_refs": refs,
                 "sequence": self.sequence, "span_id": span_id, "flags": flags, "action": None}
            if self.thinking_recorded:
                d.update(thinking_ref=sha256_bytes(pixel_free_json(response)) if reasoning else None,
                         thinking_text="\n".join(reasoning))
            self.decisions.append(d)
            if flags:
                return ToolError(code="invalid_decision", message=", ".join(flags))
            return DecisionReceipt(decision_id=d["decision_id"])

        @srv.tool()
        async def classify_window(result_id: str, cls: str) -> ClassifierPrediction | ToolError:
            """Classify a prior successful imagery window using the configured model; returns a model estimate."""
            if self.classifier is None:
                return ToolError(code="not_configured", message="no classifier configured")
            if result_id not in self.windows or cls not in self.card.classes:
                return ToolError(code="invalid_evidence", message="requires successful imagery and a task class")
            window, image = self.windows[result_id]
            if not image.bytes_:
                return ToolError(code="missing_pixels", message="classifier requires actual image bytes")
            self.budget.check()
            self.current_span.update({"treehouse.classifier.attempted": True,
                                      "treehouse.classifier.pricing": "unpriced"})
            try:
                result = await self.classifier.classify(window=window, image=image, cls=cls)
            except Exception as exc:
                # Do not expose trusted plugin internals or filesystem paths to the worker.
                self._account_classifier(getattr(exc, "usage", None), getattr(exc, "cost_usd", None))
                return ToolError(code="classifier_error", message="classifier failed; no successful evidence")
            usage, cost = result.get("usage"), result.get("cost_usd")
            usage, valid_accounting = self._account_classifier(usage, cost)
            if not valid_accounting:
                return ToolError(code="invalid_classifier_result", message="invalid classifier cost or token accounting")
            if self.current_span:
                self.current_span.set("treehouse.classifier.model_id", str(result.get("model_id", "")))
            confidence = result.get("confidence")
            if (not isinstance(confidence, int | float) or not math.isfinite(confidence)
                    or not 0 <= confidence <= 1 or not all(isinstance(result.get(k), str) and result[k]
                                                         for k in ("label", "explanation", "model_id"))):
                return ToolError(code="invalid_classifier_result", message="classifier returned invalid prediction")
            # Explicit fields only: plugins cannot smuggle pixels or reference data in arbitrary extra fields.
            return ClassifierPrediction(**{"label": result["label"], "confidence": confidence, "explanation": result["explanation"],
                    "model_id": result["model_id"], "usage": usage, "cost_usd": cost,
                    "pricing": "reported" if cost is not None else "unpriced",
                    "usage_status": "reported" if usage is not None else "unknown",
                    "cls": cls, "evidence_refs": [result_id], "evidence_ref": result_id,
                    "source": "model_estimated", "tier": "MODEL-ESTIMATED",
                    "synthetic": window.synthetic})

        return {**servers, "investigation": srv}

    def snapshot(self, result):
        return {"schema_version": "treehouse.investigation-ledger/1", "decisions": self.decisions,
                "actions": self.actions, "stop": result.stop, "stop_detail": result.detail}
