"""Public projections of verified local runs and pinned offline replay presets."""

import json
import os
import re
import stat
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from treehouse import service
from treehouse.cards import load_card
from treehouse.investigation.public import PRIVATE
from treehouse.investigation.public import public_value as redact_value
from treehouse.schemas.checks import CheckLedger
from treehouse.schemas.config import RunConfig
from treehouse.schemas.passport import TrustPassport
from treehouse.schemas.scorecard import Scorecard
from treehouse.schemas.tools import ClaySearchResult
from treehouse.store.local import LEDGER_GENESIS, LocalStore, check_run_id
from treehouse.store.verify import verify
from treehouse.ui.projection import metadata, parameters

MAX_BODY = 4096
MAX_FILES = 20_000
MAX_STORE_BYTES = 256 * 1024 * 1024
MAX_EVENTS = 200
SAFE_ATTRS = frozenset(
    {
        "gen_ai.agent.name",
        "gen_ai.operation.name",
        "gen_ai.provider.name",
        "gen_ai.request.model",
        "gen_ai.request.max_tokens",
        "gen_ai.request.temperature",
        "cloud.region",
        "aws.region",
        "treehouse.classifier.model_id",
        "treehouse.classifier.pricing",
        "treehouse.classifier.cost_usd",
        "treehouse.classifier.tokens",
        "gen_ai.response.model",
        "gen_ai.tool.call.id",
        "gen_ai.tool.name",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "gen_ai.usage.cache_creation.input_tokens",
        "gen_ai.usage.cache_read.input_tokens",
        "treehouse.claim.id",
        "treehouse.config.hash",
        "treehouse.cost.ledger_usd",
        "treehouse.cost.replayed",
        "treehouse.cost.usd",
        "treehouse.evidence.refs",
        "treehouse.harness",
        "treehouse.image.sha256",
        "treehouse.key_access_attempt",
        "treehouse.license.spdx",
        "treehouse.price_table.version",
        "treehouse.recorded_latency_ms",
        "treehouse.role",
        "treehouse.run.id",
        "treehouse.scene.id",
        "treehouse.stop",
        "treehouse.stop_reason",
        "treehouse.task.hash",
        "treehouse.task.id",
        "treehouse.tool.args_hash",
        "treehouse.tool.blocked",
        "treehouse.tool.bytes_read",
        "treehouse.tool.result_id",
        "treehouse.tool.result_ref",
        "treehouse.trial.id",
        "treehouse.trial.index",
        "treehouse.turn",
        "treehouse.turns",
    }
)
PRIVATE_KEYS = frozenset(
    {
        "path",
        "key_path",
        "keys",
        "key_labels",
        "labels",
        "raw_prompt",
        "prompt",
        "system_prompt",
        "source_prompt",
        "messages",
        "pixels",
        "image_base64",
        "blob",
        "authorization",
        "api_key",
        "access_token",
        "secret_access_key",
        "cassette",
        "script",
    }
)


class PublicDataError(Exception):
    """No filesystem or raw record values are included in public error messages."""


def safe_text(value: str) -> str:
    value = redact_value(value)
    if len(value) > 8000 or any(ord(char) < 32 and char not in "\n\t" for char in value):
        return "[redacted unsafe text]"
    if re.search(
        r"(?i)(?:keys[/\\]|data:image/|AKIA[A-Z0-9]{16}|(?:api[_-]?key|secret[_-]?access[_-]?key|authorization|password)\s*[:=])",
        value,
    ):
        return "[redacted unsafe text]"
    return re.sub(
        r'(?<!\w)(?:/(?:Users|home|private|tmp|var|etc|opt|mnt)/[^\s<>"\']+|[A-Za-z]:\\[^\s<>"\']+)',
        "[redacted path]",
        value,
    )


def public_value(value):
    if isinstance(value, str):
        return safe_text(value)
    if isinstance(value, list):
        return [public_value(item) for item in value]
    if isinstance(value, dict):
        value = dict(value)
        if isinstance(value.get("tool"), str) and "parameters" in value:
            value["parameters"] = parameters(value["tool"], value["parameters"])
        if "provenance" in value and isinstance(value["provenance"], dict) and "embeddings" not in value["provenance"]:
            value["provenance"] = metadata({"provenance": value["provenance"]})["provenance"]
        return {
            safe_text(str(key)): public_value(item)
            for key, item in value.items()
            if str(key).lower() not in PRIVATE_KEYS
            and re.sub(r"[^a-z0-9]", "", str(key).lower()) not in PRIVATE
        }
    return value


def public_bundle(bundle):
    data = bundle.model_dump(mode="json")
    for row in data["trace_rows"]:
        row["attributes"] = {key: value for key, value in row["attributes"].items() if key in SAFE_ATTRS}
        for event in row["events"]:
            event["attributes"] = {
                key: value for key, value in event["attributes"].items() if key in SAFE_ATTRS
            }
        if row["error"]:
            row["error"]["message"] = "Tool call failed (details sealed in the trace)"
    return public_value(data)


class Reader(LocalStore):
    """LocalStore read methods without its mkdir-on-construction side effect."""

    def __init__(self, root):
        self.root = root
        self.ledger_path = root / "ledger.jsonl"
        self.index_path = root / "evals/index.jsonl"


def inspect_tree(root: Path):
    if root.is_symlink():
        raise PublicDataError()
    if not root.exists():
        return
    if not root.is_dir():
        raise PublicDataError()
    count = total = 0
    for base, directories, files in os.walk(root, followlinks=False):
        for name in [*directories, *files]:
            path = Path(base) / name
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise PublicDataError()
            if not path.resolve().is_relative_to(root):
                raise PublicDataError()
            count += 1
            total += path.stat().st_size if stat.S_ISREG(mode) else 0
            if count > MAX_FILES or total > MAX_STORE_BYTES:
                raise PublicDataError()


def valid_id(value):
    if len(value) > 128:
        raise ValueError("Invalid run identifier")
    check_run_id(value)
    return value


def presets():
    result = {}
    for entry in service.load_runs():
        rid = valid_id(entry["run_id"])
        config = RunConfig.model_validate_json((service.demo_root() / "configs" / f"{rid}.json").read_bytes())
        card = load_card(service.card_path(entry["task"]))
        if (
            config.task_ref != card.ref()
            or config.mode != "replay"
            or config.worker.provider != "replay"
            or config.backends.store != "local"
            or config.backends.tracer != ["jsonl"]
            or config.harness != "plain_loop"
            or config.trials != 1
            or config.max_turns > 40
        ):
            raise PublicDataError()
        safe_config = config.model_dump(mode="json")
        for role in ("worker", "verifier", "summarizer"):
            if safe_config[role]:
                for key in ("script", "cassette"):
                    safe_config[role].pop(key, None)
        result[rid] = (
            config,
            public_value(
                {
                    "preset_id": rid,
                    "title": f"{card.title} · {rid}",
                    "goal": card.goal,
                    "task_id": card.id,
                    "task_ref": card.ref(),
                    "mode": "replay",
                    "synthetic": card.synthetic,
                    "tools": card.tools_allowed,
                    "model_id": config.worker.model_key,
                    "harness": config.harness,
                    "tracers": config.backends.tracer,
                    "budget": config.budget.model_dump(mode="json"),
                    "config": safe_config,
                }
            ),
        )
    return result


class Controller:
    def __init__(self, root):
        self.root = root
        self.store = Reader(root)
        self.presets = presets()
        self.jobs = {}
        self.busy = False
        self.job_lock = threading.Lock()
        self.store_lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="treehouse-replay")

    def pending(self, rid):
        with self.job_lock:
            return self.jobs.get(rid, {}).get("status") in ("queued", "running")

    def sealed(self, rid):
        inspect_tree(self.root)
        return service.load_sealed(self.store, rid)

    def bundle(self, rid, reference=None):
        run = self.sealed(rid)
        records = {kind: self.store.list_records(rid, kind) for kind in ("rules", "score", "trust")}
        if not all(records.values()):
            raise PublicDataError()
        rules = records["rules"][-1].record
        ledgers = [CheckLedger.model_validate(item) for item in rules["ledgers"]]
        score = Scorecard.model_validate(records["score"][-1].record)
        trust = TrustPassport.model_validate(records["trust"][-1].record)
        if score.run_ref != run.manifest.manifest_hash or trust.manifest_ref != run.manifest.manifest_hash:
            raise PublicDataError()
        return {**public_bundle(service.build_bundle(run, ledgers, score, trust)),
                "snapshot": self.snapshot(rid, reference=reference)}

    def snapshot(self, rid, reference=None):
        from treehouse.ui.snapshot import pending_snapshot, snapshot

        if self.pending(rid) or (rid in self.jobs and self.jobs[rid]["status"] == "failed"):
            return public_value(pending_snapshot(self.summary(rid)))
        result = snapshot(self.store, self.sealed(rid), reference=reference)
        for step in result["steps"]:
            step["attributes"] = {key: value for key, value in step["attributes"].items() if key in SAFE_ATTRS}
        return public_value(result)

    def summary(self, rid):
        if rid in self.jobs:
            return {key: value for key, value in self.jobs[rid].items() if key != "future"}
        run = self.sealed(rid)
        ready = all(self.store.list_records(rid, kind) for kind in ("rules", "score", "trust"))
        return public_value(
            {
                "run_id": rid,
                "title": run.card.title,
                "task_id": run.card.id,
                "mode": run.manifest.mode,
                "synthetic": run.synthetic,
                "status": "report_ready" if ready else "sealed",
            }
        )

    def start(self, preset_id):
        with self.job_lock:
            if self.busy:
                return None
            self.busy = True
            rid = "replay-" + uuid4().hex
            config, task = self.presets[preset_id]
            self.jobs[rid] = {key: task[key] for key in ("title", "task_id", "mode", "synthetic")}
            self.jobs[rid].update(run_id=rid, status="queued")
            self.jobs[rid]["future"] = self.executor.submit(self.execute, rid, config)
            return rid

    def execute(self, rid, config):
        with self.job_lock:
            self.jobs[rid]["status"] = "running"
        try:
            with self.store_lock:
                inspect_tree(self.root)
                store = LocalStore(self.root)
                service.run(store, config, run_id=rid, mode="replay")
                service.evaluate(store, rid)
            with self.job_lock:
                self.jobs[rid]["status"] = "report_ready"
        except Exception:
            with self.job_lock:
                self.jobs[rid].update(
                    status="failed", message="Pinned replay failed; inspect local CLI diagnostics."
                )
        finally:
            with self.job_lock:
                self.busy = False


def create_app(
    store_root: Path, *, origin="http://127.0.0.1:8765", frontend_dist: Path | None = None, judge_app=None, server_reference: Path | None = None,
    live: bool = False,
):
    """Serve verified public data. POST /api/runs starts a pinned offline replay; POST /api/pitch/live starts a
    pinned live run only when the operator set TREEHOUSE_PITCH_LIVE=1 (see pitch_live)."""
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import FileResponse, JSONResponse

    parsed = urlsplit(origin)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
    ):
        raise ValueError("Origin must be an exact HTTP(S) origin without a trailing slash")
    root = Path(store_root).absolute()
    if root.is_symlink():
        raise ValueError("Store root must not be a symlink")
    root = root.resolve()
    if server_reference is not None:
        from treehouse.investigation.evaluation import Reference

        # Server-owned current comparison input is fixed at startup, never selected by a browser.
        server_reference = Reference.model_validate_json(Path(server_reference).read_bytes()).model_dump(mode="json")
    controller = Controller(root)
    allowed_hosts = {parsed.netloc.lower(), "127.0.0.1:8765", "localhost:8765"}
    allowed_origins = {origin, "http://127.0.0.1:8765", "http://localhost:8765"}
    dist = Path(frontend_dist).absolute() if frontend_dist is not None else None

    @asynccontextmanager
    async def lifespan(app):
        yield
        controller.executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.controller = controller

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.headers.get("host", "").lower() not in allowed_hosts:
            return JSONResponse({"detail": "Host is not allowed"}, status_code=400)
        if request.method == "POST" and (
            request.headers.get("origin") != origin
            or request.headers.get("sec-fetch-site", "").lower() == "cross-site"
        ):
            return JSONResponse({"detail": "Same-origin request required"}, status_code=403)
        if request.headers.get("origin") and request.headers["origin"] not in allowed_origins:
            return JSONResponse({"detail": "Origin is not allowed"}, status_code=400)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        # img-src also allows GSI's public aerial tiles (Japan) for the storybook and dev-view maps.
        # frame-ancestors 'self': the /pitch page embeds the story and dev views (demo mode B); no other origin may.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' https://cyberjapandata.gsi.go.jp; "
            "connect-src 'self'; object-src 'none'; frame-ancestors 'self'; base-uri 'self'"
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse({"detail": "Invalid request parameters"}, status_code=400)

    @app.exception_handler(Exception)
    async def unavailable(request, exc):
        return JSONResponse({"detail": "Product data is unavailable"}, status_code=409)

    def run_id(value):
        try:
            return valid_id(value)
        except ValueError:
            raise HTTPException(400, "Invalid run identifier") from None

    def exists(rid):
        run_id(rid)
        if rid not in controller.jobs and not (root / "runs" / rid).exists():
            raise HTTPException(404, "Run not found")

    def read(rid, action):
        exists(rid)
        if controller.pending(rid):
            raise HTTPException(409, "Run is not sealed and evaluated yet")
        try:
            with controller.store_lock:
                return action()
        except Exception as error:
            if isinstance(error, HTTPException):
                raise
            raise HTTPException(409, "Recorded run is not ready or failed integrity verification") from None

    @app.get("/api/capabilities")
    def capabilities():
        value = _capabilities()
        if live:  # ui serve --live: the dev-view agent console runs real Strands agents on Amazon Bedrock
            value["execution"] = "live"
            on = {
                "bedrock": ("available", "Live runs call Amazon Bedrock (Converse) with the models in config/models.yaml; spend guard enforced."),
                "strands": ("available", "Live console runs use the Strands harness."),
                "live_runs": ("available", "Agent console in the dev view: prompt + Bedrock model, one run at a time."),
                "polly": ("available", "Run summaries are spoken with Amazon Polly (neural) when no pre-rendered narration exists."),
            }
            caps = [c for c in value["capabilities"] if c["id"] != "polly"]
            for c in caps:
                if c["id"] in on:
                    c["status"], c["reason"] = on[c["id"]]
            caps.append({"id": "polly", "label": "Amazon Polly", "status": on["polly"][0], "reason": on["polly"][1]})
            value["capabilities"] = caps
        return value

    def _capabilities():
        return {
            "schema_version": "treehouse.ui/1",
            "execution": "offline",
            "capabilities": [
                {
                    "id": "bedrock",
                    "label": "Bedrock",
                    "status": "not_configured",
                    "reason": "Live Bedrock execution is not configured or verified for product runs; historical probes are not live geospatial execution.",
                },
                {
                    "id": "strands",
                    "label": "Strands",
                    "status": "not_configured",
                    "reason": "Pinned product replay uses plain_loop; Strands execution is not configured for this product path.",
                },
                {
                    "id": "agentcore",
                    "label": "AgentCore",
                    "status": "not_configured",
                    "reason": "The optional judge workbench is separate; mounting it or loading server configuration does not verify an AWS endpoint.",
                },
                {
                    "id": "simulation",
                    "label": "Simulation",
                    "status": "unsupported",
                    "reason": "No simulation engine, terrain, validated geometry or boundary conditions are configured; recorded presets are not simulations.",
                },
                {
                    "id": "pinned_replay",
                    "label": "Recorded demo presets",
                    "status": "offline_demo",
                    "reason": "Pinned local replay only; goals, models and budgets are read-only.",
                },
                {
                    "id": "live_runs",
                    "label": "Live model runs",
                    "status": "not_configured",
                    "reason": "Product live runs not configured; optional workbench is separate and requires Kiro verification.",
                },
                {
                    "id": "scene_builder",
                    "label": "Scene Builder",
                    "status": "unsupported",
                    "reason": "Scene editing is not implemented.",
                },
                {
                    "id": "trust",
                    "label": "Trust passport",
                    "status": "not_configured",
                    "reason": "Trust engine is a stub; Not issued.",
                },
            ],
            "limits": {"max_parallel_runs": 1},
            "judge_url": "/judge/" if judge_app is not None else None,
        }

    @app.get("/api/tasks")
    def tasks():
        return {"tasks": [value[1] for value in controller.presets.values()]}

    @app.get("/api/runs")
    def runs():
        try:
            with controller.store_lock:
                inspect_tree(root)
                directory = root / "runs"
                ids = (
                    {
                        path.name
                        for path in directory.iterdir()
                        if path.is_dir() and not path.name.startswith(".")
                    }
                    if directory.is_dir()
                    else set()
                )
                ids.update(controller.jobs)
                summaries = []
                for rid in sorted(ids):
                    valid_id(rid)
                    try:
                        summaries.append(controller.summary(rid))
                    except Exception:
                        summaries.append(
                            {
                                "run_id": rid,
                                "title": "Unavailable recorded run",
                                "task_id": "",
                                "mode": "replay",
                                "synthetic": False,
                                "status": "failed",
                                "message": "Recorded run failed integrity verification.",
                            }
                        )
                return {"runs": summaries}
        except Exception:
            raise HTTPException(409, "Store failed integrity or safety checks") from None

    @app.post("/api/runs", status_code=202)
    async def start(request: Request):
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise HTTPException(400, "JSON content type required")
        body = b""
        async for chunk in request.stream():
            body += chunk
            if len(body) > MAX_BODY:
                raise HTTPException(413, "Request body is too large")
        try:
            value = json.loads(body)
        except ValueError:
            raise HTTPException(400, "Expected a JSON preset request") from None
        if (
            not isinstance(value, dict)
            or set(value) != {"preset_id"}
            or not isinstance(value["preset_id"], str)
        ):
            raise HTTPException(400, "Only a pinned preset_id is accepted")
        if value["preset_id"] not in controller.presets:
            raise HTTPException(422, "Unknown replay preset")
        rid = controller.start(value["preset_id"])
        if rid is None:
            raise HTTPException(409, "One replay is already in progress")
        return {"run_id": rid, "status": "queued"}

    @app.get("/api/runs/{rid}")
    def run_summary(rid: str):
        exists(rid)
        if rid in controller.jobs:
            return controller.summary(rid)
        return read(rid, lambda: controller.summary(rid))

    @app.get("/api/runs/{rid}/snapshot")
    def run_snapshot(rid: str):
        exists(rid)
        if controller.pending(rid):
            with controller.store_lock:
                return controller.snapshot(rid, reference=server_reference)
        return read(rid, lambda: controller.snapshot(rid, reference=server_reference))

    @app.get("/api/runs/{rid}/bundle")
    def bundle(rid: str):
        return read(rid, lambda: controller.bundle(rid, reference=server_reference))

    @app.get("/api/runs/{rid}/investigation")
    def investigation(rid: str):
        def collect():
            from treehouse.ui.snapshot import investigation_report

            result = investigation_report(controller.store, controller.sealed(rid), reference=server_reference)
            return public_value(result)

        return read(rid, collect)

    @app.get("/api/runs/{rid}/database")
    def database(rid: str):
        def collect():
            from treehouse.investigation import database_geojson

            inspect_tree(root)
            return database_geojson(controller.store, rid)

        return read(rid, collect)

    @app.get("/api/runs/{rid}/export")
    def export(rid: str):
        def collect():
            if all(controller.store.list_records(rid, kind) for kind in ("rules", "score", "trust")):
                return controller.bundle(rid, reference=server_reference)
            return {"snapshot": controller.snapshot(rid, reference=server_reference)}

        result = read(rid, collect)
        return JSONResponse(result, headers={"Content-Disposition": f'attachment; filename="{rid}.json"'})

    @app.get("/api/runs/{rid}/clay-searches")
    def searches(rid: str):
        def collect():
            run = controller.sealed(rid)
            searches = []
            for trial in run.trials:
                for call in trial.calls:
                    if call.name == "clay_search" and call.status == "success":
                        payload = {key: value for key, value in call.payload.items() if key != "result_id"}
                        result = ClaySearchResult.model_validate(payload).model_dump(mode="json")
                        searches.append(
                            {
                                "search_id": f"{trial.trial_id}:{call.span_id}",
                                "trial_id": trial.trial_id,
                                "span_id": call.span_id,
                                "result_id": call.result_id,
                                "trace_ref": f"span:{call.span_id}",
                                "result": public_value(result),
                            }
                        )
            return (
                {"searches": searches}
                if searches
                else {"searches": [], "unavailable_reason": "No successful Clay search is recorded."}
            )

        return read(rid, collect)

    @app.get("/api/runs/{rid}/events")
    def events(rid: str, after: int = 0, limit: int = 100):
        if after < 0 or limit < 1 or limit > MAX_EVENTS:
            raise HTTPException(400, "Invalid event cursor or limit")
        exists(rid)
        if controller.pending(rid):
            return {"events": [], "next_cursor": 0, "source": "recorded_trace", "complete": False}

        def collect():
            run = controller.sealed(rid)
            spans = sorted(
                ((span, trial.trial_id) for trial in run.trials for span in trial.spans),
                key=lambda pair: (pair[0].end_ns, pair[1], pair[0].span_id),
            )
            data = []
            for index, (span, trial) in enumerate(spans[after : after + limit], start=after + 1):
                event = {
                    "event_id": f"{rid}:{trial}:{span.span_id}",
                    "run_id": rid,
                    "sequence": index,
                    "trial_id": trial,
                    "span_id": span.span_id,
                    "time_ns": span.end_ns,
                    "type": span.op,
                    "name": safe_text(span.name),
                    "status": span.status,
                }
                if "gen_ai.tool.name" in span.attributes:
                    event["tool_name"] = safe_text(str(span.attributes["gen_ai.tool.name"]))
                data.append(event)
            return {
                "events": data,
                "next_cursor": min(after + len(data), len(spans)),
                "source": "recorded_trace",
                "complete": after + len(data) >= len(spans),
            }

        return read(rid, collect)

    @app.get("/api/runs/{rid}/associations")
    def associations(rid: str):
        return read(
            rid,
            lambda: (
                controller.sealed(rid),
                {"associations": [], "reason": "No verified cell-to-claim association is recorded."},
            )[1],
        )

    @app.get("/api/runs/{rid}/verify")
    def verify_run(rid: str):
        exists(rid)
        if controller.pending(rid):
            raise HTTPException(409, "Run is not sealed yet")
        try:
            with controller.store_lock:
                inspect_tree(root)
                report = verify(controller.store, rid)
                manifest_ref = controller.sealed(rid).manifest.manifest_hash if report.ok else None
                return {
                    "ok": report.ok,
                    "scope": "sealed_run_and_evaluation_ledger",
                    "manifest_ref": manifest_ref,
                    "ledger_head": report.ledger_head,
                    "problems": ["Recorded integrity verification failed."] if report.problems else [],
                    "bundle_source": "reconstructed_from_verified_records",
                }
        except Exception:
            return {
                "ok": False,
                "scope": "sealed_run_and_evaluation_ledger",
                "manifest_ref": None,
                "ledger_head": LEDGER_GENESIS,
                "problems": ["Store failed integrity or safety checks."],
                "bundle_source": "reconstructed_from_verified_records",
            }

    # Pitch page demo mode C (live Bedrock run); off unless TREEHOUSE_PITCH_LIVE=1. Delete to strip it.
    from treehouse.ui import pitch_live

    pitch_live.register(app, controller)

    if judge_app is not None:
        app.mount("/judge", judge_app)

    if live:  # opt-in live console (ui serve --live): real Bedrock runs started from the dev view
        from treehouse.ui.live import mount

        mount(app, store_root)

        from treehouse.ui.voice import mount_voice

        mount_voice(app, store_root, lambda rid: controller.snapshot(rid, reference=server_reference))

    @app.get("/{path:path}")
    def frontend(path: str):
        if path == "api" or path.startswith("api/") or path == "judge" or path.startswith("judge/"):
            raise HTTPException(404, "Not found")
        if dist is None or not dist.is_dir():
            raise HTTPException(503, "Product UI build is missing")
        try:
            inspect_tree(dist.resolve())
            if dist.is_symlink():
                raise PublicDataError()
            target = (dist / path).resolve()
            if not target.is_relative_to(dist.resolve()):
                raise PublicDataError()
            public_asset = (
                path.startswith("assets/") and target.suffix in {".js", ".css", ".svg", ".woff", ".woff2"}
            ) or ("/" not in path and target.suffix in {".svg", ".ico"}) or (
                path.startswith("narration/") and path.count("/") == 1 and target.suffix in {".json", ".mp3"}
            )
            if path != "index.html" and not public_asset:
                target = dist / "index.html"
            elif not target.is_file():
                if public_asset:  # missing narration sidecar or asset: let the client fall back
                    raise HTTPException(404, "Not found")
                target = dist / "index.html"
            if not target.is_file() or target.is_symlink():
                raise PublicDataError()
            return FileResponse(target)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Product UI build is unavailable") from None

    return app
