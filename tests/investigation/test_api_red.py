"""Independent API smoke test, authored before the investigation implementation."""
import importlib


def test_investigation_public_api_exists():
    try:
        module = importlib.import_module("treehouse.investigation")
    except ModuleNotFoundError as exc:
        if exc.name != "treehouse.investigation":
            raise
        module = None
    assert module is not None, "the investigation public API does not yet exist"
    assert callable(getattr(module, "run_investigation", None))
    assert callable(getattr(module, "evaluate_investigation", None))
