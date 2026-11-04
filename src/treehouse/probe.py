"""AWS capability probe (K1): one cheap call per service, each classified, never aborting.

Output is ``treehouse.aws-capabilities/v1`` (``schemas/probe.py``). Every Bedrock Converse call goes through
``SpendLedger.reserve(..., unpriced_cap_usd=0.25)`` with ``max_tokens <= 32`` (AWS-B1). Reservations are
counted against a $3 probe cap; once the next one would pass it, the remaining Bedrock checks report
``skipped_budget``. Commits use actual usage at the placeholder prices in
``config/prices/probe-ceiling.yaml`` and are tagged ``estimated``.

The tiny probe image is generated in memory (an 8x8 RGB gradient PNG) and never written to disk.
"""

from __future__ import annotations

import asyncio
import os
import platform
import struct
import sys
import zlib
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from treehouse.providers.bedrock import BOTOCORE_RETRIES, BedrockConverseProvider, BedrockError
from treehouse.providers.prices import PriceTable, load_probe_ceiling
from treehouse.providers.registry import ModelEntry, ModelRegistry
from treehouse.providers.spend import BudgetAlarm, BudgetHardStop, SpendLedger, UnpricedModel
from treehouse.schemas.config import InferenceParams
from treehouse.schemas.model_io import Image, Message, ModelRequest, Text, ToolResult, ToolSpec, ToolUse
from treehouse.schemas.probe import AwsCapabilities, CheckStatus, ProbeCheck, ProbeModel, ProbeSpend

PROBE_VERSION = "1"
PROBE_CAP_USD = 3.0
PER_CALL_CAP_USD = 0.25
PROBE_MAX_TOKENS = 32
MODES = ("user_turn", "tool_result")
LOG_GROUP = "/treehouse/probe"

DENIED = {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation", "UnrecognizedClientException",
          "InvalidClientTokenId", "ExpiredToken", "ExpiredTokenException", "NotAuthorized",
          "AuthorizationError", "AuthFailure", "SignatureDoesNotMatch", "MissingAuthenticationToken"}
UNAVAILABLE = {"ResourceNotFoundException", "ValidationException", "UnknownOperationException",
               "NoSuchBucket", "UnknownServiceError", "EndpointConnectionError", "NoSuchEntity",
               "OptInRequired", "SubscriptionRequiredException", "UnsupportedOperation",
               "InvalidAction", "NotFound", "NotFoundException"}

ClientFactory = Callable[[str], Any]


def tiny_png(w: int = 8, h: int = 8) -> tuple[bytes, str]:
    """(png bytes, pixel sha256) for a small RGB gradient, built in memory."""
    import numpy as np

    from treehouse.pixels import array_sha256

    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[..., 0] = np.linspace(0, 255, w, dtype=np.uint8)[None, :]
    arr[..., 1] = np.linspace(0, 255, h, dtype=np.uint8)[:, None]
    raw = b"".join(b"\x00" + arr[y].tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    return png, array_sha256(arr)


def error_code(e: BaseException) -> str:
    if isinstance(e, BedrockError) and e.code:
        return e.code
    resp = getattr(e, "response", None)
    if isinstance(resp, dict) and (resp.get("Error") or {}).get("Code"):
        return str(resp["Error"]["Code"])
    return type(e).__name__


def classify(e: BaseException) -> CheckStatus:
    if isinstance(e, BudgetHardStop | BudgetAlarm | UnpricedModel):
        return "skipped_budget"
    code = error_code(e)
    if code in DENIED or "AccessDenied" in code or "not authorized" in str(e):
        return "denied"
    if code in UNAVAILABLE or code.endswith("NotFound") or code.endswith("NotFoundException"):
        return "unavailable"
    return "error"


def execution_locus() -> dict[str, Any]:
    env = os.environ
    if env.get("AWS_LAMBDA_FUNCTION_NAME"):
        locus = "lambda"
    elif env.get("ECS_CONTAINER_METADATA_URI_V4") or env.get("ECS_CONTAINER_METADATA_URI"):
        locus = "ecs"
    elif env.get("CODEBUILD_BUILD_ID"):
        locus = "codebuild"
    elif env.get("AWS_EXECUTION_ENV"):
        locus = env["AWS_EXECUTION_ENV"]
    else:
        locus = "local-or-ec2"
    return {"locus": locus, "platform": platform.platform(), "python": sys.version.split()[0],
            "aws_execution_env": env.get("AWS_EXECUTION_ENV")}


def default_client_factory(region: str) -> ClientFactory:
    import boto3
    from botocore.config import Config

    session = boto3.Session(region_name=region)

    def make(service: str) -> Any:
        read = 300 if service == "bedrock-runtime" else 30
        return session.client(service, config=Config(retries=dict(BOTOCORE_RETRIES), connect_timeout=5,
                                                     read_timeout=read))
    return make


class Probe:
    def __init__(
        self,
        client_factory: ClientFactory,
        *,
        region: str,
        registry: ModelRegistry,
        ledger: SpendLedger,
        ceiling: PriceTable | None = None,
        cap_usd: float = PROBE_CAP_USD,
        per_call_cap_usd: float = PER_CALL_CAP_USD,
        max_tokens: int = PROBE_MAX_TOKENS,
        bucket: str | None = None,
        log_group: str | None = LOG_GROUP,
        sleep: Callable[[float], Any] | None = None,
    ) -> None:
        if max_tokens > PROBE_MAX_TOKENS:
            raise ValueError(f"probe max_tokens must be <= {PROBE_MAX_TOKENS}")
        if per_call_cap_usd > PER_CALL_CAP_USD or cap_usd > PROBE_CAP_USD:
            raise ValueError("probe caps may only be lowered")
        self.cf, self.region, self.registry, self.ledger = client_factory, region, registry, ledger
        self.ceiling = ceiling or load_probe_ceiling()
        self.cap_usd, self.per_call_cap_usd, self.max_tokens = cap_usd, per_call_cap_usd, max_tokens
        self.bucket, self.log_group = bucket, log_group
        self._sleep = sleep
        self.checks: list[ProbeCheck] = []
        self.reserved_usd = 0.0
        self.committed_usd = 0.0
        self.calls = 0
        self.events: list[dict[str, Any]] = []  # the adapter's treehouse.retry events
        self._clients: dict[str, Any] = {}

    # -- helpers ------------------------------------------------------------------------------
    def client(self, service: str) -> Any:
        if service not in self._clients:
            self._clients[service] = self.cf(service)
        return self._clients[service]

    def _record(self, name: str, service: str, status: CheckStatus, detail: str = "", code: str | None = None,
                **data: Any) -> ProbeCheck:
        c = ProbeCheck(name=name, service=service, status=status, detail=detail[:500], error_code=code, data=data)
        self.checks.append(c)
        return c

    def check(self, name: str, service: str, fn: Callable[[], dict[str, Any] | None]) -> ProbeCheck:
        """Run one check; any exception is classified, never raised."""
        try:
            data = fn() or {}
            detail = str(data.pop("_detail", ""))
            return self._record(name, service, "ok", detail, **data)
        except Exception as e:  # noqa: BLE001 - the probe never aborts
            return self._record(name, service, classify(e), f"{type(e).__name__}: {e}", error_code(e))

    # -- Bedrock calls -------------------------------------------------------------------------
    def _request(self, entry: ModelEntry, mode: str) -> ModelRequest:
        png, sha = tiny_png()
        img = Image(format="png", sha256=sha, bytes_=png)
        params = InferenceParams(max_tokens=self.max_tokens, temperature=0.0)
        ask = Text(text="Reply with one word: is the image mostly red, green, or mixed?")
        if mode == "user_turn":
            return ModelRequest(model_id=entry.key, system="You are a capability probe. Be brief.",
                                messages=[Message(role="user", content=[ask, img])], params=params)
        tool = ToolSpec(name="get_image", description="Returns the probe image.",
                        input_schema={"type": "object", "properties": {}})
        return ModelRequest(
            model_id=entry.key, system="You are a capability probe. Be brief.", tools=[tool], params=params,
            messages=[
                Message(role="user", content=[Text(text="Call get_image, then answer.")]),
                Message(role="assistant", content=[ToolUse(id="probe-tu-1", name="get_image", input={})]),
                Message(role="user", content=[ToolResult(tool_use_id="probe-tu-1", status="success",
                                                         content=[img, ask])]),
            ])

    def converse(self, entry: ModelEntry, mode: str, invoke_id: str) -> ProbeCheck:
        name = f"bedrock.converse:{entry.key}:{mode}:{invoke_id}"
        if self.reserved_usd + self.per_call_cap_usd > self.cap_usd + 1e-9:
            return self._record(name, "bedrock-runtime", "skipped_budget",
                                f"probe cap ${self.cap_usd:.2f} reached ({self.calls} calls reserved)")
        e2 = entry.model_copy(update={"inference_profile": invoke_id, "alt_profiles": []})
        reg = ModelRegistry(models=[e2])
        kw: dict[str, Any] = {}
        if self._sleep is not None:
            kw["sleep"] = self._sleep
        provider = BedrockConverseProvider(
            lambda _region: self.client("bedrock-runtime"), reg, PriceTable(version="null", region=self.region),
            self.ledger, self.region, concurrency=1, max_attempts=2, unpriced_cap_usd=self.per_call_cap_usd,
            commit_price_override=self.ceiling, image_delivery=mode, **kw)
        before = self.ledger.status().spent_usd
        self.reserved_usd += self.per_call_cap_usd  # counted before the call: the cap holds even if it fails
        self.calls += 1
        try:
            resp = asyncio.run(provider.complete(self._request(entry, mode), role="probe", trial_index=0, turn=0))
        except Exception as e:  # noqa: BLE001
            self.events += [{"name": ev.name, **ev.attributes} for ev in getattr(e, "events", [])]
            return self._record(name, "bedrock-runtime", classify(e), f"{type(e).__name__}: {e}", error_code(e),
                                invoke_id=invoke_id, mode=mode)
        finally:
            self.committed_usd += self.ledger.status().spent_usd - before
        self.events += [{"name": ev.name, **ev.attributes} for ev in resp.events]
        text = "".join(b.text for b in resp.message.content if isinstance(b, Text))[:80]
        return self._record(name, "bedrock-runtime", "ok", "", None, invoke_id=invoke_id, mode=mode,
                            stop_reason=resp.stop_reason, reply=text, usage=resp.usage.model_dump(mode="json"),
                            estimated_cost_usd=resp.cost_usd)

    # -- the run --------------------------------------------------------------------------------
    def run(self) -> AwsCapabilities:
        execution = execution_locus()
        ident: dict[str, Any] = {}

        def sts() -> dict[str, Any]:
            r = self.client("sts").get_caller_identity()
            ident.update(account=r.get("Account"), arn=r.get("Arn"))
            return {"account": r.get("Account"), "arn": r.get("Arn")}
        self.check("sts.get_caller_identity", "sts", sts)
        execution.update(identity_arn=ident.get("arn"), account=ident.get("account"))
        try:
            import boto3
            execution["boto3"] = boto3.__version__
        except Exception:  # noqa: BLE001
            execution["boto3"] = None

        fms: dict[str, dict[str, Any]] = {}
        profiles: set[str] = set()
        fm_ok = self.check("bedrock.list_foundation_models", "bedrock", lambda: self._list_models(fms)).status == "ok"
        pr_ok = self.check("bedrock.list_inference_profiles", "bedrock",
                           lambda: self._list_profiles(profiles)).status == "ok"

        models: list[ProbeModel] = []
        for entry in self.registry.models:
            models.append(self._probe_model(entry, fms, profiles, fm_ok, pr_ok))

        quotas: list[dict[str, Any]] = []
        self.check("service-quotas.list_service_quotas:bedrock", "service-quotas", lambda: self._quotas(quotas))
        logging_cfg: dict[str, Any] = {}
        self.check("bedrock.get_model_invocation_logging_configuration", "bedrock",
                   lambda: self._invocation_logging(logging_cfg))
        self.check("s3.list_buckets", "s3", lambda: {"buckets": len(self.client("s3").list_buckets()
                                                                     .get("Buckets", []))})
        if self.bucket:
            self.check(f"s3.get_bucket_versioning:{self.bucket}", "s3", self._versioning)
            self.check(f"s3.get_object_lock_configuration:{self.bucket}", "s3", self._object_lock)
        self.check("athena.list_work_groups", "athena",
                   lambda: {"work_groups": [w["Name"] for w in self.client("athena")
                                            .list_work_groups(MaxResults=5).get("WorkGroups", [])]})
        self.check("lambda.list_functions", "lambda",
                   lambda: {"functions_seen": len(self.client("lambda").list_functions(MaxItems=1)
                                                  .get("Functions", []))})
        if self.log_group:
            self.check(f"logs.put_log_events:{self.log_group}", "logs", self._put_log_events)
        self.check("stepfunctions.list_state_machines", "stepfunctions",
                   lambda: {"state_machines_seen": len(self.client("stepfunctions")
                                                       .list_state_machines(maxResults=1).get("stateMachines", []))})
        self.check("bedrock-agentcore-control.list_agent_runtimes", "bedrock-agentcore-control",
                   lambda: {"runtimes_seen": len(self.client("bedrock-agentcore-control")
                                                 .list_agent_runtimes(maxResults=1).get("agentRuntimes", []))})

        def budgets() -> dict[str, Any]:
            if not ident.get("account"):
                raise RuntimeError("account id unknown (sts failed)")
            r = self.client("budgets").describe_budgets(AccountId=ident["account"], MaxResults=5)
            return {"budgets": [b.get("BudgetName") for b in r.get("Budgets", [])]}
        self.check("budgets.describe_budgets", "budgets", budgets)

        throttles = [e for e in self.events if e["name"] == "treehouse.retry"]
        note = (f"{len(throttles)} retryable error(s) during {self.calls} probe Converse call(s)"
                f" ({', '.join(sorted({str(e.get('error_code')) for e in throttles})) or 'none'}). "
                "The adapter runs at concurrency 2 with botocore total_max_attempts=1 and its own jittered loop.")
        summary = {s: sum(1 for c in self.checks if c.status == s)
                   for s in ("ok", "denied", "unavailable", "error", "skipped_budget")}
        return AwsCapabilities(
            generated_at=datetime.now(UTC).isoformat(timespec="seconds"), probe_version=PROBE_VERSION,
            region=self.region, execution=execution, checks=self.checks, models=models,
            foundation_models=sorted(fms), inference_profiles=sorted(profiles), quotas=quotas,
            throttle_note=note, invocation_logging=logging_cfg,
            spend=ProbeSpend(cap_usd=self.cap_usd, per_call_cap_usd=self.per_call_cap_usd, max_tokens=self.max_tokens,
                             reserved_usd=round(self.reserved_usd, 6), committed_usd=round(self.committed_usd, 6),
                             calls=self.calls, price_table=self.ceiling.version),
            summary=summary,
        )

    def _probe_model(self, entry: ModelEntry, fms: dict[str, dict[str, Any]], profiles: set[str], fm_ok: bool,
                     pr_ok: bool) -> ProbeModel:
        fm = fms.get(entry.model_id)
        listed = (fm is not None) if fm_ok else None
        image_input = ("IMAGE" in (fm.get("inputModalities") or [])) if fm else None
        candidates = [p for p in [entry.inference_profile, *entry.alt_profiles] if p] or [entry.model_id]
        results: dict[str, CheckStatus | None] = {"user_turn": None, "tool_result": None}
        used: str | None = None
        for cand in candidates:
            c = self.converse(entry, "user_turn", cand)
            results["user_turn"] = c.status
            if c.status == "ok":
                used = cand
                break
            if c.status not in ("unavailable",):
                break  # denied / error / skipped_budget: another profile will not help
        if used is not None:
            results["tool_result"] = self.converse(entry, "tool_result", used).status
        elif results["user_turn"] == "skipped_budget":
            results["tool_result"] = self._record(f"bedrock.converse:{entry.key}:tool_result", "bedrock-runtime",
                                                  "skipped_budget", "probe cap reached").status
        rec = ("tool_result" if results["tool_result"] == "ok" else "user_turn" if results["user_turn"] == "ok"
               else None)
        return ProbeModel(key=entry.key, model_id=entry.model_id, inference_profile=entry.inference_profile,
                          listed=listed, profile_listed=(entry.inference_profile in profiles) if pr_ok else None,
                          image_input=image_input, user_turn_image=results["user_turn"],
                          tool_result_image=results["tool_result"], invoke_id_used=used,
                          recommended_image_delivery=rec)

    def _list_models(self, out: dict[str, dict[str, Any]]) -> dict[str, Any]:
        r = self.client("bedrock").list_foundation_models()
        for m in r.get("modelSummaries", []):
            out[m["modelId"]] = {"inputModalities": m.get("inputModalities", []),
                                 "inferenceTypesSupported": m.get("inferenceTypesSupported", [])}
        return {"count": len(out)}

    def _list_profiles(self, out: set[str]) -> dict[str, Any]:
        c = self.client("bedrock")
        token = None
        for _ in range(10):
            r = c.list_inference_profiles(**({"nextToken": token} if token else {}))
            out.update(p["inferenceProfileId"] for p in r.get("inferenceProfileSummaries", []))
            token = r.get("nextToken")
            if not token:
                break
        return {"count": len(out)}

    def _quotas(self, out: list[dict[str, Any]]) -> dict[str, Any]:
        c = self.client("service-quotas")
        words = [w.lower() for e in self.registry.models for w in (e.key.replace("-", " "),)]
        token, seen = None, 0
        for _ in range(10):
            r = c.list_service_quotas(ServiceCode="bedrock", MaxResults=100, **({"NextToken": token} if token else {}))
            for q in r.get("Quotas", []):
                seen += 1
                name = q.get("QuotaName", "")
                low = name.lower().replace("-", " ").replace(".", " ")
                if any(all(t in low for t in w.split()) for w in words):
                    out.append({"name": name, "value": q.get("Value"), "adjustable": q.get("Adjustable")})
            token = r.get("NextToken")
            if not token:
                break
        return {"quotas_seen": seen, "matched": len(out)}

    def _invocation_logging(self, out: dict[str, Any]) -> dict[str, Any]:
        r = self.client("bedrock").get_model_invocation_logging_configuration()
        cfg = r.get("loggingConfig") or {}
        out.update(enabled=bool(cfg), image_data_delivery=bool(cfg.get("imageDataDeliveryEnabled")),
                   text_data_delivery=bool(cfg.get("textDataDeliveryEnabled")),
                   destinations=[k for k in ("cloudWatchConfig", "s3Config") if k in cfg])
        out["policy"] = ("image payloads ARE logged: Vantor (CC-BY-NC) pixels would be copied to the log "
                         "destination; keep it private or disable image delivery" if out["image_data_delivery"]
                         else "image payloads are not logged")
        return {"_detail": out["policy"]}

    def _versioning(self) -> dict[str, Any]:
        r = self.client("s3").get_bucket_versioning(Bucket=self.bucket)
        return {"versioning": r.get("Status", "Disabled"), "mfa_delete": r.get("MFADelete")}

    def _object_lock(self) -> dict[str, Any]:
        try:
            r = self.client("s3").get_object_lock_configuration(Bucket=self.bucket)
        except Exception as e:
            if error_code(e) == "ObjectLockConfigurationNotFoundError":
                return {"object_lock": "Disabled"}
            raise
        cfg = r.get("ObjectLockConfiguration") or {}
        return {"object_lock": cfg.get("ObjectLockEnabled", "Disabled"), "rule": cfg.get("Rule")}

    def _put_log_events(self) -> dict[str, Any]:
        c = self.client("logs")
        for fn, kw in ((c.create_log_group, {"logGroupName": self.log_group}),
                       (c.create_log_stream, {"logGroupName": self.log_group, "logStreamName": "probe"})):
            try:
                fn(**kw)
            except Exception as e:
                if error_code(e) != "ResourceAlreadyExistsException":
                    raise
        ts = int(datetime.now(UTC).timestamp() * 1000)
        c.put_log_events(logGroupName=self.log_group, logStreamName="probe",
                         logEvents=[{"timestamp": ts, "message": "treehouse probe"}])
        return {"log_group": self.log_group}
