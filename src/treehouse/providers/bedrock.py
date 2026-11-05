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
  ``ModelResponse.cost_usd`` / ``price_table_version``. The ledger's price table is the ONLY price source
  (M5); the provider's ``prices`` argument must carry the same version. Usage is committed BEFORE the
  response content is mapped (M4). A call that failed with a service error response (4xx, throttling,
  5xx codes) or before connecting releases its reservation; an AMBIGUOUS failure (read timeout, dropped
  connection, cancel, interrupt, any unknown exception) commits the full reservation as
  ``estimated``/``ambiguous`` (M3), because Bedrock may have billed it. An unpriced model is refused before
  any call; ``unpriced_cap_usd`` (the K1 probe only) is limited to $0.25 and ``max_tokens <= 32``.
* Images (F4): the adapter rejects formats other than png|jpeg|gif|webp and bytes whose magic number
  does not match the declared format; live calls need pixels whose decoded hash matches ``Image.sha256``
  (``require_pixels(decode=decode_png)``, M10).

boto3/botocore are imported lazily, so this module imports without them.
"""

from __future__ import annotations

import asyncio
import hashlib
import random
import threading
import time
from collections.abc import Awaitable, Callable
from copy import deepcopy
from typing import Any

from treehouse.canon import canonical_json
from treehouse.pixels import array_sha256
from treehouse.providers.base import (
    PixelHashMismatch,
    ProviderError,
    decode_png,
    iter_images,
    pixel_free,
    require_pixels,
)
from treehouse.providers.prices import PriceTable, profile_of
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
STOP_REASONS: dict[str, str] = {  # F3: every Bedrock value maps to itself except guardrail_intervened -> guardrail
    "end_turn": "end_turn",
    "tool_use": "tool_use",
    "max_tokens": "max_tokens",
    "stop_sequence": "stop_sequence",
    "guardrail_intervened": "guardrail",
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
TOOLS_TOKEN_ALLOWANCE = 1000  # hidden tool-use system prompt the chars/3 estimate never sees (minor 13)
UNPRICED_CAP_MAX_USD, UNPRICED_MAX_TOKENS = 0.25, 32  # unpriced calls: the K1 probe only (minor 20)
# failures known to happen before Bedrock bills: the client never sent the request (M3)
UNBILLED_TRANSPORT = frozenset({"EndpointConnectionError", "ConnectTimeoutError", "ParamValidationError",
                                "NoCredentialsError", "PartialCredentialsError", "NoRegionError"})


# -- errors -------------------------------------------------------------------------------------
class BedrockError(ProviderError):
    def __init__(self, message: str, *, code: str | None = None, request_id: str | None = None) -> None:
        super().__init__(message)
        self.code, self.request_id = code, request_id
        self.events: list[ProviderEvent] = []
        self.service_error = False  # True: Bedrock answered with an error code (not billed)
        self.cost_usd: float | None = None  # set when the ledger booked spend for this failed call


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
    """ClientErrors map by error code; other botocore errors (ReadTimeoutError, ConnectTimeoutError,
    ConnectionClosedError, ...) by class name, as plain BedrockError (``service_error`` False)."""
    service_code = _error_code(exc)
    code = service_code or type(exc).__name__
    cls = _TYPED.get(code, BedrockError)
    err = cls(f"{code}: {exc}", code=code, request_id=_error_request_id(exc))
    err.service_error = service_code is not None
    return err


def known_unbilled(exc: BaseException) -> bool:
    """True only when the failure provably happened before Bedrock could bill (M3)."""
    return isinstance(exc, BedrockError) and (exc.service_error or exc.code in UNBILLED_TRANSPORT)


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


def build_converse_kwargs(req: ModelRequest, entry: ModelEntry, *, delivery: str | None = None,
                          thinking: bool = False) -> dict[str, Any]:
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
    if thinking:
        if not entry.request_fields.get("thinking"):
            raise BedrockValidationError(f"{entry.key}: no thinking request_fields configured")
        kw["additionalModelRequestFields"] = deepcopy(entry.request_fields)
    if (not thinking and entry.family == "anthropic-claude" and req.params.temperature is not None
            and req.params.top_p is not None):
        raise BedrockValidationError(f"{entry.key}: recent Claude models reject temperature and top_p together")
    inf: dict[str, Any] = {"maxTokens": req.params.max_tokens}
    if req.params.temperature is not None and not thinking:
        inf["temperature"] = req.params.temperature
    if req.params.top_p is not None:
        inf["topP"] = req.params.top_p
    kw["inferenceConfig"] = inf  # params.seed has no Converse equivalent; it stays in the request key only
    return kw


def estimate_input_tokens(req: ModelRequest) -> int:
    """A deliberately high estimate: 1 token per 3 characters of the pixel-free request, plus a fixed
    allowance per image."""
    n_images = sum(1 for _ in iter_images(req.messages))
    return (len(canonical_json(pixel_free(req))) // 3 + 1 + IMAGE_TOKEN_ESTIMATE * n_images
            + (TOOLS_TOKEN_ALLOWANCE if req.tools else 0))


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
        prices: PriceTable | None,
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
        thinking: bool = False,
    ) -> None:
        if max_attempts < 1 or concurrency < 1:
            raise ValueError("max_attempts and concurrency must be >= 1")
        if unpriced_cap_usd is not None and unpriced_cap_usd > UNPRICED_CAP_MAX_USD:
            raise ValueError(f"unpriced_cap_usd may be at most ${UNPRICED_CAP_MAX_USD} (the K1 probe cap)")
        lp = ledger.prices
        if prices is not None and lp is not None and prices.version != lp.version:
            raise ValueError(f"provider price table {prices.version} != ledger price table {lp.version}: the ledger's "
                             "table is the only price source; pass the same table (M5)")
        if lp is not None and lp.region not in (region, "any"):
            raise ValueError(f"price table {lp.version} is for {lp.region}, provider region is {region}")
        self._factory = client_factory or default_client_factory
        self.registry, self.prices, self.ledger, self.region = registry, prices, ledger, region
        self.concurrency, self.max_attempts = concurrency, max_attempts
        self.base_delay_s, self.max_delay_s = base_delay_s, max_delay_s
        self._sleep, self._rng = sleep, rng or random.Random()
        self.unpriced_cap_usd, self.commit_price_override = unpriced_cap_usd, commit_price_override
        self.image_delivery = image_delivery
        self.thinking = thinking
        self.allow_over_alarm, self.over_alarm_reason = allow_over_alarm, over_alarm_reason
        self.price_table_version = lp.version if lp is not None else (prices.version if prices else "none")
        self._verified: dict[tuple[str, str], tuple[int, ...] | None] = {}  # (bytes sha, Image.sha256) -> shape
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
        if entry.region != self.region:
            raise BedrockValidationError(f"{entry.key} is registered in {entry.region}; provider region is {self.region}")
        images = list(iter_images(req.messages))
        if images and not entry.vision:
            raise VisionNotSupported(f"{entry.key} has vision: false but the request carries {len(images)} image(s)")
        require_pixels(req)  # byte-less or empty images first (MissingPixels)
        for _, img in images:
            check_image(img)  # F4: allowed format and matching magic number
        for i, img in images:
            shape = self._verify_pixels(i, img)  # M10: decoded pixels reproduce Image.sha256 (cached, M8)
            if shape is not None and entry.max_image_px is not None and max(shape[:2]) > entry.max_image_px:
                raise UnsupportedImage(f"image {img.sha256}: {shape[1]}x{shape[0]} px exceeds {entry.key} "
                                       f"max_image_px {entry.max_image_px}")
        return entry, build_converse_kwargs(req, entry, delivery=self.image_delivery, thinking=self.thinking)

    def _verify_pixels(self, i: int, img: Image) -> tuple[int, ...] | None:
        """Decode once per (bytes, claimed hash): the history resends every image each turn (M8)."""
        key = (hashlib.sha256(img.bytes_ or b"").hexdigest(), img.sha256)
        if key in self._verified:
            return self._verified[key]
        try:
            arr = decode_png(img.bytes_ or b"", img.format)
        except ValueError as e:
            raise PixelHashMismatch(f"message {i}: image {img.sha256} does not decode as {img.format}: {e}") from e
        if arr is not None and array_sha256(arr) != img.sha256:
            raise PixelHashMismatch(f"message {i}: decoded pixels hash to {array_sha256(arr)}, not {img.sha256}")
        shape = tuple(arr.shape) if arr is not None else None
        self._verified[key] = shape
        return shape

    async def complete(self, req: ModelRequest, *, role: str, trial_index: int, turn: int) -> ModelResponse:
        entry, kwargs = self.prepare(req)
        if self.unpriced_cap_usd is not None and req.params.max_tokens > UNPRICED_MAX_TOKENS:
            raise BedrockValidationError(f"unpriced calls (probe) need max_tokens <= {UNPRICED_MAX_TOKENS}")
        reservation = self.ledger.reserve(
            entry.key, estimate_input_tokens(req), req.params.max_tokens,
            allow_over_alarm=self.allow_over_alarm, reason=self.over_alarm_reason,
            unpriced_cap_usd=self.unpriced_cap_usd, price_ref=entry.price_ref, profile=profile_of(entry.invoke_id),
        )
        events: list[ProviderEvent] = []
        try:
            raw, elapsed_ms = await self._call_with_retries(kwargs, events)
        except BaseException as e:
            if known_unbilled(e):
                self.ledger.release(reservation, why=type(e).__name__)
            else:  # M3: Bedrock may have billed (timeout, dropped connection, cancel): book the worst case
                cost = self.ledger.commit_worst(reservation, why=f"ambiguous: {type(e).__name__}")
                try:
                    e.cost_usd = cost  # type: ignore[attr-defined]
                except AttributeError:  # pragma: no cover
                    pass
            if isinstance(e, BedrockError):
                e.events = events
            raise
        # M4: the call returned (billed). Book its usage before anything else can raise.
        if not isinstance(raw.get("usage"), dict):
            cost = self.ledger.commit_worst(reservation, why="ambiguous: response without usage")
            raise self._failed(BedrockError("Bedrock response has no usage block", code="MalformedResponse"),
                               events, cost)
        try:
            usage = map_usage(raw["usage"])
        except Exception as e:  # noqa: BLE001
            cost = self.ledger.commit_worst(reservation, why=f"ambiguous: unparseable usage ({e})")
            raise self._failed(BedrockError(f"unparseable usage: {e}", code="MalformedResponse"), events, cost) from e
        cost = self.ledger.commit(reservation, usage, price_override=self.commit_price_override)
        try:
            resp = map_response(raw, model_id=entry.invoke_id, elapsed_ms=elapsed_ms)
        except Exception as e:  # noqa: BLE001
            err = e if isinstance(e, BedrockError) else BedrockError(
                f"unmappable Bedrock response: {type(e).__name__}: {e}", code="MalformedResponse")
            raise self._failed(err, events, cost) from e
        if reservation.unpriced:
            version = self.commit_price_override.version if self.commit_price_override else "unpriced-cap"
        else:
            version = self.price_table_version
        return resp.model_copy(update={"cost_usd": cost, "price_table_version": version, "events": events})

    @staticmethod
    def _failed(err: BedrockError, events: list[ProviderEvent], cost: float) -> BedrockError:
        err.events, err.cost_usd = events, cost
        return err

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
                        err = BedrockRetriesExhausted(
                            f"{code} after {attempt} attempts", code=code, request_id=_error_request_id(e))
                        err.service_error = True
                        raise err from e
                    await self._sleep(delay)
        raise AssertionError("unreachable")  # pragma: no cover


def _is_botocore_error(e: BaseException) -> bool:
    return type(e).__module__.startswith("botocore")
