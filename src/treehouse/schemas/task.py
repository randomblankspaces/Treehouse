"""Task Card (SYSTEM-DESIGN §A2). A region enters only through the AOI, data URIs and keys."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import AwareDatetime, model_validator

from treehouse.canon import sha256_json
from treehouse.schemas.base import Frozen
from treehouse.schemas.config import Budget
from treehouse.schemas.geo import BBox, Polygon

ClaimStatus = Literal["present", "absent", "intact", "damaged", "destroyed", "cannot_assess"]


class DataSource(Frozen):
    source_id: str
    kind: Literal["stac", "imagery", "embeddings", "vector"]
    access: Literal["static_catalog", "s3_listing", "synthetic", "recorded"]
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
    status: Literal["present", "pending_fetch", "none"]

    @model_validator(mode="after")
    def _rules(self) -> Keying:
        if self.mode == "unkeyed":
            if self.status != "none" or self.key_path or self.key_source:
                raise ValueError("an unkeyed step has status 'none' and no key_source or key_path")
        else:
            if self.status == "none":
                raise ValueError("a keyed step needs status 'present' or 'pending_fetch'")
            missing = [f for f in ("key_source", "key_path", "license", "match_rule") if getattr(self, f) is None]
            if missing:
                raise ValueError(f"a keyed step needs {', '.join(missing)}")
            if self.status == "present" and not self.version_hash:
                raise ValueError("a present key needs version_hash")
        return self


class Step(Frozen):
    step_id: str
    question_id: Literal["exists", "damaged"]
    statuses_allowed: list[ClaimStatus]
    keying: Keying


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
    min_N_h: int = 4
    n_total: int
    census_if_N_le: int = 60
    seed: int
    controls: Controls = Controls()
    unreported_frame: dict[str, str] | None = None  # W10


class BlindProtocol(Frozen):
    hide: list[str]
    shuffle: Literal[True] = True
    seal_before_reveal: Literal[True] = True
    relabels: int = 5


class GoldPlan(Frozen):
    n_gold: int
    rubric: str
    labeller: str
    date: date
    seed_file: str
    blind_protocol: BlindProtocol


class Event(Frozen):
    date: date
    footprint_ref: str | None = None


class Windows(Frozen):
    max_side_m: float
    max_out_px: int
    max_bytes_per_run: int


class Thresholds(Frozen):
    rely_lo: float


class TaskCard(Frozen):
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

    @model_validator(mode="after")
    def _rules(self) -> TaskCard:
        if self.synthetic and not self.synthetic_notice:
            raise ValueError("a synthetic card needs synthetic_notice")
        if any(s.keying.mode != "unkeyed" for s in self.steps) and not self.forbidden_sources:
            raise ValueError("forbidden_sources must be non-empty when any step is keyed")
        if self.time_window[0] > self.time_window[1]:
            raise ValueError("time_window start must not be after its end")
        if len({s.step_id for s in self.steps}) != len(self.steps):
            raise ValueError("step ids must be unique")
        return self

    def card_hash(self) -> str:
        return sha256_json(self.model_dump(mode="json"))

    def ref(self) -> str:
        return f"{self.id}@{self.card_hash()}"

