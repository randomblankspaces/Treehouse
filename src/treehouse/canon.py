"""Canonical JSON and hashing helpers.

Every sealed record is hashed over its canonical JSON form: sorted keys, no NaN/Infinity,
UTF-8, compact separators. Two machines produce the same hash for the same record.

Golden files compare ``stable_view(record)``: the record with its volatile fields removed at any depth
(``VOLATILE_FIELDS``: wall-clock time, commit, interpreter and lockfile identity, and the manifest/code
references that embed them). Sealed hashes still cover every field; only golden comparisons ignore them.
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


VOLATILE_FIELDS = frozenset({"created_at", "git_sha", "python", "uv_lock_sha256", "code_sha", "manifest_ref"})


def stable_view(obj: Any, volatile: frozenset[str] = VOLATILE_FIELDS) -> Any:
    """JSON-mode copy of ``obj`` without ``volatile`` keys at any depth, for golden comparisons."""
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {k: stable_view(v, volatile) for k, v in obj.items() if k not in volatile}
    if isinstance(obj, list | tuple):
        return [stable_view(v, volatile) for v in obj]
    return obj


def stable_hash(obj: Any) -> str:
    """sha256 of the canonical ``stable_view`` of ``obj``: the golden hash of a passport or scorecard."""
    return sha256_json(stable_view(obj))


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_json(obj: Any) -> str:
    return sha256_bytes(canonical_json(obj).encode("utf-8"))
