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
        if m.near_matches:
            typer.echo(f"  near matches (listed ids sharing the registry stem): {', '.join(m.near_matches)}")
        if m.invoke_id_used and m.invoke_id_used != m.inference_profile:
            typer.echo(f"  -> config/models.yaml, key {m.key}: set `inference_profile: {m.invoke_id_used}`")
    for c in report.checks:
        if c.status != "ok":
            typer.echo(f"  {c.status:<14} {c.name} {c.error_code or ''}")
    typer.echo(f"probe spend: reserved ${report.spend.reserved_usd:.2f} of ${report.spend.cap_usd:.2f}, "
               f"committed ${report.spend.committed_usd:.4f} (estimated, {report.spend.price_table})")


def _ledger(prices_path: Path | None = None):
    """A ledger for reading/planning. The price table is only used for planning, so a synthetic table passed
    with --prices is allowed here (the CLI never makes a live call)."""
    from treehouse.providers.prices import PriceTable, load_default
    from treehouse.providers.registry import ModelRegistry
    from treehouse.providers.spend import SpendLedger

    prices = PriceTable.load(prices_path) if prices_path else load_default()
    return SpendLedger(prices=prices, registry=ModelRegistry.load(), allow_synthetic=True), prices


def _level_exit(level: str) -> int:
    return {"ok": 0, "over_planned": 0, "over_alarm": 2, "hard_stop": 3}[level]


NOT_THE_BILL = ("note: this ledger counts only Treehouse's own Bedrock calls at our price table; it is NOT the "
                "AWS bill. Check AWS Billing / Cost Explorer after each live step (treehouse budget reconcile).")


@budget_app.command("init")
def budget_init(
    account: Annotated[str | None, typer.Option("--account", help="Note which account (last 4 digits).")] = None,
    note: Annotated[str | None, typer.Option("--note")] = None,
) -> None:
    """Create the spend ledger (genesis row). Live calls refuse to reserve until this has run once."""
    from treehouse.providers.spend import SpendError, SpendLedger

    led = SpendLedger()
    try:
        led.init(account=account, note=note)
    except SpendError as e:
        typer.echo(f"FAIL {e}", err=True)
        raise typer.Exit(1) from e
    typer.echo(f"created spend ledger {led.path}; commit .spend/ after every live step")


@budget_app.command("status")
def budget_status() -> None:
    """Spent, reserved and the threshold level. Exits 2 above the $350 alarm, 3 at the hard stop,
    4 when the ledger is missing or is not the repo ledger that already holds spend."""
    from treehouse.providers.spend import SpendError, SpendLedger, repo_ledger_path

    ledger, _ = _ledger()
    try:
        st = ledger.status()
    except SpendError as e:
        typer.echo(f"FAIL {e}", err=True)
        raise typer.Exit(4) from e
    typer.echo(f"ledger: {st.path}")
    if not st.initialized:
        typer.echo(f"NO LEDGER: {st.path} does not exist (or has no genesis row). Live calls will be refused. "
                   "If this is the first live step run `uv run treehouse budget init`; otherwise find the "
                   "existing ledger (git log -- .spend/) and point TREEHOUSE_SPEND_LEDGER at it.", err=True)
        raise typer.Exit(4)
    repo = repo_ledger_path()
    if repo is not None and repo.resolve() != Path(st.path) and repo.is_file():
        other = SpendLedger(repo).status()
        if other.calls > st.calls:
            typer.echo(f"WRONG LEDGER: {st.path} has {st.calls} call(s) but the repo ledger {repo} has "
                       f"{other.calls} (${other.total_usd:.4f}). Unset or fix TREEHOUSE_SPEND_LEDGER.", err=True)
            raise typer.Exit(4)
    if st.calls == 0 and not st.open_reservations:
        typer.echo("WARNING: EMPTY LEDGER (0 calls). If any live call was ever made in this account, this is the "
                   "wrong file: stop and find the real ledger (git log -- .spend/).", err=True)
    typer.echo(f"spent ${st.spent_usd:.4f} (estimated ${st.estimated_usd:.4f}, ambiguous ${st.ambiguous_usd:.4f}) "
               f"+ reserved ${st.reserved_usd:.4f} = ${st.total_usd:.4f} over {st.calls} call(s)")
    typer.echo(f"planned ${st.planned:.0f} / alarm ${st.alarm:.0f} / hard stop ${st.hard_stop:.0f}: {st.level}")
    if st.overshoot_usd > 0:
        typer.echo(f"overshoot over reservations: ${st.overshoot_usd:.4f}")
    if st.open_reservations:
        typer.echo(f"open reservations: {len(st.open_reservations)} (a crashed process leaves these reserved; "
                   "see `treehouse budget open`)")
    for r in st.over_alarm_reasons:
        typer.echo(f"over-alarm reason: {r}")
    if st.last_reconcile:
        rc = st.last_reconcile
        typer.echo(f"last AWS reconcile {rc.get('ts')}: AWS ${rc['aws_usd']:.2f} vs ledger "
                   f"${rc['ledger_spent_usd']:.2f} (delta ${rc['delta_usd']:+.2f}, {rc.get('source')})")
    else:
        typer.echo("no AWS reconcile recorded yet")
    typer.echo(NOT_THE_BILL)
    if st.level in ("over_alarm", "hard_stop"):
        typer.echo("STOP: spend is above the alarm; tell Suhas before any further live call", err=True)
    raise typer.Exit(_level_exit(st.level))


@budget_app.command("open")
def budget_open() -> None:
    """List open reservations (reserved, never committed or released)."""
    from treehouse.providers.spend import SpendLedger

    rows = SpendLedger().open_reservations()
    for r in rows:
        typer.echo(f"{r['id']} {r.get('ts')} {r.get('model_key')} worst ${float(r['worst_usd']):.4f}")
    typer.echo(f"{len(rows)} open reservation(s), ${sum(float(r['worst_usd']) for r in rows):.4f} reserved")


@budget_app.command("release-stale")
def budget_release_stale(
    reason: Annotated[str, typer.Option("--reason", help="Why (logged in the ledger).")],
    older_than_min: Annotated[float, typer.Option("--older-than-min")] = 60.0,
    release: Annotated[bool, typer.Option("--release", help="Drop them instead of booking them as spent. Only "
                                          "when you KNOW the calls never reached Bedrock.")] = False,
) -> None:
    """Resolve open reservations older than N minutes. Default: book each at its worst case (estimated,
    ambiguous), because a crashed call may have been billed."""
    from treehouse.providers.spend import SpendLedger

    done = SpendLedger().resolve_stale(older_than_s=older_than_min * 60, release=release, reason=reason)
    verb = "released" if release else "booked as spent at worst case"
    typer.echo(f"{len(done)} stale reservation(s) {verb}: ${sum(float(r['worst_usd']) for r in done):.4f}")


@budget_app.command("reconcile")
def budget_reconcile(
    aws_usd: Annotated[float, typer.Option("--aws-usd", help="Month-to-date cost from AWS Billing/Cost Explorer.")],
    source: Annotated[str, typer.Option("--source", help="e.g. 'aws ce get-cost-and-usage 2026-11-04'.")],
    note: Annotated[str | None, typer.Option("--note")] = None,
) -> None:
    """Record the AWS bill figure next to the ledger (the ledger is not the bill). Exits 2 if AWS > ledger + $25."""
    from treehouse.providers.spend import SpendLedger

    row = SpendLedger().reconcile(aws_usd, source=source, note=note)
    typer.echo(f"AWS ${row['aws_usd']:.2f} vs ledger ${row['ledger_spent_usd']:.2f}: delta ${row['delta_usd']:+.2f}")
    if row["delta_usd"] > 25:
        typer.echo("STOP: AWS reports much more than the ledger; tell Suhas before any further live call", err=True)
        raise typer.Exit(2)


@budget_app.command("plan")
def budget_plan(
    task: Annotated[Path | None, typer.Option("--task", help="Task card; uses its per-run budget.usd cap.")] = None,
    trials: Annotated[int, typer.Option("--trials")] = 1,
    model: Annotated[str | None, typer.Option("--model", help="Registry key (default: the default worker).")] = None,
    verifier_calls: Annotated[int, typer.Option("--verifier-calls", help="Verifier calls per trial.")] = 0,
    verifier_input_tokens: Annotated[int, typer.Option("--verifier-input-tokens")] = 8000,
    verifier_max_tokens: Annotated[int, typer.Option("--verifier-max-tokens")] = 1024,
    calls: Annotated[int, typer.Option("--calls", help="Model calls per trial (without --task).")] = 40,
    input_tokens: Annotated[int, typer.Option("--input-tokens", help="Estimated MEAN input tokens per call (the "
                                              "history grows each turn; raise it for long image loops).")] = 20000,
    max_tokens: Annotated[int, typer.Option("--max-tokens")] = 4096,
    prices: Annotated[Path | None, typer.Option("--prices", help="Price table (default: the dated table).")] = None,
) -> None:
    """Worst-case cost of a planned run against the ledger thresholds. Exits 1 if a model is unpriced, 2/3 if it
    would pass alarm/hard stop. With --task the worker is capped at budget.usd PLUS one call's worst case
    (the per-run guard checks before each call, so the last call can overshoot)."""
    from treehouse.providers.prices import profile_of
    from treehouse.providers.registry import ModelRegistry

    ledger, table = _ledger(prices)
    reg = ModelRegistry.load()
    key = model or reg.defaults.get("worker", "")
    entry = reg.get(key)
    price = table.price(entry.price_ref, profile_of(entry.invoke_id))
    if price is None or not price.priced:
        typer.echo(f"UNPRICED: {entry.key} has a null price in {table.version}; every live call would be refused. "
                   "Fill the price table (K2a) and run `treehouse prices check`", err=True)
        raise typer.Exit(1)
    per_call = price.worst_case(input_tokens, max_tokens)
    per_trial = per_call * calls
    basis = f"{calls} calls x (in {input_tokens} + out {max_tokens} tokens) at {table.version}"
    if task is not None:
        from treehouse.cards import load_card

        card = load_card(task)
        if card.budget.enabled and card.budget.usd is not None and card.budget.usd + per_call < per_trial:
            per_trial = card.budget.usd + per_call
            basis = (f"per-run budget.usd cap ${card.budget.usd:.2f} from {task.name} + one call overshoot "
                     f"${per_call:.4f} (else {basis})")
    if verifier_calls > 0:
        vkey = reg.defaults.get("verifier", "")
        ventry = reg.get(vkey)
        vprice = table.price(ventry.price_ref, profile_of(ventry.invoke_id))
        if vprice is None or not vprice.priced:
            typer.echo(f"UNPRICED: verifier {ventry.key} has a null price in {table.version}", err=True)
            raise typer.Exit(1)
        vcost = vprice.worst_case(verifier_input_tokens, verifier_max_tokens) * verifier_calls
        per_trial += vcost
        basis += (f"; verifier {ventry.key}: {verifier_calls} calls x (in {verifier_input_tokens} + out "
                  f"{verifier_max_tokens}) = ${vcost:.4f}")
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
    """Report prices per registry model and inference profile, with the $/1M equivalent. Exits 1 if the default
    worker or verifier has no priced row for the exact profile it calls, or the table fails the plausibility band."""
    from treehouse.providers.prices import PriceError, PriceTable, load_default, profile_of
    from treehouse.providers.registry import ModelRegistry

    try:
        t = PriceTable.load(table) if table else load_default()
    except (PriceError, ValueError) as e:
        typer.echo(f"FAIL {e}", err=True)
        raise typer.Exit(1) from e
    reg = ModelRegistry.load()
    typer.echo(f"table {t.version} ({t.region}, {t.unit}); source={t.source} retrieved={t.retrieved}"
               + (f" unit_source={t.unit_source}" if t.unit_source else "")
               + (" SYNTHETIC" if t.synthetic else "") + (" ESTIMATED/PLACEHOLDER" if t.estimated else ""))
    required = {v: k for k, v in reg.defaults.items()}
    bad: list[str] = []
    for m in reg.models:
        prof = profile_of(m.invoke_id)
        p, row = t.resolve(m.price_ref, prof)
        exact = f"{m.price_ref}@{prof}" if prof else m.price_ref
        fields = {f: getattr(p, f) if p else None for f in ("input", "output", "cache_read", "cache_write")}
        nulls = [f for f, v in fields.items() if v is None]
        state = "ok" if p is not None and p.priced else "UNPRICED"
        if state == "ok" and row != exact:
            state = "FALLBACK"
        role = f" [{required[m.key]}]" if m.key in required else ""
        per_m = " ".join(f"{f}=${v * 1000:g}/1M" for f, v in fields.items() if v is not None)
        typer.echo(f"{m.key}{role} via {m.invoke_id} (row {row}): {state} "
                   + " ".join(f"{f}={v}" for f, v in fields.items())
                   + (f" (null: {', '.join(nulls)})" if nulls else "") + (f"\n    = {per_m}" if per_m else ""))
        if state == "FALLBACK":
            typer.echo(f"    no priced {exact} row: the ledger uses {row}; fill {exact} for the profile you call")
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


@app.command("demo")
def demo_cmd(
    out: Annotated[Path, typer.Option("--out", help="Output directory (store and index.html).")] = Path("out/demo"),
) -> None:
    """Replay every demo run offline into a fresh store, check, score, trust (stub), report and verify."""
    from treehouse.service import DemoError, demo

    try:
        demo(out, echo=typer.echo)
    except DemoError as e:
        typer.echo(f"FAIL {e}", err=True)
        raise typer.Exit(1) from e


@app.command("run")
def run_cmd(
    config: Annotated[Path, typer.Argument(help="RunConfig JSON (e.g. fixtures/demo/configs/synth-good.json).")],
    mode: Annotated[str, typer.Option("--mode", help="fake | replay | record (live needs P6).")] = "replay",
    run_id: Annotated[str | None, typer.Option("--run-id", help="Run id (default: the config file stem).")] = None,
    store: Annotated[Path | None, typer.Option("--store", help="Store root (default $TREEHOUSE_STORE).")] = None,
    cassette_out: Annotated[Path, typer.Option("--cassette-out", help="Where record mode writes cassettes.")]
    = Path("out/cassettes"),
    evaluate: Annotated[bool, typer.Option("--evaluate/--no-evaluate", help="Check, score, trust, report.")] = True,
) -> None:
    """Run one config through the plain loop, the gateway and the in-process MCP servers, and seal it."""
    from treehouse.schemas.config import RunConfig
    from treehouse.service import DemoError, preflight_recording, run
    from treehouse.service import evaluate as evaluate_run
    from treehouse.store.local import LocalStore, default_store_root

    if mode not in ("fake", "replay", "record"):
        typer.echo(f"FAIL mode {mode!r}: use fake, replay or record (live runs need the Bedrock adapter, P6)",
                   err=True)
        raise typer.Exit(2)
    cfg = RunConfig.model_validate_json(config.read_bytes())
    rid = run_id or config.stem
    try:
        if mode == "record":
            preflight_recording(rid, cfg.trials, cassette_out)
        st = LocalStore(store or default_store_root())
        out = run(st, cfg, run_id=rid, mode=mode, cassette_out=cassette_out)  # type: ignore[arg-type]
    except DemoError as e:
        typer.echo(f"FAIL {e}", err=True)
        raise typer.Exit(1) from e
    for t in out.trials:
        typer.echo(f"sealed {rid} {t.trial_id}: stop={t.stop} claims={t.n_claims} head={t.head}")
    if evaluate:
        ev = evaluate_run(st, rid)
        typer.echo(f"report {st.root / 'bundles' / rid / 'report.html'} (trust: {ev.passport.headline.chip()})")


if __name__ == "__main__":  # pragma: no cover
    app()
