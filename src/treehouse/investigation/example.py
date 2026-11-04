"""Offline example controller: choices use observations, with no reference or world-generator imports.

The brightness heuristic is deliberately specific to synthetic grayscale scenes. It is a
transport/investigation example, not a trained detector or a geospatial accuracy baseline.
"""

import json

import numpy as np
from scipy.ndimage import center_of_mass, label

from treehouse.geo.geom import bbox_of
from treehouse.providers.base import decode_png
from treehouse.schemas.geo import Polygon
from treehouse.schemas.model_io import Image, Json, Message, ModelResponse, Text, ToolResult, ToolUse, Usage


class ObservationExample:
    provider_name = "offline-observation-example"

    def __init__(self):
        self.stage = 0
        self.pending = None
        self.next_id = 0
        self.parent = None

    def _plan(self, tool, args, rationale, refs=None):
        self.next_id += 1
        action_id = f"example-{self.next_id}"
        self.pending = ToolUse(id=action_id, name=tool, input=args)
        return ToolUse(id="plan-" + action_id, name="record_decision", input={
            "action_id": action_id, "tool": tool, "parameters": args, "rationale": rationale,
            "alternatives": [{"option": "stop now", "reason": "would leave this observation or limitation unrecorded"}],
            "confidence": .5, "evidence_refs": refs or [], "parent_id": self.parent})

    async def complete(self, req, *, role, trial_index, turn):
        if self.pending is not None:
            block, self.pending = self.pending, None
        else:
            task = json.loads(req.messages[0].content[0].text)
            observations = [(r, [b for b in r.content if isinstance(b, Json)])
                            for m in req.messages for r in m.content if isinstance(r, ToolResult)]
            payloads = [b.json_ for _, blocks in observations for b in blocks]
            self.parent = next((p["decision_id"] for p in reversed(payloads) if "decision_id" in p), None)
            x0, y0, x1, y1 = bbox_of(Polygon.model_validate(task["aoi"]).polygons())
            if self.stage == 0:
                block = self._plan("stac_search", {"aoi_bbox": [x0, y0, x1, y1],
                                   "start": task["time_window"][0], "end": task["time_window"][1]},
                                   "Inspect the available scene dates, cloud and coverage before choosing imagery.")
            elif self.stage == 1:
                searches = [p for p in payloads if p.get("scenes")]
                if not searches:
                    block = self._limitation("Search supplied no usable scenes; no detections are inferred.")
                    self.stage = 4
                else:
                    search = searches[-1]
                    scene = min(search["scenes"], key=lambda s: (s["phase"] != "pre", s["cloud_pct"],
                                                               -s["aoi_coverage_fraction"], s["scene_id"]))
                    block = self._plan("imagery_window", {"scene_id": scene["scene_id"],
                                       "lon": (x0 + x1) / 2, "lat": (y0 + y1) / 2,
                                       "side_m": min(500, task["windows"]["max_side_m"]),
                                       "out_px": min(512, task["windows"]["max_out_px"]), "resampling": "average"},
                                       "Inspect a bounded clear pre-event window; selected from actual scene metadata.",
                                       [search["result_id"]])
            elif self.stage == 2:
                window = next((p for p in reversed(payloads) if "pixel_sha256" in p), None)
                image = next((b for r, _ in reversed(observations) for b in r.content if isinstance(b, Image)), None)
                if window is None or image is None or not image.bytes_:
                    block = self._limitation("Imagery failed or has no pixels; no detections are inferred.")
                    self.stage = 4
                else:
                    pixels = decode_png(image.bytes_, image.format)
                    components, count = label((pixels > 175) & (pixels < 215))
                    sizes = np.bincount(components.ravel())
                    eligible = [i for i in range(1, count + 1) if 5 <= sizes[i] <= 250]
                    if not eligible:
                        block = self._limitation("The synthetic brightness heuristic found no candidate; this is not evidence of absence.")
                        self.stage = 4
                    else:
                        component = max(eligible, key=lambda i: sizes[i])
                        row, col = center_of_mass(components == component)
                        wx0, wy0, wx1, wy1 = window["bbox_read"]
                        lon = wx0 + (col + .5) / pixels.shape[1] * (wx1 - wx0)
                        lat = wy1 - (row + .5) / pixels.shape[0] * (wy1 - wy0)
                        cls = max(task["classes"], key=lambda c: task["classes"][c]["min_size_m"])
                        step = next(s for s in task["steps"] if s["question_id"] == "exists")
                        args = {"step_id": step["step_id"], "lon": lon, "lat": lat, "cls": cls,
                                "status": "present", "confidence": .5,
                                "reason": "Synthetic brightness component candidate; unvalidated illustrative classification.",
                                "evidence_refs": [{"result_id": window["result_id"], "role": "existence"}]}
                        block = self._plan("record_claim", args,
                                           "Record the pixel-derived candidate with low self-reported confidence for later independent checking.",
                                           [window["result_id"]])
            elif self.stage == 3:
                block = self._limitation("Only one bounded window inspected. The brightness heuristic is synthetic-specific and unvalidated; "
                                         "class, post-event status, other candidates and the remaining AOI require further investigation.")
            else:
                block = Text(text="Stopping the offline example with explicitly partial coverage.")
            self.stage += 1
        return ModelResponse(message=Message(role="assistant", content=[block]),
                             stop_reason="tool_use" if isinstance(block, ToolUse) else "end_turn",
                             usage=Usage(input_tokens=0, output_tokens=0), latency_ms=0,
                             response_model_id="offline-observation-example", cost_usd=0)

    def _limitation(self, text):
        return self._plan("note_limitation", {"text": text},
                          "Preserve observed limits and unresolved coverage instead of claiming an exhaustive inventory.")


def make_provider(*, card=None, config=None):
    """Trusted ``module:factory`` example; receives task/config, never grading references."""
    return ObservationExample()
