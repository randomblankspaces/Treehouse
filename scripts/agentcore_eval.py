"""KA2: run Amazon Bedrock AgentCore Evaluations on a sealed Treehouse run (a comparison signal only).

    uv run python scripts/agentcore_eval.py --run out/demo/store/runs/synth-good \\
        --evaluators Builtin.TrajectoryInOrderMatch,Builtin.GoalSuccessRate,<treehouse_rules-id>

``--run`` is a sealed run directory inside a store (``<store>/runs/<run_id>``). The run is verified and loaded,
converted to AgentCore session spans plus ground truth from the task card, evaluated once per evaluator,
and the raw results are written append-only to ``<store>/comparisons/agentcore/<run_id>/<sha256>.json``
(outside ``runs/`` and ``evals/``, so they never reach the scorecard). Requires ``uv sync --extra aws``.
AgentCore's LLM-judged built-ins bill Bedrock tokens to the account; they are NOT in the Treehouse ledger.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from treehouse.aws.agentcore import record_results, run_agentcore_eval
from treehouse.service import load_sealed
from treehouse.store.local import LocalStore


def _load_tool_args(run_dir: Path) -> dict[str, object] | None:
    ledgers = sorted((run_dir / "trials").glob("*.investigation.json"))
    if not ledgers:
        return None
    tool_args = {}
    for path in ledgers:
        for action in json.loads(path.read_text()).get("actions", []):
            tool_args[action["span_id"]] = action["parameters"]
    return tool_args


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, required=True, help="<store>/runs/<run_id>")
    ap.add_argument("--evaluators", required=True, help="comma-separated evaluator ids")
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--no-references", action="store_true", help="send no ground truth (reference-free run)")
    a = ap.parse_args(argv)
    run_dir = a.run.resolve()
    if run_dir.parent.name != "runs" or not (run_dir / "SEALED").is_file():
        print(f"error: {a.run} is not a sealed run directory under <store>/runs/", file=sys.stderr)
        return 2
    store = LocalStore(run_dir.parent.parent)
    run = load_sealed(store, run_dir.name)
    evaluators = [e.strip() for e in a.evaluators.split(",") if e.strip()]
    results = run_agentcore_eval(run, evaluators, region=a.region, references=[] if a.no_references else None,
                                 tool_args=_load_tool_args(run_dir))
    key = record_results(store, run, evaluators, results)
    for r in results:
        print(json.dumps({"evaluator": r.evaluator_id, "trace": r.trace_id, "label": r.label, "value": r.value,
                          "error": r.error_code, "ignored": r.ignored_reference_fields}))
    print(f"wrote {store.root / key}")
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
