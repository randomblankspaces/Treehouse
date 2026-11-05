"""Pitch page, demo mode C ("Live on Bedrock"): start ONE real Strands + Bedrock run from the pitch page.

Off unless the server operator sets ``TREEHOUSE_PITCH_LIVE=1``; a page load never starts a run, and the
browser can only press "start" on a pinned task + config (it sends no prompt, model or budget). Before each
run the repo spend guard is read and the run is refused when the ledger is missing or above the alarm.

The run uses the same path as ``treehouse sandbox run --provider treehouse.providers.factories:bedrock_recording``:
``run_investigation`` -> seal -> ``service.evaluate``, writing into the store the UI already serves, so the
finished run opens in the ordinary story and dev views. The Bedrock responses are recorded to a pixel-free
cassette under ``TREEHOUSE_PITCH_CASSETTES`` (default ``out/pitch-live``) so the run can be replayed later.

To strip this mode: delete this file, the ``pitch_live.register`` line in ``web.py``,
``tests/unit/test_pitch_live.py`` and ``ui/src/pitch/demo/live.tsx`` (+ its line in ``ui/src/pitch/demo/modes.ts``).
"""
# No ``from __future__ import annotations``: FastAPI must resolve the ``Request`` annotation imported in register().

import importlib.util
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from treehouse.paths import repo_root

ENV_FLAG = "TREEHOUSE_PITCH_LIVE"
ENV_CASSETTES = "TREEHOUSE_PITCH_CASSETTES"
TASK = Path("tasks/t1-nagoya-warehouses.yaml")
CONFIG = Path("fixtures/live/configs/t1-nagoya-sonnet-strands.json")
MAX_BODY = 64


def enabled() -> bool:
    return os.environ.get(ENV_FLAG) == "1"


def _missing_extras() -> list[str]:
    return [name for name in ("boto3", "strands") if importlib.util.find_spec(name) is None]


def budget_check() -> tuple[bool, str]:
    """(ok, reason) from the repo spend guard; never raises."""
    try:
        from treehouse.providers.prices import load_default
        from treehouse.providers.registry import ModelRegistry
        from treehouse.providers.spend import SpendLedger

        st = SpendLedger(prices=load_default(), registry=ModelRegistry.load()).status()
    except Exception as error:  # a broken ledger must refuse, not crash the page
        return False, f"Spend guard unreadable: {type(error).__name__}."
    if not st.initialized:
        return False, "Spend ledger not initialised (run `treehouse budget init` on the presenter machine)."
    if st.level in ("over_alarm", "hard_stop"):
        return False, f"Spend guard level is {st.level}; live runs are refused."
    return True, f"Spend guard ok: ${st.total_usd:.2f} of ${st.alarm:.0f} alarm used."


def status() -> dict[str, Any]:
    """What the pitch page shows before anyone presses start."""
    base = {"task": str(TASK), "config": str(CONFIG), "model_key": None, "harness": None, "synthetic": True}
    try:
        from treehouse.cards import load_card
        from treehouse.schemas.config import RunConfig

        card = load_card(repo_root() / TASK)
        cfg = RunConfig.model_validate_json((repo_root() / CONFIG).read_bytes())
        base.update(model_key=cfg.worker.model_key, harness=cfg.harness, synthetic=card.synthetic,
                    title=card.title)
    except Exception:
        return {**base, "enabled": False, "reason": "Pinned live task or config is unreadable."}
    if not enabled():
        return {**base, "enabled": False,
                "reason": f"Live runs are off. The operator starts the server with {ENV_FLAG}=1 to allow one."}
    missing = _missing_extras()
    if missing:
        return {**base, "enabled": False,
                "reason": f"Missing Python extras: {', '.join(missing)} (uv sync --extra aws --extra strands --extra api)."}
    ok, reason = budget_check()
    return {**base, "enabled": ok, "reason": reason}


def make_provider(config, cassette: Path):
    """Live Bedrock provider recording a new cassette (same construction as factories.bedrock_recording)."""
    from treehouse.providers.bedrock import BedrockConverseProvider
    from treehouse.providers.cassette import Cassette, RecordingProvider
    from treehouse.providers.prices import load_default
    from treehouse.providers.registry import ModelRegistry
    from treehouse.providers.spend import SpendLedger

    registry, prices = ModelRegistry.load(), load_default()
    ledger = SpendLedger(prices=prices, registry=registry)
    live = BedrockConverseProvider(None, registry, prices, ledger, region="us-east-1", thinking=config.thinking)
    return RecordingProvider(live, Cassette(cassette))


def run_job(root: Path, rid: str, store_lock) -> None:
    """Run, seal and evaluate one live investigation into the served store. Replaced in tests."""
    from treehouse import service
    from treehouse.cards import load_card
    from treehouse.investigation import run_investigation
    from treehouse.schemas.config import RunConfig
    from treehouse.store.local import LocalStore

    card = load_card(repo_root() / TASK)
    config = RunConfig.model_validate_json((repo_root() / CONFIG).read_bytes())
    out = Path(os.environ.get(ENV_CASSETTES) or repo_root() / "out" / "pitch-live")
    out.mkdir(parents=True, exist_ok=True)
    cassette = out / f"{rid}.model.jsonl"
    if cassette.exists():
        raise FileExistsError(cassette)
    store = LocalStore(root)
    # The live run writes only under runs/<rid>; readers of that id are answered from controller.jobs until
    # it is ready, so the store lock is held only for the evaluation write (a live run takes minutes).
    run_investigation(store, card, config, make_provider(config, cassette), run_id=rid)
    with store_lock:
        service.evaluate(store, rid)


def _execute(controller, rid: str) -> None:
    with controller.job_lock:
        controller.jobs[rid]["status"] = "running"
    try:
        run_job(controller.root, rid, controller.store_lock)
        with controller.job_lock:
            controller.jobs[rid]["status"] = "report_ready"
    except Exception as error:
        with controller.job_lock:
            controller.jobs[rid].update(status="failed",
                                        message=f"Live run failed ({type(error).__name__}); see server log.")
    finally:
        with controller.job_lock:
            controller.busy = False


def start(controller) -> str | None:
    """Queue one live run on the controller's single worker; None when a run is already in progress."""
    st = status()
    with controller.job_lock:
        if controller.busy:
            return None
        controller.busy = True
        rid = "pitch-live-" + uuid4().hex[:12]
        controller.jobs[rid] = {"run_id": rid, "title": st.get("title", "Live pitch run"), "task_id": TASK.stem,
                                "mode": "live", "synthetic": bool(st.get("synthetic", True)), "status": "queued"}
        controller.jobs[rid]["future"] = controller.executor.submit(_execute, controller, rid)
        return rid


def register(app, controller) -> None:
    from fastapi import HTTPException, Request

    @app.get("/api/pitch/live")
    def live_status():
        return status()

    @app.post("/api/pitch/live", status_code=202)
    async def live_start(request: Request):
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise HTTPException(400, "JSON content type required")
        body = await request.body()
        if len(body) > MAX_BODY:
            raise HTTPException(413, "Request body is too large")
        try:
            value = json.loads(body or b"{}")
        except ValueError:
            raise HTTPException(400, "Expected an empty JSON object") from None
        if value != {}:
            raise HTTPException(400, "The live demo takes no parameters; task and model are pinned")
        st = status()
        if not st["enabled"]:
            raise HTTPException(403, st["reason"])
        rid = start(controller)
        if rid is None:
            raise HTTPException(409, "A run is already in progress")
        return {"run_id": rid, "status": "queued"}
