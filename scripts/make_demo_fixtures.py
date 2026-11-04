"""Rebuild every committed demo fixture (IMPLEMENTATION-DESIGN §5.3). SYNTHETIC.

    uv run python scripts/make_demo_fixtures.py            # writes into the repo
    uv run python scripts/make_demo_fixtures.py --out DIR  # writes the same tree under DIR (rebuild test)

Writes keys/synth/synth-crossings-v1.key.json (from synth.world.build_key()), keys/synth/nepal-demo-truth.json,
fixtures/demo/{runs.yaml, configs/, cassettes/, nepal/, prereg/gold-seed.txt} and fixtures/golden/heads.json.
Each run is recorded (scripted fake policy -> RecordingProvider, tool cassette in live mode) into a throwaway
store, then replayed (ReplayProvider, tool_mode=verify, logical clock) to take the golden trace heads. Output
is byte-identical on every rebuild (a test checks it). Offline; no pixels are written anywhere.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from treehouse.canon import canonical_json
from treehouse.cards import load_card
from treehouse.paths import repo_root
from treehouse.service import card_path, demo_config, run, trace_heads
from treehouse.store.local import LocalStore
from treehouse.synth import nepal as corridor
from treehouse.synth import world
from treehouse.synth.policies import _items

RUNS = [
    {"run_id": "synth-good", "task": "synth-crossings-v1", "policy": "good"},
    {"run_id": "synth-overconfident", "task": "synth-crossings-v1", "policy": "overconfident"},
    {"run_id": "synth-skimmer", "task": "synth-crossings-v1", "policy": "skimmer"},
    {"run_id": "synth-fabricator", "task": "synth-crossings-v1", "policy": "fabricator"},
    {"run_id": "synth-key-peeker", "task": "synth-crossings-v1", "policy": "key-peeker"},
    {"run_id": "synth-looper", "task": "synth-crossings-v1", "policy": "looper"},
    {"run_id": "synth-budget-stop", "task": "synth-crossings-v1", "policy": "budget-stop",
     "budget": {"tool_calls": 12}},
    {"run_id": "nepal-good", "task": "nepal-bhote-koshi-bridges", "policy": "vhr-good"},
    {"run_id": "nepal-guesser", "task": "nepal-bhote-koshi-bridges", "policy": "vhr-guesser"},
]
GOLD_SEED = "20261104\n"


def _json(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def write(out: Path, rel: str, text: str | bytes) -> None:
    p = out / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))


def build(out: Path) -> None:
    write(out, "keys/synth/synth-crossings-v1.key.json", _json(world.build_key()))
    ncard = load_card(card_path("nepal-bhote-koshi-bridges"))
    scene = corridor.clearest_post_scene(ncard, _items(ncard))
    write(out, "keys/synth/nepal-demo-truth.json", _json(corridor.truth(ncard, scene)))
    write(out, "fixtures/demo/nepal/corridor.geojson", _json(corridor.corridor_geojson(ncard)))
    pts = corridor.points(ncard, scene)
    csv = ["point_id,lon,lat,synthetic,note"] + [f"{p['point_id']},{p['lon']},{p['lat']},true,{p['note']}" for p in pts]
    write(out, "fixtures/demo/nepal/points.csv", "\n".join(csv) + "\n")
    write(out, "fixtures/demo/nepal/windows.jsonl",
          "".join(canonical_json(r) + "\n" for r in corridor.recorded_windows(ncard, scene)))
    write(out, "fixtures/demo/prereg/gold-seed.txt", GOLD_SEED)
    header = ("# SYNTHETIC DEMO DATA. Written by scripts/make_demo_fixtures.py; `treehouse demo` replays every run.\n"
              "# Nepal rows are illustrative, not surveyed bridges.\n")
    write(out, "fixtures/demo/runs.yaml", header + json.dumps({"runs": RUNS}, indent=1) + "\n")

    with tempfile.TemporaryDirectory() as tmp:
        rec_store, rep_store = LocalStore(Path(tmp) / "rec"), LocalStore(Path(tmp) / "rep")
        cas = Path(tmp) / "fixtures/demo/cassettes"
        outcomes = {}
        for e in RUNS:
            card = load_card(card_path(e["task"]))
            cfg = demo_config(e, card, mode="replay")
            write(out, f"fixtures/demo/configs/{e['run_id']}.json", canonical_json(cfg) + "\n")
            run(rec_store, cfg, run_id=e["run_id"], mode="record", cassette_out=cas)
            outcomes[e["run_id"]] = run(rep_store, cfg, run_id=e["run_id"], mode="replay", cassette_root=Path(tmp))
        destination = out / "fixtures/demo/cassettes"
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(cas, destination)
        write(out, "fixtures/golden/heads.json", _json(trace_heads(outcomes)))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=None, help="root to write under (default: the repo)")
    a = ap.parse_args(argv)
    build((a.out or repo_root()).resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
