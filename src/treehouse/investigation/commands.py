"""Explicit local sandbox actions. GET/UI paths never invoke these provider factories."""

import importlib
import json
from pathlib import Path
from typing import Annotated

import typer

from treehouse.canon import canonical_json

sandbox_app = typer.Typer(help="Opt-in agent investigations using trusted local plugins.", no_args_is_help=True)


def _factory(spec):
    module, separator, name = spec.partition(":")
    if not separator or not module or not name.isidentifier():
        raise ValueError("plugin must be a trusted installed Python module:factory")
    value = getattr(importlib.import_module(module), name)
    if not callable(value):
        raise ValueError("plugin factory is not callable")
    return value


@sandbox_app.command("demo")
def demo_command(
    store: Annotated[Path, typer.Option("--store")] = Path("out/investigation/store"),
    run_id: Annotated[str, typer.Option("--run-id")] = "investigation-demo",
):
    """Run the offline observation-driven synthetic example, seal it and build the existing UI bundle."""
    from treehouse.cards import load_card
    from treehouse.investigation import evaluate_investigation, run_investigation
    from treehouse.investigation.example import ObservationExample
    from treehouse.paths import repo_root
    from treehouse.service import demo_config, evaluate
    from treehouse.store.local import LocalStore

    card = load_card(repo_root() / "tasks/synth-crossings-v1.yaml")
    card = card.model_copy(update={"tools_allowed": [*card.tools_allowed, "record_decision", "classify_window"]})
    config = demo_config({"policy": "good", "run_id": run_id}, card, mode="fake")
    st = LocalStore(store)
    result = run_investigation(st, card, config, ObservationExample(), run_id=run_id)
    evaluate(st, run_id)  # explicit write action prepares the ordinary ReportBundle for the UI
    report = evaluate_investigation(st, run_id)
    typer.echo(f"sealed {run_id}: {result.trials[0].stop}; {result.trials[0].n_claims} claim(s); synthetic example")
    typer.echo(f"manifest {report['manifest_ref']}")
    typer.echo(f"UI bundle {st.root / 'bundles' / run_id / 'bundle.json'}")


@sandbox_app.command("run")
def run_command(
    task: Annotated[Path, typer.Option("--task")],
    config: Annotated[Path, typer.Option("--config")],
    provider: Annotated[str, typer.Option("--provider", help="Trusted installed module:factory; no automatic provider fallback.")],
    run_id: Annotated[str, typer.Option("--run-id")],
    store: Annotated[Path, typer.Option("--store")],
    classifier: Annotated[str | None, typer.Option("--classifier", help="Optional trusted module:factory.")] = None,
    servers: Annotated[str | None, typer.Option("--servers", help="Trusted server factory replacing/augmenting default MCP servers.")] = None,
    bundle: Annotated[bool, typer.Option("--bundle/--no-bundle")] = True,
):
    """Invoke trusted server-owned Python plugins explicitly. Live paid calls belong on Kiro only."""
    from treehouse.cards import load_card
    from treehouse.investigation import run_investigation
    from treehouse.schemas.config import RunConfig
    from treehouse.service import evaluate
    from treehouse.store.local import LocalStore

    card = load_card(task)
    cfg = RunConfig.model_validate_json(config.read_bytes())
    st = LocalStore(store)
    worker = _factory(provider)(card=card, config=cfg)
    vision = _factory(classifier)(card=card, config=cfg) if classifier else None
    result = run_investigation(st, card, cfg, worker, run_id=run_id, classifier=vision,
                              server_factory=_factory(servers) if servers else None)
    if bundle:
        evaluate(st, run_id)
    typer.echo(canonical_json({"manifest_ref": result.manifest.manifest_hash,
                               "trials": [{"trial_id": t.trial_id, "stop": t.stop,
                                           "claims": t.n_claims, "detail": t.detail} for t in result.trials]}))


@sandbox_app.command("evaluate")
def evaluate_command(
    run_id: Annotated[str, typer.Argument()],
    store: Annotated[Path, typer.Option("--store")],
    reference: Annotated[Path | None, typer.Option("--reference", help="Grader-only reference JSON; never supplied to the worker.")] = None,
):
    """Verify and print an independent report without modifying the sealed store."""
    from treehouse.investigation import evaluate_investigation
    from treehouse.store.local import LocalStore

    typer.echo(canonical_json(evaluate_investigation(LocalStore(store), run_id, reference=reference)))


@sandbox_app.command("export")
def export_command(
    run_id: Annotated[str, typer.Argument()],
    store: Annotated[Path, typer.Option("--store")],
    output: Annotated[Path, typer.Option("--output", help="New directory only; existing output is refused.")],
):
    """Export exact sealed claims as SQLite and positive detections as GeoJSON."""
    from treehouse.investigation import export_database
    from treehouse.store.local import LocalStore

    typer.echo(canonical_json(export_database(LocalStore(store), run_id, output)))


@sandbox_app.command("review")
def review_command(
    run_id: Annotated[str, typer.Argument()],
    store: Annotated[Path, typer.Option("--store")],
    reviewer: Annotated[str, typer.Option("--reviewer", help="Trusted module:factory providing a distinct ModelProvider.")],
    model_id: Annotated[str, typer.Option("--model-id")],
    output: Annotated[Path, typer.Option("--output", help="New JSON file; review helper never mutates the sealed store.")],
):
    """One explicit optional model-estimated process review; never an automatic page-load inference."""
    from treehouse.investigation import review_investigation
    from treehouse.schemas.config import InferenceParams
    from treehouse.store.local import LocalStore

    if output.exists():
        raise typer.BadParameter("output already exists")
    result = review_investigation(LocalStore(store), run_id, _factory(reviewer)(card=None, config=None),
                                  model_id=model_id, params=InferenceParams(max_tokens=800))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    typer.echo(str(output))
