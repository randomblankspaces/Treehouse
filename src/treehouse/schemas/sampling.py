"""Sample designs, gold draws and blind items."""

from __future__ import annotations

from typing import Literal

from treehouse.schemas.base import Frozen


class SampledUnit(Frozen):
    unit_id: str
    kind: Literal["claim", "control_pos", "control_neg", "placebo", "retest", "unreported"]  # sealed
    ref: str  # sealed; never shown to the verifier
    stratum: str
    pi: float
    order: int


class SampleDesign(Frozen):
    design_id: str
    seed: int
    rng: Literal["numpy.PCG64"] = "numpy.PCG64"
    algorithm: Literal["strat-srswor-v1"] = "strat-srswor-v1"
    frame_hash: str
    N_h: dict[str, int]
    n_h: dict[str, int]
    units: list[SampledUnit]
    created_seq: int


class GoldDraw(Frozen):
    draw_id: str
    design_id: str
    seed: int
    n_gold: int
    unit_ids: list[str]
    pi2: dict[str, float]
    committed_ref: str
    committed_seq: int


class BlindItem(Frozen):
    """Everything the verifier or human labeller sees. Nothing else, ever."""

    unit_id: str
    lon: float
    lat: float
    object_definition: str
    question_id: Literal["exists", "damaged"]
    scene_ids: list[str]
