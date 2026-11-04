"""Strict, bounded receipts. These observations are not AWS-signed attestations."""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class JudgeConfig(Record):
    schema_version: Literal["treehouse.judge-config/1"]
    region: str = Field(min_length=1, max_length=64)
    runtime_arn: str = Field(pattern=r"^arn:aws[a-z-]*:bedrock-agentcore:[a-z0-9-]+:\d{12}:runtime/.+", max_length=2048)
    gateway_url: str = Field(max_length=2048)
    gateway_id: str = Field(min_length=1, max_length=256)
    knowledge_base_id: str = Field(min_length=1, max_length=256)
    model_id: str = Field(min_length=1, max_length=2048)
    evidence_dir: str | None = None

    @field_validator("gateway_url")
    @classmethod
    def https_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if re.search(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|(?i:bearer)\s+", value):
            raise ValueError("citation cannot contain credential strings")
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.fragment:
            raise ValueError("gateway_url must be an HTTPS endpoint without credentials or fragment")
        return value


class Citation(Record):
    uri: str = Field(min_length=1, max_length=4096)
    title: str | None = Field(default=None, max_length=1024)
    quote: str | None = Field(default=None, max_length=12000)

    @field_validator("uri")
    @classmethod
    def source_uri(cls, value: str) -> str:
        parts = urlsplit(value)
        if re.search(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|(?i:bearer)\s+", value):
            raise ValueError("citation cannot contain credential strings")
        if parts.scheme not in {"https", "http", "s3"} or not parts.hostname:
            raise ValueError("citation needs an HTTP(S) host or an S3 bucket and key")
        if parts.username or parts.password or any(c.isspace() for c in parts.netloc):
            raise ValueError("citation cannot contain credentials or an invalid host")
        if parts.scheme == "s3" and (not parts.path.strip("/") or parts.port):
            raise ValueError("S3 citation needs a bucket and nonempty object key")
        if parts.query:
            from urllib.parse import parse_qsl

            for key, _ in parse_qsl(parts.query):
                if re.search(r"(?i)(credential|signature|token|password|secret|access.?key|api.?key|authorization)", key):
                    raise ValueError("citation cannot expose signed or credential-bearing query parameters")
        return value


def tool_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,256}", value):
        raise ValueError("tool names must be nonempty identifiers without whitespace")
    return value


class ToolCall(Record):
    name: str = Field(min_length=1, max_length=256)
    arguments: dict[str, Any]
    result: Any
    is_error: bool
    request_id: str | None = Field(default=None, max_length=256)

    _name = field_validator("name")(tool_name)


class Receipt(Record):
    schema_version: Literal["treehouse.judge-invocation/1"]
    answer: str = Field(max_length=100000)
    citations: list[Citation] = Field(max_length=50)
    tool_calls: list[ToolCall] = Field(max_length=100)
    gateway_tools: list[str] = Field(max_length=100)
    knowledge_base_id: str = Field(min_length=1, max_length=256)
    gateway_id: str = Field(min_length=1, max_length=256)
    session_id: str = Field(min_length=1, max_length=256)
    model_id: str = Field(min_length=1, max_length=2048)
    runtime_arn: str = Field(min_length=1, max_length=2048)
    request_id: str = Field(min_length=1, max_length=256)
    captured_at: datetime
    source: Literal["live", "recorded", "sample"]

    @field_validator("gateway_tools")
    @classmethod
    def catalog_names(cls, names: list[str]) -> list[str]:
        return [tool_name(name) for name in names]

    @field_validator("captured_at", mode="before")
    @classmethod
    def timestamp(cls, value: Any) -> datetime:
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise ValueError("captured_at needs a timezone")
        if value > datetime.now(UTC).replace(microsecond=0) and (value - datetime.now(UTC)).total_seconds() > 60:
            raise ValueError("receipt timestamp is in the future")
        return value

    def match(self, config: JudgeConfig) -> None:
        for key in ("knowledge_base_id", "gateway_id", "runtime_arn", "model_id"):
            if getattr(self, key) != getattr(config, key):
                raise ValueError(f"receipt {key} does not match server configuration")

    def proofs(self) -> list[dict[str, str]]:
        catalog = {name for name in self.gateway_tools if name.strip()}
        successful = any(
            not call.is_error and call.name in catalog and call.result not in (None, "", {}, [])
            for call in self.tool_calls
        )
        criteria = [
            ("Know Your Stuff", bool(self.answer.strip() and any(c.quote and c.quote.strip() for c in self.citations)),
             f"{len(self.citations)} document citation(s) returned."),
            ("Gateway Builder", len(catalog) >= 3 and successful,
             f"{len(catalog)} catalog tools; {sum(not c.is_error for c in self.tool_calls)} successful call(s) reported."),
            ("Ship It", bool(self.answer.strip() and self.request_id.strip()),
             "Runtime response and invocation request ID received."),
        ]
        return [{"name": name, "state": ("unverified" if self.source == "sample" else
                 ("observed" if self.source == "live" else "recorded")) if ok else "missing",
                 "detail": detail if ok else "Required evidence is missing. " + detail}
                for name, ok, detail in criteria]
