"""``treehouse.aws-capabilities/v1``: the output of ``scripts/aws_probe.py`` (K1)."""

from __future__ import annotations

from typing import Any, Literal

from treehouse.schemas.base import Frozen

# invalid_request: a ValidationException that is NOT about the model id / profile / on-demand throughput,
# i.e. our request shape or parameters; the detail says why (M9)
CheckStatus = Literal["ok", "denied", "unavailable", "invalid_request", "error", "skipped_budget"]


class ProbeCheck(Frozen):
    name: str  # e.g. "sts.get_caller_identity", "bedrock.converse:nova-pro:user_turn"
    service: str
    status: CheckStatus
    detail: str = ""
    error_code: str | None = None
    data: dict[str, Any] = {}


class ProbeModel(Frozen):
    key: str
    model_id: str
    inference_profile: str | None
    listed: bool | None  # model_id in ListFoundationModels (None if the list call failed)
    profile_listed: bool | None
    image_input: bool | None  # "IMAGE" in inputModalities
    user_turn_image: CheckStatus | None
    tool_result_image: CheckStatus | None
    invoke_id_used: str | None = None
    recommended_image_delivery: Literal["tool_result", "user_turn"] | None = None
    # listed model ids / profile ids that share the registry id's stem (e.g. dated -v1:0 suffixes) (M10)
    near_matches: list[str] = []


class ProbeSpend(Frozen):
    cap_usd: float
    per_call_cap_usd: float
    max_tokens: int
    reserved_usd: float
    committed_usd: float
    calls: int
    estimated: Literal[True] = True
    price_table: str


class AwsCapabilities(Frozen):
    schema_version: Literal["treehouse.aws-capabilities/v1"] = "treehouse.aws-capabilities/v1"
    generated_at: str
    probe_version: str
    region: str
    execution: dict[str, Any]  # locus, identity_arn, account, python, boto3
    checks: list[ProbeCheck]
    models: list[ProbeModel]
    foundation_models: list[str] = []
    inference_profiles: list[str] = []
    quotas: list[dict[str, Any]] = []
    throttle_note: str = ""
    invocation_logging: dict[str, Any] = {}
    spend: ProbeSpend
    summary: dict[str, int]
