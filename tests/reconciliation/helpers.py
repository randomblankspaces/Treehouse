"""Independent offline fixtures; no production implementation or existing test imports."""
from __future__ import annotations

import hashlib
from pathlib import Path

from treehouse.cards import load_card
from treehouse.investigation import run_investigation
from treehouse.paths import repo_root
from treehouse.schemas.model_io import Message, ModelResponse, Text, ToolUse, Usage
from treehouse.service import demo_config

ROOT = repo_root()
ORIGIN = "http://127.0.0.1:8765"


class ScriptProvider:
    provider_name = "reconciliation-independent"

    def __init__(self, actions):
        self.actions = iter(actions)
        self.requests = []

    async def complete(self, req, *, role, trial_index, turn):
        self.requests.append(req.model_dump(mode="json"))
        action = next(self.actions, None)
        content = [Text(text="Finished independent fixture")]
        reason = "end_turn"
        if action is not None:
            tool, call_id, args = action
            content = [ToolUse(id=call_id, name=tool, input=args)]
            reason = "tool_use"
        return ModelResponse(message=Message(role="assistant", content=content), stop_reason=reason,
                             usage=Usage(input_tokens=1, output_tokens=1), latency_ms=1,
                             response_model_id="independent-reconciliation")


def planned(call_id, tool, parameters, refs=None):
    return [("record_decision", "plan-" + call_id,
             {"action_id": call_id, "tool": tool, "parameters": parameters,
              "rationale": "Inspect a deterministic acceptance location",
              "alternatives": [{"option": "stop", "reason": "would leave this location unchecked"}],
              "confidence": 0.6, "evidence_refs": refs or []}),
            (tool, call_id, parameters)]


def claim(call_id, coordinates, status="present", confidence=0.8):
    return planned(call_id, "record_claim",
                   {"step_id": "inventory", "lon": coordinates[0], "lat": coordinates[1],
                    "cls": "warehouse", "status": status, "confidence": confidence,
                    "reason": "Independent synthetic method fixture; no field observation", "evidence_refs": []})


def run_case(store, run_id, actions, *, synthetic=None):
    card = load_card(ROOT / "tasks/t1-nagoya-warehouses.yaml")
    if synthetic is not None:
        card = card.model_copy(update={"synthetic": synthetic,
                                      "synthetic_notice": "Independent synthetic acceptance fixture" if synthetic else None})
    config = demo_config({"policy": "good", "run_id": run_id}, card, mode="fake")
    config = config.model_copy(update={"max_turns": 40})
    provider = ScriptProvider(actions)
    run_investigation(store, card, config, provider, run_id=run_id)
    assert provider.requests, "test must exercise the injected provider"
    return card, provider


def hashes(root: Path):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file() and not path.is_symlink()}
