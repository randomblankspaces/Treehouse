"""Command-line entry point. Sub-commands are added by later packages."""

from __future__ import annotations

import json
from pathlib import Path

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


if __name__ == "__main__":  # pragma: no cover
    app()
