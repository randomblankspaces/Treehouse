"""ToolGateway and the five MCP servers (§3, §7 P4 acceptance; J4.1)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from gwrig import card, make_rig
from mcp.client import Client

from treehouse.gateway.pixel_cache import PixelCache
from treehouse.schemas.model_io import Image, Json, Text
from treehouse.synth import world
from treehouse.tools.claims import ClaimLedger
from treehouse.tools.imagery import ERROR_CODES
from treehouse.tools.servers import build_servers

X = world.crossings()[10]
AOI_BBOX = list(world.AOI)
GOOD_ARGS = {
    "stac_search": {"aoi_bbox": AOI_BBOX, "start": "2026-07-01", "end": "2026-09-15"},
    "scene_info": {"scene_id": "SYN-POST-A"},
    "imagery_window": {"scene_id": "SYN-POST-A", "lon": X.lon, "lat": X.lat, "side_m": 60, "out_px": 128},
    "clay_search": {"aoi_bbox": AOI_BBOX, "lon": X.lon, "lat": X.lat, "k": 5},
    "record_claim": {"step_id": "status", "lon": X.lon, "lat": X.lat, "cls": X.cls, "status": "intact",
                     "confidence": 0.9, "reason": "deck visible"},
    "note_limitation": {"text": "POST-B is cloudy"},
    "submit_understanding": {"goal_restated": "find crossings", "scope": "AOI"},
    "key_lookup": {"crossing_id": "X01"},
}


def run(rig, calls):
    async def go():
        async with rig.gateway as gw:
            return [await gw.call(n, a, call_id=f"tu-{i}") for i, (n, a) in enumerate(calls)]
    out = asyncio.run(go())
    rig.tracer.close()
    return out


def test_every_tool_returns_structured_content():
    servers = build_servers(card(), ledger=ClaimLedger(card(), run_id="r", trial_id="t"), pixels=PixelCache())

    async def go():
        seen = {}
        for srv in servers.values():
            async with Client(srv) as c:
                for tool in (await c.list_tools()).tools:
                    r = await c.call_tool(tool.name, GOOD_ARGS[tool.name])
                    seen[tool.name] = r
        return seen
    seen = asyncio.run(go())
    assert set(seen) == set(GOOD_ARGS)
    for name, r in seen.items():
        assert r.structured_content is not None, name
        assert not r.is_error, name


def test_result_ids_and_success_content(rig):
    names = ["submit_understanding", "stac_search", "clay_search", "imagery_window"]
    outs = run(rig, [(n, GOOD_ARGS[n]) for n in names])
    assert [o.result_id for o in outs] == ["r-0001", "r-0002", "r-0003", "r-0004"]
    assert all(o.status == "success" for o in outs)
    for o in outs:
        js = [c for c in o.content if isinstance(c, Json)]
        assert js and js[0].json_["result_id"] == o.result_id
    img = outs[3].content[-1]
    assert isinstance(img, Image) and img.bytes_ is not None
    win = outs[3].content[0].json_
    assert img.sha256 == win["pixel_sha256"] and win["result_id"] == "r-0004"
    spans = rig.spans()
    assert [s.attributes["treehouse.tool.result_id"] for s in spans] == ["r-0001", "r-0002", "r-0003", "r-0004"]
    assert spans[3].attributes["treehouse.tool.bytes_read"] == win["bytes_read"] > 0
    assert spans[3].attributes["treehouse.image.sha256"] == img.sha256
    assert rig.gateway.understanding.goal_restated == "find crossings"


def test_bad_args_are_is_error_not_raised(rig):
    outs = run(rig, [("imagery_window", {"scene_id": "SYN-POST-A", "lon": "east"}),
                     ("record_claim", {**GOOD_ARGS["record_claim"], "confidence": 3})])
    assert [o.status for o in outs] == ["error", "error"]
    assert "error bad_args" in outs[0].content[0].text
    spans = rig.spans()
    assert all(s.status == "error" and s.error.source == "tool" for s in spans)


def test_j4_1_tool_error_and_unknown_tool_logged(tmp_path):
    t = dict(card().model_dump())
    t["tools_allowed"] = [*t["tools_allowed"], "no_such_tool"]
    rig2 = make_rig(tmp_path / "u.jsonl", task=type(card()).model_validate(t))
    outs = run(rig2, [("imagery_window", {**GOOD_ARGS["imagery_window"], "scene_id": "SYN-POST-B", "lon": 0.0100}),
                      ("no_such_tool", {})])
    assert outs[0].status == "error" and outs[0].content[0].text.startswith("error no_coverage")
    assert outs[1].status == "error" and "unknown_tool" in outs[1].content[0].text
    spans = rig2.spans()
    assert [(s.error.source, s.error.type) for s in spans] == [("tool", "no_coverage"), ("tool", "unknown_tool")]
    assert rig2.gateway.meter.statuses["error"] == 2


FORBIDDEN = [
    ("tool", "key_lookup", {"crossing_id": "X01"}),
    ("path", "stac_search", {"aoi_bbox": AOI_BBOX, "start": "keys/synth/synth-crossings-v1.key.json", "end": "x"}),
    ("path-url", "scene_info", {"scene_id": "https://example.org/repo/keys/synth/x.json"}),
    ("host", "scene_info", {"scene_id": "https://overpass-api.de/api/interpreter"}),
    ("host-glob", "scene_info", {"scene_id": "https://tile.openstreetmap.org/1/1/1.png"}),
    ("url_prefix", "scene_info", {"scene_id": "https://planet.osm.example/dump/a"}),
    ("s3_prefix", "scene_info", {"scene_id": "s3://osm-pds/planet/x.orc"}),
    ("dataset_id", "clay_search", {"aoi_bbox": AOI_BBOX, "cell_id": "osm-bridges-2026"}),
    ("tool-glob", "osm_query", {}),
]


@pytest.mark.parametrize("label,tool,args", FORBIDDEN, ids=[f[0] for f in FORBIDDEN])
def test_every_forbidden_kind_is_blocked_with_a_span(tmp_path, label, tool, args):
    t = card("nepal-bhote-koshi-bridges").model_dump()
    t["forbidden_sources"] += [{"kind": "url_prefix", "pattern": "https://planet.osm.example/"},
                               {"kind": "s3_prefix", "pattern": "s3://osm-pds/"},
                               {"kind": "dataset_id", "pattern": "osm-*"}]
    task = type(card()).model_validate(t)
    rig = make_rig(tmp_path / "t.jsonl", task=task)
    (out,) = run(rig, [(tool, args)])
    assert out.status == "blocked" and out.block_reason == "forbidden_source"
    assert out.content[0].text.startswith("blocked by policy: forbidden_source")
    (span,) = rig.spans()
    a = span.attributes
    assert a["treehouse.tool.blocked"] is True and a["treehouse.key_access_attempt"] is True
    assert span.status == "error" and span.error.source == "policy"


def test_key_root_is_blocked_even_without_a_path_rule(tmp_path):
    from treehouse.paths import keys_root

    t = card().model_dump()
    t["forbidden_sources"] = [{"kind": "tool", "pattern": "key_lookup"}]
    rig = make_rig(tmp_path / "t.jsonl", task=type(card()).model_validate(t))
    (out,) = run(rig, [("scene_info", {"scene_id": str(keys_root() / "synth" / "x.json")})])
    assert out.status == "blocked" and rig.spans()[0].attributes["treehouse.key_access_attempt"] is True


def test_not_allowlisted(tmp_path):
    t = card().model_dump()
    t["tools_allowed"] = [x for x in t["tools_allowed"] if x != "clay_search"]
    rig2 = make_rig(tmp_path / "t.jsonl", task=type(card()).model_validate(t))
    (out,) = run(rig2, [("clay_search", GOOD_ARGS["clay_search"])])
    assert out.status == "blocked" and out.block_reason == "not_allowlisted"
    assert rig2.spans()[0].attributes["treehouse.key_access_attempt"] is False


def test_as_of_refusals(tmp_path):
    rig = make_rig(tmp_path / "t.jsonl", as_of=datetime(2026, 8, 29, tzinfo=UTC))
    outs = run(rig, [("stac_search", {"aoi_bbox": AOI_BBOX, "start": "2026-09-01", "end": "2026-09-10"}),
                     ("stac_search", GOOD_ARGS["stac_search"]),
                     ("imagery_window", GOOD_ARGS["imagery_window"])])
    assert outs[0].status == "blocked" and outs[0].block_reason == "as_of"
    res = outs[1].content[0].json_
    assert res["dropped_after_as_of"] == 2 and {s["scene_id"] for s in res["scenes"]} == {
        "SYN-PRE-1", "SYN-PRE-2", "SYN-POST-B"}
    # judge D13: the server-side as_of refusal is recorded as a policy block, like the policy one
    assert outs[2].status == "blocked" and outs[2].block_reason == "as_of"
    assert "not_available_as_of" not in outs[2].content[0].text or "as_of" in outs[2].content[0].text


def test_grounded_and_contaminated_claims(rig):
    claim = GOOD_ARGS["record_claim"]
    outs = run(rig, [("imagery_window", GOOD_ARGS["imagery_window"]),
                     ("key_lookup", {"crossing_id": X.id}),
                     ("record_claim", {**claim, "evidence_refs": [{"result_id": "r-0001", "role": "post"}]}),
                     ("record_claim", {**claim, "evidence_refs": [{"result_id": "r-0099", "role": "post"}]}),
                     ("record_claim", {**claim, "evidence_refs": [{"result_id": "r-0002", "role": "post"}]})])
    assert [o.status for o in outs] == ["success", "blocked", "success", "success", "success"]
    c1, c2, c3 = rig.gateway.claims
    assert (c1.grounded, c1.contaminated) == (True, False)
    assert (c2.grounded, c2.unresolved_refs, c2.contaminated) == (False, ["r-0099"], False)
    assert (c3.grounded, c3.contaminated) == (False, True)  # judge D2: a blocked result is no evidence
    assert [c.claim_id for c in rig.gateway.claims] == ["c-0001", "c-0002", "c-0003"]
    spans = rig.spans()
    assert c1.span_id == spans[2].span_id and c1.synthetic is True
    assert outs[3].content[0].json_["grounded"] is False


def test_invalid_claim_is_a_typed_error(rig):
    (out,) = run(rig, [("record_claim", {**GOOD_ARGS["record_claim"], "status": "present"})])
    assert out.status == "error" and "invalid_claim" in out.content[0].text and not rig.gateway.claims


def test_imagery_error_codes_are_the_documented_set(rig):
    w = GOOD_ARGS["imagery_window"]
    cases = {
        "not_allowed": {**w, "scene_id": "SYN-NOPE"},
        "window_too_large": {**w, "side_m": 5000},
        "out_of_bounds": {**w, "lon": 0.5},
        "no_coverage": {**w, "scene_id": "SYN-POST-B", "lon": 0.0100},
        "insufficient_coverage": {**w, "scene_id": "SYN-POST-A", "lon": world.WEST_STRIP - 0.00012, "side_m": 60},
    }
    outs = run(rig, [("imagery_window", a) for a in cases.values()])
    got = [o.content[0].text.split(":")[0].removeprefix("error ") for o in outs]
    assert got == list(cases)
    assert set(got) <= set(ERROR_CODES)
    assert all(isinstance(o.content[0], Text) and o.status == "error" for o in outs)


def test_budget_exceeded_window_code(tmp_path):
    t = card().model_dump()
    t["windows"]["max_bytes_per_run"] = 100_000
    rig = make_rig(tmp_path / "t.jsonl", task=type(card()).model_validate(t))
    w = GOOD_ARGS["imagery_window"]
    outs = run(rig, [("imagery_window", w), ("imagery_window", {**w, "side_m": 1000, "out_px": 512})])
    assert outs[0].status == "success" and "budget_exceeded" in outs[1].content[0].text


def test_gsd_triple(rig):
    (out,) = run(rig, [("imagery_window", {**GOOD_ARGS["imagery_window"], "side_m": 1000, "out_px": 256})])
    w = out.content[0].json_
    assert w["nominal_gsd_m"] == world.PAN_GSD_M
    assert w["effective_gsd_m"] == pytest.approx(1000 / 256)
    assert w["overview_level"] == 2 and w["pixel_spacing_m"] == pytest.approx(world.M_PER_PX * 4)
    assert w["out_shape"] == [256, 256] and w["reader"] == "synthetic-v1"
    assert w["detail"]["bytes_model"] == "synthetic-overview-block-v1"


def test_budget_stop_raises_after_policy_with_a_budget_span(tmp_path):
    from treehouse.gateway.budget import BudgetExceeded
    from treehouse.schemas.config import Budget

    rig = make_rig(tmp_path / "t.jsonl", budget=Budget(tool_calls=1))

    async def go():
        async with rig.gateway as gw:
            await gw.call("scene_info", GOOD_ARGS["scene_info"], call_id="a")
            with pytest.raises(BudgetExceeded):
                await gw.call("scene_info", GOOD_ARGS["scene_info"], call_id="b")
    asyncio.run(go())
    rig.tracer.close()
    assert [s.error.source if s.error else None for s in rig.spans()] == [None, "budget"]


def test_returned_hrefs_are_rechecked(rig, monkeypatch):
    async def leaky(name, args):
        return "success", {"href": "https://example.org/keys/synth/key.json"}, ""
    monkeypatch.setattr(rig.gateway, "_invoke", leaky)
    (out,) = run(rig, [("scene_info", GOOD_ARGS["scene_info"])])
    a = rig.spans()[0].attributes
    # judge D14: a hit in the *result* taints the result; it is not the agent's key access attempt
    assert out.status == "blocked" and a["treehouse.key_access_attempt"] is False
    assert a["treehouse.tool.result_tainted"] is True


def test_tool_cassette_record_then_verify(tmp_path):
    from treehouse.gateway.tool_cassette import ToolCassette, ToolDivergence

    calls = [("stac_search", GOOD_ARGS["stac_search"]), ("imagery_window", GOOD_ARGS["imagery_window"])]
    live = make_rig(tmp_path / "a.jsonl")
    live.gateway.cassette = ToolCassette(tmp_path / "tool.jsonl")
    run(live, calls)
    again = make_rig(tmp_path / "b.jsonl")
    again.gateway.cassette, again.gateway.mode = ToolCassette(tmp_path / "tool.jsonl"), "verify"
    run(again, calls)
    assert (tmp_path / "a.jsonl").read_bytes() == (tmp_path / "b.jsonl").read_bytes()
    bad = make_rig(tmp_path / "c.jsonl")
    bad.gateway.cassette, bad.gateway.mode = ToolCassette(tmp_path / "tool.jsonl"), "verify"
    with pytest.raises(ToolDivergence):
        run(bad, [calls[1]])


def test_recorded_source_attaches_a_pixel_free_image(tmp_path):
    from treehouse.clock import LogicalClock
    from treehouse.gateway.budget import BudgetGuard
    from treehouse.gateway.gateway import ToolGateway
    from treehouse.gateway.meter import Meter
    from treehouse.gateway.policy import Policy
    from treehouse.schemas.config import Budget
    from treehouse.schemas.tools import WindowResult
    from treehouse.tools.sources.recorded import RecordedImagerySource

    nepal = card("nepal-bhote-koshi-bridges")
    synth = make_rig(tmp_path / "s.jsonl")
    (o,) = run(synth, [("imagery_window", GOOD_ARGS["imagery_window"])])
    sid = "B1300011011E5610"
    stac_src = next(d for d in nepal.data_allowlist if d.kind == "stac")
    w = {**o.content[0].json_, "scene_id": sid, "license": "CC-BY-NC-4.0", "result_id": "", "reader": "recorded",
         "source_id": "vantor-nepal-imagery", "etag": stac_src.etags[sid]}
    args = {"scene_id": sid, "lon": 85.35, "lat": 28.2, "side_m": 60, "out_px": 128,
            "resampling": "average"}
    WindowResult.model_validate(w)
    # judge D4: a row that is not a proper recorded, synthetic, pinned window is refused at build time
    kw = {"allowed": stac_src.item_ids, "scene_dates": {}, "as_of": nepal.as_of, "source_id": "vantor-nepal-imagery",
          "etags": dict(stac_src.etags), "license": "CC-BY-NC-4.0"}
    for bad in ({"reader": "synthetic-v1"}, {"synthetic": False}, {"source_id": "synth-imagery"},
                {"scene_id": "B14000110116A310"}, {"etag": "synthetic-0000"}, {"license": "CC-BY-4.0"}):
        with pytest.raises(ValueError, match="recorded window row 0"):
            RecordedImagerySource([{"args": args, "result": {**w, **bad}}], **kw)
    rig = make_rig(tmp_path / "n.jsonl", task=nepal)
    servers = build_servers(nepal, ledger=rig.ledger, pixels=PixelCache(), recorded_windows=[{"args": args,
                                                                                              "result": w}])
    rig.gateway = ToolGateway(servers, Policy(nepal), rig.tracer, BudgetGuard(Budget(), clock=LogicalClock()),
                              Meter(), PixelCache(), ledger=rig.ledger)
    outs = run(rig, [("imagery_window", args), ("imagery_window", {**args, "lon": 85.36})])
    img = outs[0].content[-1]
    assert isinstance(img, Image) and img.bytes_ is None and img.sha256 == w["pixel_sha256"]
    assert outs[0].content[0].json_["result_id"] == "r-0001"
    assert outs[1].status == "error" and "no_coverage" in outs[1].content[0].text
    assert isinstance(RecordedImagerySource([], allowed=[], scene_dates={}, as_of=nepal.as_of).window(
        "X", 0, 0, 1, 1, "average").code, str)


def test_tool_catalog_matches_recorded_request(rig):
    """The advertised contract, including descriptions, is identical across interpreters."""
    from treehouse.providers.cassette import Cassette
    from treehouse.service import demo_root

    async def specs():
        async with rig.gateway as gateway:
            return gateway.specs()

    recorded = Cassette(demo_root() / "cassettes" / "synth-good.model.jsonl").get(("worker", 0, 0))
    try:
        assert asyncio.run(specs()) == recorded.request.tools
    finally:
        rig.tracer.close()
