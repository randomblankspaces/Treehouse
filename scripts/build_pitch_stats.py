"""Build the pitch page's "By the numbers" data from committed evidence only.

    uv run python scripts/build_pitch_stats.py

Reads (never writes) the Bedrock spend ledger ``.spend/spend.jsonl`` and the live experiment matrix
``fixtures/live/experiments/metrics.json``; writes ``ui/src/pitch/data/stats.json``. Every number carries its source
and a basis label: ``measured`` (recorded from live runs), ``synthetic`` (live agent, synthetic embeddings/answer key)
or ``projection`` (arithmetic on measured means; not a quote or an AWS bill).
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / ".spend/spend.jsonl"
METRICS = ROOT / "fixtures/live/experiments/metrics.json"
OUT = ROOT / "ui/src/pitch/data/stats.json"

# The ADB benchmark scope in the inception report (Table 1 places and concepts, Table 7 "5 seeds"), used only to
# size a projection. Three worker models matches the live matrix (Sonnet, Nova Pro, Haiku).
BENCHMARK = {"places": 7, "asset_classes": 5, "models": 3, "seeds": 5}
IMAGERY_BUDGET_USD = 5000  # inception report §5.3: "planned imagery budget of up to $5,000" for test blocks


def ledger() -> dict:
    rows = [json.loads(line) for line in LEDGER.read_text().splitlines() if line.strip()]
    commits = [r for r in rows if r.get("kind") == "commit"]
    by_model: dict[str, dict] = defaultdict(lambda: {"calls": 0, "usd": 0.0, "input_tokens": 0, "output_tokens": 0})
    for r in commits:
        m, u = by_model[r["model_key"]], r.get("usage") or {}
        m["calls"] += 1
        m["usd"] += r.get("usd") or 0
        m["input_tokens"] += u.get("input_tokens") or 0
        m["output_tokens"] += u.get("output_tokens") or 0
    for m in by_model.values():
        m["usd_per_call"] = m["usd"] / m["calls"]
    return {"basis": "measured", "source": ".spend/spend.jsonl (Bedrock spend ledger, not the AWS bill)",
            "calls": len(commits), "usd": sum(r.get("usd") or 0 for r in commits),
            "input_tokens": sum(m["input_tokens"] for m in by_model.values()),
            "output_tokens": sum(m["output_tokens"] for m in by_model.values()),
            "first": commits[0]["ts"][:10], "last": commits[-1]["ts"][:10], "by_model": dict(by_model)}


def _metric(cfg: dict, name: str) -> dict:
    m = cfg["metrics"].get(name) or {}
    return {"mean": m.get("mean"), "interval_95": m.get("interval_95"), "n": m.get("n", 0)}


def matrix(m: dict) -> dict:
    configs = {}
    for label, cfg in m["configs"].items():
        card, model, harness = label.split("|")
        configs[label] = {"card": card, "model": model, "harness": harness,
                          **{k: _metric(cfg, k) for k in ("cost.usd", "cost.wall_seconds", "cost.tool_calls",
                                                         "cost.model_calls", "output.recall", "output.precision",
                                                         "output.count_ratio")}}
    runs = []
    for rid, run in m["runs"].items():
        for trial in run["panels_by_trial"].values():
            c = trial.get("cost") or {}
            if c.get("usd") is not None:
                runs.append({"run_id": rid, "usd": c["usd"], "wall_seconds": c.get("wall_seconds"),
                             "tool_calls": c.get("tool_calls")})
    usd = [r["usd"] for r in runs]
    wall = [r["wall_seconds"] for r in runs if r["wall_seconds"] is not None]
    baseline = m["comparisons"]["classifier"]["methods"]
    return {"basis": "synthetic", "source": "fixtures/live/experiments/metrics.json",
            "note": m["metadata"]["note"], "n_runs": len(runs),
            "usd_per_run": {"mean": statistics.mean(usd), "min": min(usd), "max": max(usd)},
            "wall_seconds": {"mean": statistics.mean(wall), "min": min(wall), "max": max(wall)},
            "configs": configs,
            "baseline": {"label": m["comparisons"]["classifier"]["label"],
                         "linear_probe_recall": baseline["linear_probe"]["recall"]["mean"],
                         "linear_svm_recall": baseline["linear_svm"]["recall"]["mean"],
                         "linear_probe_precision": baseline["linear_probe"]["precision"]["mean"]}}


def projection(per_run_usd: float, per_run_s: float) -> dict:
    runs = BENCHMARK["places"] * BENCHMARK["asset_classes"] * BENCHMARK["models"] * BENCHMARK["seeds"]
    return {"basis": "projection", "scope": BENCHMARK, "runs": runs,
            "bedrock_usd": runs * per_run_usd, "sequential_hours": runs * per_run_s / 3600,
            "imagery_budget_usd": IMAGERY_BUDGET_USD,
            "source": "measured mean cost and wall time per live run × ADB benchmark scope (inception report)"}


def main() -> int:
    m = json.loads(METRICS.read_text())
    mx = matrix(m)
    out = {"ledger": ledger(), "matrix": mx,
           "projection": projection(mx["usd_per_run"]["mean"], mx["wall_seconds"]["mean"])}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {mx['n_runs']} runs, ${out['ledger']['usd']:.2f} ledger, "
          f"{out['projection']['runs']} projected runs ≈ ${out['projection']['bedrock_usd']:.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
