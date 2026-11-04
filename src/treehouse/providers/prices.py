"""Dated price tables (USD per 1,000 tokens).

``config/prices/bedrock-us-east-1.2026-11-04.yaml`` is the real table; it ships all null until K2a.
``fixture.yaml`` holds synthetic prices for tests. ``probe-ceiling.yaml`` holds deliberately high
placeholder prices used only to commit the K1 probe's spend (AWS-B1), always tagged ``estimated``.
A null input or output price means UNPRICED.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, field_validator

from treehouse.paths import repo_root
from treehouse.schemas.base import Frozen
from treehouse.schemas.model_io import Usage

DEFAULT_TABLE = "bedrock-us-east-1.2026-11-04.yaml"


class Price(Frozen):
    input: float | None = Field(default=None, ge=0)
    output: float | None = Field(default=None, ge=0)
    cache_read: float | None = Field(default=None, ge=0)
    cache_write: float | None = Field(default=None, ge=0)

    @property
    def priced(self) -> bool:
        return self.input is not None and self.output is not None

    def worst_case(self, est_input_tokens: int, max_tokens: int) -> float:
        """``in_est * in_price + max_tokens * out_price`` (§3 SpendLedger)."""
        if not self.priced:
            raise ValueError("unpriced")
        return (est_input_tokens * self.input + max_tokens * self.output) / 1000.0  # type: ignore[operator]

    def cost(self, usage: Usage) -> float:
        """usage × price. A null cache price falls back to input (read) or 1.25 × input (write)."""
        if not self.priced:
            raise ValueError("unpriced")
        inp, out = self.input, self.output
        cr = self.cache_read if self.cache_read is not None else inp
        cw = self.cache_write if self.cache_write is not None else 1.25 * inp  # type: ignore[operator]
        return (usage.input_tokens * inp + usage.output_tokens * out  # type: ignore[operator]
                + usage.cache_read * cr + usage.cache_write * cw) / 1000.0  # type: ignore[operator]


class PriceTable(Frozen):
    schema_version: Literal["treehouse.prices/1"] = "treehouse.prices/1"
    version: str
    region: str
    currency: Literal["USD"] = "USD"
    unit: Literal["per_1k_tokens"] = "per_1k_tokens"
    source: str | None = None
    retrieved: str | None = None
    synthetic: bool = False
    estimated: bool = False
    default: Price | None = None
    models: dict[str, Price] = {}

    @field_validator("retrieved", "source", mode="before")
    @classmethod
    def _dates_as_text(cls, v: object) -> object:
        return v.isoformat() if hasattr(v, "isoformat") else v  # YAML reads 2026-11-04 as a date

    @classmethod
    def load(cls, path: Path | str) -> PriceTable:
        return cls.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))

    def price(self, price_ref: str) -> Price | None:
        """The price row for ``price_ref``; ``default`` if absent; None if neither exists."""
        return self.models.get(price_ref) or self.default

    def is_priced(self, price_ref: str) -> bool:
        p = self.price(price_ref)
        return p is not None and p.priced


def prices_dir() -> Path:
    return repo_root() / "config" / "prices"


def load_default() -> PriceTable:
    return PriceTable.load(prices_dir() / DEFAULT_TABLE)


def load_fixture() -> PriceTable:
    return PriceTable.load(prices_dir() / "fixture.yaml")


def load_probe_ceiling() -> PriceTable:
    return PriceTable.load(prices_dir() / "probe-ceiling.yaml")
