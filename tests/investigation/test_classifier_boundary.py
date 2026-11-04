"""Classifier contract with a genuine synthetic window and injected provider; no network."""
import json

from test_investigation_acceptance import planned

from treehouse.schemas.config import Budget
from treehouse.schemas.model_io import Image, Json, Message, ModelResponse, Text, ToolResult, ToolUse, Usage
from treehouse.schemas.tools import WindowResult


class ImageThenClassify:
    provider_name = "independent-vision-controller"

    def __init__(self):
        self.requests = []
        self.window_id = None
        self.observations = []

    async def complete(self, req, *, role, trial_index, turn):
        self.requests.append(req.model_dump(mode="json"))
        jsons = [b.json_ for m in req.messages for r in m.content if isinstance(r, ToolResult)
                 for b in r.content if isinstance(b, Json)]
        self.observations = jsons
        window = {"scene_id": "SYN-POST-A", "lon": .003, "lat": .003,
                  "side_m": 100, "out_px": 128, "resampling": "average"}
        if turn == 0:
            use = planned("image", "imagery_window", window)
        elif turn == 1:
            use = ("imagery_window", "image", window)
        elif turn == 2:
            result = next(j for j in jsons if j.get("scene_id") == "SYN-POST-A" and "pixel_sha256" in j)
            self.window_id = result["result_id"]
            params = {"result_id": self.window_id, "cls": "road_bridge"}
            use = planned("classify", "classify_window", params, refs=[self.window_id])
        elif turn == 3:
            use = ("classify_window", "classify", {"result_id": self.window_id, "cls": "road_bridge"})
        else:
            use = None
        content = [ToolUse(id=use[1], name=use[0], input=use[2])] if use else [Text(text="done")]
        return ModelResponse(message=Message(role="assistant", content=content),
                             stop_reason="tool_use" if use else "end_turn",
                             usage=Usage(input_tokens=1, output_tokens=1), latency_ms=1,
                             response_model_id="independent-controller")


class CapturingClassifier:
    def __init__(self, *, priced=True):
        self.calls = []
        self.priced = priced

    async def classify(self, *, window, image, cls):
        self.calls.append((window, image, cls))
        answer = {"label": "present", "confidence": .62, "explanation": "test classifier output",
                  "model_id": "independent-vision"}
        if self.priced:
            answer.update(usage={"input_tokens": 13, "output_tokens": 7}, cost_usd=.004)
        return answer


def test_classifier_receives_real_window_and_image_prediction_cites_source(context):
    store, card, config, execute, evaluate, _ = context
    model, classifier = ImageThenClassify(), CapturingClassifier()
    execute(store, card, config, model, run_id="classifier", classifier=classifier)
    assert len(classifier.calls) == 1
    window, image, cls = classifier.calls[0]
    assert isinstance(window, WindowResult) and window.result_id == model.window_id
    assert isinstance(image, Image) and image.bytes_ and image.sha256 == window.pixel_sha256
    assert cls == "road_bridge"
    assert all(secret not in json.dumps(model.requests) for secret in ("keys/synth/", "hidden-a", "hidden-b"))
    prediction = next(j for j in model.observations if j.get("label") == "present" and j.get("source") == "model_estimated")
    assert model.window_id in json.dumps(prediction)
    report = evaluate(store, "classifier")
    decision = next(d for d in report["decisions"] if d["action_id"] == "classify")
    assert model.window_id in decision["evidence_refs"] and decision["action"]["status"] == "success"


def test_missing_classifier_returns_explicit_failure_without_fake_prediction(context):
    store, card, config, execute, evaluate, _ = context
    model = ImageThenClassify()
    execute(store, card, config, model, run_id="no-classifier", classifier=None)
    assert not any(j.get("source") == "model_estimated" for j in model.observations)
    report = evaluate(store, "no-classifier")
    d = next(d for d in report["decisions"] if d["action_id"] == "classify")
    assert d["action"]["status"] != "success"
    assert report["process"]["limitations"]


def test_budget_exhaustion_prevents_classifier_call(context):
    store, card, config, execute, evaluate, _ = context
    config = config.model_copy(update={"budget": Budget(tokens=5)})
    model, classifier = ImageThenClassify(), CapturingClassifier()
    result = execute(store, card, config, model, run_id="bounded", classifier=classifier)
    assert result.trials[0].stop == "budget"
    assert classifier.calls == []
    assert evaluate(store, "bounded")["process"]["limitations"]
