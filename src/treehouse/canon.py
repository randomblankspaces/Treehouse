"""Canonical JSON and hashing helpers.

Every sealed record is hashed over its canonical JSON form: sorted keys, no NaN/Infinity,
UTF-8, compact separators. Two machines produce the same hash for the same record.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any


def _check_finite(obj: Any) -> None:
    if isinstance(obj, float) and not math.isfinite(obj):
        raise ValueError("canonical JSON forbids NaN and Infinity")
    if isinstance(obj, dict):
        for v in obj.values():
            _check_finite(v)
    elif isinstance(obj, list | tuple):
        for v in obj:
            _check_finite(v)


def canonical_json(obj: Any) -> str:
    """Return the canonical JSON string for ``obj`` (pydantic models are dumped in JSON mode)."""
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump(mode="json")
    _check_finite(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_json(obj: Any) -> str:
    return sha256_bytes(canonical_json(obj).encode("utf-8"))
