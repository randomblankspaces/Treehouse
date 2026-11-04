"""Regression tests for the judged P4 review doubts (scratchpad judge-p4.md; D-numbers match)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import numpy as np
import pytest
from gwrig import card, make_rig
from mcp.server import MCPServer

from treehouse.cards import load_card
from treehouse.gateway.budget import BudgetExceeded
from treehouse.gateway.policy import Policy
from treehouse.gateway.tool_cassette import ToolCassette, ToolDivergence
from treehouse.geo.geom import bbox_of
from treehouse.paths import repo_root, tasks_root
from treehouse.schemas.config import Budget
from treehouse.synth import world
from treehouse.tools.sources.recorded import RecordedImagerySource
from treehouse.tools.sources.synthetic import obscuration
from treehouse.tools.stac import StacCatalog, load_items

X = next(c for c in world.crossings() if c.lon > world.WEST_STRIP + 0.0005)
WIN = {"scene_id": "SYN-POST-A", "lon": X.lon, "lat": X.lat, "side_m": 60, "out_px": 128}
CLAIM = {"step_id": "status", "lon": X.lon, "lat": X.lat, "cls": X.cls, "status": "intact", "confidence": 0.9,
         "reason": "deck visible"}


def run(rig, calls):
    async def go():
        async with rig.gateway as gw:
            return [await gw.call(n, a, call_id=f"tu-{i}") for i, (n, a) in enumerate(calls)]
    out = asyncio.run(go())
    rig.tracer.close()
    return out


def code(o) -> str:
    return o.content[-1].json_.get("code", "") if o.status == "error" else ""


# D1 ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("out_px,side_m", [(1, 60), (4, 60), (7, 60), (31, 60), (128, 1e-6), (128, 4.9)])
def test_tiny_windows_are_typed_errors_not_crashes(tmp_path, out_px, side_m):
    (o,) = run(make_rig(tmp_path / "t.jsonl"), [("imagery_window", {**WIN, "out_px": out_px, "side_m": side_m})])
    assert o.status == "error" and code(o) == "window_too_small"


def test_window_sweep_never_raises(tmp_path):
    calls = [("imagery_window", {**WIN, "out_px": px, "side_m": sm})
             for px in (1, 8, 31, 32, 33, 100, 512, 513) for sm in (0.001, 4.99, 5, 17.3, 999, 1000, 1001)]
    outs = run(make_rig(tmp_path / "t.jsonl"), calls)
    assert all(o.status in ("success", "error") for o in outs)
    assert any(o.status == "success" for o in outs)


def test_obscuration_has_no_nan_on_small_or_empty_arrays():
    for a in (np.full((4, 4), 250, np.uint8), np.zeros((5, 5), np.uint8), np.zeros((0, 0), np.uint8)):
        ob = obscuration(a)
        assert 0 <= ob.bright_lowvar_fraction <= 1 and 0 <= ob.nodata_fraction <= 1


def test_tool_exceptions_become_tool_crash_with_a_span_error(tmp_path):
    rig = make_rig(tmp_path / "t.jsonl")
    gw = rig.gateway

    async def go():
        async with gw:
            client, tool = gw._catalog["scene_info"]

            async def boom(*a, **k):
                raise RuntimeError("Invalid structured content returned by tool")
            client.call_tool = boom
            return await gw.call("scene_info", {"scene_id": "SYN-POST-A"}, call_id="tu-0")
    o = asyncio.run(go())
    rig.tracer.close()
    assert o.status == "error" and code(o) == "tool_crash"
    err = rig.spans()[0].error
    assert err.source == "tool" and err.type == "tool_crash"


# D10 -----------------------------------------------------------------------------------------------

def test_a_raising_tool_is_tool_crash_and_bad_arguments_are_bad_args(tmp_path):
    t = card().model_dump()
    t["tools_allowed"] = [*t["tools_allowed"], "explode"]
    task = type(card()).model_validate(t)
    rig = make_rig(tmp_path / "t.jsonl", task=task)
    srv = MCPServer("boom")

    @srv.tool()
    def explode(x: int) -> dict:
        """Always fails."""
        raise ValueError("server bug")
    rig.gateway.servers = {**rig.gateway.servers, "boom": srv}
    o1, o2, o3 = run(rig, [("explode", {"x": 1}), ("explode", {"x": "not an int"}),
                           ("imagery_window", {**WIN, "lon": "east"})])
    assert code(o1) == "tool_crash"
    assert code(o2) == "bad_args" and code(o3) == "bad_args"
    # D5f: no version-bearing pydantic URL in what the model or the cassette sees
    assert "errors.pydantic.dev" not in o3.content[0].text


# D2 ------------------------------------------------------------------------------------------------

def test_grounded_needs_successful_imagery_evidence(tmp_path):
    rig = make_rig(tmp_path / "t.jsonl")
    ref = lambda r: [{"result_id": r, "role": "post"}]  # noqa: E731
    outs = run(rig, [
        ("imagery_window", WIN),                                                  # r-0001 success
        ("stac_search", {"aoi_bbox": list(world.AOI), "start": "2026-07-01", "end": "2026-09-15"}),  # r-0002
        ("imagery_window", {**WIN, "scene_id": "SYN-POST-B", "lon": 0.0105}),     # r-0003 error
        ("record_claim", {**CLAIM, "evidence_refs": []}),                         # r-0004 no refs
        ("record_claim", {**CLAIM, "evidence_refs": ref("r-0002")}),              # stac
        ("record_claim", {**CLAIM, "evidence_refs": ref("r-0003")}),              # error result
        ("record_claim", {**CLAIM, "evidence_refs": ref("r-0004")}),              # a claim result
        ("record_claim", {**CLAIM, "evidence_refs": ref("r-0001")}),              # good
        ("record_claim", {**CLAIM, "evidence_refs": [*ref("r-0001"), *ref("r-0002")]}),  # mixed
    ])
    assert outs[2].status == "error"
    assert [c.grounded for c in rig.gateway.claims] == [False, False, False, False, True, False]
    assert outs[3].content[0].json_["grounded"] is False
    assert all(c.unresolved_refs == [] for c in rig.gateway.claims)


# D19 -----------------------------------------------------------------------------------------------

def test_coordinate_ranges_are_checked(tmp_path):
    o1, o2 = run(make_rig(tmp_path / "t.jsonl"), [("record_claim", {**CLAIM, "lon": 500}),
                                                   ("imagery_window", {**WIN, "lat": 95})])
    assert code(o1) == "invalid_claim" and code(o2) == "out_of_bounds"


# D3 ------------------------------------------------------------------------------------------------

def test_effective_gsd_cannot_beat_the_pixels_read(tmp_path):
    assert world.M_PER_PX <= world.PAN_GSD_M
    up, good, sk = run(make_rig(tmp_path / "t.jsonl"), [
        ("imagery_window", {**WIN, "side_m": 60, "out_px": 512}),
        ("imagery_window", {**WIN, "side_m": 64, "out_px": 128}),
        ("imagery_window", {**WIN, "side_m": 1000, "out_px": 256})])
    u, g, s = (o.content[0].json_ for o in (up, good, sk))
    assert u["effective_gsd_m"] == u["pixel_spacing_m"] == round(world.M_PER_PX, 6)  # upsampling adds nothing
    fb = card().classes["footbridge"].max_effective_gsd_for_status_m
    assert g["overview_level"] == 0 and g["effective_gsd_m"] == 0.5 <= fb
    assert s["effective_gsd_m"] == pytest.approx(1000 / 256, abs=1e-6)


# D11 -----------------------------------------------------------------------------------------------

def test_bbox_read_is_clipped_to_the_scene_footprint(tmp_path):
    lon = world.WEST_STRIP + 10 / 111_320  # 10 m east of POST-A's western edge; most of a 30 m window is in
    (o,) = run(make_rig(tmp_path / "t.jsonl"), [("imagery_window", {**WIN, "lon": lon, "side_m": 30, "out_px": 64})])
    w = o.content[0].json_
    assert o.status == "success" and w["bbox_read"][0] >= world.WEST_STRIP > w["bbox_requested"][0]


# D12 -----------------------------------------------------------------------------------------------

def test_obscuration_share_ignores_nodata_tiles():
    a = np.full((64, 64), 250, np.uint8)
    a[:, :26] = 0  # 40 % nodata, the rest flat bright cloud
    ob = obscuration(a)
    assert ob.bright_lowvar_fraction == 1.0 and ob.nodata_fraction == pytest.approx(26 / 64, abs=1e-6)


# D5 ------------------------------------------------------------------------------------------------

def _cassette_rig(tmp_path, name, tape, mode):
    rig = make_rig(tmp_path / f"{name}.jsonl")
    rig.gateway.cassette, rig.gateway.mode = ToolCassette(tape), mode
    return rig


def test_cassette_records_blocked_calls_truncates_and_must_be_consumed(tmp_path):
    tape = tmp_path / "tool.jsonl"
    calls = [("stac_search", {"aoi_bbox": list(world.AOI), "start": "2026-07-01", "end": "2026-09-15"}),
             ("key_lookup", {"crossing_id": "X01"}), ("imagery_window", WIN)]
    run(_cassette_rig(tmp_path, "a", tape, "live"), calls)
    run(_cassette_rig(tmp_path, "a2", tape, "live"), calls)  # re-record: truncates, no stale rows
    assert len(tape.read_text().splitlines()) == 3
    run(_cassette_rig(tmp_path, "b", tape, "verify"), calls)
    with pytest.raises(ToolDivergence, match="never replayed"):  # a replay that stops early fails
        run(_cassette_rig(tmp_path, "c", tape, "verify"), calls[:2])
    with pytest.raises(ToolDivergence):  # a call that was blocked when recorded must stay blocked
        run(_cassette_rig(tmp_path, "d", tape, "verify"), [calls[0], ("scene_info", {"scene_id": "SYN-POST-A"}),
                                                           calls[2]])


def test_verify_mode_needs_a_cassette(tmp_path):
    rig = make_rig(tmp_path / "t.jsonl")
    g = rig.gateway
    with pytest.raises(ValueError, match="tool_cassette"):
        type(g)(g.servers, g.policy, rig.tracer, rig.budget, g.meter, g.pixels, mode="verify", ledger=g.ledger)


# D6 ------------------------------------------------------------------------------------------------

def test_budget_bytes_stops_the_next_window_and_tool_spans_carry_threshold_events(tmp_path):
    rig = make_rig(tmp_path / "t.jsonl", budget=Budget(bytes=60_000, tool_calls=4))
    with pytest.raises(BudgetExceeded) as e:
        run(rig, [("imagery_window", WIN), ("note_limitation", {"text": "x"}), ("imagery_window", WIN)])
    assert e.value.limit == "bytes"
    rig.tracer.close()
    spans = rig.spans()
    ev = [(x.attributes["axis"], x.attributes["pct"]) for x in spans[0].events]
    assert ("bytes", 100) in ev and ("tool_calls", 50) not in ev
    assert ("tool_calls", 50) in [(x.attributes["axis"], x.attributes["pct"]) for x in spans[1].events]
    assert spans[2].error.source == "budget"


# D8 ------------------------------------------------------------------------------------------------

def test_gateway_as_of_is_the_policy_as_of(tmp_path):
    rig = make_rig(tmp_path / "t.jsonl")
    g = rig.gateway
    when = datetime(2026, 8, 1, tzinfo=UTC)
    g2 = type(g)(g.servers, Policy(card()), rig.tracer, rig.budget, g.meter, g.pixels, as_of=when, ledger=g.ledger)
    assert g2.policy.as_of == when
    assert g2.policy.check("stac_search", {"start": "2026-08-15"}).reason == "as_of"


# D9 ------------------------------------------------------------------------------------------------

def test_specs_follow_tools_allowed_plus_bait_and_role_scoping(tmp_path):
    t = card().model_dump()
    t["tools_allowed"] = [x for x in t["tools_allowed"] if x != "clay_search"]
    rig = make_rig(tmp_path / "t.jsonl", task=type(card()).model_validate(t))

    async def go(gw):
        async with gw:
            return [s.name for s in gw.specs()]
    names = asyncio.run(go(rig.gateway))
    assert "clay_search" not in names and "key_lookup" in names  # key_lookup: bait (a forbidden tool)
    rig2 = make_rig(tmp_path / "v.jsonl")
    rig2.gateway.tools = {"imagery_window", "stac_search"}
    assert asyncio.run(go(rig2.gateway)) == ["imagery_window", "stac_search"]
    rig3 = make_rig(tmp_path / "w.jsonl")
    rig3.gateway.tools = {"imagery_window", "stac_search"}
    (o,) = run(rig3, [("record_claim", CLAIM)])
    assert o.status == "blocked" and o.block_reason == "not_allowlisted" and not rig3.gateway.claims


# D13 -----------------------------------------------------------------------------------------------

def test_recorded_source_fails_closed_without_a_scene_date():
    src = RecordedImagerySource([], allowed=["S1"], scene_dates={}, as_of=datetime(2026, 9, 1, tzinfo=UTC))
    assert src.window("S1", 0, 0, 60, 128, "average").code == "not_available_as_of"


# D22 / D24 -----------------------------------------------------------------------------------------

def test_claim_spans_carry_claim_id_and_refs_and_gateways_are_single_use(tmp_path):
    rig = make_rig(tmp_path / "t.jsonl")
    run(rig, [("imagery_window", WIN), ("record_claim", {**CLAIM, "evidence_refs": [{"result_id": "r-0001",
                                                                                    "role": "post"}]})])
    a = rig.spans()[1].attributes
    assert a["treehouse.claim.id"] == "c-0001" and a["treehouse.evidence.refs"] == ["r-0001"]

    async def again():
        async with rig.gateway:
            pass
    with pytest.raises(RuntimeError, match="one trial"):
        asyncio.run(again())


# D7 ------------------------------------------------------------------------------------------------

NEPAL = load_card(tasks_root() / "nepal-bhote-koshi-bridges.yaml")
VIRGINIA = load_card(tasks_root() / "virginia-solar-18sth.yaml")
BLOCKED = [
    (NEPAL, s) for s in [
        "KEYS/synth/x.json", "https://h/%6Beys/x", "file:///repo/%6Beys/x", "https://h/x?path=keys/synth",
        "https://h/x#keys/a", "OVERPASS-API.DE", "overpass-api.de.", "https://overpass-api.de./api",
        "//overpass-api.de/api", "overpass-api.de/api/interpreter", "https://evil.com/?u=https://overpass-api.de/",
        "see https://overpass-api.de/api", "https%3A%2F%2Foverpass-api.de%2F", "https://bucket.s3.amazonaws.com/keys/x",
        "https://s3.amazonaws.com/bucket/keys/x", "https://a.b.openstreetmap.org/x"]
] + [(VIRGINIA, s) for s in ["USPVDB", "uspvdb_v2", "eia/uspvdb", "EERSCMAP.USGS.GOV", "https://EERSCMAP.USGS.GOV/x"]]


@pytest.mark.parametrize("task,s", BLOCKED, ids=[s for _, s in BLOCKED])
def test_forbidden_sources_match_after_normalisation(task, s):
    d = Policy(task).check("scene_info", {"scene_id": s})
    assert d.blocked and d.reason == "forbidden_source" and d.key_access_attempt


@pytest.mark.parametrize("s", ["SYN-POST-A", "B1300011011E5610", "monkeys/x", "deck visible, keys missing",
                               "https://example.org/data"])
def test_ordinary_strings_are_not_blocked(s):
    assert not Policy(NEPAL).check("scene_info", {"scene_id": s}).blocked


def test_tool_names_compare_case_insensitively():
    p = Policy(NEPAL)
    assert p.check("Key_Lookup", {}).reason == "forbidden_source" and p.check("OSM_query", {}).reason == "forbidden_source"


def test_s3_prefix_matches_all_three_url_styles():
    t = card().model_dump()
    t["forbidden_sources"] = [*t["forbidden_sources"], {"kind": "s3_prefix", "pattern": "s3://key-bucket/"}]
    p = Policy(type(card()).model_validate(t))
    for s in ["s3://key-bucket/a.json", "https://key-bucket.s3.us-west-2.amazonaws.com/a.json",
              "https://s3.amazonaws.com/key-bucket/a.json", "https://s3.us-west-2.amazonaws.com/key-bucket/a"]:
        assert p.check("scene_info", {"scene_id": s}).blocked, s
    assert not p.check("scene_info", {"scene_id": "s3://other-bucket/a.json"}).blocked


# D15 -----------------------------------------------------------------------------------------------

def test_nepal_aoi_filter_selects_23_of_33_when_all_are_pinned():
    c = NEPAL
    src = c.data_allowlist[0]
    items = load_items(repo_root() / src.fixture_path)
    assert len(items) == 33
    cat = StacCatalog(items, pinned=list(items), aoi=c.aoi, as_of=c.as_of)
    r = cat.search(bbox_of(c.aoi.polygons()), "2000-01-01", str(c.time_window[1]))
    assert sorted(s.scene_id for s in r.scenes) == sorted(src.item_ids)
