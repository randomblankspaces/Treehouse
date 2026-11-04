"""Blind verifier batches (V2): whitelist projection, keyed-hash ids, seeded shuffle."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping, Sequence

import numpy as np

BLIND_FIELDS = ("lon", "lat", "object_definition", "question_id", "scene_ids")


def assemble_verifier_batch(claims: Sequence[Mapping], controls: Sequence[Mapping], *, seed: int,
                            hmac_key: bytes) -> tuple[list[dict], dict[str, str]]:
    """Claims and controls go through the same projection, so the verifier cannot tell them apart. Each
    item keeps only ``BLIND_FIELDS`` plus an HMAC unit id; label, confidence, reason and worker id never
    pass. Returns (BlindItem dicts in shuffled order, sealed map blind_id -> unit_id)."""
    items, sealed = [], {}
    for u in [*claims, *controls]:
        bid = "b-" + hmac.new(hmac_key, u["unit_id"].encode(), hashlib.sha256).hexdigest()[:16]
        if bid in sealed:
            raise ValueError(f"duplicate unit_id {u['unit_id']!r}")
        sealed[bid] = u["unit_id"]
        items.append({"unit_id": bid, **{k: u[k] for k in BLIND_FIELDS}})
    items.sort(key=lambda x: x["unit_id"])  # order independent of input order before the shuffle
    perm = np.argsort(np.random.PCG64(seed).random_raw(len(items)), kind="stable")
    return [items[i] for i in perm], sealed
