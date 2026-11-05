"""Bounded, anonymous LGND GeoParquet reads; pyarrow is loaded only on index().

Schema: https://source.coop/clay/lgnd-embeddings/monthly-aggregated/README.md
Only the footer and columns of AOI-intersecting row groups are read. The cap counts
all reads, including cached ranges, across all objects in an index operation.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import struct
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

import numpy as np

from treehouse.paths import repo_root
from treehouse.tools.sources.clay_lgnd import NATIVE_CELLS_M
from treehouse.tools.sources.embedding_source import BBox, CellIndex, pool_to_grid

BUCKET = "us-west-2.opendata.source.coop"
BASE = "clay/lgnd-embeddings/monthly-aggregated/model_version=v1.5/collection=sentinel-2-l2a/chip_size=1280m/dims=256/"
S3_HOST = f"https://{BUCKET}.s3.us-west-2.amazonaws.com"
DEFAULT_MAX_BYTES = 64 * 1024 * 1024


class _RangeReader(io.RawIOBase):
    """Seekable local/HTTPS object with an enforced read budget and immutable range cache."""

    def __init__(self, uri: str, *, max_bytes: int, cache_dir: Path):
        super().__init__()
        self.uri, self.max_bytes, self.cache_dir = uri, max_bytes, Path(cache_dir)
        self.bytes_read, self.position = 0, 0
        self.etag = self.version_id = None
        self.local = None
        if uri.startswith("s3://"):
            parsed = urlsplit(uri)
            if parsed.netloc != BUCKET:
                raise ValueError("LGND S3 objects must use the public Source Cooperative bucket")
            uri = S3_HOST + parsed.path
        self.url = uri
        if uri.startswith("https://"):
            with urlopen(Request(uri, method="HEAD"), timeout=30) as response:
                self.size = int(response.headers["Content-Length"])
                self.etag = response.headers.get("ETag")
                self.version_id = response.headers.get("x-amz-version-id")
            if not self.etag:
                raise ValueError("LGND HTTP object needs an ETag for consistent range reads")
        else:
            self.local = Path(uri).open("rb")
            self.size = os.fstat(self.local.fileno()).st_size

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        position = offset + (0 if whence == 0 else self.position if whence == 1 else self.size)
        if position < 0 or whence not in (0, 1, 2):
            raise ValueError("invalid seek")
        self.position = position
        return position

    def read(self, size=-1):
        size = max(0, self.size - self.position) if size is None or size < 0 else min(size, max(0, self.size - self.position))
        if self.bytes_read + size > self.max_bytes:
            raise ValueError(f"LGND byte cap ({self.max_bytes} bytes) exceeded; narrow the AOI or raise max_bytes")
        if not size:
            return b""
        if self.local:
            self.local.seek(self.position)
            data = self.local.read(size)
        else:
            end = self.position + size - 1
            key = hashlib.sha256(f"{self.uri}|{self.etag}|{self.version_id}|{self.position}|{end}".encode()).hexdigest()
            cached = self.cache_dir / key
            if cached.exists():
                with cached.open("rb") as stream:
                    data = stream.read(size)
            else:
                request = Request(self.url, headers={"Range": f"bytes={self.position}-{end}", "If-Match": self.etag})
                with urlopen(request, timeout=30) as response:
                    expected = f"bytes {self.position}-{end}/{self.size}"
                    if response.status != 206 or response.headers.get("Content-Range") != expected:
                        raise ValueError("LGND server did not honor the requested byte range")
                    if response.headers.get("ETag") != self.etag:
                        raise ValueError("LGND object changed during range read")
                    data = response.read(size)
                if len(data) == size:
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    with tempfile.NamedTemporaryFile(dir=self.cache_dir, delete=False) as stream:
                        temporary = Path(stream.name)
                        stream.write(data)
                    temporary.replace(cached)
        self.bytes_read += len(data)
        self.position += len(data)
        if len(data) != size:
            raise ValueError("truncated LGND object/cache range; remove the cached range and retry")
        return data

    def readinto(self, buffer):
        data = self.read(len(buffer))
        buffer[:len(data)] = data
        return len(data)

    def close(self):
        if self.local:
            self.local.close()
        super().close()


def _geohashes(bbox):
    # Two-character geohashes form a fixed 32 x 32 global grid.
    alphabet = "0123456789bcdefghjkmnpqrstuvwxyz"
    for code in range(1024):
        bounds = [[-180.0, 180.0], [-90.0, 90.0]]
        for bit in range(10):
            axis = bit % 2
            mid = sum(bounds[axis]) / 2
            bounds[axis][0 if code & (1 << (9 - bit)) else 1] = mid
        if _intersects((bounds[0][0], bounds[1][0], bounds[0][1], bounds[1][1]), bbox):
            yield alphabet[code // 32] + alphabet[code % 32]


def _intersects(box, aoi):
    return box[0] < aoi[2] and box[2] > aoi[0] and box[1] < aoi[3] and box[3] > aoi[1]


def _objects(bbox, year, month, max_bytes):
    """List only the AOI's gh2 partitions, anonymously; bound listing responses too."""
    uris, used = [], 0
    for geohash in _geohashes(bbox):
        prefix = f"{BASE}geohash={geohash}/year={year}/month={month:02d}/"
        token = None
        while True:
            params = {"list-type": "2", "prefix": prefix}
            if token:
                params["continuation-token"] = token
            with urlopen(S3_HOST + "/?" + urlencode(params), timeout=30) as response:
                remaining = max_bytes - used
                length = int(response.headers.get("Content-Length", 0))
                if remaining <= 0 or length > remaining:
                    raise ValueError("LGND byte cap exceeded during object listing")
                data = response.read(remaining)
                used += len(data)
            try:
                root = ET.fromstring(data)
            except ET.ParseError as exc:
                if len(data) == remaining:
                    raise ValueError("LGND byte cap exceeded during object listing") from exc
                raise
            uris.extend(f"s3://{BUCKET}/{node.text}" for node in root.findall(".//{*}Contents/{*}Key")
                        if node.text and node.text.endswith(".parquet"))
            token = root.findtext("{*}NextContinuationToken")
            if root.findtext("{*}IsTruncated") != "true":
                break
            if not token:
                raise ValueError("LGND listing truncated without a continuation token")
    return sorted(uris), used


def _intersecting_groups(parquet, bbox):
    for i in range(parquet.num_row_groups):
        group = parquet.metadata.row_group(i)
        stats = {group.column(j).path_in_schema: group.column(j).statistics for j in range(group.num_columns)}
        names = ("bbox.xmin", "bbox.ymin", "bbox.xmax", "bbox.ymax")
        if not all(stats.get(n) is not None and stats[n].has_min_max for n in names):
            raise ValueError("LGND GeoParquet requires bbox row-group statistics for bounded spatial reads")
        box = (stats[names[0]].min, stats[names[1]].min, stats[names[2]].max, stats[names[3]].max)
        if _intersects(box, bbox):
            yield i


class RealClayLgndSource:
    source_id = "lgnd-clay-embeddings"
    licence = "CC-BY-4.0"
    resolution_m = 10.0
    native_cell_m = 1280.0
    access = "real"

    def __init__(self, uri: str | Path | None = None, *, month: int = 4,
                 max_bytes: int = DEFAULT_MAX_BYTES, cache_dir: Path | None = None):
        self.uri = str(uri) if uri is not None else None
        if not 1 <= month <= 12 or max_bytes < 1:
            raise ValueError("LGND month must be 1..12 and max_bytes must be positive")
        self.month, self.max_bytes = month, max_bytes
        self.cache_dir = cache_dir if cache_dir is not None else repo_root() / ".cache" / "lgnd"

    def index(self, aoi_bbox: BBox, cell_size_m: float, year: int) -> CellIndex:
        if cell_size_m not in NATIVE_CELLS_M:
            raise ValueError(f"LGND precomputed cells are {NATIVE_CELLS_M} m only; got {cell_size_m:g}")
        if not all(math.isfinite(v) for v in aoi_bbox) or not (-180 <= aoi_bbox[0] < aoi_bbox[2] <= 180
                                                                            and -90 <= aoi_bbox[1] < aoi_bbox[3] <= 90):
            raise ValueError("LGND AOI must be a nonempty EPSG:4326 bbox without antimeridian crossing")
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise ValueError("real LGND access requires pyarrow; install treehouse[real]") from exc
        uris, used = ([self.uri], 0) if self.uri else _objects(aoi_bbox, year, self.month, self.max_bytes)
        points, vectors, scenes, dates, objects = [], [], set(), set(), []
        for uri in uris:
            with _RangeReader(uri, max_bytes=self.max_bytes - used, cache_dir=self.cache_dir) as reader:
                # Parse only the footer, avoiding ParquetFile's eager 64 KiB tail read.
                if reader.size < 12:
                    raise ValueError("invalid LGND Parquet file")
                reader.seek(-8, 2)
                tail = reader.read(8)
                length = struct.unpack("<I", tail[:4])[0]
                if tail[4:] != b"PAR1" or length > reader.size - 12:
                    raise ValueError("invalid LGND Parquet footer")
                reader.seek(-8 - length, 2)
                metadata = pq.read_metadata(pa.BufferReader(b"PAR1" + reader.read(length) + tail))
                parquet = pq.ParquetFile(reader, metadata=metadata, pre_buffer=False)
                if not {"bbox", "embedding", "stac_item_id", "datetime", "geometry"} <= set(parquet.schema_arrow.names):
                    raise ValueError("LGND GeoParquet is missing required footprint, embedding or scene columns")
                geo = json.loads((metadata.metadata or {}).get(b"geo", b"{}"))
                geometry = geo.get("columns", {}).get(geo.get("primary_column"), {})
                crs = geometry.get("crs", {"id": {"authority": "OGC", "code": "CRS84"}})
                crs_id = crs.get("id", {}) if isinstance(crs, dict) else {}
                if geometry.get("encoding") != "WKB" or (crs_id.get("authority"), str(crs_id.get("code"))) not in {
                    ("EPSG", "4326"), ("OGC", "CRS84")
                }:
                    raise ValueError("LGND requires GeoParquet WKB footprints in EPSG:4326/CRS84")
                for group in _intersecting_groups(parquet, aoi_bbox):
                    rows = parquet.read_row_group(group, columns=["bbox", "embedding", "stac_item_id", "datetime"],
                                                  use_threads=False).to_pylist()
                    for row in rows:
                        b = row["bbox"]
                        box = tuple(b[k] for k in ("xmin", "ymin", "xmax", "ymax"))
                        if not _intersects(box, aoi_bbox):
                            continue
                        date = row["datetime"]
                        if not isinstance(date, datetime):
                            raise ValueError("LGND datetime must be a non-null timestamp")
                        if date.year != year or date.month != self.month:
                            continue
                        vector = np.asarray(row["embedding"], dtype=np.float32)
                        if vector.shape != (256,) or not np.isfinite(vector).all() or not np.linalg.norm(vector):
                            raise ValueError("LGND embedding must contain 256 finite, nonzero float32 values")
                        # Keep footprint centres; clamp outside centres to retain intersecting edge cells.
                        centre = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
                        points.append(np.clip(centre, aoi_bbox[:2], np.nextafter(aoi_bbox[2:], aoi_bbox[:2])))
                        vectors.append(vector)
                        scenes.add(row["stac_item_id"])
                        dates.add(date.date().isoformat())
                used += reader.bytes_read
                object_uri = uri if "://" in uri else Path(uri).resolve().as_uri()
                objects.append({"uri": object_uri, "etag": reader.etag, "version_id": reader.version_id,
                                "bytes_read": reader.bytes_read})
        if not points:
            raise ValueError(f"no LGND cells intersect AOI for {year}-{self.month:02d}")
        xy = np.asarray(points)
        ids, lon, lat, emb, grid = pool_to_grid(xy[:, 0], xy[:, 1], np.asarray(vectors), aoi_bbox, cell_size_m)
        return CellIndex(
            grid_id=f"{self.source_id}:real:{year}-{self.month:02d}:{cell_size_m:g}m:{aoi_bbox}",
            cell_size_m=cell_size_m, crs="EPSG:4326", **grid, cell_ids=ids, lon=lon, lat=lat, emb=emb,
            source="LGND Clay v1.5 / Sentinel-2 L2A", source_id=self.source_id,
            date_range=(min(dates), max(dates)), resolution_m=self.resolution_m, licence=self.licence,
            cost_usd=0.0, synthetic=False,
            provenance={"access": "real", "object_uris": [o["uri"] for o in objects], "objects": objects,
                        "scene_ids": sorted(scenes), "months": [f"{year}-{self.month:02d}"],
                        "attribution": "LGND / Clay", "bytes_read": used})

