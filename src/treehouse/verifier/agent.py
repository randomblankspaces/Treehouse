"""ConverseVerifier (default) and StrandsVerifier (DEFENSE-BOOK #15).

Both take a ``BlindItem`` and nothing else from the worker side: the prompt is built from its fields, so a
worker label, confidence, reason or id cannot reach the verifier (M17). Both answer one JSON object
``{"answer": "yes" | "no" | "cannot_assess"}``; anything else is an abstention (``cannot_assess``).

- ``ConverseVerifier``: one tool-free call per item through ``chat_turn`` (chat span, cassette key
  ``("verifier", index, 0)``, spend, budget). Windows the item needs are fetched by the caller and passed as
  ``images``; lower variance, cheaper and replayable.
- ``StrandsVerifier``: a ``StrandsHarness`` run per item whose gateway exposes only the window-fetch tools
  (``WINDOW_TOOLS``); used only where the verifier must choose its own windows.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from treehouse.canon import canonical_json
from treehouse.gateway.base import Gateway
from treehouse.gateway.budget import BudgetGuard
from treehouse.harness.plain_loop import chat_turn, put_blob, text_of
from treehouse.harness.strands_harness import StrandsHarness
from treehouse.providers.base import ModelProvider
from treehouse.schemas.config import InferenceParams
from treehouse.schemas.model_io import Image, Message, ModelRequest, Text
from treehouse.schemas.sampling import BlindItem
from treehouse.schemas.verdicts import Answer, VerifierVerdict
from treehouse.trace.tracer import TrialTracer

WINDOW_TOOLS = frozenset({"imagery_window", "stac_search"})  # §3: AgentVerifier tools
ANSWERS = {"yes", "no", "cannot_assess"}
SYSTEM = ("You are an independent imagery verifier. Judge only what the imagery shows at the given location. "
          'Reply with exactly one JSON object: {"answer": "yes"} or {"answer": "no"} or '
          '{"answer": "cannot_assess"} when the imagery cannot settle it (cloud, resolution, no coverage).')
QUESTIONS = {"exists": "Is there a {d} at this location?",
             "damaged": "Is the {d} at this location damaged or destroyed?"}
_OBJ = re.compile(r"\{[^{}]*\}")


def blind_prompt(item: BlindItem) -> str:
    """The verifier's whole view of the unit: the BlindItem fields, nothing else."""
    q = QUESTIONS[item.question_id].format(d=item.object_definition)
    return f"{q}\nItem: {canonical_json(item)}"


def parse_answer(text: str) -> Answer:
    for m in _OBJ.finditer(text):
        try:
            a = json.loads(m.group(0)).get("answer")
        except (json.JSONDecodeError, AttributeError):
            continue
        if a in ANSWERS:
            return a
    return "cannot_assess"


class _KeySpy:
    """Remembers the last request key (VerifierVerdict.request_hash); forwards everything else."""

    def __init__(self, inner: ModelProvider) -> None:
        self.inner, self.last_key = inner, ""
        self.provider_name = inner.provider_name

    async def complete(self, req: ModelRequest, **kw: Any):
        self.last_key = req.key()
        return await self.inner.complete(req, **kw)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)


class ConverseVerifier:
    def __init__(self, *, model_id: str, params: InferenceParams, provider: ModelProvider, tracer: TrialTracer,
                 budget: BudgetGuard, config_hash: str, synthetic: bool,
                 blob_sink: Callable[[bytes], str] | None = None) -> None:
        self.model_id, self.params, self.provider, self.tracer, self.budget = model_id, params, provider, tracer, budget
        self.config_hash, self.synthetic, self.blob_sink = config_hash, synthetic, blob_sink

    async def verdict(self, item: BlindItem, *, index: int, created_seq: int,
                      images: tuple[Image, ...] = ()) -> VerifierVerdict:
        req = ModelRequest(model_id=self.model_id, system=SYSTEM, params=self.params, tools=[],
                           messages=[Message(role="user", content=[Text(text=blind_prompt(item)), *images])])
        resp = await chat_turn(req, provider=self.provider, tracer=self.tracer, budget=self.budget,
                               put=lambda b: put_blob(self.blob_sink, b), role="verifier", trial_index=index, turn=0)
        return VerifierVerdict(unit_id=item.unit_id, question_id=item.question_id, answer=parse_answer(text_of(resp)),
                               verifier_config_hash=self.config_hash, request_hash=req.key(), recorded=False,
                               synthetic=self.synthetic, created_seq=created_seq)


class StrandsVerifier:
    def __init__(self, *, model_id: str, params: InferenceParams, provider: ModelProvider, tracer: TrialTracer,
                 budget: BudgetGuard, config_hash: str, synthetic: bool, max_turns: int = 8,
                 blob_sink: Callable[[bytes], str] | None = None) -> None:
        self.harness = StrandsHarness(model_id=model_id, params=params, blob_sink=blob_sink)
        self.provider, self.tracer, self.budget, self.max_turns = _KeySpy(provider), tracer, budget, max_turns
        self.config_hash, self.synthetic = config_hash, synthetic

    async def verdict(self, item: BlindItem, *, index: int, created_seq: int, gateway: Gateway) -> VerifierVerdict:
        extra = {s.name for s in gateway.specs()} - WINDOW_TOOLS
        if extra:
            raise ValueError(f"verifier gateway exposes non-window tools {sorted(extra)}; build it with "
                             f"tools={sorted(WINDOW_TOOLS)}")
        res = await self.harness.run(system=SYSTEM, user=blind_prompt(item), provider=self.provider, gateway=gateway,
                                     tracer=self.tracer, budget=self.budget, max_turns=self.max_turns,
                                     role="verifier", trial_index=index)
        answer = parse_answer(res.final_text) if res.stop == "completed" else "cannot_assess"
        return VerifierVerdict(unit_id=item.unit_id, question_id=item.question_id, answer=answer,
                               verifier_config_hash=self.config_hash, request_hash=self.provider.last_key,
                               recorded=False, synthetic=self.synthetic, created_seq=created_seq)
