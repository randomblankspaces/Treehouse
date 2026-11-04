"""Random gold subsample G from the phase-1 sample S (A5): SRSWOR over ALL sampled claim units, including
the ones the verifier abstains on. It takes no verdicts, by construction."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

import numpy as np


def draw_gold(design: Mapping, n_gold: int, *, seed: int, committed_ref: str, committed_seq: int) -> dict:
    """``design`` is a SampleDesign dump. Returns the fields of ``schemas.sampling.GoldDraw``."""
    S = sorted(u["unit_id"] for u in design["units"] if u["kind"] == "claim")
    if not 0 < n_gold <= len(S):
        raise ValueError(f"n_gold must be in 1..{len(S)}")
    keys = np.random.PCG64(seed).random_raw(len(S))
    ids = [S[i] for i in np.argsort(keys, kind="stable")[:n_gold]]
    draw_id = "gd-" + hashlib.sha256(f"{design['design_id']}|{seed}|{n_gold}".encode()).hexdigest()[:16]
    return {"draw_id": draw_id, "design_id": design["design_id"], "seed": seed, "n_gold": n_gold,
            "unit_ids": ids, "pi2": {u: n_gold / len(S) for u in ids}, "committed_ref": committed_ref,
            "committed_seq": committed_seq}
