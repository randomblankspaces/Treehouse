"""Same-origin judge workbench. This module alone needs the optional API extra."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from treehouse.judge.service import JudgeError, JudgeService

ASSETS = Path(__file__).parent / "assets"


def create_app(service: JudgeService | None = None, *, origin: str = "http://127.0.0.1:8765") -> FastAPI:
    parts = urlsplit(origin)
    if parts.scheme not in {"http", "https"} or not parts.netloc or parts.path or parts.query or parts.fragment:
        raise ValueError("origin must be an exact HTTP(S) origin without a path")
    service = service or JudgeService()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def guards(request: Request, call_next):
        if request.headers.get("host") != parts.netloc:
            return JSONResponse({"detail": "Host is not allowed."}, status_code=403)
        supplied = request.headers.get("origin")
        if supplied is not None and supplied != origin:
            return JSONResponse({"detail": "Origin is not allowed."}, status_code=403)
        if request.method == "POST" and (supplied != origin or request.headers.get("sec-fetch-site") == "cross-site"):
            return JSONResponse({"detail": "A same-origin request is required."}, status_code=403)
        response = await call_next(request)
        response.headers.update({"Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
                                 "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
                                 "Cache-Control": "no-store"})
        return response

    @app.get("/")
    async def index():
        return FileResponse(ASSETS / "index.html")

    @app.get("/assets/{name}")
    async def asset(name: str):
        if name not in {"app.js", "style.css"}:
            return Response(status_code=404)
        return FileResponse(ASSETS / name)

    @app.get("/favicon.ico")
    async def favicon():
        return Response(status_code=204)

    @app.get("/api/status")
    async def status():
        return service.snapshot()

    @app.post("/api/invoke")
    async def invoke(request: Request):
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            return JSONResponse({"detail": "Use application/json."}, status_code=415)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 10000:
                return JSONResponse({"detail": "Question is too large."}, status_code=413)
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict) or set(payload) != {"prompt"}:
                raise ValueError
            prompt = payload["prompt"]
            if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 2000:
                raise ValueError
        except (ValueError, UnicodeDecodeError):
            return JSONResponse({"detail": "Enter a question between 1 and 2,000 characters."}, status_code=422)
        try:
            return await service.invoke(prompt.strip())
        except JudgeError as exc:
            return JSONResponse({"detail": exc.message}, status_code=exc.status)

    @app.get("/api/receipt")
    async def receipt():
        if not service.receipt:
            return JSONResponse({"detail": "No receipt is available yet."}, status_code=404)
        return JSONResponse(service.receipt.model_dump(mode="json"), headers={
            "Content-Disposition": 'attachment; filename="treehouse-judge-receipt.json"'})

    return app
