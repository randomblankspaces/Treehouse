"""GSI seamless aerial tile selection and provenance. No network."""

from __future__ import annotations

import hashlib

import pytest

from treehouse.tools.sources.gsi import GsiSeamlessPhotoSource

NAGOYA = (136.885, 35.11)
BYTES = b"jpeg-bytes-for-test"


def test_chip_uses_expected_nagoya_xyz_tile_and_reports_provenance():
    urls = []

    def fetch(url):
        urls.append(url)
        return BYTES

    data, provenance = GsiSeamlessPhotoSource(fetcher=fetch).chip(*NAGOYA, 160)

    assert data == BYTES
    assert urls == ["https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/18/230748/103736.jpg"]
    assert provenance == {
        "source": "GSI seamless aerial photo",
        "attribution": "出典：国土地理院 (GSI Japan) seamless aerial photographs",
        "licence": "LicenseRef-gsi-japan-attribution",
        "tile": {"z": 18, "x": 230748, "y": 103736},
        "url": urls[0],
        "gsd_m": pytest.approx(0.4885098525),
        "sha256": hashlib.sha256(BYTES).hexdigest(),
        "bytes": len(BYTES),
    }


@pytest.mark.parametrize("lon,lat", [(121.99, 35), (154.01, 35), (136, 19.99), (136, 46.01)])
def test_chip_refuses_points_outside_japan(lon, lat):
    source = GsiSeamlessPhotoSource(fetcher=lambda _url: BYTES)

    with pytest.raises(ValueError, match="outside Japan"):
        source.chip(lon, lat, 160)


def test_chip_enforces_size_cap_for_injected_fetcher():
    source = GsiSeamlessPhotoSource(fetcher=lambda _url: b"too-large", max_bytes=3)

    with pytest.raises(ValueError, match="byte limit"):
        source.chip(*NAGOYA, 160)
