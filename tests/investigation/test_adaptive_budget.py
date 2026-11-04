"""Supplemental independent tests: actual response-driven action and runtime boundaries."""
from test_investigation_acceptance import ScriptProvider, planned

from treehouse.schemas.config import Budget
from treehouse.schemas.model_io import Json, Message, ModelResponse, Text, ToolResult, ToolUse, Usage


class AdaptiveProvider(ScriptProvider):
    def __init__(self):
        super().__init__([])
        self.observed = None
        self.stage = 0

    async def complete(self, req, *, role, trial_index, turn):
        self.requests.append(req.model_dump(mode="json"))
        args = {"aoi_bbox": [0, 0, .0108, .0108], "start": "2026-07-01", "end": "2026-09-15"}
        if self.stage == 0:
            use = planned("search", "stac_search", args)
        elif self.stage == 1:
            use = ("stac_search", "search", args)
        elif self.stage == 2:
            payloads = [b.json_ for m in req.messages for result in m.content if isinstance(result, ToolResult)
                        for b in result.content if isinstance(b, Json) and "scenes" in b.json_]
            assert payloads and payloads[-1]["scenes"], "model must receive successful search observations"
            payload = payloads[-1]
            self.observed = (payload["result_id"], payload["scenes"][0]["scene_id"])
            use = planned("inspect", "scene_info", {"scene_id": self.observed[1]}, refs=[self.observed[0]])
        elif self.stage == 3:
            use = ("scene_info", "inspect", {"scene_id": self.observed[1]})
        else:
            use = None
        self.stage += 1
        content = [ToolUse(id=use[1], name=use[0], input=use[2])] if use else [Text(text="Finished")]
        return ModelResponse(message=Message(role="assistant", content=content),
                             stop_reason="tool_use" if use else "end_turn", usage=Usage(input_tokens=1, output_tokens=1),
                             latency_ms=1, response_model_id="independent-test")


def test_model_adapts_next_action_to_actual_previous_observation(context):
    store, card, config, execute, evaluate, _ = context
    provider = AdaptiveProvider()
    execute(store, card, config, provider, run_id="adaptive")
    report = evaluate(store, "adaptive")
    assert provider.observed is not None
    decision = next(d for d in report["decisions"] if d["action_id"] == "inspect")
    assert decision["parameters"]["scene_id"] == provider.observed[1]
    assert provider.observed[0] in decision["evidence_refs"]
    assert decision["action"]["status"] == "success"
    assert not decision["flags"]


def test_budget_stop_is_explicit_and_does_not_fabricate_action(context):
    store, card, config, execute, evaluate, _ = context
    config = config.model_copy(update={"budget": Budget(tool_calls=0)})
    args = {"aoi_bbox": [0, 0, .0108, .0108], "start": "2026-07-01", "end": "2026-09-15"}
    outcome = execute(store, card, config, ScriptProvider([planned("search", "stac_search", args),
                                                           ("stac_search", "search", args)]), run_id="budget")
    assert outcome.trials[0].stop == "budget"
    report = evaluate(store, "budget")
    assert report["process"]["limitations"]
    assert not any(d.get("action") and d["action"]["status"] == "success" for d in report["decisions"])
