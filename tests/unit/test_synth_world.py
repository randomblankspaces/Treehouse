"""synth-crossings-v1 (§5.1): counts, spacing, hidden crossings, key format, render determinism and
byte-identical regeneration of the committed STAC items and embeddings npz."""

from __future__ import annotations

import collections
import json
import math

import numpy as np

from treehouse.pixels import array_sha256
from treehouse.synth import fixtures, world
from treehouse.synth.render import render_scene


def test_world_counts_and_spacing():
    cs = world.crossings()
    assert len(cs) == 40
    assert collections.Counter(c.cls for c in cs) == {"road_bridge": 24, "footbridge": 16}
    assert collections.Counter(c.status_post for c in cs) == {"intact": 30, "damaged": 6, "destroyed": 4}
    sep = min(math.hypot(a.lon - b.lon, a.lat - b.lat) * world.M_PER_DEG for i, a in enumerate(cs) for b in cs[i + 1:])
    assert sep >= 20
    assert len(world.distractors()) == 15 and len(world.canaries()) == 3


def test_four_western_crossings_have_no_clear_post_scene():
    hidden = [c for c in world.crossings()
              if not any(v for s, v in world.visible_in(c).items() if world.SCENES[s].phase == "post")]
    assert len(hidden) == 4 and all(c.lon < world.WEST_STRIP for c in hidden)
    assert all(world.visible_in(c)["SYN-PRE-1"] for c in hidden)


def test_key_format():
    k = world.build_key()
    assert k["synthetic"] is True and k["version_hash"].startswith("sha256:")
    rows = k["crossings"]
    assert len(rows) == 43 and sum(r["canary"] for r in rows) == 3
    r = rows[0]
    assert set(r) == {"id", "point", "line", "cls", "status_post", "visible_in", "canary"}
    assert set(r["visible_in"]) == set(world.SCENES) and len(r["line"]) == 2
    assert world.build_key() == k


def test_scene_table():
    s = world.SCENES
    assert [s[i].phase for i in sorted(s)] == ["post", "post", "post", "pre", "pre"]
    assert s["SYN-POST-B"].cloud_pct == 70 and s["SYN-POST-B"].footprint[2] < world.W
    assert s["SYN-POST-A"].footprint[0] == world.WEST_STRIP and s["SYN-POST-C"].shift_px == 3


def test_render_is_deterministic_and_shows_status():
    a = render_scene("SYN-POST-A")
    assert a.dtype == np.uint8 and a.shape == (2400, 2400) and not a.flags.writeable
    assert array_sha256(a) == array_sha256(render_scene.__wrapped__("SYN-POST-A"))
    assert (a[:, :300] == 0).all() and (a[:, 400:] > 0).all()  # western strip is nodata
    pre, post = render_scene("SYN-PRE-1"), a
    destroyed = next(c for c in world.crossings() if c.status_post == "destroyed" and c.lon > world.WEST_STRIP)
    cx, cy = (int(v) for v in world.pixel_of(destroyed.lon, destroyed.lat))
    assert pre[cy - 1:cy + 2, cx - 1:cx + 2].max() == 200 and post[cy - 1:cy + 2, cx - 1:cx + 2].max() < 200
    assert not np.array_equal(render_scene("SYN-POST-A"), render_scene("SYN-POST-C"))


def test_committed_fixtures_regenerate_byte_identical(tmp_path):
    for p in fixtures.write_stac(tmp_path / "stac"):
        assert p.read_bytes() == (fixtures.stac_dir() / "items" / p.name).read_bytes()
    out = fixtures.write_embeddings(tmp_path / "e.npz")
    assert out.read_bytes() == fixtures.embeddings_path().read_bytes()
    item = json.loads((fixtures.stac_dir() / "items" / "SYN-POST-A.json").read_text())
    assert item["properties"]["treehouse:synthetic"] is True and item["assets"]["visual"]["etag"]
