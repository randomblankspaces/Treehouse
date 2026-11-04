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
    from treehouse.service import DemoError, evaluate as evaluate_run, run
    from treehouse.store.local import LocalStore, default_store_root

    if mode not in ("fake", "replay", "record"):
        typer.echo(f"FAIL mode {mode!r}: use fake, replay or record (live runs need the Bedrock adapter, P6)",
                   err=True)
        raise typer.Exit(2)
    cfg = RunConfig.model_validate_json(config.read_bytes())
    st = LocalStore(store or default_store_root())
    rid = run_id or config.stem
    try:
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
