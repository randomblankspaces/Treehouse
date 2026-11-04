"""Shared base: every schema is frozen, rejects unknown fields and rejects NaN/Infinity at validation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Frozen(BaseModel):
    """Frozen is shallow: list/dict fields can still be mutated in place. Whatever seals or hashes a
    record must re-validate it first (``type(x).model_validate(x.model_dump())``) so an in-place edit
    is caught by the validators before it reaches a hash."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
