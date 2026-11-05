"""Live Amazon Polly narration for runs started from the dev view (``ui serve --live``).

GET /api/voice/runs/{rid}        -> {"text", "sha256", "audio_url"}  (synthesizes once, caches the MP3)
GET /api/voice/runs/{rid}/audio  -> the cached MP3 (audio/mpeg)

The spoken text is the public snapshot's ``thinking_summary.text`` (same snapshot builder the UI uses), so no
sealed or private data is exposed. Errors are short 503s; credentials are never echoed.
"""
from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse

from treehouse.store.local import check_run_id

POLLY_LIMIT = 3000
VOICE = "Joanna"  # same voice as scripts/narrate_polly.py
ENGINE = "neural"
_lock = threading.Lock()


def _synthesize(text: str) -> bytes:
    import boto3

    polly = boto3.client("polly", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    resp = polly.synthesize_speech(Text=text, OutputFormat="mp3", VoiceId=VOICE, Engine=ENGINE)
    return resp["AudioStream"].read()


def mount_voice(app, store_root, snapshot_fn):
    cache = Path(store_root).resolve().parent / "voice-cache"

    def rid_of(rid: str) -> str:
        try:
            if len(rid) > 128:
                raise ValueError
            check_run_id(rid)
        except Exception:
            raise HTTPException(404, "Not found") from None
        return rid

    def spoken_text(rid: str) -> str:
        try:
            snap = snapshot_fn(rid)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Run snapshot unavailable") from None
        summary = snap.get("thinking_summary") or {}
        text = summary.get("text") if summary.get("status") == "available" else None
        if not text:
            raise HTTPException(503, "No narration text for this run yet")
        text = text.strip()
        if len(text) > POLLY_LIMIT:
            cut = text[:POLLY_LIMIT]
            end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
            text = cut[: end + 1] if end > POLLY_LIMIT // 2 else cut
        return text

    def cached(rid: str, sha: str) -> Path:
        return cache / f"{rid}-{sha[:12]}.mp3"

    @app.get("/api/voice/runs/{rid}")
    def voice_run(rid: str, request: Request):
        rid = rid_of(rid)
        text = spoken_text(rid)
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        path = cached(rid, sha)
        with _lock:
            if not path.is_file() or path.stat().st_size == 0:
                try:
                    audio = _synthesize(text)
                except Exception as exc:  # noqa: BLE001 - never leak credentials/ARNs
                    raise HTTPException(503, f"Polly unavailable ({type(exc).__name__})") from None
                if not audio:
                    raise HTTPException(503, "Polly returned no audio")
                cache.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(".tmp")
                tmp.write_bytes(audio)
                tmp.replace(path)
        return {"text": text, "sha256": sha, "audio_url": f"/api/voice/runs/{rid}/audio"}

    @app.get("/api/voice/runs/{rid}/audio")
    def voice_audio(rid: str, request: Request):
        rid = rid_of(rid)
        sha = hashlib.sha256(spoken_text(rid).encode("utf-8")).hexdigest()
        path = cached(rid, sha)
        if not path.is_file():
            raise HTTPException(404, "Audio not generated")
        return FileResponse(path, media_type="audio/mpeg")
