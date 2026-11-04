"""Actual vision adapter injection, metering, and unknown price handling."""
import json

import pytest
from test_classifier_boundary import ImageThenClassify

from treehouse.providers.base import iter_images
from treehouse.schemas.config import InferenceParams
from treehouse.schemas.model_io import Message, ModelResponse, Text, Usage


class VisionProvider:
    provider_name = "independent-injected-vision"

    def __init__(self, cost):
        self.cost = cost
        self.requests = []

    async def complete(self, req, *, role, trial_index, turn):
        self.requests.append(req)
        answer = {"label": "present", "confidence": .62, "explanation": "test output"}
        return ModelResponse(message=Message(role="assistant", content=[Text(text=json.dumps(answer))]),
                             stop_reason="end_turn", usage=Usage(input_tokens=13, output_tokens=7),
                             latency_ms=2, response_model_id="test-vision-model", cost_usd=self.cost)


@pytest.mark.parametrize("cost", [.004, None])
def test_vision_adapter_calls_injected_model_and_reports_actual_or_unpriced_cost(context, cost):
    from treehouse.investigation import VisionClassifier
    store, card, config, execute, evaluate, _ = context
    vision = VisionProvider(cost)
    classifier = VisionClassifier(vision, "test-vision-model", InferenceParams(max_tokens=100))
    controller = ImageThenClassify()
    execute(store, card, config, controller, run_id="vision", classifier=classifier)
    assert len(vision.requests) == 1
    req = vision.requests[0]
    images = [image for _, image in iter_images(req.messages)]
    assert images and images[0].bytes_
    assert req.model_id == "test-vision-model"
    assert all(x not in req.model_dump_json() for x in ("keys/synth/", "hidden-a", "hidden-b"))
    report = evaluate(store, "vision")
    price = report["cost"]["numbers"]["classifier_usd"]
    assert price["panel"] == "cost" and price["tier"] == "MEASURED"
    if cost is None:
        assert price["value"] is None and "unpriced" in price["reasons"]
    else:
        assert price["value"] == pytest.approx(cost)
    pred = next(j for j in controller.observations if j.get("source") == "model_estimated")
    assert pred["evidence_ref"] == controller.window_id
    assert pred["model_id"] == "test-vision-model"
    assert pred["usage"]["input_tokens"] == 13 and pred["usage"]["output_tokens"] == 7
    assert pred["cost_usd"] == cost
