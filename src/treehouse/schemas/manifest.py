"""Run manifest: what ran, with which inputs, and which backends actually ran."""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, model_validator

from treehouse.canon import sha256_json
from treehouse.schemas.base import Frozen
from treehouse.schemas.config import RunConfig
from treehouse.schemas.geo import BBox
from treehouse.schemas.trace import ChainHead

BackendSlot = Literal["store", "key_isolation", "model.worker", "model.verifier", "tracer"]


class BackendResolution(Frozen):
    requested: str
    ran: str
    degraded_from: str | None = None
    reason: str | None = None
    evidence: list[str] = []
    statement: str | None = None

    @model_validator(mode="after")
    def _rules(self) -> BackendResolution:
        if self.ran != self.requested and not (self.degraded_from and self.reason):
            raise ValueError("a backend that differs from the request needs degraded_from and reason")
        if self.ran in {"s3", "iam"} and not self.evidence:
            raise ValueError(f"ran={self.ran} requires read-back or denial evidence")
        return self


class TrialHead(Frozen):
    trial_id: str
    role: str
    trace_file: str
    head: ChainHead
    claims_sha256: str
    stop: Literal["completed", "max_turns", "budget", "error"]


class DataPointer(Frozen):
    scene_id: str
    href: str | None = None
    etag: str | None = None
    bbox: BBox
    datetime: AwareDatetime
    license: str


class TaskRef(Frozen):
    id: str
    version: str
    hash: str


class Versions(Frozen):
    treehouse: str
    git_sha: str | None = None
    uv_lock_sha256: str | None = None
    python: str
    harness: str
    prompts_sha: str | None = None
    semconv_ref: str | None = None
    price_table: str | None = None
    registry: str | None = None


class Cassettes(Frozen):
    model_sha: str | None = None
    tool_sha: str | None = None


class Manifest(Frozen):
    """``license_floor`` is the most restrictive input licence; ``license_obligations`` lists every input
    licence that carries an obligation (attribution, share-alike, non-commercial), so none is lost.

    ``manifest_hash`` covers everything, including the volatile ``created_at``, ``versions.git_sha``,
    ``versions.python`` and ``versions.uv_lock_sha256``. Golden tests compare ``canon.stable_view`` of a
    record, which drops those fields (and ``manifest_ref`` / ``code_sha`` wherever they appear)."""

    schema_version: Literal["treehouse.manifest/1"] = "treehouse.manifest/1"
    run_id: str
    created_at: AwareDatetime
    task: TaskRef
    config_hash: str
    config: RunConfig
    mode: Literal["fake", "replay", "record", "live"]
    backends_resolved: dict[BackendSlot, BackendResolution]
    versions: Versions
    trials: list[TrialHead]
    cassettes: Cassettes = Cassettes()
    data_pointers: list[DataPointer] = []
    files: dict[str, str] = {}  # run-relative path -> sha256 of every sealed file except manifest.json/SEALED
    key_isolation_statement: str
    license_floor: str
    nc_notice: str | None = None
    license_obligations: list[str] = []
    synthetic_data: bool
    prev_manifest_hash: str | None = None
    manifest_hash: str

    def compute_hash(self) -> str:
        """sha256 of the canonical manifest without its own ``manifest_hash``."""
        return sha256_json(self.model_dump(mode="json", exclude={"manifest_hash"}))
