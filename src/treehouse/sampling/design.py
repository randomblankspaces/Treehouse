"""Stratified SRSWOR sample designs (``strat-srswor-v1``)."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence

import numpy as np

ALGORITHM = "strat-srswor-v1"


def _sha(obj) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def assign_strata(units: Sequence[Mapping], *, keys: Sequence[str], min_N_h: int = 4,
                  collapse_order: Sequence[str] = ("cloud_class", "conf_tercile")) -> list[str]:
    """Stratum label per unit. While any stratum has fewer than ``min_N_h`` units, drop the next key in
    ``collapse_order``; if that is not enough, everything falls into one stratum ``all``."""
    keys = list(keys)
    drop = [k for k in collapse_order if k in keys]
    while True:
        labels = ["|".join(f"{k}={u[k]}" for k in keys) or "all" for u in units]
        if min(Counter(labels).values(), default=min_N_h) >= min_N_h:
            return labels
        if not drop:
            return ["all"] * len(units)
        keys.remove(drop.pop(0))


def allocate(N_h: Mapping[str, int], n_total: int, *, min_per_stratum: int = 2,
             census_if_N_le: int = 60) -> dict[str, int]:
    """Census when the frame is small; else proportional allocation (largest remainder), at least
    ``min_per_stratum`` per stratum and never more than N_h."""
    if sum(N_h.values()) <= census_if_N_le or n_total >= sum(N_h.values()):
        return dict(N_h)
    N = sum(N_h.values())
    n = {h: min(N_h[h], max(min_per_stratum, int(n_total * N_h[h] / N))) for h in N_h}
    rem = sorted(N_h, key=lambda h: (-(n_total * N_h[h] / N - int(n_total * N_h[h] / N)), h))
    while sum(n.values()) < n_total:
        open_ = [h for h in rem if n[h] < N_h[h]]
        if not open_:
            break
        for h in open_:
            if sum(n.values()) >= n_total:
                break
            n[h] += 1
    return n


def srswor_indices(strata: Sequence[str], n_h: Mapping[str, int], seed: int) -> np.ndarray:
    """Indices of the sampled units: in each stratum the n_h smallest PCG64 ``random_raw`` keys. Returned in
    key order, which is the unit ``order``."""
    keys = np.random.PCG64(seed).random_raw(len(strata))
    strata = np.asarray(strata)
    picked = [i for h, k in n_h.items() for i in np.flatnonzero(strata == h)[np.argsort(keys[strata == h])[:k]]]
    picked = np.array(picked, dtype=int)
    return picked[np.argsort(keys[picked], kind="stable")]


def stratified_sample(frame: Sequence[Mapping], n_h: Mapping[str, int], *, seed: int,
                      created_seq: int = 0) -> dict:
    """``frame`` rows carry unit_id, kind, ref and stratum (frame order is normalised by unit_id).
    Returns the fields of ``schemas.sampling.SampleDesign``; pi = n_h/N_h."""
    frame = sorted(frame, key=lambda u: u["unit_id"])
    strata = [u["stratum"] for u in frame]
    N_h = dict(Counter(strata))
    if set(n_h) != set(N_h) or any(not 0 < n_h[h] <= N_h[h] for h in N_h):
        raise ValueError("n_h must give 1..N_h units for every stratum of the frame")
    frame_hash = _sha([[u["unit_id"], u["kind"], u["ref"], u["stratum"]] for u in frame])
    units = [{"unit_id": frame[i]["unit_id"], "kind": frame[i]["kind"], "ref": frame[i]["ref"],
              "stratum": frame[i]["stratum"], "pi": n_h[frame[i]["stratum"]] / N_h[frame[i]["stratum"]],
              "order": o} for o, i in enumerate(srswor_indices(strata, n_h, seed))]
    design_id = "sd-" + _sha([ALGORITHM, seed, frame_hash, sorted(n_h.items()), np.__version__])[7:23]
    return {"design_id": design_id, "seed": seed, "rng": "numpy.PCG64", "algorithm": ALGORITHM,
            "numpy_version": np.__version__, "frame_hash": frame_hash, "N_h": N_h, "n_h": dict(n_h),
            "units": units, "created_seq": created_seq}


def ht_mean(y, pi, N: int) -> float:
    """Horvitz-Thompson estimate of the population mean."""
    return float(np.sum(np.asarray(y, float) / np.asarray(pi, float)) / N)
