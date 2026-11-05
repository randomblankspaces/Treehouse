"""Byte limits and HTTP range caching work without importing pyarrow."""
from __future__ import annotations

from io import BytesIO

import pytest


def test_local_range_reader_caps_cumulative_reads(tmp_path):
    from treehouse.tools.sources.clay_lgnd_real import _RangeReader

    path = tmp_path / "object"
    path.write_bytes(b"0123456789")
    with _RangeReader(str(path), max_bytes=5, cache_dir=tmp_path / "cache") as reader:
        assert reader.read(3) == b"012"
        reader.seek(-2, 2)
        assert reader.read(2) == b"89"
        assert reader.bytes_read == 5
        reader.seek(0)
        with pytest.raises(ValueError, match="byte cap"):
            reader.read(1)


def test_http_reader_caches_ranges_and_pins_etag(tmp_path, monkeypatch):
    from treehouse.tools.sources import clay_lgnd_real as real

    calls = []

    class Response(BytesIO):
        status = 206
        headers = {"Content-Length": "3", "Content-Range": "bytes 2-4/10", "ETag": '"etag"'}

    def open_request(request, **kwargs):
        calls.append(request)
        if request.get_method() == "HEAD":
            response = Response()
            response.headers = {"Content-Length": "10", "ETag": '"etag"'}
            return response
        assert request.get_header("Range") == "bytes=2-4"
        assert request.get_header("If-match") == '"etag"'
        return Response(b"234")

    monkeypatch.setattr(real, "urlopen", open_request)
    uri = "https://data.source.coop/clay/lgnd-embeddings/test.parquet"
    for _ in range(2):
        with real._RangeReader(uri, max_bytes=3, cache_dir=tmp_path) as reader:
            reader.seek(2)
            assert reader.read(3) == b"234"
            assert reader.bytes_read == 3
            assert reader.etag == '"etag"'
    assert [r.get_method() for r in calls] == ["HEAD", "GET", "HEAD"]
    assert list(tmp_path.iterdir())


def test_http_reader_rejects_server_ignoring_range(tmp_path, monkeypatch):
    from treehouse.tools.sources import clay_lgnd_real as real

    class Response(BytesIO):
        status = 200
        headers = {"Content-Length": "10", "ETag": '"etag"'}

    monkeypatch.setattr(real, "urlopen", lambda *a, **kw: Response(b"0123456789"))
    with real._RangeReader("https://data.source.coop/clay/lgnd-embeddings/test.parquet",
                           max_bytes=3, cache_dir=tmp_path) as reader:
        with pytest.raises(ValueError, match="range"):
            reader.read(3)


def test_nagoya_discovers_only_xn_month_partition_and_lists_objects(monkeypatch):
    from treehouse.tools.sources import clay_lgnd_real as real

    assert list(real._geohashes((136.82, 35.05, 136.92, 35.12))) == ["xn"]
    calls = []

    class Response(BytesIO):
        headers = {}

    def list_objects(url, **kwargs):
        calls.append(url)
        return Response(b'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                        b'<IsTruncated>false</IsTruncated><Contents><Key>clay/test.parquet</Key></Contents>'
                        b'</ListBucketResult>')

    monkeypatch.setattr(real, "urlopen", list_objects)
    uris, used = real._objects((136.82, 35.05, 136.92, 35.12), 2024, 4, 1000)
    assert uris == [f"s3://{real.BUCKET}/clay/test.parquet"]
    assert 0 < used < 1000
    assert len(calls) == 1
    assert "geohash%3Dxn%2Fyear%3D2024%2Fmonth%3D04%2F" in calls[0]
    with pytest.raises(ValueError, match="byte cap"):
        real._objects((136.82, 35.05, 136.92, 35.12), 2024, 4, 1)
