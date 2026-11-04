"""BedrockConverseProvider: the live adapter (IMPLEMENTATION-DESIGN §3, fact-check F1–F4, F10).

* Call shape: ``converse(modelId=<inference profile>, system, messages, toolConfig, inferenceConfig)``.
* Image delivery (registry ``image_delivery``) is applied *after* the request key is computed: the
  harness keys ``ModelRequest``; only the wire payload differs. ``tool_result`` keeps an image inside its
  toolResult; ``user_turn`` moves it out into the same user message, after the toolResult blocks, and
  leaves a text pointer in the toolResult.
* Retries (F1/F2): botocore makes exactly one HTTP attempt (``total_max_attempts=1``, standard mode);
  our jittered loop retries Throttling, ServiceUnavailable, ModelNotReady, ModelTimeout and
  InternalServer, recording one ``treehouse.retry`` event per failed attempt in ``ModelResponse.events``
  (the harness copies them onto the chat span; a raised BedrockError carries them as ``.events``). ServiceQuotaExceeded is
  never retried. A semaphore caps concurrency (default 2).
* Usage maps cacheRead/cacheWrite; ``reasoningContent`` becomes a ``Reasoning`` block (never scored).
* Spend: ``ledger.reserve()`` before the call, ``commit()`` after (usage × dated price), reported as
  ``ModelResponse.cost_usd`` / ``price_table_version``; a failed call releases its reservation. An unpriced
  model is refused before any call.
* Images (F4): the adapter rejects formats other than png|jpeg|gif|webp and bytes whose magic number
  does not match the declared format; live calls need pixels whose decoded hash matches ``Image.sha256``
  (``require_pixels(decode=decode_png)``, M10).

boto3/botocore are imported lazily, so this module imports without them.
"""

from __future__ import annotations

import asyncio
import random
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any

from treehouse.canon import canonical_json
from treehouse.providers.base import ProviderError, decode_png, iter_images, pixel_free, require_pixels
from treehouse.providers.prices import PriceTable
from treehouse.providers.registry import ModelEntry, ModelRegistry
from treehouse.providers.spend import SpendLedger
from treehouse.schemas.model_io import (
    Image,
    Json,
    Message,
    ModelRequest,
    ModelResponse,
    ProviderEvent,
    Reasoning,
    Text,
    ToolResult,
    ToolUse,
    Usage,
)

PROVIDER_NAME = "aws.bedrock"  # F10
# F1: {"max_attempts": 1} still makes 2 HTTP attempts; total_max_attempts=1 makes exactly one.
BOTOCORE_RETRIES = {"total_max_attempts": 1, "mode": "standard"}
READ_TIMEOUT_S = 300
RETRYABLE = frozenset({
    "ThrottlingException",
    "ServiceUnavailableException",
    "ModelNotReadyException",
    "ModelTimeoutException",
    "InternalServerException",
})
NEVER_RETRY = frozenset({"ServiceQuotaExceededException"})
STOP_REASONS: dict[str, str] = {  # identity: ModelResponse.stop_reason carries every Bedrock value (F3)
    "end_turn": "end_turn",
    "tool_use": "tool_use",
    "max_tokens": "max_tokens",
    "stop_sequence": "stop_sequence",
    "guardrail_intervened": "guardrail_intervened",
    "content_filtered": "content_filtered",
    "malformed_model_output": "malformed_model_output",
    "malformed_tool_use": "malformed_tool_use",
    "model_context_window_exceeded": "model_context_window_exceeded",
}
IMAGE_FORMATS = ("png", "jpeg", "gif", "webp")
_MAGIC: dict[str, Callable[[bytes], bool]] = {
    "png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
    "jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
    "gif": lambda b: b[:6] in (b"GIF87a", b"GIF89a"),
    "webp": lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP",
}
IMAGE_TOKEN_ESTIMATE = 1600  # conservative per-image input-token estimate for the reservation


# -- errors -------------------------------------------------------------------------------------
class BedrockError(ProviderError):
    def __init__(self, message: str, *, code: str | None = None, request_id: str | None = None) -> None:
        super().__init__(message)
        self.code, self.request_id = code, request_id
        self.events: list[ProviderEvent] = []


class BedrockValidationError(BedrockError):
    """ValidationException: a bad request (wrong id, unsupported content, bad params). Not retried."""


class BedrockAccessDenied(BedrockError):
    pass


class BedrockModelNotFound(BedrockError):
    pass


class BedrockQuotaExceeded(BedrockError):
    """ServiceQuotaExceededException: never retried (F2)."""


class BedrockModelError(BedrockError):
    pass


class BedrockRetriesExhausted(BedrockError):
    pass


class UnsupportedImage(BedrockValidationError):
    pass


class VisionNotSupported(BedrockValidationError):
    pass


_TYPED: dict[str, type[BedrockError]] = {
    "ValidationException": BedrockValidationError,
    "AccessDeniedException": BedrockAccessDenied,
    "ResourceNotFoundException": BedrockModelNotFound,
    "ServiceQuotaExceededException": BedrockQuotaExceeded,
    "ModelErrorException": BedrockModelError,
}


def _error_code(exc: BaseException) -> str | None:
    resp = getattr(exc, "response", None)
    if isinstance(resp, dict):
        return (resp.get("Error") or {}).get("Code")
    return None


def _error_request_id(exc: BaseException) -> str | None:
    resp = getattr(exc, "response", None)
    if isinstance(resp, dict):
        return (resp.get("ResponseMetadata") or {}).get("RequestId")
    return None


def typed_error(exc: BaseException) -> BedrockError:
    code = _error_code(exc) or type(exc).__name__
    cls = _TYPED.get(code, BedrockError)
    return cls(f"{code}: {exc}", code=code, request_id=_error_request_id(exc))


# -- client -------------------------------------------------------------------------------------
def default_client_factory(region: str, *, endpoint_url: str | None = None, retries: dict | None = None) -> Any:
    """A bedrock-runtime client that makes exactly one HTTP attempt per call (F1)."""
    import boto3
    from botocore.config import Config

    cfg = Config(retries=dict(retries or BOTOCORE_RETRIES), read_timeout=READ_TIMEOUT_S, connect_timeout=10)
    return boto3.client("bedrock-runtime", region_name=region, endpoint_url=endpoint_url, config=cfg)


# -- request building ---------------------------------------------------------------------------
def check_image(img: Image) -> None:
    fmt = img.format
    if fmt not in IMAGE_FORMATS:
        raise UnsupportedImage(f"image {img.sha256}: format {fmt!r} not in {IMAGE_FORMATS}")
    if img.bytes_ is not None and not _MAGIC[fmt](img.bytes_):
        raise UnsupportedImage(f"image {img.sha256}: bytes do not look like {fmt}")


def _image_block(img: Image) -> dict[str, Any]:
    return {"image": {"format": img.format, "source": {"bytes": img.bytes_}}}


def _assistant_block(b: Any) -> dict[str, Any] | None:
    if isinstance(b, Text):
        return {"text": b.text}
    if isinstance(b, ToolUse):
        return {"toolUse": {"toolUseId": b.id, "name": b.name, "input": b.input}}
    if isinstance(b, Reasoning):
        if b.signature is None:
            return None  # unsigned reasoning cannot be sent back; it stays in the trace only
        return {"reasoningContent": {"reasoningText": {"text": b.text, "signature": b.signature}}}
    if isinstance(b, Image):
        return _image_block(b)
    raise BedrockValidationError(f"unsupported assistant block {type(b).__name__}")


def _user_blocks(m: Message, delivery: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    moved: list[dict[str, Any]] = []
    for b in m.content:
        if isinstance(b, Text):
            out.append({"text": b.text})
        elif isinstance(b, Image):
            out.append(_image_block(b))
        elif isinstance(b, ToolResult):
            content: list[dict[str, Any]] = []
            for c in b.content:
                if isinstance(c, Text):
                    content.append({"text": c.text})
                elif isinstance(c, Json):
                    content.append({"json": c.json_})
                elif isinstance(c, Image):
                    if delivery == "tool_result":
                        content.append(_image_block(c))
                    else:
                        content.append({"text": f"[image {c.sha256} follows in this user message]"})
                        moved.append(_image_block(c))
            out.append({"toolResult": {"toolUseId": b.tool_use_id, "status": b.status, "content": content}})
        elif isinstance(b, Reasoning | ToolUse):
            raise BedrockValidationError(f"{type(b).__name__} block in a user message")
    return out + moved


def build_converse_kwargs(req: ModelRequest, entry: ModelEntry, *, delivery: str | None = None) -> dict[str, Any]:
    """The ``converse`` kwargs for ``req``. ``delivery`` defaults to the registry's image_delivery."""
    delivery = delivery or entry.image_delivery
    if delivery not in ("tool_result", "user_turn"):
        raise ValueError(f"unknown image delivery {delivery!r}")
    messages = []
    for m in req.messages:
        if m.role == "user":
            content = _user_blocks(m, delivery)
        else:
            content = [x for x in (_assistant_block(b) for b in m.content) if x is not None]
        messages.append({"role": m.role, "content": content})
    kw: dict[str, Any] = {"modelId": entry.invoke_id, "messages": messages}
    if req.system:
        kw["system"] = [{"text": req.system}]
    if req.tools:
        kw["toolConfig"] = {"tools": [{"toolSpec": {"name": t.name, "description": t.description,
                                                     "inputSchema": {"json": t.input_schema}}}
                                       for t in req.tools]}
    inf: dict[str, Any] = {"maxTokens": req.params.max_tokens}
    if req.params.temperature is not None:
        inf["temperature"] = req.params.temperature
    if req.params.top_p is not None:
        inf["topP"] = req.params.top_p
    kw["inferenceConfig"] = inf  # params.seed has no Converse equivalent; it stays in the request key only
    return kw


def estimate_input_tokens(req: ModelRequest) -> int:
    """A deliberately high estimate: 1 token per 3 characters of the pixel-free request, plus a fixed
    allowance per image."""
    n_images = sum(1 for _ in iter_images(req.messages))
    return len(canonical_json(pixel_free(req))) // 3 + 1 + IMAGE_TOKEN_ESTIMATE * n_images


# -- response mapping ---------------------------------------------------------------------------
def map_stop_reason(raw: str) -> str:
    try:
        return STOP_REASONS[raw]
    except KeyError:
        raise BedrockError(f"unknown Bedrock stopReason {raw!r}", code="UnknownStopReason") from None


def map_usage(u: dict[str, Any]) -> Usage:
    return Usage(input_tokens=int(u.get("inputTokens", 0)), output_tokens=int(u.get("outputTokens", 0)),
                 cache_read=int(u.get("cacheReadInputTokens", 0) or 0),
                 cache_write=int(u.get("cacheWriteInputTokens", 0) or 0))


def map_response(raw: dict[str, Any], *, model_id: str, elapsed_ms: int) -> ModelResponse:
    blocks: list[Any] = []
    for c in ((raw.get("output") or {}).get("message") or {}).get("content", []):
        if "text" in c:
            blocks.append(Text(text=c["text"]))
        elif "toolUse" in c:
            tu = c["toolUse"]
            blocks.append(ToolUse(id=tu["toolUseId"], name=tu["name"], input=tu.get("input") or {}))
        elif "reasoningContent" in c:
            rc = c["reasoningContent"]
            if "reasoningText" in rc:
                blocks.append(Reasoning(text=rc["reasoningText"].get("text", ""),
                                        signature=rc["reasoningText"].get("signature")))
            else:
                blocks.append(Reasoning(text="[redacted reasoning]", signature=None))
        # other output blocks (citations, images) are not used by Treehouse roles
    latency = (raw.get("metrics") or {}).get("latencyMs")
    return ModelResponse(
        message=Message(role="assistant", content=blocks),
        stop_reason=map_stop_reason(raw.get("stopReason", "")),
        usage=map_usage(raw.get("usage") or {}),
        latency_ms=int(latency if latency is not None else elapsed_ms),
        response_model_id=model_id,
        request_id=(raw.get("ResponseMetadata") or {}).get("RequestId"),
    )


# -- provider -----------------------------------------------------------------------------------
class BedrockConverseProvider:
    provider_name = PROVIDER_NAME

    def __init__(
        self,
        client_factory: Callable[[str], Any] | None,
        registry: ModelRegistry,
        prices: PriceTable,
        ledger: SpendLedger,
        region: str = "us-east-1",
        concurrency: int = 2,
        max_attempts: int = 6,
        *,
        base_delay_s: float = 1.0,
        max_delay_s: float = 20.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rng: random.Random | None = None,
        unpriced_cap_usd: float | None = None,
        commit_price_override: PriceTable | None = None,
        image_delivery: str | None = None,
        allow_over_alarm: bool = False,
        over_alarm_reason: str | None = None,
    ) -> None:
        if max_attempts < 1 or concurrency < 1:
            raise ValueError("max_attempts and concurrency must be >= 1")
        self._factory = client_factory or default_client_factory
        self.registry, self.prices, self.ledger, self.region = registry, prices, ledger, region
        self.concurrency, self.max_attempts = concurrency, max_attempts
        self.base_delay_s, self.max_delay_s = base_delay_s, max_delay_s
        self._sleep, self._rng = sleep, rng or random.Random()
        self.unpriced_cap_usd, self.commit_price_override = unpriced_cap_usd, commit_price_override
        self.image_delivery = image_delivery
        self.allow_over_alarm, self.over_alarm_reason = allow_over_alarm, over_alarm_reason
        self.price_table_version = prices.version
        self._client: Any = None
        self._client_lock = threading.Lock()
        self._sems: dict[int, asyncio.Semaphore] = {}

    @property
    def client(self) -> Any:
        with self._client_lock:
            if self._client is None:
                self._client = self._factory(self.region)
            return self._client

    def _sem(self) -> asyncio.Semaphore:
        loop_id = id(asyncio.get_running_loop())
        if loop_id not in self._sems:
            self._sems[loop_id] = asyncio.Semaphore(self.concurrency)
        return self._sems[loop_id]

    def _delay(self, attempt: int) -> float:
        cap = min(self.max_delay_s, self.base_delay_s * (2 ** (attempt - 1)))
        return cap * (0.5 + 0.5 * self._rng.random())  # "equal jitter"

    def prepare(self, req: ModelRequest) -> tuple[ModelEntry, dict[str, Any]]:
        """Validate and build the wire request (no ledger, no network)."""
        entry = self.registry.get(req.model_id)
        images = [img for _, img in iter_images(req.messages)]
        if images and not entry.vision:
            raise VisionNotSupported(f"{entry.key} has vision: false but the request carries {len(images)} image(s)")
        require_pixels(req)  # byte-less or empty images first (MissingPixels)
        for img in images:
            check_image(img)  # F4: allowed format and matching magic number
        require_pixels(req, decode=decode_png)  # M10: decoded pixels reproduce Image.sha256
        return entry, build_converse_kwargs(req, entry, delivery=self.image_delivery)

    async def complete(self, req: ModelRequest, *, role: str, trial_index: int, turn: int) -> ModelResponse:
        entry, kwargs = self.prepare(req)
        reservation = self.ledger.reserve(
            entry.key, estimate_input_tokens(req), req.params.max_tokens,
            allow_over_alarm=self.allow_over_alarm, reason=self.over_alarm_reason,
            unpriced_cap_usd=self.unpriced_cap_usd,
        )
        events: list[ProviderEvent] = []
        try:
            raw, elapsed_ms = await self._call_with_retries(kwargs, events)
        except BaseException as e:
            self.ledger.release(reservation, why=type(e).__name__)
            if isinstance(e, BedrockError):
                e.events = events
            raise
        resp = map_response(raw, model_id=entry.invoke_id, elapsed_ms=elapsed_ms)
        cost = self.ledger.commit(reservation, resp.usage, price_override=self.commit_price_override)
        version = (self.commit_price_override.version if reservation.unpriced and self.commit_price_override
                   else self.prices.version)
        return resp.model_copy(update={"cost_usd": cost, "price_table_version": version, "events": events})

    async def _call_with_retries(self, kwargs: dict[str, Any], events: list[ProviderEvent]) -> tuple[dict[str, Any], int]:
        async with self._sem():
            for attempt in range(1, self.max_attempts + 1):
                t0 = time.monotonic()
                try:
                    raw = await asyncio.to_thread(self.client.converse, **kwargs)
                    return raw, int((time.monotonic() - t0) * 1000)
                except Exception as e:
                    code = _error_code(e)
                    if code is None and not _is_botocore_error(e):
                        raise
                    retryable = code in RETRYABLE and code not in NEVER_RETRY
                    will_retry = retryable and attempt < self.max_attempts
                    delay = self._delay(attempt) if will_retry else 0.0
                    if retryable:
                        attrs = {"attempt": attempt, "error_code": code, "delay_s": round(delay, 3),
                                 "will_retry": will_retry, "request_id": _error_request_id(e)}
                        events.append(ProviderEvent(name="treehouse.retry",  # span attributes cannot be None
                                                    attributes={k: v for k, v in attrs.items() if v is not None}))
                    if not retryable:
                        raise typed_error(e) from e
                    if not will_retry:
                        raise BedrockRetriesExhausted(
                            f"{code} after {attempt} attempts", code=code, request_id=_error_request_id(e)) from e
                    await self._sleep(delay)
        raise AssertionError("unreachable")  # pragma: no cover


def _is_botocore_error(e: BaseException) -> bool:
    return type(e).__module__.startswith("botocore")
