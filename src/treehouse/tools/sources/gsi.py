"""GSI seamless aerial JPEG tiles for short-lived, model-facing Japan chips."""

from __future__ import annotations

import hashlib
import math
import urllib.request
from collections.abc import Callable

SOURCE = "GSI seamless aerial photo"
ATTRIBUTION = "出典：国土地理院 (GSI Japan) seamless aerial photographs"
LICENCE = "LicenseRef-gsi-japan-attribution"
URL = "https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg"
JAPAN_BBOX = (122.0, 20.0, 154.0, 46.0)
TARGET_GSD_M = 0.5
MAX_SIDE_M = 160.0
MAX_BYTES = 5_000_000
_USER_AGENT = "Treehouse/1.0 (research imagery classifier)"
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
        west, south, east, north = JAPAN_BBOX
        if not (west <= lon <= east and south <= lat <= north):
            raise ValueError(f"point ({lon}, {lat}) is outside Japan's supported bbox {JAPAN_BBOX}")
        if not 0 < side_m <= MAX_SIDE_M:
            raise ValueError(f"GSI chip side_m must be in (0, {MAX_SIDE_M:g}]")
        zoom = _zoom(lat)
        x, y = _tile(lon, lat, zoom)
        url = URL.format(z=zoom, x=x, y=y)
        # shortcut: without a JPEG codec, return the containing tile for a <=160 m chip; do not stitch or crop.
        data = self.fetcher(url)
        if not isinstance(data, bytes) or not data:
            raise ValueError("GSI fetcher must return non-empty bytes")
        if len(data) > self.max_bytes:
            raise ValueError(f"GSI tile exceeds {self.max_bytes} byte limit")
        return data, {
            "source": SOURCE,
            "attribution": ATTRIBUTION,
            "licence": LICENCE,
            "tile": {"z": zoom, "x": x, "y": y},
            "url": url,
            "gsd_m": _ground_resolution(lat, zoom),
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        }
