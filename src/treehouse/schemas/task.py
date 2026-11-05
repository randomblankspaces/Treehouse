"""Task Card (SYSTEM-DESIGN §A2). A region enters only through the AOI, data URIs and keys."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from treehouse.canon import sha256_json
from treehouse.schemas.base import Frozen
from treehouse.schemas.config import Budget
from treehouse.schemas.geo import BBox, Polygon

ClaimStatus = Literal["present", "absent", "intact", "damaged", "destroyed", "cannot_assess"]
STATUSES_FOR = {
    "exists": {"present", "absent", "cannot_assess"},
    "damaged": {"intact", "damaged", "destroyed", "cannot_assess"},
}


class DataSource(Frozen):
    source_id: str
    kind: Literal["stac", "imagery", "embeddings", "vector"]
    access: Literal["static_catalog", "s3_listing", "synthetic", "recorded", "real"]
    fixture_path: str | None = None
    item_ids: list[str] = []
    etags: dict[str, str] = {}
    license: str  # SPDX id or LicenseRef-*
    status: Literal["pinned", "unpinned", "pending_fixture"]


class ClassSpec(Frozen):
    min_size_m: float
    max_effective_gsd_for_existence_m: float
    max_effective_gsd_for_status_m: float
    match_tolerance_m: float
    key_geometry: Literal["point", "line", "polygon"]


class MatchRule(Frozen):
    tolerance_m: dict[str, float]
    one_to_one: Literal[True] = True


class Keying(Frozen):
    mode: Literal["keyed", "partly_keyed", "unkeyed"]
    key_source: str | None = None
    key_path: str | None = None  # repo-relative; must sit under keys/
    version_hash: str | None = None
    license: str | None = None
    reference_quality: Literal["complete", "incomplete", "synthetic"] | None = None
    completeness_caveat: str | None = None
    key_coverage_mask: Polygon | None = None
    match_rule: MatchRule | None = None
    status: Literal["present", "pending_fetch", "pending_generation", "none"]

    @model_validator(mode="after")
    def _rules(self) -> Keying:
        if self.mode == "unkeyed":
            if self.status != "none" or self.key_path or self.key_source:
                raise ValueError("an unkeyed step has status 'none' and no key_source or key_path")
        else:
            if self.status == "none":
                raise ValueError("a keyed step needs status 'present', 'pending_fetch' or 'pending_generation'")
            missing = [f for f in ("key_source", "key_path", "license", "match_rule") if getattr(self, f) is None]
            if missing:
                raise ValueError(f"a keyed step needs {', '.join(missing)}")
            if self.status == "present" and not self.version_hash:
                raise ValueError("a present key needs version_hash")
            if self.mode == "partly_keyed" and not self.completeness_caveat:
                raise ValueError("a partly_keyed step needs completeness_caveat")
        return self


class Step(Frozen):
    step_id: str
    question_id: Literal["exists", "damaged"]
    statuses_allowed: list[ClaimStatus]
    keying: Keying

    @model_validator(mode="after")
    def _statuses(self) -> Step:
        bad = sorted(set(self.statuses_allowed) - STATUSES_FOR[self.question_id])
        if bad or not self.statuses_allowed:
            raise ValueError(f"statuses_allowed: {bad or 'empty'} not allowed for question {self.question_id}")
        return self


class ForbiddenSource(Frozen):
    kind: Literal["host", "url_prefix", "s3_prefix", "dataset_id", "tool", "path"]
    pattern: str


class NoticeItem(Frozen):
    id: str
    kind: Literal["mentions_any", "plans_tool", "declares_limit"]
    terms: list[str] = []
    tool: str | None = None
    weight: float = 1.0


class Controls(Frozen):
    keyed_pos: int = 0
    keyed_neg: int = 0
    placebo_pairs: int = 0
    retest_pairs: int = 0


class SamplingPlan(Frozen):
    strata_keys: list[Literal["class", "conf_tercile", "cloud_class"]]
    min_N_h: int = Field(default=4, ge=1)
    n_total: int = Field(ge=1)
    census_if_N_le: int = Field(default=60, ge=0)
    seed: int
    controls: Controls = Controls()
    unreported_frame: dict[str, str] | None = None  # W10

    @field_validator("strata_keys")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("strata keys must be unique")
        return v


class BlindProtocol(Frozen):
    hide: list[str]
    shuffle: Literal[True] = True
    seal_before_reveal: Literal[True] = True
    relabels: int = 5


class GoldPlan(Frozen):
    n_gold: int = Field(ge=1)
    rubric: str
    labeller: str
    date: date
    seed_file: str
    blind_protocol: BlindProtocol


class Event(Frozen):
    date: date
    footprint_ref: str | None = None


class Windows(Frozen):
    max_side_m: float = Field(gt=0)
    max_out_px: int = Field(ge=1)
    max_bytes_per_run: int = Field(ge=0)


class Thresholds(Frozen):
    rely_lo: float


class TaskCard(Frozen):
    """A task card.

    ``synthetic`` means *synthetic task* (written by the team, not a partner's), which requires
    ``synthetic_notice``. It does not decide the per-number ``synthetic`` flag: that comes from the data
    a number was computed on (a source with ``access: synthetic``, a synthetic key or labeller, or a
    ``WindowResult.synthetic``), so a real-data run of a synthetic task is not chipped SYNTHETIC.

    The worker sees ``goal``, the AOI, the time window and the tools only. ``known_limits``,
    ``must_notice``, keys and plans are grader-side and never enter a worker prompt. ``as_of`` is
    normalised to UTC so the card hash does not depend on the offset it was written with.
    """

    schema_version: Literal["treehouse.task/1"] = "treehouse.task/1"
    id: str
    version: str
    title: str
    family: str
    synthetic: bool
    synthetic_notice: str | None = None
    goal: str
    aoi: Polygon
    smoke_aoi: BBox | None = None
    time_window: tuple[date, date]
    as_of: AwareDatetime
    event: Event | None = None
    data_allowlist: list[DataSource]
    tools_allowed: list[str]
    needs_vision: bool
    classes: dict[str, ClassSpec]
    windows: Windows
    steps: list[Step]
    forbidden_sources: list[ForbiddenSource]  # required; [] only if no step is keyed
    must_notice: list[NoticeItem] = []
    known_limits: list[str] = []
    sampling_plan: SamplingPlan
    gold_plan: GoldPlan | None = None
    thresholds: Thresholds
    budget: Budget

    @field_validator("as_of")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return v.astimezone(UTC)

    @model_validator(mode="after")
    def _rules(self) -> TaskCard:
        # Card-level messages start with their field path (pydantic gives model-level errors no loc).
        if self.synthetic and not self.synthetic_notice:
            raise ValueError("synthetic_notice: a synthetic card needs synthetic_notice")
        if any(s.keying.mode != "unkeyed" for s in self.steps) and not self.forbidden_sources:
            raise ValueError("forbidden_sources: must be non-empty when any step is keyed")
        if self.time_window[0] > self.time_window[1]:
            raise ValueError("time_window: start must not be after its end")
        if self.as_of.date() < self.time_window[0]:
            raise ValueError("as_of: must not precede the time_window start")
        ids = [s.step_id for s in self.steps]
        if len(set(ids)) != len(ids):
            raise ValueError("steps: step ids must be unique")
        for i, s in enumerate(self.steps):
            mr = s.keying.match_rule
            unknown = sorted(set(mr.tolerance_m) - set(self.classes)) if mr else []
            if unknown:
                raise ValueError(f"steps.{i}.keying.match_rule.tolerance_m: unknown classes {unknown}")
        return self

    def card_hash(self) -> str:
        return sha256_json(self.model_dump(mode="json"))

    def ref(self) -> str:
        return f"{self.id}@{self.card_hash()}"

