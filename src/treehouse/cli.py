"""Command-line entry point. Sub-commands are added by later packages."""

from __future__ import annotations

import typer

from treehouse import __version__

app = typer.Typer(
    help="Treehouse: observe, check, score and estimate trust for agent runs.", no_args_is_help=True
)


@app.callback()
def main() -> None:
    """Treehouse command-line interface."""


@app.command()
def version() -> None:
    """Print the Treehouse version."""
    typer.echo(__version__)


if __name__ == "__main__":  # pragma: no cover
    app()
