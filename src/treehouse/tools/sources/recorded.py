"""RecordedImagerySource: WindowResults replayed from a pixel-free recording (no pixels, no reads).

Rows are ``{"args": {scene_id, lon, lat, side_m, out_px, resampling}, "result": WindowResult}``. Used for
Nepal tonight: real scene ids and GSD, modelled bytes, ``synthetic: true``. The gateway attaches the
image block with ``bytes_=None`` because no pixels exist (OBS-B1).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from treehouse.canon import sha256_json
from treehouse.schemas.tools import ToolError, WindowResult


def args_key(scene_id: str, lon: float, lat: float, side_m: float, out_px: int, resampling: str) -> str:
    return sha256_json({"scene_id": scene_id, "lon": float(lon), "lat": float(lat), "side_m": float(side_m),
                        "out_px": int(out_px), "resampling": resampling})


class RecordedImagerySource:
    def __init__(self, rows: list[dict], *, allowed: list[str], scene_dates: dict[str, datetime], as_of: datetime,
                 source_id: str = "recorded-imagery") -> None:
        self.source_id, self.allowed, self.scene_dates, self.as_of = source_id, set(allowed), scene_dates, as_of
        self._by_key = {args_key(**r["args"]): WindowResult.model_validate(r["result"]) for r in rows}

    @classmethod
    def from_jsonl(cls, path: Path | str, **kw) -> RecordedImagerySource:
        p = Path(path)
        rows = [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.is_file() else []
        return cls(rows, **kw)

    def window(self, scene_id: str, lon: float, lat: float, side_m: float, out_px: int,
               resampling: str) -> WindowResult | ToolError:
        if scene_id not in self.allowed:
            return ToolError(code="not_allowed", message=f"scene {scene_id} is not on the allow-list")
        when = self.scene_dates.get(scene_id)
        if when is not None and when > self.as_of:
            return ToolError(code="not_available_as_of", message=f"scene {scene_id} is after as_of")
        hit = self._by_key.get(args_key(scene_id, lon, lat, side_m, out_px, resampling))
        if hit is None:
            return ToolError(code="no_coverage", message="no recorded window for these arguments")
        return hit
