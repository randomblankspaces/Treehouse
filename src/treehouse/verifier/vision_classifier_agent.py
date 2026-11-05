"""Budget-bounded vision classification through Treehouse's injected ModelProvider path.

A direct, single model request per cell is deliberate: classification has no tools or iterative decisions, so a
Strands agent loop would add machinery without changing the provider, spend-ledger, or cassette boundary.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable

from treehouse.assets import AssetClasses
from treehouse.canon import canonical_json
from treehouse.schemas.config import InferenceParams
from treehouse.schemas.model_io import Image, Message, ModelRequest, Text

MAX_CELLS = 20
_OBJ = re.compile(r"\{[^{}]*\}")
ChipFn = Callable[[float, float, float], tuple[bytes, dict]]


def _parse(text: str) -> tuple[str, float, str] | str:
    for match in _OBJ.finditer(text):
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            continue
        label, confidence, explanation = value.get("label"), value.get("confidence"), value.get("explanation")
        if label not in ("present", "absent"):
            continue
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            continue
        confidence = float(confidence)
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            continue
        if not isinstance(explanation, str) or not explanation.strip():
            continue
        return label, confidence, explanation.strip()
    return "invalid model response: expected JSON with label present|absent, confidence 0..1, and explanation"


class VisionSubagent:
    def __init__(
        self, provider, model_id: str, registry: AssetClasses | None = None, cls: str = "warehouse"
    ) -> None:
        self.provider, self.model_id = provider, model_id
        self.registry, self.cls = registry or AssetClasses.load(), cls
        self.definition = self.registry.get(cls)
        self.params = InferenceParams(max_tokens=512, temperature=0)

    async def classify_cells(self, cells: list[dict], chip_fn: ChipFn) -> list[dict]:
        if len(cells) > MAX_CELLS:
            raise ValueError(f"vision_subagent accepts at most {MAX_CELLS} cells per call")
        results = []
        for index, cell in enumerate(cells):
            jpeg, imagery = chip_fn(float(cell["lon"]), float(cell["lat"]), self.definition.cell_size_m)
            prompt = canonical_json(
                {
                    "cell_id": str(cell["cell_id"]),
                    "class": self.cls,
                    "positive_definition": self.definition.positive,
                    "negative_definitions": self.definition.negative,
                    "instruction": (
                        "Classify only the supplied aerial image. Reply with exactly one JSON object: "
                        '{"label":"present|absent","confidence":0.0,"explanation":"brief visual evidence"}. '
                        "Confidence is confidence in the chosen label. Do not infer unseen objects."
                    ),
                }
            )
            # JPEG decoding is intentionally left to Bedrock; the encoded-byte digest gives this transient image
            # a stable request identity without adding an image-codec dependency.
            image = Image(format="jpeg", sha256="sha256:" + hashlib.sha256(jpeg).hexdigest(), bytes_=jpeg)
            request = ModelRequest(
                model_id=self.model_id,
                params=self.params,
                system=(
                    "You are an aerial-imagery classifier. Use the supplied class definitions and image only. "
                    "Return strict JSON and state the visible evidence briefly."
                ),
                messages=[Message(role="user", content=[Text(text=prompt), image])],
            )
            response = await self.provider.complete(request, role="classifier", trial_index=index, turn=0)
            text = "".join(block.text for block in response.message.content if isinstance(block, Text))
            parsed = _parse(text)
            common = {
                "cell_id": str(cell["cell_id"]),
                "model_id": response.response_model_id,
                "usage": response.usage.model_dump(mode="json"),
                "cost_usd": response.cost_usd,
                "imagery": imagery,
            }
            if isinstance(parsed, str):
                results.append({**common, "score": None, "label": None, "explanation": parsed})
                continue
            label, confidence, explanation = parsed
            score = confidence if label == "present" else 1.0 - confidence
            results.append({**common, "score": score, "label": label, "explanation": explanation})
        return results
