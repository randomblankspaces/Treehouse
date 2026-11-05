"""Offline Nagoya warehouse investigation through the Strands harness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from treehouse.cards import load_card
from treehouse.investigation import run_investigation
from treehouse.investigation.reasoning_rules import evaluate
from treehouse.paths import repo_root
from treehouse.providers.factories import bedrock_recording, replay
from treehouse.schemas.config import RunConfig
from treehouse.schemas.model_io import Json, Message, ModelResponse, Text, ToolResult, ToolUse, Usage
from treehouse.store.local import LocalStore
from treehouse.store.verify import verify

ROOT = repo_root()
CONFIGS = {
    "t1-nagoya-sonnet-strands.json": "t1-nagoya-warehouses.yaml",
    "t5-gifu-sonnet-strands.json": "t5-gifu-warehouses.yaml",
    "t1-bangladesh-sonnet-strands.json": "t1-bangladesh-warehouses.yaml",
}


class WarehouseScriptProvider:
    provider_name = "scripted-warehouse"

    def __init__(self) -> None:
        self.index = 0
        self.pending: tuple[str, str, dict] | None = None
        self.results: dict[str, dict] = {}
        self.requests = []
        self.used_chained_results = False

    def _collect_results(self, req) -> None:
        for message in req.messages:
            for block in message.content:
                if not isinstance(block, ToolResult):
                    continue
                payload = next((content.json_ for content in block.content if isinstance(content, Json)), None)
                if payload is not None:
                    self.results[block.tool_use_id] = payload

    def _prior(self, action_index: int) -> dict:
        payload = self.results[f"action-{action_index:02d}"]
        self.used_chained_results = True
        return payload

    def _action(self) -> tuple[str, dict]:
        if self.index == 0:
            return "submit_understanding", {
                "goal_restated": "Find warehouse and logistics buildings of about 1,600 m2 or larger.",
                "scope": "The full Nagoya task AOI, excluding factories, markets, and hangars.",
                "planned_data": ["AEF 10 m annual embeddings pooled to 160 m cells", "training examples"],
                "known_limits": ["10 m data may miss small warehouses and confuse large roof types"],
            }
        if self.index == 1:
            return "list_embedding_sources", {}
        if self.index == 2:
            return "build_index", {"source_id": "aef-10m-annual", "cell_size_m": 160, "year": 2024}
        if self.index == 3:
            return "get_examples", {"n": 10, "split": "train"}
        index_id = self._prior(2)["index_id"]
        examples = [item["example_id"] for item in self._prior(3)["examples"]]
        if self.index == 4:
            return "retrieve", {
                "index_id": index_id,
                "method": "few_shot",
                "k": 50,
                "example_ids": examples,
            }
        candidates = self._prior(4)["cells"]
        if self.index == 5:
            return "classify", {
                "index_id": index_id,
                "method": "linear_probe",
                "cell_ids": [item["cell_id"] for item in candidates],
                "example_ids": examples,
            }
        scores = self._prior(5)["scores"]
        if self.index == 6:
            return "aggregate", {
                "index_id": index_id,
                "scored_cells": scores,
                "threshold": 0.88,
                "merge_rule": "8-neighbour",
            }
        aggregate = self._prior(6)
        if self.index in (7, 8):
            site = aggregate["sites"][self.index - 7]
            return "record_claim", {
                "step_id": "inventory",
                "lon": site["lon"],
                "lat": site["lat"],
                "cls": "warehouse",
                "status": "present",
                "confidence": site["max_score"],
                "reason": f"Linear-probe aggregate site {site['site_id']} at 160 m cell scale.",
                "evidence_refs": [],
            }
        if self.index == 9:
            count = aggregate["count"]
            return "note_limitation", {
                "text": (
                    f"The model-derived count range is {count['low']} to {count['high']} sites; "
                    f"{aggregate['unreviewed_area_km2']} km2 in {aggregate['unreviewed_cell_count']} cells "
                    "was unreviewed, so the run cannot claim complete coverage."
                )
            }
        raise AssertionError(f"unexpected scripted action {self.index}")

    def _decision_refs(self) -> list[str]:
        if self.index == 0:
            return []
        previous = self.results.get(f"action-{self.index - 1:02d}")
        return [previous["result_id"]] if previous is not None else []

    async def complete(self, req, *, role, trial_index, turn):
        self.requests.append(req)
        self._collect_results(req)
        if self.pending is not None:
            tool, action_id, params = self.pending
            self.pending = None
            self.index += 1
            content, reason = [ToolUse(id=action_id, name=tool, input=params)], "tool_use"
        elif self.index == 10:
            content, reason = [Text(text="Finished the warehouse investigation.")], "end_turn"
        else:
            tool, params = self._action()
            action_id = f"action-{self.index:02d}"
            self.pending = (tool, action_id, params)
            decision = {
                "action_id": action_id,
                "tool": tool,
                "parameters": params,
                "rationale": (
                    "Use the 10 m AEF source at 160 m cells and carry forward observed tool results; "
                    "unreviewed areas and count uncertainty remain a limitation."
                ),
                "alternatives": [{"option": "stop", "reason": "would leave the AOI less reviewed"}],
                "confidence": 0.8,
                "evidence_refs": self._decision_refs(),
            }
            content, reason = [ToolUse(id=f"decision-{self.index:02d}", name="record_decision", input=decision)], "tool_use"
        return ModelResponse(
            message=Message(role="assistant", content=content),
            stop_reason=reason,
            usage=Usage(input_tokens=1, output_tokens=1),
            latency_ms=1,
            response_model_id="scripted-warehouse",
        )


def test_provider_factories_require_new_explicit_cassette_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TREEHOUSE_CASSETTE_OUT", raising=False)
    monkeypatch.delenv("TREEHOUSE_CASSETTE_IN", raising=False)
    with pytest.raises(ValueError, match="TREEHOUSE_CASSETTE_OUT is required"):
        bedrock_recording(card=None, config=None)
    with pytest.raises(ValueError, match="TREEHOUSE_CASSETTE_IN is required"):
        replay(card=None, config=None)

    existing = tmp_path / "existing.jsonl"
    existing.write_text("")
    monkeypatch.setenv("TREEHOUSE_CASSETTE_OUT", str(existing))
    with pytest.raises(ValueError, match="already exists"):
        bedrock_recording(card=None, config=None)


def test_provider_factories_construct_record_and_replay_without_network(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "record.jsonl"
    source = tmp_path / "replay.jsonl"
    source.write_text("")
    ledger = tmp_path / "spend.jsonl"
    monkeypatch.setenv("TREEHOUSE_CASSETTE_OUT", str(output))
    monkeypatch.setenv("TREEHOUSE_CASSETTE_IN", str(source))
    monkeypatch.setenv("TREEHOUSE_SPEND_LEDGER", str(ledger))

    recording = bedrock_recording(card=None, config=None)
    replaying = replay(card=None, config=None)

    assert recording.inner.region == "us-east-1"
    assert recording.inner.ledger.path == ledger
    assert recording.cassette.path == output and not output.exists()
    assert replaying.cassette.path == source


@pytest.mark.parametrize("config_name,card_name", CONFIGS.items())
def test_live_config_task_ref_matches_card(config_name: str, card_name: str) -> None:
    config = RunConfig.model_validate_json((ROOT / "fixtures/live/configs" / config_name).read_bytes())
    card = load_card(ROOT / "tasks" / card_name)
    assert config.task_ref == card.ref()


def test_nagoya_warehouse_run_seals_with_bound_decisions(tmp_path: Path) -> None:
    card = load_card(ROOT / "tasks/t1-nagoya-warehouses.yaml")
    live = RunConfig.model_validate_json(
        (ROOT / "fixtures/live/configs/t1-nagoya-sonnet-strands.json").read_bytes()
    )
    config = live.model_copy(
        update={
            "mode": "fake",
            "clock": "logical",
            "worker": live.worker.model_copy(update={"provider": "fake"}),
        }
    )
    store = LocalStore(tmp_path / "store")
    provider = WarehouseScriptProvider()

    outcome = run_investigation(store, card, config, provider, run_id="nagoya-strands-offline")

    assert outcome.trials[0].stop == "completed"
    assert provider.requests and provider.used_chained_results
    assert verify(store, "nagoya-strands-offline").ok
    run_dir = store.run_dir("nagoya-strands-offline")
    claims = [json.loads(line) for line in (run_dir / "trials/t-0.claims.jsonl").read_text().splitlines()]
    warehouse_claims = [claim for claim in claims if claim["cls"] == "warehouse"]
    assert len(warehouse_claims) >= 2
    sites = provider.results["action-06"]["sites"]
    assert [claim["geometry"]["coordinates"] for claim in warehouse_claims[:2]] == [
        [sites[0]["lon"], sites[0]["lat"]],
        [sites[1]["lon"], sites[1]["lat"]],
    ]
    ledger = json.loads((run_dir / "trials/t-0.investigation.json").read_text())
    assert ledger["actions"]
    assert all(action["status"] == "success" for action in ledger["actions"])
    assert all(action["decision_id"] is not None for action in ledger["actions"])
    assert all(action["block_reason"] != "missing_decision" for action in ledger["actions"])
    assert all(not decision["flags"] and decision["action"] is not None for decision in ledger["decisions"])
    notes = json.loads((run_dir / "trials/t-0.understanding.json").read_text())["limitations"]
    assert len(notes) == 1 and "count range" in notes[0]["text"] and "unreviewed" in notes[0]["text"]
    report = evaluate(ledger, card, asset_class="warehouse", claims=claims)
    assert not ({"RV1", "RV2", "RV4"} & set(report["summary"]["failed_rules"]))
