"""Score (b) confidence calibration (R6.1): per-claim stated confidence vs graded correctness on keyed
runs. Reports the Brier score, equal-width reliability bins with counts, and ECE (count-weighted
|accuracy - mean confidence|). Pure: stdlib only."""
from __future__ import annotations

import math
from collections.abc import Sequence

CALIBRATION_VERSION = "calib-v1"
KEYED_ONLY = "keyed runs only: correctness comes from the grader, so unkeyed runs have no calibration"
def _validate(confidences: Sequence[float], correct: Sequence[bool], n_bins: int) -> None:
    if isinstance(n_bins, bool) or not isinstance(n_bins, int) or n_bins < 1:
        raise ValueError(f"n_bins must be a positive int, got {n_bins!r}")
    if len(confidences) != len(correct):
        raise ValueError(f"length mismatch: {len(confidences)} confidences vs {len(correct)} outcomes")
    for c in confidences:
        if isinstance(c, bool) or not isinstance(c, int | float) or not math.isfinite(c) or not 0 <= c <= 1:
            raise ValueError(f"confidence must be a finite number in [0, 1], got {c!r}")
    for k in correct:
        if not isinstance(k, bool) and type(k).__name__ != "bool_":  # accept numpy.bool_ without importing it
            raise ValueError(f"correct must be boolean, got {k!r}")
def calibrate(confidences: Sequence[float], correct: Sequence[bool], n_bins: int = 10) -> dict:
    _validate(confidences, correct, n_bins)
    n = len(confidences)
    out = {"version": CALIBRATION_VERSION, "n": n, "n_bins": n_bins, "keyed_only": KEYED_ONLY}
    members: list[list[int]] = [[] for _ in range(n_bins)]
    for i, c in enumerate(confidences):
        members[min(int(math.floor(c * n_bins)), n_bins - 1)].append(i)  # last bin includes 1.0
    bins, ece = [], 0.0
    for b, idx in enumerate(members):
        row = {"lo": b / n_bins, "hi": (b + 1) / n_bins, "n": len(idx), "mean_confidence": None,
               "accuracy": None}
        if idx:
            row["mean_confidence"] = sum(float(confidences[i]) for i in idx) / len(idx)
            row["accuracy"] = sum(bool(correct[i]) for i in idx) / len(idx)
            ece += len(idx) / n * abs(row["accuracy"] - row["mean_confidence"])
        bins.append(row)
    out["bins"] = bins
    if n == 0:
        return out | {"brier": None, "ece": None, "reason": "no graded claims with stated confidence"}
    brier = sum((float(c) - float(bool(k))) ** 2 for c, k in zip(confidences, correct, strict=True)) / n
    return out | {"brier": brier, "ece": ece, "reason": None}
