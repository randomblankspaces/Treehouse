"""Build the pitch page's recorded-demo excerpt (demo mode A) from a committed live Bedrock run.

    uv run python scripts/build_pitch_demo.py            # default run: exp-nagoya-sonnet-1

Replays ``fixtures/live/cassettes/<run>.model.jsonl`` offline (no AWS) into a temporary store, reads the same
public snapshot the UI API serves, and writes a slim excerpt to ``ui/src/pitch/data/recorded-run.json``. The
excerpt keeps provenance labels (synthetic embeddings and reference) so the page can never present it as
real-world accuracy. Re-run it whenever the snapshot contract or the run changes.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ui/src/pitch/data/recorded-run.json"


def slim(snap: dict) -> dict:
    tools = Counter((s.get("tool") or {}).get("name") or s["kind"] for s in snap["steps"])
    chats = [s for s in snap["steps"] if s["kind"] == "chat" and s.get("model")]
    rules = snap["evaluation"]["reasoning_rules"]
    return {
        "run_id": snap["run_id"], "title": snap["title"], "mode": snap["mode"],
        "source": "live Amazon Bedrock run (Strands), replayed offline from its recorded cassette",
        "model_id": snap["context"]["model_id"], "harness": snap["context"]["harness"],
        "goal": snap["input"]["goal"], "aoi_bbox": snap["input"]["aoi_bbox"],
        "cost_usd": snap["cost_usd"], "cost_basis": snap.get("cost_basis"),
        "provenance": snap["provenance"],
        "trace": {"spans": len(snap["steps"]), "model_calls": len(chats),
                  "input_tokens": sum(s["model"].get("input_tokens") or 0 for s in chats),
                  "output_tokens": sum(s["model"].get("output_tokens") or 0 for s in chats),
                  "errors": sum(s["status"] == "error" for s in snap["steps"]),
                  "blocked": dict(Counter((s.get("error") or {}).get("type") or "error"
                                          for s in snap["steps"] if s["status"] == "error").most_common()),
                  "tools": dict(tools.most_common())},
        "decisions": [{k: d[k] for k in ("decision_id", "parent_id", "tool", "rationale", "alternatives",
                                         "confidence", "verdict", "claim_ids")}
                      | {"rv": [{k: r[k] for k in ("rule_id", "verdict", "reason")} for r in d["rv"]]}
                      for d in snap.get("decisions") or []],
        "markers": [{"lon": m["lon"], "lat": m["lat"], "status": m["status"], "confidence": m["confidence"],
                     "label": m["label"], "claim_id": m["claim_id"],
                     "earned": (m.get("confidence_provenance") or {}).get("label"),
                     "lowered": (m.get("confidence_provenance") or {}).get("lowered", [])} for m in snap["markers"]],
        "scores": {name: {"status": sec["status"], "reason": sec.get("reason"),
                          "scores": [{k: s.get(k) for k in ("metric", "value", "unit", "numerator", "denominator",
                                                            "basis")} for s in sec.get("scores") or []]}
                   for name, sec in snap["evaluation"].items()},
        "rules_basis": rules.get("reason"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_id", nargs="?", default="exp-nagoya-sonnet-1")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "store"
        subprocess.run([sys.executable, str(ROOT / "scripts/replay_live.py"), a.run_id, "--store", str(store)],
                       check=True, stdout=subprocess.DEVNULL)
        from treehouse.ui.web import Controller

        snap = Controller(store.resolve()).snapshot(a.run_id)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(slim(snap), indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {a.out.relative_to(ROOT)} ({a.out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
