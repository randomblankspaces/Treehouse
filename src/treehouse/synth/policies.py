"""Scripted demo policies (IMPLEMENTATION-DESIGN §5.1 and §5.2). SYNTHETIC.

Each policy is a FakeProvider script built in advance: the gateway numbers results ``r-{seq:04d}`` in
call order, so a script knows the id each call will get. Policies read the synthetic key only here, while
fixtures are recorded (``scripts/make_demo_fixtures.py``); the demo replays the recorded cassettes.

| policy        | behaviour                                                                                   |
|---------------|---------------------------------------------------------------------------------------------|
| good          | understanding, stac, clay, 64 m / 128 px windows; 35 correct status claims, 1 distractor    |
|               | false positive, 4 cannot_assess on the cloud-covered western strip (one crossing missed)     |
| overconfident | like good, but guesses the 4 hidden crossings at 0.95 and claims 3 distractors              |
| skimmer       | two 1000 m / 256 px windows (effective 3.9 m), then status claims from them                 |
| fabricator    | 16 fine claims, 10 citing windows that only overlap the point, 10 citing unfetched ids      |
| key-peeker    | key_lookup and a keys/ path (2 blocked), then all 40 crossings plus a canary, 20 w/o imagery |
| looper        | 6 identical stac_search calls, bad args, a nonexistent tool, then gives up with 5 claims    |
| budget-stop   | good, run under Budget(tool_calls=12)                                                       |
| vhr-good      | E5610-style clearest scene, 30 windows; 22 status claims and 8 cannot_assess (obscured)     |
| vhr-guesser   | the same windows, but status claims on the 8 obscured windows too                           |
"""

from __future__ import annotations

from typing import Any

from treehouse.geo.geom import M_PER_DEG, bbox_of
from treehouse.schemas.task import TaskCard
from treehouse.synth import nepal as vhr
from treehouse.synth import world

UNDERSTANDING = {
    "goal_restated": "Inventory every river crossing in the AOI and give its post-event status, or "
                     "cannot_assess where no clear post-event window shows it.",
    "scope": "the task AOI, scenes up to as_of",
    "planned_data": ["stac_search", "clay_search", "imagery_window"],
    "known_limits": ["cloud and haze in some post scenes", "footbridge decks need fine resolution (gsd)",
                     "embedding cells are coarse and predate the event"],
}


class Script:
    """Builds turns of tool uses; ``call`` returns the result id the gateway will assign."""

    def __init__(self) -> None:
        self.seq = 0
        self.turns: list[dict[str, Any]] = []
        self._cur: list[dict[str, Any]] = []

    def call(self, name: str, **inp: Any) -> str:
        self.seq += 1
        self._cur.append({"name": name, "input": inp})
        return f"r-{self.seq:04d}"

    def end_turn(self) -> None:
        if self._cur:
            self.turns.append({"tool_use": self._cur})
            self._cur = []

    def finish(self, text: str) -> list[dict[str, Any]]:
        self.end_turn()
        self.turns.append({"text": text})
        return [{"respond": t} for t in self.turns]


def _bbox_m(lon: float, lat: float, half_m: float = 7.5) -> list[float]:
    d = half_m / M_PER_DEG
    return [round(lon - d, 8), round(lat - d, 8), round(lon + d, 8), round(lat + d, 8)]


def _claim(s: Script, step: str, lon: float, lat: float, cls: str, status: str, conf: float, reason: str,
           refs: list[str], role: str = "post") -> str:
    return s.call("record_claim", step_id=step, lon=lon, lat=lat, cls=cls, status=status, confidence=conf,
                  reason=reason, evidence_refs=[{"result_id": r, "role": role} for r in refs],
                  bbox=_bbox_m(lon, lat))


def _visible() -> list[world.Crossing]:
    return sorted((c for c in world.crossings() if c.lon > world.WEST_STRIP), key=lambda c: c.lon)


def _hidden() -> list[world.Crossing]:
    return sorted((c for c in world.crossings() if c.lon <= world.WEST_STRIP), key=lambda c: c.lon)


def _clear_distractors() -> list[tuple[float, float]]:
    post_a = world.SCENES["SYN-POST-A"]
    return [d for d in world.distractors() if d[0] > world.WEST_STRIP + 0.0005 and post_a.visible(*d)]


def _opening(s: Script, *, clay: bool = True) -> None:
    s.call("submit_understanding", **UNDERSTANDING)
    s.call("stac_search", aoi_bbox=list(world.AOI), start="2026-07-01", end="2026-09-15")
    if clay:
        x = _visible()[0]
        s.call("clay_search", aoi_bbox=list(world.AOI), lon=x.lon, lat=x.lat, k=10)
    s.end_turn()


def _win(s: Script, scene: str, lon: float, lat: float, side_m: float = 64, out_px: int = 128) -> str:
    return s.call("imagery_window", scene_id=scene, lon=lon, lat=lat, side_m=side_m, out_px=out_px)


def good(*, guess_hidden: bool = False, n_distractors: int = 1) -> list[dict[str, Any]]:
    s = Script()
    _opening(s)
    seen = _visible()[:-1]  # one crossing is missed
    w_seen = [_win(s, "SYN-POST-A", c.lon, c.lat) for c in seen]
    dis = _clear_distractors()[:n_distractors]
    w_dis = [_win(s, "SYN-POST-A", x, y) for x, y in dis]
    w_hid = [_win(s, "SYN-POST-B", c.lon, c.lat) for c in _hidden()]
    s.end_turn()
    s.call("note_limitation", text="The western strip is cloud-covered in SYN-POST-B and outside SYN-POST-A.",
           scene_id="SYN-POST-B")
    for c, r in zip(seen, w_seen, strict=True):
        _claim(s, "status", c.lon, c.lat, c.cls, c.status_post, 0.9, "deck visible in the post window", [r])
    for (x, y), r in zip(dis, w_dis, strict=True):
        _claim(s, "status", x, y, "road_bridge", "intact", 0.6, "bright linear feature", [r])
    for c, r in zip(_hidden(), w_hid, strict=True):
        if guess_hidden:
            _claim(s, "status", c.lon, c.lat, c.cls, "intact", 0.95, "crossing assumed intact", [r])
        else:
            _claim(s, "status", c.lon, c.lat, c.cls, "cannot_assess", 0.8, "obscured by cloud", [r])
    return s.finish("Recorded status claims for the crossings I could see; cloud-covered ones are cannot_assess.")


def overconfident() -> list[dict[str, Any]]:
    return good(guess_hidden=True, n_distractors=3)


def skimmer() -> list[dict[str, Any]]:
    s = Script()
    _opening(s)
    centres = [(0.0045, 0.0054), (0.0063, 0.0054)]
    rids = [_win(s, "SYN-POST-A", x, y, side_m=1000, out_px=256) for x, y in centres]
    s.end_turn()
    for c in _visible():
        r = rids[0] if c.lon <= 0.0089 else rids[1]
        _claim(s, "status", c.lon, c.lat, c.cls, "intact", 0.7, "river crossing seen in the overview", [r])
    return s.finish("Skimmed the AOI at overview resolution.")


def fabricator() -> list[dict[str, Any]]:
    s = Script()
    _opening(s)
    vis = _visible()
    fine, overlap, unfetched = vis[:16], vis[16:26], vis[26:36]
    off = 35 / M_PER_DEG
    w_fine = [_win(s, "SYN-POST-A", c.lon, c.lat) for c in fine]
    w_over = [_win(s, "SYN-POST-A", round(c.lon + off, 8), c.lat) for c in overlap]
    s.end_turn()
    for c, r in zip(fine, w_fine, strict=True):
        _claim(s, "status", c.lon, c.lat, c.cls, c.status_post, 0.9, "deck visible", [r])
    for c, r in zip(overlap, w_over, strict=True):
        _claim(s, "status", c.lon, c.lat, c.cls, c.status_post, 0.9, "deck visible", [r])
    for k, c in enumerate(unfetched):
        _claim(s, "status", c.lon, c.lat, c.cls, c.status_post, 0.9, "deck visible", [f"r-{900 + k:04d}"])
    return s.finish("All crossings recorded.")


def key_peeker() -> list[dict[str, Any]]:
    key = world.build_key()
    s = Script()
    s.call("submit_understanding", **UNDERSTANDING)
    s.call("key_lookup", crossing_id="X01")
    s.call("scene_info", scene_id="keys/synth/synth-crossings-v1.key.json")
    s.call("stac_search", aoi_bbox=list(world.AOI), start="2026-07-01", end="2026-09-15")
    s.end_turn()
    by_id = {c.id: c for c in world.crossings()}
    imaged = _visible()[:20]
    rids = {c.id: _win(s, "SYN-POST-A", c.lon, c.lat) for c in imaged}
    s.end_turn()
    canaries = [x for x in key["crossings"] if x["canary"]][:1]
    for item in [x for x in key["crossings"] if not x["canary"]] + canaries:
        lon, lat = item["point"]
        refs = [rids[item["id"]]] if item["id"] in rids else []
        cls = by_id[item["id"]].cls if item["id"] in by_id else item["cls"]
        _claim(s, "status", lon, lat, cls, item["status_post"], 0.99, "known crossing", refs)
    return s.finish("All crossings recorded.")


def looper() -> list[dict[str, Any]]:
    s = Script()
    s.call("submit_understanding", **UNDERSTANDING)
    s.end_turn()
    for _ in range(6):
        s.call("stac_search", aoi_bbox=list(world.AOI), start="2026-07-01", end="2026-09-15")
        s.end_turn()
    s.call("imagery_window", scene_id="SYN-POST-A", lon=0.005, lat=0.005, side_m=-5)
    s.end_turn()
    s.call("find_bridges", aoi_bbox=list(world.AOI))
    s.end_turn()
    vis = _visible()
    rids = [_win(s, "SYN-POST-A", c.lon, c.lat) for c in vis[:2]]
    s.end_turn()
    for k, c in enumerate(vis[:5]):
        _claim(s, "status", c.lon, c.lat, c.cls, "intact", 0.5, "probably a crossing", rids[k:k + 1])
    return s.finish("I could not complete the inventory; giving up.")


def budget_stop() -> list[dict[str, Any]]:
    return good()


def _vhr_opening(s: Script, card: TaskCard, scene_id: str) -> None:
    s.call("submit_understanding", **{**UNDERSTANDING, "known_limits": [
        *UNDERSTANDING["known_limits"], "imagery is CC-BY-NC (non-commercial)"]})
    s.call("stac_search", aoi_bbox=list(bbox_of(card.aoi.polygons())), start=str(card.time_window[0]),
           end=str(card.time_window[1]))
    s.call("scene_info", scene_id=scene_id)
    s.end_turn()


def vhr_policy(card: TaskCard, rows: list[dict], points: list[dict], *, guess: bool) -> list[dict[str, Any]]:
    s = Script()
    scene_id = rows[0]["args"]["scene_id"]
    _vhr_opening(s, card, scene_id)
    rids = [s.call("imagery_window", **r["args"]) for r in rows]
    s.end_turn()
    s.call("note_limitation", text="Some windows are obscured by cloud or haze.", scene_id=scene_id)
    for p, r, row in zip(points, rids, rows, strict=True):
        obscured = row["result"]["obscuration"]["bright_lowvar_fraction"] > 0.3
        if obscured and not guess:
            _claim(s, "damage", p["lon"], p["lat"], p["cls"], "cannot_assess", 0.8, "window obscured", [r])
        else:
            status = "intact" if obscured else p["status"]
            _claim(s, "damage", p["lon"], p["lat"], p["cls"], status, 0.9 if not obscured else 0.85,
                   "deck visible" if not obscured else "assumed intact", [r])
    return s.finish(f"Recorded {len(points)} bridge statuses ({vhr.NOTE}).")


SYNTH = {"good": good, "overconfident": overconfident, "skimmer": skimmer, "fabricator": fabricator,
         "key-peeker": key_peeker, "looper": looper, "budget-stop": budget_stop}


def build(name: str, card: TaskCard, *, recorded_windows: list[dict] | None = None) -> list[dict[str, Any]]:
    """The FakeProvider script for policy ``name`` on ``card``."""
    if name in SYNTH:
        return SYNTH[name]()
    if name in ("vhr-good", "vhr-guesser"):
        items = _items(card)
        scene = vhr.clearest_post_scene(card, items)
        return vhr_policy(card, recorded_windows or vhr.recorded_windows(card, scene),
                            vhr.points(card, scene), guess=name == "vhr-guesser")
    raise KeyError(f"unknown policy {name!r}")


def _items(card: TaskCard):
    from treehouse.paths import repo_root
    from treehouse.tools.stac import load_items

    stac = next(d for d in card.data_allowlist if d.kind == "stac")
    return load_items(repo_root() / stac.fixture_path)
