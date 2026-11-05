"""GSI seamless aerial JPEG tiles for short-lived, model-facing Japan chips."""

from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.request
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from treehouse.canon import canonical_json

SOURCE = "GSI seamless aerial photo"
ATTRIBUTION = "出典：国土地理院 (GSI Japan) seamless aerial photographs"
LICENCE = "LicenseRef-gsi-japan-attribution"
URL = "https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg"
JAPAN_BBOX = (122.0, 20.0, 154.0, 46.0)
TARGET_GSD_M = 0.5
MAX_SIDE_M = 160.0
MAX_BYTES = 5_000_000
_USER_AGENT = "Treehouse/1.0 (research imagery classifier)"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
Fetcher = Callable[[str], bytes]


def _ground_resolution(lat: float, zoom: int) -> float:
    return 156543.03392804097 * math.cos(math.radians(lat)) / (2**zoom)


def _zoom(lat: float) -> int:
    return min(range(1, 23), key=lambda z: abs(_ground_resolution(lat, z) - TARGET_GSD_M))


def _tile(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    n = 2**zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return x, y


def _tile_request(lon: float, lat: float, side_m: float) -> tuple[int, int, int, str]:
    west, south, east, north = JAPAN_BBOX
    if not (west <= lon <= east and south <= lat <= north):
        raise ValueError(f"point ({lon}, {lat}) is outside Japan's supported bbox {JAPAN_BBOX}")
    if not 0 < side_m <= MAX_SIDE_M:
        raise ValueError(f"GSI chip side_m must be in (0, {MAX_SIDE_M:g}]")
    zoom = _zoom(lat)
    x, y = _tile(lon, lat, zoom)
    return zoom, x, y, URL.format(z=zoom, x=x, y=y)


def _provenance(lat: float, zoom: int, x: int, y: int, url: str, sha256: str, n_bytes: int) -> dict:
    return {
        "source": SOURCE,
        "attribution": ATTRIBUTION,
        "licence": LICENCE,
        "tile": {"z": zoom, "x": x, "y": y},
        "url": url,
        "gsd_m": _ground_resolution(lat, zoom),
        "sha256": sha256,
        "bytes": n_bytes,
    }


class GsiSeamlessPhotoSource:
    """Fetch one Web-Mercator XYZ tile containing a Japan point; never persists its bytes."""

    def __init__(
        self, fetcher: Fetcher | None = None, *, timeout_s: float = 15.0, max_bytes: int = MAX_BYTES
    ) -> None:
        self.timeout_s, self.max_bytes = timeout_s, max_bytes
        self.fetcher = fetcher or self._fetch

    def _fetch(self, url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(request, timeout=self.timeout_s) as response:  # noqa: S310 - fixed HTTPS host
            declared = response.headers.get("Content-Length")
            if declared is not None and int(declared) > self.max_bytes:
                raise ValueError(f"GSI tile exceeds {self.max_bytes} byte limit")
            data = response.read(self.max_bytes + 1)
        if len(data) > self.max_bytes:
            raise ValueError(f"GSI tile exceeds {self.max_bytes} byte limit")
        if not data:
            raise ValueError("GSI returned an empty tile")
        return data

    def chip(self, lon: float, lat: float, side_m: float) -> tuple[bytes, dict]:
        zoom, x, y, url = _tile_request(lon, lat, side_m)
        # shortcut: without a JPEG codec, return the containing tile for a <=160 m chip; do not stitch or crop.
        data = self.fetcher(url)
        if not isinstance(data, bytes) or not data:
            raise ValueError("GSI fetcher must return non-empty bytes")
        if len(data) > self.max_bytes:
            raise ValueError(f"GSI tile exceeds {self.max_bytes} byte limit")
        return data, _provenance(lat, zoom, x, y, url, hashlib.sha256(data).hexdigest(), len(data))


class RecordingGsiSeamlessPhotoSource(GsiSeamlessPhotoSource):
    """Fetch live tiles and append only their identity and retrieval metadata to a JSONL log."""

    def __init__(self, log_path: Path | str, fetcher: Fetcher | None = None, **kwargs) -> None:
        super().__init__(fetcher=fetcher, **kwargs)
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("x", encoding="utf-8"):
            pass

    def chip(self, lon: float, lat: float, side_m: float) -> tuple[bytes, dict]:
        data, provenance = super().chip(lon, lat, side_m)
        retrieved_at = datetime.now(UTC).isoformat()
        tile = provenance["tile"]
        entry = {
            "url": provenance["url"],
            "z": tile["z"],
            "x": tile["x"],
            "y": tile["y"],
            "sha256": provenance["sha256"],
            "bytes": provenance["bytes"],
            "retrieved_at": retrieved_at,
        }
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(canonical_json(entry) + "\n")
        return data, {**provenance, "retrieved_at": retrieved_at}


class ReplayGsiSeamlessPhotoSource:
    """Rebuild byte-less chips from a required pixel-free GSI JSONL log."""

    def __init__(self, log_path: Path | str) -> None:
        self.log_path = Path(log_path)
        if not self.log_path.is_file():
            raise ValueError(f"GSI replay log is not a file: {self.log_path}")
        self._entries: dict[str, deque[dict]] = defaultdict(deque)
        for line_number, line in enumerate(self.log_path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid GSI replay log JSON at line {line_number}") from exc
            required = {"url", "z", "x", "y", "sha256", "bytes", "retrieved_at"}
            if (not isinstance(entry, dict) or set(entry) != required
                    or not isinstance(entry["url"], str) or not _SHA256.fullmatch(str(entry["sha256"]))
                    or isinstance(entry["bytes"], bool) or not isinstance(entry["bytes"], int)
                    or entry["bytes"] <= 0 or not isinstance(entry["retrieved_at"], str)):
                raise ValueError(f"invalid GSI replay log entry at line {line_number}")
            self._entries[entry["url"]].append(entry)

    def chip(self, lon: float, lat: float, side_m: float) -> tuple[bytes, dict]:
        zoom, x, y, url = _tile_request(lon, lat, side_m)
        if not self._entries[url]:
            raise ValueError(f"GSI replay log has no remaining entry for {url}")
        entry = self._entries[url].popleft()
        if (entry["z"], entry["x"], entry["y"]) != (zoom, x, y):
            raise ValueError(f"GSI replay log tile coordinates do not match {url}")
        provenance = _provenance(lat, zoom, x, y, url, entry["sha256"], entry["bytes"])
        return b"", {**provenance, "retrieved_at": entry["retrieved_at"]}
