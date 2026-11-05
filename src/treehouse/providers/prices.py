"""Dated price tables (USD per 1,000 tokens).

``config/prices/bedrock-us-east-1.2026-11-04.yaml`` is the real table; it ships all null until K2a.
``fixture.yaml`` holds synthetic prices for tests. ``probe-ceiling.yaml`` holds deliberately high
placeholder prices used only to commit the K1 probe's spend (AWS-B1), always tagged ``estimated``.
A null input or output price means UNPRICED.

Rows are keyed ``<price_ref>@<profile>`` (``claude-sonnet-5-5@us``) because geographic cross-region
profiles (``us.``/``eu.``/``apac.``) can cost more (about +10% for recent Claude) than ``global.``; a bare
``<price_ref>`` row means "profile unknown". ``price(ref, profile)`` uses the exact row; without a priced
exact row it takes the MOST EXPENSIVE priced row for that model and, for a geographic profile, adds
``GEO_PREMIUM`` (never under-count). Real (non-synthetic, non-estimated) tables must pass a plausibility
band (per 1K tokens: input in [``MIN_PER_1K``, ``MAX_INPUT_PER_1K``], output in [``MIN_PER_1K``,
``MAX_OUTPUT_PER_1K``]) so a per-token / per-1M units slip cannot silently disable the $450 hard stop.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, field_validator, model_validator

from treehouse.paths import repo_root
from treehouse.schemas.base import Frozen
from treehouse.schemas.model_io import Usage

DEFAULT_TABLE = "bedrock-us-east-1.2026-11-04.yaml"
# plausibility band for real tables, USD per 1K tokens (B2): $0.01..$200 per 1M input, <= $1000 per 1M output
MIN_PER_1K, MAX_INPUT_PER_1K, MAX_OUTPUT_PER_1K = 1e-5, 0.2, 1.0
GEO_PREMIUM = 1.10  # applied when a geographic profile falls back to a global/unknown-profile row (M6)
GEO_PROFILES = ("us", "eu", "apac", "jp", "au", "ca", "us-gov")
PROFILE_PREFIXES = (*GEO_PROFILES, "global")


class PriceError(ValueError):
    pass


def profile_of(invoke_id: str | None) -> str | None:
    """``us`` for ``us.anthropic.claude-...``; None for a bare model id."""
    if not invoke_id or "." not in invoke_id:
        return None
    head = invoke_id.split(".", 1)[0]
    return head if head in PROFILE_PREFIXES else None


class Price(Frozen):
    # > 0: a zero price would make every call free and bypass the hard stop (B2)
    input: float | None = Field(default=None, gt=0)
    output: float | None = Field(default=None, gt=0)
    cache_read: float | None = Field(default=None, gt=0)
    cache_write: float | None = Field(default=None, gt=0)
    price_basis: Literal["ceiling"] | None = Field(default=None, exclude_if=lambda v: v is None)

    def implausible(self) -> list[str]:
        """Reasons this row is outside the plausibility band (empty if fine or unpriced)."""
        out = []
        for f, hi in (("input", MAX_INPUT_PER_1K), ("output", MAX_OUTPUT_PER_1K), ("cache_read", MAX_INPUT_PER_1K),
                      ("cache_write", MAX_INPUT_PER_1K * 1.25)):
            v = getattr(self, f)
            if v is not None and not (MIN_PER_1K <= v <= hi):
                out.append(f"{f}={v} per 1K (= ${v * 1000:g} per 1M) outside [{MIN_PER_1K}, {hi}] per 1K")
        if self.input is not None and self.output is not None and self.output < self.input:
            out.append(f"output {self.output} < input {self.input}: inverted?")
        return out

    def scaled(self, k: float) -> Price:
        return Price(price_basis=self.price_basis, **{f: (None if getattr(self, f) is None else getattr(self, f) * k)
                        for f in ("input", "output", "cache_read", "cache_write")})

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
    unit_source: str | None = None  # e.g. "page quotes per 1M; divided by 1000"
    synthetic: bool = False
    estimated: bool = False
    default: Price | None = None
    models: dict[str, Price] = {}

    @field_validator("retrieved", "source", mode="before")
    @classmethod
    def _dates_as_text(cls, v: object) -> object:
        return v.isoformat() if hasattr(v, "isoformat") else v  # YAML reads 2026-11-04 as a date

    @model_validator(mode="after")
    def _plausible(self) -> PriceTable:
        if self.synthetic or self.estimated:
            return self  # test fixtures / probe ceiling; the SpendLedger refuses them for live spend
        bad = [f"{k}: {r}" for k, p in [*self.models.items(), ("default", self.default)] if p is not None
               for r in p.implausible()]
        if bad:
            raise PriceError(f"price table {self.version}: implausible prices (units slip? the table is USD per "
                             "1,000 tokens; divide a per-1M price by 1000): " + "; ".join(bad))
        return self

    @property
    def live_ok(self) -> bool:
        """Usable for real spend: not synthetic, not a placeholder."""
        return not (self.synthetic or self.estimated)

    @classmethod
    def load(cls, path: Path | str) -> PriceTable:
        return cls.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))

    def resolve(self, price_ref: str, profile: str | None = None) -> tuple[Price | None, str]:
        """(price, row label). Exact ``ref@profile`` row (or bare ``ref`` when ``profile`` is None) if priced;
        else the most expensive priced row for ``ref`` (+``GEO_PREMIUM`` for a geographic profile); else
        ``default``; else None."""
        exact = f"{price_ref}@{profile}" if profile else price_ref
        p = self.models.get(exact)
        if p is not None and p.priced:
            return p, exact
        rows = [(k, v) for k, v in self.models.items()
                if (k == price_ref or k.startswith(price_ref + "@")) and v.priced]
        if rows:
            k, best = max(rows, key=lambda kv: (kv[1].output, kv[1].input))  # type: ignore[arg-type,return-value]
            if profile in GEO_PROFILES and not k.endswith(f"@{profile}"):
                return best.scaled(GEO_PREMIUM), f"{k} x{GEO_PREMIUM} (no priced {exact} row)"
            return best, f"{k} (no priced {exact} row; most expensive)"
        if p is not None:
            return p, exact  # an unpriced exact row
        return self.default, "default"

    def price(self, price_ref: str, profile: str | None = None) -> Price | None:
        """The price for ``price_ref`` (see ``resolve``)."""
        return self.resolve(price_ref, profile)[0]

    def is_priced(self, price_ref: str, profile: str | None = None) -> bool:
        p = self.price(price_ref, profile)
        return p is not None and p.priced


def prices_dir() -> Path:
    return repo_root() / "config" / "prices"


def load_default() -> PriceTable:
    return PriceTable.load(prices_dir() / DEFAULT_TABLE)


def load_fixture() -> PriceTable:
    return PriceTable.load(prices_dir() / "fixture.yaml")


def load_probe_ceiling() -> PriceTable:
    return PriceTable.load(prices_dir() / "probe-ceiling.yaml")
