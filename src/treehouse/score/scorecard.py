"""Scorecard for the demo skeleton (P5): Panel 1 basics from R4 and the trace, and Panel 5 (cost, speed,
data). Every number is MEASURED from the sealed trace and carries ``synthetic`` and ``replayed``.
``bytes_read`` from the synthetic block model is chipped "modelled bytes". Panels 2 and 3 arrive in P7."""

from __future__ import annotations

from treehouse.schemas.checks import CheckLedger
from treehouse.schemas.numbers import Tier, TypedNumber
from treehouse.schemas.scorecard import Panel, Scorecard
from treehouse.sealed import SealedRun

VERSION = "score-p5-v1"
P7 = "arrives with P7 (checks and panels)"


def _num(run: SealedRun, metric: str, value, type_: str, panel: str, n: int | None, **detail) -> TypedNumber:
    return TypedNumber(metric=metric, value=value, type=type_, tier=Tier.MEASURED, panel=panel, n=n,
                       estimator_version=VERSION, config_hash=run.manifest.config_hash,
                       manifest_ref=run.manifest_ref, synthetic=run.synthetic, replayed=run.replayed,
                       detail=detail)


def process_panel(run: SealedRun, ledgers: list[CheckLedger]) -> Panel:
    n = len(ledgers)
    r4 = sum(1 for lg in ledgers for r in lg.results if r.check_id == "R4" and r.result == "pass")
    calls = [c for t in run.trials for c in t.calls]
    nums = {
        "claims": _num(run, "claims", n, "count", "process", n),
        "forbidden_attempts": _num(run, "forbidden_attempts", sum(c.key_access_attempt for c in calls), "count",
                                   "process", len(calls)),
        "blocked_calls": _num(run, "blocked_calls", sum(c.status == "blocked" for c in calls), "count", "process",
                              len(calls)),
        "tool_errors": _num(run, "tool_errors", sum(c.status == "error" for c in calls), "count", "process",
                            len(calls)),
    }
    if n:
        nums["grounding_rate"] = _num(run, "grounding_rate", round(r4 / n, 6), "proportion", "process", n,
                                      rule="R4")
    return Panel(name="process", version=VERSION, numbers=nums)


def cost_panel(run: SealedRun) -> Panel:
    spans = [s for t in run.trials for s in t.spans]
    chats = [s for s in spans if s.op == "chat"]
    calls = [c for t in run.trials for c in t.calls]
    windows = [c for c in calls if c.name == "imagery_window" and c.status == "success"]
    # no windows => zero bytes, trivially measured (an empty set used to fall through to the invalid "mixed")
    models = {str(w.payload.get("detail", {}).get("bytes_model", "measured")) for w in windows} or {"measured"}
    bytes_detail = {"bytes_model": models.pop()} if len(models) == 1 else {"bytes_model": "mixed"}
    if bytes_detail["bytes_model"] != "measured":
        bytes_detail["chip"] = "modelled bytes"
    tin = sum(int(s.attributes.get("gen_ai.usage.input_tokens", 0)) for s in chats)
    tout = sum(int(s.attributes.get("gen_ai.usage.output_tokens", 0)) for s in chats)
    usd = sum(float(s.attributes.get("treehouse.cost.usd", 0.0)) for s in chats)
    nums = {
        "usd.worker": _num(run, "usd.worker", round(usd, 6), "usd", "cost", len(chats),
                           price_table=str(chats[0].attributes.get("treehouse.price_table.version", "none"))
                           if chats else "none"),
        "model_calls": _num(run, "model_calls", len(chats), "count", "cost", len(chats)),
        "tokens.input": _num(run, "tokens.input", tin, "tokens", "cost", len(chats)),
        "tokens.output": _num(run, "tokens.output", tout, "tokens", "cost", len(chats)),
        "tool_calls": _num(run, "tool_calls", len(calls), "count", "cost", len(calls)),
        "windows": _num(run, "windows", len(windows), "count", "cost", len(windows)),
        "bytes_read": _num(run, "bytes_read", sum(int(w.payload.get("bytes_read", 0)) for w in windows), "bytes",
                           "cost", len(windows), **bytes_detail),
    }
    note = "tool latency is not measured in replay (logical clock)" if run.replayed else None
    return Panel(name="cost", version=VERSION, numbers=nums, no_grade_reason=note)


def build_scorecard(run: SealedRun, ledgers: list[CheckLedger], *, trust_ref: str | None = None) -> Scorecard:
    return Scorecard(run_ref=run.manifest_ref, process=process_panel(run, ledgers),
                     understanding=Panel(name="understanding", version=VERSION,
                                         no_grade_reason=f"must_notice coverage {P7}"),
                     output=Panel(name="output", version=VERSION,
                                  no_grade_reason=f"keyed precision and recall {P7}; R1/R2/R4 are in the claim table"),
                     cost=cost_panel(run), trust_ref=trust_ref, versions={"score": VERSION})
