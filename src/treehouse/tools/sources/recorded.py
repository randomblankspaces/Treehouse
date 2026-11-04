"""RecordedImagerySource: WindowResults replayed from a pixel-free recording (no pixels, no reads).

Rows are ``{"args": {scene_id, lon, lat, side_m, out_px, resampling}, "result": WindowResult}``. Used for
Nepal tonight: real scene ids and GSD, modelled bytes, ``synthetic: true``. The gateway attaches the
image block with ``bytes_=None`` because no pixels exist (OBS-B1).

Rows are checked when the source is built (judge D4) and a bad row raises ``ValueError``: every result must
say ``reader="recorded"`` and ``synthetic: true``, carry this source's ``source_id``, the ``scene_id`` its
args ask for (a scene on the allow-list), the card's pinned ETag for that scene (when ``etags`` is given;
a scene with no pinned ETag is refused) and the source licence (when ``license`` is given). A scene with
no known date is refused as ``not_available_as_of`` (fail closed, D13).
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
                 source_id: str = "recorded-imagery", etags: dict[str, str] | None = None,
                 license: str | None = None) -> None:
        self.source_id, self.allowed, self.scene_dates, self.as_of = source_id, set(allowed), scene_dates, as_of
        self.etags, self.license = etags, license
        self._by_key: dict[str, WindowResult] = {}
        for i, r in enumerate(rows):
            w = WindowResult.model_validate(r["result"])
            self._check_row(i, r["args"], w)
            self._by_key[args_key(**r["args"])] = w

    def _check_row(self, i: int, args: dict, w: WindowResult) -> None:
        def bad(msg: str) -> ValueError:
            return ValueError(f"recorded window row {i}: {msg}")
        if w.reader != "recorded":
            raise bad(f"reader is {w.reader!r}, not 'recorded'")
        if w.synthetic is not True:
            raise bad("a recorded window must be marked synthetic")
        if w.source_id != self.source_id:
            raise bad(f"source_id {w.source_id!r} is not {self.source_id!r}")
        if w.scene_id != args.get("scene_id"):
            raise bad(f"scene_id {w.scene_id!r} differs from the requested {args.get('scene_id')!r}")
        if w.scene_id not in self.allowed:
            raise bad(f"scene {w.scene_id} is not on the allow-list")
        if self.etags is not None and (self.etags.get(w.scene_id) is None or w.etag != self.etags[w.scene_id]):
            raise bad(f"etag {w.etag!r} is not the pinned ETag {self.etags.get(w.scene_id)!r}")
        if self.license is not None and w.license != self.license:
            raise bad(f"license {w.license!r} is not the source licence {self.license!r}")

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
        if when is None:
            return ToolError(code="not_available_as_of", message=f"scene {scene_id} has no known date (refused)")
        if when > self.as_of:
            return ToolError(code="not_available_as_of", message=f"scene {scene_id} is after as_of")
        hit = self._by_key.get(args_key(scene_id, lon, lat, side_m, out_px, resampling))
        if hit is None:
            return ToolError(code="no_coverage", message="no recorded window for these arguments")
        return hit
