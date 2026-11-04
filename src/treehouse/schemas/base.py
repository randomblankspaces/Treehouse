"""Shared base: every schema is frozen and rejects unknown fields."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
