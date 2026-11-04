"""One explicit bounded invocation at a time; reads never contact AWS."""
from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from treehouse.judge.models import JudgeConfig, Receipt

MAX_RECEIPT_BYTES = 1_000_000


def redact(value: Any) -> Any:
    """Defense in depth for public-document traces, not a general secret detector."""
    if isinstance(value, dict):
        safe = {}
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", key.lower())
            sensitive = normalized == "key" or re.search(
                r"authorization|cookie|password|passwd|secret|token|credential|accesskey|apikey|privatekey", normalized
            )
            safe[redact(key)] = "[REDACTED]" if sensitive else redact(item)
        return safe
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b", "[REDACTED AWS ACCESS KEY]", value)
        value = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+", "[REDACTED BEARER]", value)
        value = re.sub(r"(?i)AWS4-HMAC-SHA256[^\r\n]*", "[REDACTED AWS AUTHORIZATION]", value)
        value = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", "[REDACTED PRIVATE KEY]", value, flags=re.S)
        value = re.sub(r"(?i)\b(aws_secret_access_key|aws_session_token|access_token|api_key|password|authorization)\b[\"']?\s*[:=]\s*[\"']?[^\s,;\"']+", r"\1=[REDACTED]", value)
    return value


class JudgeError(Exception):
    def __init__(self, status: int, message: str):
        self.status, self.message = status, message
        super().__init__(message)


def read_json(path: Path) -> dict:
    if path.stat().st_size > MAX_RECEIPT_BYTES:
        raise ValueError("JSON file exceeds 1 MB")
    return json.loads(path.read_text(encoding="utf-8"))


def live_backend(config: dict, prompt: str) -> dict:
    from treehouse.judge.aws import invoke_runtime

    return invoke_runtime(config, prompt)


class JudgeService:
    def __init__(self, config: JudgeConfig | None = None, *, recorded: dict | None = None,
                 backend: Callable[[dict, str], dict] | None = None, timeout: float = 130,
                 cooldown: float = 5):
        self.config = config
        self.backend = backend or live_backend
        self.timeout, self.cooldown = timeout, cooldown
        self.receipt: Receipt | None = None
        self.elapsed: float | None = None
        self._inflight = False
        self._last_started = float("-inf")
        if recorded is not None:
            # Provenance from disk is always recorded, even if its JSON claims "live".
            self.receipt = self.validate({**recorded, "source": "sample" if recorded.get("source") == "sample" else "recorded"})

    def validate(self, raw: dict) -> Receipt:
        if len(json.dumps(raw, default=str).encode()) > MAX_RECEIPT_BYTES:
            raise ValueError("receipt exceeds 1 MB")
        receipt = Receipt.model_validate(raw)
        if self.config:
            receipt.match(self.config)
        return Receipt.model_validate(redact(receipt.model_dump(mode="json")))

    def snapshot(self) -> dict[str, Any]:
        receipt = self.receipt
        return {"configured": self.config is not None, "busy": self._inflight,
                "receipt": receipt.model_dump(mode="json") if receipt else None,
                "proofs": receipt.proofs() if receipt else [], "elapsed_seconds": self.elapsed,
                "stale": bool(receipt and (datetime.now(UTC) - receipt.captured_at).total_seconds() > 86400),
                "resources": self.config.model_dump(exclude={"evidence_dir"}) if self.config else None}

    async def invoke(self, prompt: str) -> dict:
        if not self.config:
            raise JudgeError(409, "Live mode needs a server configuration. Ask the operator to load the AWS outputs file.")
        if self._inflight:
            raise JudgeError(409, "An invocation is still running. Wait for it to finish before trying again.")
        if time.monotonic() - self._last_started < self.cooldown:
            raise JudgeError(429, "Please wait five seconds between invocations.")
        self._inflight = True
        self._last_started = start = time.monotonic()
        async def perform():
            raw = await asyncio.to_thread(self.backend, self.config.model_dump(), prompt)
            receipt = self.validate(raw)
            if receipt.source != "live":
                raise ValueError("live backend returned a non-live receipt")
            # Keep a paid answer even if the HTTP caller or application wait has timed out.
            self.receipt = receipt
            self.elapsed = round(time.monotonic() - start, 2)

        task = asyncio.create_task(perform())
        # A timed-out SDK thread may still be billing. Keep the slot occupied until it exits.
        def finished(done):
            self._inflight = False
            if not done.cancelled():
                done.exception()  # Consume late SDK failures without leaking their contents to logs.
        task.add_done_callback(finished)
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=self.timeout)
            return self.snapshot()
        except TimeoutError as exc:
            raise JudgeError(504, "Runtime timed out. It may still be running; do not immediately retry.") from exc
        except Exception as exc:
            # SDK errors can contain account details, URLs, prompts or credentials.
            raise JudgeError(502, "Runtime request failed or returned invalid evidence. Ask the operator to check AWS permissions and server logs.") from exc
