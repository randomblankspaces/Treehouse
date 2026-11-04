"""A vision classifier adapter over the same injected ModelProvider protocol."""

import json

from treehouse.canon import canonical_json
from treehouse.providers.base import ProviderError, require_pixels
from treehouse.schemas.config import InferenceParams
from treehouse.schemas.model_io import Message, ModelRequest, Text


class BuiltinVisionClassifier:
    def __init__(self, provider, model_id: str, params: InferenceParams | None = None):
        self.provider, self.model_id = provider, model_id
        self.params = params or InferenceParams(max_tokens=512, temperature=0)
        self.turn = 0

    async def classify(self, *, window, image, cls):
        request = ModelRequest(model_id=self.model_id, params=self.params,
                               system="Classify only the supplied imagery. Return JSON with label, confidence (0..1), "
                                      "and explanation. State uncertainty and scale limitations; never infer unseen objects.",
                               messages=[Message(role="user", content=[
                                   Text(text=canonical_json({"cls": cls, "window": window.model_dump(mode="json")})), image])])
        require_pixels(request)
        response = await self.provider.complete(request, role="classifier", trial_index=0, turn=self.turn)
        self.turn += 1
        text = "".join(b.text for b in response.message.content if isinstance(b, Text))
        try:
            result = json.loads(text)
            if not isinstance(result, dict):
                raise ValueError("classifier response must be an object")
        except (ValueError, TypeError) as cause:
            exc = ProviderError("classifier returned invalid JSON")
            exc.cost_usd = response.cost_usd
            exc.usage = response.usage
            raise exc from cause
        return {**result, "model_id": response.response_model_id,
                "usage": response.usage.model_dump(mode="json"), "cost_usd": response.cost_usd}


VisionClassifier = BuiltinVisionClassifier
