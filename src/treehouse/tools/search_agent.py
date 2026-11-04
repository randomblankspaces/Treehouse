"""Embedding search agent: filter and nearest-neighbour tools over Clay embeddings, routed by size.

Routing rule (AWS-BLUEPRINT §2): up to ``LOCAL_MAX_VECTORS`` (1 M vectors, about 1.5 GB at 768-d float16)
stays local (numpy, free, replayable); above it filters go to Athena over Parquet on S3 and
nearest-neighbour search to S3 Vectors. The tools are an in-process MCP server (``make_search_server``), so
the agent (a ``StrandsHarness`` run with ``SEARCH_SYSTEM``) reaches them only through the ToolGateway: policy,
budget, meter, tool cassette and trace apply as for every other tool. The card (or a role ``tools=`` list)
must allow ``SEARCH_TOOLS``.

AWS backends take an injected boto3 client (Stubber-tested offline; the live twin is ``@live``).
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from typing import Any, Literal, Protocol

import numpy as np
from mcp.server import MCPServer

from treehouse.tools.clay import Embeddings

LOCAL_MAX_VECTORS = 1_000_000
SEARCH_TOOLS = frozenset({"embedding_filter", "embedding_nearest"})
SEARCH_SYSTEM = ("You search a large database of satellite-image embeddings. Use embedding_filter to list cells "
                 "in an area and embedding_nearest to find cells that look like a given cell. Report the cell ids "
                 "you found and the backend that answered.")
Bbox = tuple[float, float, float, float]
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")


def route(n_vectors: int) -> Literal["local", "aws"]:
    return "local" if n_vectors <= LOCAL_MAX_VECTORS else "aws"


class SearchError(ValueError):
    pass


class Backend(Protocol):
    name: str

    def filter(self, bbox: Bbox, limit: int) -> list[dict[str, Any]]: ...

    def nearest(self, bbox: Bbox, cell_id: str, k: int) -> list[dict[str, Any]]: ...


def _cell(cid: str, lon: float, lat: float, **kw: Any) -> dict[str, Any]:
    return {"cell_id": str(cid), "lon": float(lon), "lat": float(lat), **kw}


class LocalBackend:
    name = "local"

    def __init__(self, emb: Embeddings) -> None:
        self.emb = emb

    def _inside(self, b: Bbox) -> np.ndarray:
        e = self.emb
        return np.flatnonzero((e.lon >= b[0]) & (e.lon <= b[2]) & (e.lat >= b[1]) & (e.lat <= b[3]))

    def filter(self, bbox: Bbox, limit: int) -> list[dict[str, Any]]:
        e = self.emb
        idx = sorted(self._inside(bbox), key=lambda i: e.ids[i])[:limit]
        return [_cell(e.ids[i], e.lon[i], e.lat[i]) for i in idx]

    def nearest(self, bbox: Bbox, cell_id: str, k: int) -> list[dict[str, Any]]:
        e = self.emb
        hit = np.flatnonzero(e.ids == cell_id)
        if not hit.size:
            raise SearchError(f"unknown cell_id {cell_id}")
        inside = self._inside(bbox)
        sims = e.vec[inside] @ e.vec[int(hit[0])]
        order = sorted(range(len(inside)), key=lambda j: (-round(float(sims[j]), 6), e.ids[inside[j]]))[:k]
        return [_cell(e.ids[inside[j]], e.lon[inside[j]], e.lat[inside[j]], similarity=round(float(sims[j]), 6))
                for j in order]


class AthenaBackend:
    """Filters as parameterized SQL over a Parquet table (columns ``cell_id, lon, lat``)."""

    name = "athena"

    def __init__(self, client: Any, *, table: str, workgroup: str, max_polls: int = 120,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        if not _IDENT.match(table):
            raise SearchError(f"bad table name {table!r}")
        self.client, self.table, self.workgroup, self.max_polls, self.sleep = client, table, workgroup, max_polls, sleep

    def filter_request(self, bbox: Bbox, limit: int) -> dict[str, Any]:
        sql = (f"SELECT cell_id, lon, lat FROM {self.table} WHERE lon BETWEEN ? AND ? AND lat BETWEEN ? AND ? "
               f"ORDER BY cell_id LIMIT {int(limit)}")
        return {"QueryString": sql, "WorkGroup": self.workgroup,
                "ExecutionParameters": [repr(float(bbox[0])), repr(float(bbox[2])), repr(float(bbox[1])),
                                        repr(float(bbox[3]))]}

    def filter(self, bbox: Bbox, limit: int) -> list[dict[str, Any]]:
        qid = self.client.start_query_execution(**self.filter_request(bbox, limit))["QueryExecutionId"]
        for _ in range(self.max_polls):
            st = self.client.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
            if st["State"] == "SUCCEEDED":
                break
            if st["State"] in {"FAILED", "CANCELLED"}:
                raise SearchError(f"athena query {qid} {st['State']}: {st.get('StateChangeReason', '')}")
            self.sleep(1.0)
        else:
            raise SearchError(f"athena query {qid} did not finish in {self.max_polls} polls")
        out, token = [], None
        while True:
            page = self.client.get_query_results(QueryExecutionId=qid, **({"NextToken": token} if token else {}))
            for row in page["ResultSet"]["Rows"]:
                cid, lon, lat = (d.get("VarCharValue") for d in row["Data"])
                if cid != "cell_id":  # the header row
                    out.append(_cell(cid, float(lon), float(lat)))
            token = page.get("NextToken")
            if not token:
                return out

    def nearest(self, bbox: Bbox, cell_id: str, k: int) -> list[dict[str, Any]]:
        raise SearchError("athena answers filters; nearest-neighbour search goes to s3vectors")


class S3VectorsBackend:
    """Nearest neighbours from an S3 Vectors index (cosine; metadata ``lon``/``lat`` per vector)."""

    name = "s3vectors"

    def __init__(self, client: Any, *, bucket: str, index: str) -> None:
        self.client, self.bucket, self.index = client, bucket, index

    def nearest_request(self, bbox: Bbox, vector: list[float], k: int) -> dict[str, Any]:
        bounds = [{"lon": {"$gte": bbox[0]}}, {"lon": {"$lte": bbox[2]}},
                  {"lat": {"$gte": bbox[1]}}, {"lat": {"$lte": bbox[3]}}]
        return {"vectorBucketName": self.bucket, "indexName": self.index, "topK": int(k),
                "queryVector": {"float32": vector}, "filter": {"$and": bounds}, "returnMetadata": True,
                "returnDistance": True}

    def nearest(self, bbox: Bbox, cell_id: str, k: int) -> list[dict[str, Any]]:
        got = self.client.get_vectors(vectorBucketName=self.bucket, indexName=self.index, keys=[cell_id],
                                      returnData=True)["vectors"]
        if not got:
            raise SearchError(f"unknown cell_id {cell_id}")
        r = self.client.query_vectors(**self.nearest_request(bbox, got[0]["data"]["float32"], k))
        if r.get("distanceMetric") != "cosine":
            raise SearchError(f"index metric {r.get('distanceMetric')!r}; similarity needs cosine")
        return [_cell(v["key"], v["metadata"]["lon"], v["metadata"]["lat"], similarity=round(1 - v["distance"], 6))
                for v in r["vectors"]]

    def filter(self, bbox: Bbox, limit: int) -> list[dict[str, Any]]:
        raise SearchError("s3vectors answers nearest-neighbour search; filters go to athena")


class AwsBackend:
    """Above the threshold: filters on Athena, nearest neighbours on S3 Vectors."""

    name = "aws"

    def __init__(self, athena: AthenaBackend, vectors: S3VectorsBackend) -> None:
        self.filter, self.nearest = athena.filter, vectors.nearest


def pick_backend(n_vectors: int, *, local: Callable[[], Backend], aws: Callable[[], Backend]) -> Backend:
    """The routing rule; backends are built lazily so a local run never constructs an AWS client."""
    return local() if route(n_vectors) == "local" else aws()


def make_search_server(backend: Backend) -> MCPServer:
    srv = MCPServer("search")

    def run(fn: Callable[[], list[dict[str, Any]]]) -> dict[str, Any]:
        try:
            return {"backend": backend.name, "cells": fn()}
        except SearchError as e:
            return {"code": "bad_args", "message": str(e)}

    @srv.tool()
    def embedding_filter(aoi_bbox: tuple[float, float, float, float], limit: int = 100) -> dict[str, Any]:
        """Cells of the embedding database inside aoi_bbox (lon_min, lat_min, lon_max, lat_max), by cell id."""
        return run(lambda: backend.filter(aoi_bbox, max(1, min(limit, 1000))))

    @srv.tool()
    def embedding_nearest(aoi_bbox: tuple[float, float, float, float], cell_id: str, k: int = 10) -> dict[str, Any]:
        """Cells inside aoi_bbox whose embeddings are most similar (cosine) to the embedding of cell_id."""
        return run(lambda: backend.nearest(aoi_bbox, cell_id, max(1, min(k, 500))))

    return srv
