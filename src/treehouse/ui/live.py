"""Live console: start a real Bedrock investigation from the dev view (opt-in, ``ui serve --live``).

The browser picks a place (a task card under ``tasks/``) and a verified Bedrock model from
``config/models.yaml``; the server owns everything else. It builds the run config from the pinned live
template, checks the spend guard, and runs the same command as the README's "Run it live" section in a
subprocess, writing the sealed run into the served store, where the dev view then shows it like any run.
One live run at a time. The agent chooses the foundation model (Clay, AEF ...) itself; the options list the
ones each task allows, and the run's own trace shows which it used.
"""

from __future__ import annotations

import asyncio
import atexit
import collections
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from fastapi import HTTPException, Request  # only imported with `ui serve --live` (the api extra)

from treehouse.cards import load_card
from treehouse.paths import repo_root
from treehouse.providers.registry import ModelRegistry, check_roles
from treehouse.schemas.config import RunConfig

TEMPLATE = "fixtures/live/configs/t1-nagoya-nova-strands.json"
RUN_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,80}$")
LOG_TAIL = 40
MAX_RUN_S = 20 * 60  # a live run older than this is stopped, so a hung run cannot hold the slot or keep spending


def _centre(coords) -> tuple[float, float]:
    flat: list[list[float]] = []

    def walk(c):
        if c and isinstance(c[0], (int, float)):
            flat.append(c)
        else:
            for x in c:
                walk(x)

    walk(coords)
    lons, lats = [p[0] for p in flat], [p[1] for p in flat]
    return (min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2


def places(root: Path) -> dict[str, dict]:
    """Task cards that a live run can use, keyed by task id."""
    out: dict[str, dict] = {}
    template_tools = set(json.loads((root / TEMPLATE).read_text())["worker"]["tools"])
    for path in sorted((root / "tasks").glob("*.yaml")):
        try:
            card = load_card(path)
        except Exception:  # noqa: BLE001  an unreadable card is simply not offered
            continue
        # Only places the pinned live tool servers can serve; synthetic test cards are not places.
        if card.id.startswith("synth-") or not set(card.tools_allowed) <= template_tools:
            continue
        lon, lat = _centre(card.aoi.coordinates)
        out[card.id] = {
            "task_id": card.id,
            "title": card.title,
            "goal": card.goal,
            "lon": round(lon, 4),
            "lat": round(lat, 4),
            "needs_vision": card.needs_vision,
            "synthetic": card.synthetic,
            "foundation_models": [d.source_id for d in card.data_allowlist if d.kind == "embeddings"],
            "path": str(path.relative_to(root)),
        }
    return out


# Words a prompt may use for each place; the place token comes from the task id ("t1-nagoya-..." -> nagoya).
ALIASES = {"chattogram": {"chattogram", "chittagong", "bangladesh"}, "bangladesh": {"bangladesh", "chattogram", "chittagong"},
           "nagoya": {"nagoya", "aichi", "japan"}, "gifu": {"gifu", "japan"}}
ASSETS = {"warehouses": {"warehouse", "warehouses", "logistics", "storage"},
          "fuel": {"fuel", "tank", "tanks", "oil"}, "real": {"real", "clay", "lgnd"}}


def resolve(prompt: str, catalogue: dict[str, dict]) -> dict:
    """Pick the place a free-text prompt asks about: the task card with the most matching place and asset words.

    The prompt chooses the place; the task card still defines the goal, area and answer key that are sealed."""
    words = set(re.findall(r"[a-z]+", prompt.lower()))
    scored = []
    for tid, p in catalogue.items():
        parts = re.sub(r"^t\d+-", "", tid).split("-")
        place_words = ALIASES.get(parts[0], {parts[0]})
        score, matched = 0, []
        if words & place_words:
            score += 3; matched.append(parts[0])
        for part in parts[1:]:
            if words & ASSETS.get(part, {part}):
                score += 1; matched.append(part)
        if "real" in parts and not words & ASSETS["real"]:
            score -= 1  # prefer the keyed card unless real data is asked for
        scored.append((score, tid, matched))
    scored.sort(key=lambda x: (-x[0], x[1]))
    best = scored[0] if scored else (0, None, [])
    if best[0] < 3:
        names = sorted({re.sub(r"^t\d+-", "", t).split("-")[0].title() for t in catalogue})
        raise ValueError("Name a place we have data for: " + ", ".join(names))
    return {"task_id": best[1], "title": catalogue[best[1]]["title"], "matched": best[2],
            "alternatives": [t for s_, t, _ in scored[1:4] if s_ >= 3]}


def models(registry: ModelRegistry) -> list[dict]:
    rows = []
    for key in registry.keys():
        e = registry.get(key)
        if e.tool_use:
            rows.append({"key": e.key, "family": e.family, "invoke_id": e.invoke_id,
                         "vision": e.vision, "verified": e.verified})
    return sorted(rows, key=lambda r: (not r["verified"], r["key"]))


class LiveRunner:
    def __init__(self, store_root: Path):
        self.root = repo_root()
        self.store = Path(store_root)
        self.registry = ModelRegistry.load()
        self.places = places(self.root)
        self.logs = self.store.parent / "live-logs"
        self.lock = threading.Lock()
        self.current: dict | None = None

    def options(self) -> dict:
        return {"places": list(self.places.values()), "models": models(self.registry),
                "running": self.current["run_id"] if self.current and self.current["proc"].poll() is None else None}

    def _config(self, card_path: Path, model_key: str) -> Path:
        card = load_card(card_path)
        entry = self.registry.get(model_key)
        value = json.loads((self.root / TEMPLATE).read_text())
        value["task_ref"] = card.ref()
        value["worker"]["model_key"] = entry.key
        value["worker"]["family"] = entry.family
        value["worker"]["tools"] = list(card.tools_allowed)
        config = RunConfig.model_validate(value)
        check_roles(config, self.registry, needs_vision=card.needs_vision)
        self.logs.mkdir(parents=True, exist_ok=True)
        path = self.logs / f"config-{card.id}-{entry.key}.json"
        path.write_text(json.dumps(value, sort_keys=True))
        return path

    def _budget_ok(self, env: dict) -> tuple[bool, str]:
        r = subprocess.run([sys.executable, "-m", "treehouse.cli", "budget", "status"], cwd=self.root,
                           env=env, capture_output=True, text=True, timeout=60)
        return r.returncode == 0, (r.stdout + r.stderr).strip()[-600:]

    def start_prompt(self, prompt: str, model_key: str) -> dict:
        prompt = prompt.strip()
        if not 3 <= len(prompt) <= 500:
            raise ValueError("Write a prompt of 3 to 500 characters")
        found = resolve(prompt, self.places)
        out = self.start(found["task_id"], model_key)
        (self.logs / f"{out['run_id']}.prompt.json").write_text(json.dumps({"prompt": prompt, "resolved": found}))
        self.current["prompt"], self.current["resolved"] = prompt, found
        return {**out, "resolved": found}

    def start(self, task_id: str, model_key: str) -> dict:
        place = self.places.get(task_id)
        if place is None:
            raise ValueError("unknown place")
        if model_key not in {m["key"] for m in models(self.registry)}:
            raise ValueError("unknown model")
        if place["needs_vision"] and not self.registry.get(model_key).vision:
            raise ValueError("this place needs a vision model")
        with self.lock:
            if self.current and self.current["proc"].poll() is None:
                raise RuntimeError(f"live run {self.current['run_id']} is still running")
            env = dict(os.environ)
            env.setdefault("TREEHOUSE_SPEND_LEDGER", str(self.root / ".spend" / "spend.jsonl"))
            try:
                ok, budget = self._budget_ok(env)
            except subprocess.TimeoutExpired:
                raise RuntimeError("spend guard check timed out; try again") from None
            if not ok:
                raise RuntimeError("spend guard refused the run: " + budget)
            config = self._config(self.root / place["path"], model_key)
            run_id = f"live-{task_id}-{model_key}-{time.strftime('%m%d-%H%M%S')}".lower()[:80]
            if not RUN_ID.match(run_id):
                raise ValueError("bad run id")
            if (self.store / "runs" / run_id).exists():
                raise RuntimeError("a run with this id already exists; try again in a second")
            env["TREEHOUSE_CASSETTE_OUT"] = str(self.logs / f"{run_id}.model.jsonl")
            with open(self.logs / f"{run_id}.log", "w") as log:  # the child keeps its own handle
                proc = subprocess.Popen(
                    [sys.executable, "-m", "treehouse.cli", "sandbox", "run", "--task", place["path"],
                     "--config", str(config), "--provider", "treehouse.providers.factories:bedrock_recording",
                     "--run-id", run_id, "--store", str(self.store)],
                    cwd=self.root, env=env, stdout=log, stderr=subprocess.STDOUT)
            self.current = {"run_id": run_id, "proc": proc, "started": time.time(),
                            "task_id": task_id, "model_key": model_key}
            return {"run_id": run_id, "status": "running"}

    def cancel(self, run_id: str) -> dict:
        """Stop the running live run (the console's Stop button). It ends unsealed and is not scored."""
        cur = self.current
        if not cur or cur["run_id"] != run_id:
            raise KeyError(run_id)
        if cur["proc"].poll() is None:
            cur["proc"].terminate()
            try:
                cur["proc"].wait(timeout=20)
            except subprocess.TimeoutExpired:
                cur["proc"].kill()
        cur["cancelled"] = True
        return {"run_id": run_id, "state": "cancelled"}

    def stop(self) -> None:
        """Server shutdown: do not leave a live run spending in the background."""
        if self.current and self.current["proc"].poll() is None:
            self.current["proc"].terminate()

    def status(self, run_id: str) -> dict:
        cur = self.current
        if not cur or cur["run_id"] != run_id:
            raise KeyError(run_id)
        code = cur["proc"].poll()
        if code is None and time.time() - cur["started"] > MAX_RUN_S:
            cur["proc"].terminate()
            code = cur["proc"].wait(timeout=30)
        lines = (self.logs / f"{run_id}.log").read_text(errors="replace").splitlines()[-LOG_TAIL:]
        state = "running" if code is None else "cancelled" if cur.get("cancelled") else ("done" if code == 0 else "failed")
        return {"run_id": run_id, "state": state,
                "exit_code": code, "elapsed_s": round(time.time() - cur["started"], 1),
                "task_id": cur["task_id"], "model_key": cur["model_key"], "log_tail": lines,
                "prompt": cur.get("prompt"), "resolved": cur.get("resolved"),
                **cassette_progress(self.logs / f"{run_id}.model.jsonl")}


def cassette_progress(path: Path, limit: int = 8, window: int = 200) -> dict:
    """Progress of a run in flight from its partial cassette: model-call count and the latest tool requests.

    Tolerates a missing file and a half-written last line; keeps only the last ``window`` lines in memory.
    Returns tool names and short decision rationales only, never prompts, images or credentials."""
    try:
        turns, tail = 0, collections.deque(maxlen=window)
        with open(path, "rb") as fh:
            for raw in fh:
                if raw.endswith(b"\n"):  # an unterminated last line is still being written
                    turns += 1
                    tail.append(raw)
    except OSError:
        return {"model_turns": 0, "recent": []}
    recent: list[dict] = []
    for raw in reversed(tail):
        if len(recent) >= limit:
            break
        try:
            blocks = json.loads(raw)["response"]["message"]["content"]
        except (ValueError, KeyError, TypeError):
            continue
        items = []
        for b in blocks if isinstance(blocks, list) else []:
            if isinstance(b, dict) and b.get("type") == "tool_use" and isinstance(b.get("name"), str):
                item = {"kind": "tool_use", "name": b["name"][:60]}
                if b["name"] == "record_decision" and isinstance(b.get("input"), dict):
                    why = b["input"].get("rationale")
                    if isinstance(why, str):
                        item["why"] = why[:140]
                items.append(item)
        recent = items + recent
    return {"model_turns": turns, "recent": recent[-limit:]}


def mount(app, store_root: Path) -> None:
    """Add the live-console routes to the UI app (only called with ``ui serve --live``)."""
    runner = LiveRunner(store_root)
    atexit.register(runner.stop)

    @app.get("/api/live/options")
    def live_options():
        return runner.options()

    @app.post("/api/live/runs", status_code=202)
    async def live_start(request: Request):
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise HTTPException(400, "JSON content type required")
        body = await request.body()
        if len(body) > 2048:
            raise HTTPException(413, "Request body is too large")
        try:
            value = json.loads(body)
        except ValueError:
            raise HTTPException(400, "Expected JSON") from None
        if not isinstance(value, dict) or not all(isinstance(v, str) for v in value.values()) or \
                set(value) not in ({"prompt", "model_key"}, {"task_id", "model_key"}):
            raise HTTPException(400, "Send prompt (or task_id) and model_key")
        try:
            if "prompt" in value:
                return await asyncio.to_thread(runner.start_prompt, value["prompt"], value["model_key"])
            return await asyncio.to_thread(runner.start, value["task_id"], value["model_key"])
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.post("/api/live/runs/{rid}/cancel")
    async def live_cancel(rid: str):
        try:
            return await asyncio.to_thread(runner.cancel, rid)
        except KeyError:
            raise HTTPException(404, "Unknown live run") from None

    @app.get("/api/live/resolve")
    def live_resolve(prompt: str = ""):
        try:
            return resolve(prompt[:500], runner.places)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.get("/api/live/runs/{rid}")
    def live_status(rid: str):
        try:
            return runner.status(rid)
        except KeyError:
            raise HTTPException(404, "Unknown live run") from None
