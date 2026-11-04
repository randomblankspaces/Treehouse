"""Search agent: the routing rule (local at or below 1 M vectors, AWS above), the local numpy backend, Stubber-
checked Athena and S3 Vectors requests, and a Strands search run whose tool calls go through the ToolGateway."""

from __future__ import annotations

import asyncio
import os

import boto3
import numpy as np
import pytest
from botocore.stub import Stubber

from treehouse.cards import load_card
from treehouse.clock import LogicalClock
from treehouse.gateway.budget import BudgetGuard
from treehouse.gateway.gateway import ToolGateway
from treehouse.gateway.meter import Meter
from treehouse.gateway.pixel_cache import PixelCache
from treehouse.gateway.policy import Policy
from treehouse.ids import IdSource
from treehouse.paths import tasks_root
from treehouse.providers.fake import FakeProvider
from treehouse.schemas.config import Budget, InferenceParams
from treehouse.tools.claims import ClaimLedger
from treehouse.tools.clay import Embeddings
from treehouse.tools.search_agent import (
    LOCAL_MAX_VECTORS,
    SEARCH_SYSTEM,
    SEARCH_TOOLS,
    AthenaBackend,
    AwsBackend,
    LocalBackend,
    S3VectorsBackend,
    SearchError,
    make_search_server,
    pick_backend,
    route,
)
from treehouse.trace.chain import ChainedJsonlWriter, read_chain
from treehouse.trace.tracer import TrialTracer

BBOX = (0.0, 0.0, 1.0, 1.0)


def emb() -> Embeddings:
    v = np.array([[1, 0], [0.9, 0.1], [0, 1], [1, 0]], dtype=np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    return Embeddings(ids=np.array(["c3", "c1", "c2", "far"]), lon=np.array([0.1, 0.2, 0.3, 5.0]),
                      lat=np.array([0.1, 0.2, 0.3, 5.0]), vec=v, meta={})


def test_routing_rule_threshold_and_lazy_backends():
    assert route(LOCAL_MAX_VECTORS) == "local" and route(LOCAL_MAX_VECTORS + 1) == "aws"

    def boom():
        raise AssertionError("an AWS client was built for a local-sized database")
    assert pick_backend(10, local=lambda: LocalBackend(emb()), aws=boom).name == "local"
    aws = pick_backend(2_000_000, local=boom, aws=lambda: AwsBackend(
        AthenaBackend(None, table="t", workgroup="w"), S3VectorsBackend(None, bucket="b", index="i")))
    assert aws.name == "aws"
    with pytest.raises(SearchError, match="athena"):  # nearest-neighbour goes to S3 Vectors, filters to Athena
        AthenaBackend(None, table="t", workgroup="w").nearest(BBOX, "c1", 1)


def test_local_backend_filter_and_nearest():
    b = LocalBackend(emb())
    assert [c["cell_id"] for c in b.filter(BBOX, 10)] == ["c1", "c2", "c3"]
    near = b.nearest(BBOX, "c3", 2)
    assert [c["cell_id"] for c in near] == ["c3", "c1"] and near[0]["similarity"] == 1.0
    with pytest.raises(SearchError):
        b.nearest(BBOX, "nope", 2)


def test_athena_filter_request_and_results():
    client = boto3.client("athena", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="x")
    b = AthenaBackend(client, table="clay.cells", workgroup="treehouse", sleep=lambda s: None)
    req = b.filter_request(BBOX, 50)
    assert req["ExecutionParameters"] == ["0.0", "1.0", "0.0", "1.0"] and "LIMIT 50" in req["QueryString"]
    with Stubber(client) as s:
        s.add_response("start_query_execution", {"QueryExecutionId": "q1"}, req)
        s.add_response("get_query_execution", {"QueryExecution": {"Status": {"State": "RUNNING"}}},
                       {"QueryExecutionId": "q1"})
        s.add_response("get_query_execution", {"QueryExecution": {"Status": {"State": "SUCCEEDED"}}},
                       {"QueryExecutionId": "q1"})
        rows = [["cell_id", "lon", "lat"], ["c1", "0.2", "0.2"], ["c2", "0.3", "0.3"]]
        s.add_response("get_query_results", {"ResultSet": {"Rows": [
            {"Data": [{"VarCharValue": x} for x in r]} for r in rows]}}, {"QueryExecutionId": "q1"})
        assert [c["cell_id"] for c in b.filter(BBOX, 50)] == ["c1", "c2"]
        s.assert_no_pending_responses()
    with pytest.raises(SearchError):
        AthenaBackend(client, table="x; DROP TABLE y", workgroup="w")


def test_s3vectors_nearest_request_and_results():
    client = boto3.client("s3vectors", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="x")
    b = S3VectorsBackend(client, bucket="clay-vectors", index="cells")
    with Stubber(client) as s:
        s.add_response("get_vectors", {"vectors": [{"key": "c3", "data": {"float32": [1.0, 0.0]}}]},
                       {"vectorBucketName": "clay-vectors", "indexName": "cells", "keys": ["c3"], "returnData": True})
        s.add_response("query_vectors", {"distanceMetric": "cosine", "vectors": [
            {"key": "c3", "distance": 0.0, "metadata": {"lon": 0.1, "lat": 0.1}},
            {"key": "c1", "distance": 0.006, "metadata": {"lon": 0.2, "lat": 0.2}}]},
            b.nearest_request(BBOX, [1.0, 0.0], 2))
        near = b.nearest(BBOX, "c3", 2)
        s.assert_no_pending_responses()
    assert [(c["cell_id"], c["similarity"]) for c in near] == [("c3", 1.0), ("c1", 0.994)]


def test_strands_search_agent_goes_through_the_gateway(tmp_path):
    pytest.importorskip("strands")
    from treehouse.harness.strands_harness import StrandsHarness

    card = load_card(tasks_root() / "synth-crossings-v1.yaml")
    ids, clock = IdSource(9), LogicalClock()
    base = {"treehouse.task.id": card.id, "treehouse.task.hash": card.card_hash(), "treehouse.run.id": "run-s",
            "treehouse.trial.id": "s-0", "treehouse.trial.index": 0, "treehouse.role": "search",
            "treehouse.config.hash": "sha256:" + "3" * 64}
    tracer = TrialTracer(ChainedJsonlWriter.for_trial(tmp_path / "s.jsonl", "s-0"), trace_id=ids.trace_id(),
                         clock=clock, ids=ids, base_attrs=base)
    policy = Policy(card)
    policy.allowed |= SEARCH_TOOLS  # the card for a search run allows them
    guard = BudgetGuard(Budget(), clock=clock)
    gw = ToolGateway({"search": make_search_server(LocalBackend(emb()))}, policy, tracer, guard, Meter(),
                     PixelCache(), ledger=ClaimLedger(card, run_id="run-s", trial_id="s-0"), tools=SEARCH_TOOLS)
    script = [{"respond": {"tool_use": [{"name": "embedding_nearest", "input": {"aoi_bbox": list(BBOX),
                                                                                "cell_id": "c3", "k": 2}}]}},
              {"expect": {"contains": ['"backend":"local"', "c1"]}, "respond": {"text": "c3 and c1 (local)"}}]

    async def go():
        async with gw:
            return await StrandsHarness(model_id="fake", params=InferenceParams(max_tokens=64)).run(
                system=SEARCH_SYSTEM, user="find cells like c3", provider=FakeProvider(script), gateway=gw,
                tracer=tracer, budget=guard, max_turns=4, role="search", trial_index=0)
    res = asyncio.run(go())
    tracer.close()
    assert res.stop == "completed" and res.final_text == "c3 and c1 (local)"
    ops = [x["rec"]["op"] for x in read_chain(tmp_path / "s.jsonl")]
    assert ops.count("execute_tool") == 1 and ops.count("chat") == 2


@pytest.mark.live
def test_live_s3vectors_nearest():  # Kiro: TREEHOUSE_LIVE=1, a real index named by the env vars below
    client = boto3.client("s3vectors", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    b = S3VectorsBackend(client, bucket=os.environ["TREEHOUSE_S3V_BUCKET"], index=os.environ["TREEHOUSE_S3V_INDEX"])
    assert b.nearest((-180, -90, 180, 90), os.environ["TREEHOUSE_S3V_KEY"], 3)
