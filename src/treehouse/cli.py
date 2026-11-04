"""Command-line entry point. Sub-commands are added by later packages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from treehouse import __version__

app = typer.Typer(
    help="Treehouse: observe, check, score and estimate trust for agent runs.", no_args_is_help=True
)
task_app = typer.Typer(help="Task cards.", no_args_is_help=True)
app.add_typer(task_app, name="task")
probe_app = typer.Typer(help="AWS capability probe results (K1).", no_args_is_help=True)
app.add_typer(probe_app, name="probe")
budget_app = typer.Typer(help="Account-wide spend ledger ($250 planned / $350 alarm / $450 hard stop).",
                         no_args_is_help=True)
app.add_typer(budget_app, name="budget")
prices_app = typer.Typer(help="Dated Bedrock price tables.", no_args_is_help=True)
app.add_typer(prices_app, name="prices")


@app.callback()
def main() -> None:
    """Treehouse command-line interface."""


@app.command()
def version() -> None:
    """Print the Treehouse version."""
    typer.echo(__version__)


@app.command()
def schema(
    name: str = typer.Argument(None, help="Schema name; see --list."),
    list_: bool = typer.Option(False, "--list", help="List schema names."),
) -> None:
    """Print the JSON Schema of a Treehouse record."""
    from treehouse.schemas.registry import SCHEMAS

    if list_ or not name:
        typer.echo("\n".join(sorted(SCHEMAS)))
        return
    if name not in SCHEMAS:
        typer.echo(f"unknown schema {name!r}; try --list", err=True)
        raise typer.Exit(2)
    typer.echo(json.dumps(SCHEMAS[name].model_json_schema(), indent=2, sort_keys=True))


@task_app.command("validate")
def task_validate(path: Path) -> None:
    """Validate a task card. Exits 1 on any error; warnings do not fail."""
    from treehouse.cards import describe_obligations, validate_card

    report = validate_card(path)
    for e in report.errors:
        typer.echo(f"ERROR {e}")
    for w in report.warnings:
        typer.echo(f"warning {w}")
    if report.errors:
        raise typer.Exit(1)
    typer.echo(f"ok {path}\ncard hash: {report.card_hash}\nlicense floor: {report.license_floor}")
    typer.echo(f"license obligations: {describe_obligations(report.license_obligations)}")


@app.command("verify")
def verify_cmd(
    run_id: str = typer.Argument(None, help="Run id; omit to verify the whole store."),
    store: Annotated[
        Path | None, typer.Option("--store", help="Store root (default $TREEHOUSE_STORE or ./.treehouse).")
    ] = None,
    expect_head: Annotated[
        str | None, typer.Option("--expect-head", help="A ledger head recorded earlier; FAIL if it is no longer "
                                                        "a line of the ledger (the store was rewritten).")
    ] = None,
) -> None:
    """Verify traces, file hashes, manifests, the ledger chain, blobs and evals. Exits 1 on any problem.
    Prints the ledger head: record it outside the store, since the store alone cannot detect a full rewrite."""
    from treehouse.store.local import LocalStore, default_store_root
    from treehouse.store.verify import verify

    root = store or default_store_root()
    if not root.is_dir():
        typer.echo(f"FAIL {root}: store not found", err=True)
        raise typer.Exit(1)
    report = verify(LocalStore(root), run_id, expected_head=expect_head)
    for p in report.problems:
        typer.echo(str(p))
    head = f"ledger head: {report.ledger_head} ({report.ledger_n_lines} line(s))"
    if not report.ok:
        typer.echo(head)
        raise typer.Exit(1)
    typer.echo(f"ok {root}: {report.runs} run(s), {report.records} record(s), {report.blobs} blob(s)\n{head}")


@probe_app.command("import")
def probe_import(
    path: Path,
    store: Annotated[Path | None, typer.Option("--store", help="Store root (default $TREEHOUSE_STORE).")] = None,
) -> None:
    """Validate an aws-capabilities.json (treehouse.aws-capabilities/v1) and copy it into the store."""
    from treehouse.schemas.probe import AwsCapabilities
    from treehouse.store.local import default_store_root

    try:
        report = AwsCapabilities.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        typer.echo(f"FAIL {path}: not a treehouse.aws-capabilities/v1 document: {e}", err=True)
        raise typer.Exit(1) from e
    dest = (store or default_store_root()) / "probes" / "aws-capabilities.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")
    typer.echo(f"imported {path} -> {dest}")
    typer.echo(f"identity: {report.execution.get('identity_arn')} locus: {report.execution.get('locus')} "
               f"region: {report.region}")
    typer.echo("summary: " + " ".join(f"{k}={v}" for k, v in report.summary.items()))
    for m in report.models:
        typer.echo(f"model {m.key}: listed={m.listed} profile_listed={m.profile_listed} "
                   f"user_turn_image={m.user_turn_image} tool_result_image={m.tool_result_image} "
                   f"invoke_id={m.invoke_id_used} recommended_image_delivery={m.recommended_image_delivery}")
    for c in report.checks:
        if c.status != "ok":
            typer.echo(f"  {c.status:<14} {c.name} {c.error_code or ''}")
    typer.echo(f"probe spend: reserved ${report.spend.reserved_usd:.2f} of ${report.spend.cap_usd:.2f}, "
               f"committed ${report.spend.committed_usd:.4f} (estimated, {report.spend.price_table})")


def _ledger(prices_path: Path | None = None):
    from treehouse.providers.prices import PriceTable, load_default
    from treehouse.providers.registry import ModelRegistry
    from treehouse.providers.spend import SpendLedger

    prices = PriceTable.load(prices_path) if prices_path else load_default()
    return SpendLedger(prices=prices, registry=ModelRegistry.load()), prices


def _level_exit(level: str) -> int:
    return {"ok": 0, "over_planned": 0, "over_alarm": 2, "hard_stop": 3}[level]


@budget_app.command("status")
def budget_status() -> None:
    """Spent, reserved and the threshold level. Exits 2 above the $350 alarm, 3 at the hard stop."""
    ledger, _ = _ledger()
    st = ledger.status()
    typer.echo(f"ledger: {st.path}")
    typer.echo(f"spent ${st.spent_usd:.4f} (estimated ${st.estimated_usd:.4f}) + reserved ${st.reserved_usd:.4f} "
               f"= ${st.total_usd:.4f} over {st.calls} call(s)")
    typer.echo(f"planned ${st.planned:.0f} / alarm ${st.alarm:.0f} / hard stop ${st.hard_stop:.0f}: {st.level}")
    if st.open_reservations:
        typer.echo(f"open reservations: {len(st.open_reservations)} (a crashed process leaves these reserved)")
    for r in st.over_alarm_reasons:
        typer.echo(f"over-alarm reason: {r}")
    if st.level in ("over_alarm", "hard_stop"):
        typer.echo("STOP: spend is above the alarm; tell Suhas before any further live call", err=True)
    raise typer.Exit(_level_exit(st.level))


@budget_app.command("plan")
def budget_plan(
    task: Annotated[Path | None, typer.Option("--task", help="Task card; uses its per-run budget.usd cap.")] = None,
    trials: Annotated[int, typer.Option("--trials")] = 1,
    model: Annotated[str | None, typer.Option("--model", help="Registry key (default: the default worker).")] = None,
    calls: Annotated[int, typer.Option("--calls", help="Model calls per trial (without --task).")] = 40,
    input_tokens: Annotated[int, typer.Option("--input-tokens", help="Estimated input tokens per call.")] = 20000,
    max_tokens: Annotated[int, typer.Option("--max-tokens")] = 4096,
    prices: Annotated[Path | None, typer.Option("--prices", help="Price table (default: the dated table).")] = None,
) -> None:
    """Worst-case cost of a planned run against the ledger thresholds. Exits 2/3 if it would pass alarm/hard stop."""
    from treehouse.providers.registry import ModelRegistry

    ledger, table = _ledger(prices)
    reg = ModelRegistry.load()
    key = model or reg.defaults.get("worker", "")
    entry = reg.get(key)
    price = table.price(entry.price_ref)
    per_call = price.worst_case(input_tokens, max_tokens) if price is not None and price.priced else None
    per_trial: float | None = per_call * calls if per_call is not None else None
    basis = f"{calls} calls x (in {input_tokens} + out {max_tokens} tokens) at {table.version}"
    if task is not None:
        from treehouse.cards import load_card

        card = load_card(task)
        if card.budget.enabled and card.budget.usd is not None:
            per_trial = card.budget.usd if per_trial is None else min(per_trial, card.budget.usd)
            basis = f"per-run budget.usd cap ${card.budget.usd:.2f} from {task.name}" + (
                "" if per_call is None else f" (or less: {basis})")
    if per_trial is None:
        typer.echo(f"UNPRICED: {entry.key} has a null price in {table.version} and no task usd cap; "
                   "fill the price table (K2a) or pass --task", err=True)
        raise typer.Exit(1)
    plan = per_trial * trials
    st = ledger.status()
    total = st.total_usd + plan
    level = ("hard_stop" if total > ledger.hard_stop else "over_alarm" if total > ledger.alarm
             else "over_planned" if total > ledger.planned else "ok")
    typer.echo(f"model {entry.key} ({entry.invoke_id}); basis: {basis}")
    typer.echo(f"plan: {trials} trial(s) x ${per_trial:.4f} = ${plan:.4f} worst case")
    typer.echo(f"ledger now ${st.total_usd:.4f}; after plan ${total:.4f} "
               f"(planned ${ledger.planned:.0f} / alarm ${ledger.alarm:.0f} / hard stop ${ledger.hard_stop:.0f}): "
               f"{level}")
    raise typer.Exit(_level_exit(level))


@prices_app.command("check")
def prices_check(
    table: Annotated[Path | None, typer.Option("--table", help="Price table (default: the dated table).")] = None,
) -> None:
    """Report null prices per registry model. Exits 1 if the default worker or verifier is unpriced."""
    from treehouse.providers.prices import PriceTable, load_default
    from treehouse.providers.registry import ModelRegistry

    t = PriceTable.load(table) if table else load_default()
    reg = ModelRegistry.load()
    typer.echo(f"table {t.version} ({t.region}, {t.unit}); source={t.source} retrieved={t.retrieved}"
               + (" SYNTHETIC" if t.synthetic else "") + (" ESTIMATED/PLACEHOLDER" if t.estimated else ""))
    required = {v: k for k, v in reg.defaults.items()}
    bad: list[str] = []
    for m in reg.models:
        p = t.price(m.price_ref)
        fields = {f: getattr(p, f) if p else None for f in ("input", "output", "cache_read", "cache_write")}
        nulls = [f for f, v in fields.items() if v is None]
        state = "ok" if p is not None and p.priced else "UNPRICED"
        role = f" [{required[m.key]}]" if m.key in required else ""
        typer.echo(f"{m.key}{role}: {state} " + " ".join(f"{f}={v}" for f, v in fields.items())
                   + (f" (null: {', '.join(nulls)})" if nulls else ""))
        if state != "ok" and m.key in required:
            bad.append(m.key)
    problems = []
    if bad:
        problems.append(f"default role model(s) unpriced: {', '.join(bad)}")
    if not t.synthetic and not t.estimated and (bad == [] and (not t.source or not t.retrieved)):
        problems.append("source and retrieved date must be filled")
    if t.synthetic:
        problems.append("synthetic table: not usable for reported costs")
    if t.estimated:
        problems.append("placeholder table: probe use only")
    for pr in problems:
        typer.echo(f"FAIL {pr}", err=True)
    if problems:
        raise typer.Exit(1)
    typer.echo("ok: worker and verifier are priced")


if __name__ == "__main__":  # pragma: no cover
    app()
