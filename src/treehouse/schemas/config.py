"""Run, evaluation and trust configuration records."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_serializer, model_validator

from treehouse.schemas.base import Frozen


class InferenceParams(Frozen):
    max_tokens: int
    temperature: float | None = None
    top_p: float | None = None
    seed: int | None = None


class RoleConfig(Frozen):
    provider: Literal["fake", "replay", "bedrock", "openai_compat"]
    model_key: str
    family: str
    params: InferenceParams
    tools: list[str] = []
    script: str | None = None
    cassette: str | None = None


class Budget(Frozen):
    """Per-run limits; ``None`` means no limit on that axis. ``enabled=False`` disables all limits."""

    enabled: bool = True
    usd: float | None = None
    tool_calls: int | None = None
    bytes: int | None = None
    wall_s: float | None = None
    tokens: int | None = None


class Backends(Frozen):
    store: Literal["local", "s3"] = "local"
    key_isolation: Literal["local", "iam"] = "local"
    tracer: list[Literal["jsonl", "otlp", "cwlogs"]] = ["jsonl"]
    tool_locus: Literal["inproc"] = "inproc"
    allow_degrade: bool = True


class RunConfig(Frozen):
    """One run of a task. The ``needs_vision`` registry check lands with the model registry (P6)."""

    schema_version: Literal["treehouse.runconfig/1"] = "treehouse.runconfig/1"
    task_ref: str  # "<id>@sha256:<hex>"
    mode: Literal["fake", "replay", "record", "live"]
    worker: RoleConfig
    verifier: RoleConfig | None = None
    summarizer: RoleConfig | None = None
    harness: Literal["plain_loop", "strands"] = "plain_loop"
    # Omit the unset field to preserve existing sealed config hashes.
    servers: str | None = Field(default=None, exclude_if=lambda value: value is None)
    max_turns: int = 40
    tool_executor: Literal["sequential"] = "sequential"
    trials: int = 1
    seed: int
    clock: Literal["wall", "logical"] = "wall"
    budget: Budget = Budget()
    backends: Backends = Backends()
    allow_same_family: bool = False
    tool_mode: Literal["live", "verify"] = "live"
    thinking: bool = False

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        data = handler(self)
        if not self.thinking:
            data.pop("thinking", None)  # Preserve existing config hashes and replay traces.
        return data

    @model_validator(mode="after")
    def _rules(self) -> RunConfig:
        if "@sha256:" not in self.task_ref:
            raise ValueError("task_ref must be '<id>@sha256:<hex>'")
        if self.verifier and self.verifier.family == self.worker.family and not self.allow_same_family:
            raise ValueError("verifier must be from a different model family unless allow_same_family")
        return self


class VerifierSpec(Frozen):
    mode: Literal["recorded", "agent"]
    config: dict[str, Any] = {}


class GoldRef(Frozen):
    labels_path: str
    draw_ref: str


class EvalSpec(Frozen):
    schema_version: Literal["treehouse.evalspec/1"] = "treehouse.evalspec/1"
    run_ref: str
    scorers: dict[str, str]
    key_version: str | None = None
    verifier: VerifierSpec
    gold: GoldRef | None = None
    trust_config_hash: str
    estimator_version: str
    seed: int


class TrustConfig(Frozen):
    """Pre-registered trust-engine constants (copied verbatim to ``prereg/trust-config.yaml``)."""

    level: float = 0.90
    B: int = 2000
    pseudo_weight: float = 0.5
    lam_fixed_below: int = 50
    j_min: float = 0.2
    tau_floor: float = 0.5
    kappa0: float = 10
    min_runs_mle: int = 3
    g_min_label: int = 5
    max_abstention_for_rely: float = 0.3
    placebo_far_max: float = 0.10
    anecdotal_below: int = 10
