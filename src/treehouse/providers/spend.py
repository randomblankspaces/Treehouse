"""SpendLedger: the account-wide dollar guard across every live Bedrock call (§3, AWS-B1).

An append-only JSONL file (``$TREEHOUSE_SPEND_LEDGER`` or ``~/.treehouse/spend.jsonl``; Kiro points it
at ``.spend/spend.jsonl`` and commits it after every K step so a session reset cannot zero the guard).

* ``reserve()`` runs before each call. Worst case = ``est_input_tokens * in_price + max_tokens * out_price``.
  If spent + reserved + worst case would pass ``hard_stop`` ($450) it raises ``BudgetHardStop``: only
  replay (which costs $0) can continue. Above ``alarm`` ($350) it needs ``allow_over_alarm=True`` and a
  ``reason``, which is logged. Above ``planned`` ($250) it warns. A null price is refused
  (``UnpricedModel``) unless ``unpriced_cap_usd`` is given; the reservation is then that cap.
* ``commit()`` records the actual cost (usage × dated price). An unpriced reservation is committed at
  ``price_override`` (the probe-ceiling table) or at its cap, and is tagged ``estimated``.
* ``release()`` drops a reservation whose call failed before Bedrock billed it.

The state is recomputed from the file under an exclusive lock on every operation, so two processes
sharing one ledger cannot both slip under the cap. Open reservations from a crashed process stay
reserved (conservative); ``treehouse budget status`` lists them.
"""

from __future__ import annotations

import json
import os
import uuid
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from treehouse.canon import canonical_json
from treehouse.providers.prices import PriceTable
from treehouse.providers.registry import ModelRegistry
from treehouse.schemas.base import Frozen
from treehouse.schemas.model_io import Usage

try:  # POSIX advisory lock; Windows falls back to in-process only
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

PLANNED, ALARM, HARD_STOP = 250.0, 350.0, 450.0
EPS = 1e-9


class SpendError(RuntimeError):
    pass


class BudgetHardStop(SpendError):
    """spent + reserved would pass the hard stop. Only replay (which costs $0) may continue."""


class BudgetAlarm(SpendError):
    """Above the alarm line without ``allow_over_alarm=True`` and a reason."""


class UnpricedModel(SpendError):
    """The model's price is null and no ``unpriced_cap_usd`` was given."""


class SpendWarning(UserWarning):
    pass


def default_ledger_path() -> Path:
    env = os.environ.get("TREEHOUSE_SPEND_LEDGER")
    return Path(env) if env else Path.home() / ".treehouse" / "spend.jsonl"


@dataclass(frozen=True)
class Reservation:
    id: str
    model_key: str
    price_ref: str
    worst_usd: float
    unpriced: bool
    price_version: str | None


class SpendStatus(Frozen):
    path: str
    spent_usd: float
    reserved_usd: float
    estimated_usd: float  # part of spent_usd committed at placeholder (estimated) prices
    planned: float
    alarm: float
    hard_stop: float
    level: Literal["ok", "over_planned", "over_alarm", "hard_stop"]
    calls: int
    open_reservations: list[str]
    over_alarm_reasons: list[str]

    @property
    def total_usd(self) -> float:
        return self.spent_usd + self.reserved_usd


class SpendLedger:
    def __init__(
        self,
        path: Path | str | None = None,
        *,
        planned: float = PLANNED,
        alarm: float = ALARM,
        hard_stop: float = HARD_STOP,
        prices: PriceTable | None = None,
        registry: ModelRegistry | None = None,
    ) -> None:
        if not planned <= alarm <= hard_stop:
            raise ValueError("need planned <= alarm <= hard_stop")
        self.path = Path(path) if path is not None else default_ledger_path()
        self.planned, self.alarm, self.hard_stop = planned, alarm, hard_stop
        self.prices, self.registry = prices, registry

    # -- file ---------------------------------------------------------------------------------
    @contextmanager
    def _locked(self) -> Iterator[list[dict[str, Any]]]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a+", encoding="utf-8") as f:
            if fcntl is not None:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.seek(0)
                rows = [json.loads(line) for line in f.read().splitlines() if line.strip()]
                self._f = f
                yield rows
            finally:
                self._f = None
                if fcntl is not None:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _append(self, row: dict[str, Any]) -> None:
        row = {"ts": datetime.now(UTC).isoformat(timespec="milliseconds"), **row}
        self._f.write(canonical_json(row) + "\n")
        self._f.flush()

    @staticmethod
    def _state(rows: list[dict[str, Any]]) -> dict[str, Any]:
        open_: dict[str, float] = {}
        spent = est = 0.0
        calls = 0
        reasons: list[str] = []
        for r in rows:
            k = r.get("kind")
            if k == "reserve":
                open_[r["id"]] = float(r["worst_usd"])
                if r.get("over_alarm_reason"):
                    reasons.append(r["over_alarm_reason"])
            elif k == "commit":
                open_.pop(r["id"], None)
                spent += float(r["usd"])
                calls += 1
                if r.get("estimated"):
                    est += float(r["usd"])
            elif k == "release":
                open_.pop(r["id"], None)
        return {"open": open_, "spent": spent, "estimated": est, "calls": calls, "reasons": reasons}

    # -- API ----------------------------------------------------------------------------------
    def _price_ref(self, model_key: str) -> str:
        if self.registry is not None:
            try:
                return self.registry.get(model_key).price_ref
            except ValueError:
                pass
        return model_key

    def reserve(
        self,
        model_key: str,
        est_input_tokens: int,
        max_tokens: int,
        *,
        allow_over_alarm: bool = False,
        reason: str | None = None,
        unpriced_cap_usd: float | None = None,
    ) -> Reservation:
        if est_input_tokens < 0 or max_tokens < 0:
            raise ValueError("token counts must be >= 0")
        ref = self._price_ref(model_key)
        price = self.prices.price(ref) if self.prices is not None else None
        if price is not None and price.priced:
            worst, unpriced = price.worst_case(est_input_tokens, max_tokens), False
        elif unpriced_cap_usd is not None:
            if unpriced_cap_usd <= 0:
                raise ValueError("unpriced_cap_usd must be > 0")
            worst, unpriced = float(unpriced_cap_usd), True
        else:
            raise UnpricedModel(f"{model_key}: price is null in "
                                f"{self.prices.version if self.prices else 'no price table'}; refusing the call "
                                "(fill config/prices and run `treehouse prices check`)")
        with self._locked() as rows:
            st = self._state(rows)
            total = st["spent"] + sum(st["open"].values()) + worst
            if total > self.hard_stop + EPS:
                raise BudgetHardStop(f"spent+reserved would reach ${total:.4f} > hard stop ${self.hard_stop:.2f}; "
                                     "only replay is allowed")
            over_alarm_reason = None
            if total > self.alarm + EPS:
                if not (allow_over_alarm and reason):
                    raise BudgetAlarm(f"spent+reserved would reach ${total:.4f} > alarm ${self.alarm:.2f}; "
                                      "pass allow_over_alarm=True with a reason")
                over_alarm_reason = reason
            if total > self.planned + EPS:
                warnings.warn(f"spend ${total:.4f} is over the planned ${self.planned:.2f}", SpendWarning,
                              stacklevel=2)
            res = Reservation(id=uuid.uuid4().hex, model_key=model_key, price_ref=ref, worst_usd=worst,
                              unpriced=unpriced, price_version=self.prices.version if self.prices else None)
            self._append({"kind": "reserve", "id": res.id, "model_key": model_key, "price_ref": ref,
                          "est_input_tokens": est_input_tokens, "max_tokens": max_tokens, "worst_usd": worst,
                          "unpriced": unpriced, "price_version": res.price_version,
                          "over_alarm_reason": over_alarm_reason})
        return res

    def commit(self, reservation: Reservation, usage: Usage, *, price_override: PriceTable | None = None) -> float:
        """Record actual spend; returns the dollars committed. Never raises on overshoot."""
        estimated = False
        version = reservation.price_version
        if reservation.unpriced:
            p = price_override.price(reservation.price_ref) if price_override is not None else None
            if p is not None and p.priced:
                usd, version = p.cost(usage), price_override.version  # type: ignore[union-attr]
            else:
                usd = reservation.worst_usd
            estimated = True
        else:
            p = self.prices.price(reservation.price_ref)  # type: ignore[union-attr]
            usd = p.cost(usage)  # type: ignore[union-attr]
            estimated = bool(self.prices.estimated)  # type: ignore[union-attr]
        with self._locked():
            self._append({"kind": "commit", "id": reservation.id, "model_key": reservation.model_key,
                          "usd": usd, "estimated": estimated, "price_version": version,
                          "usage": usage.model_dump(mode="json")})
        return usd

    def release(self, reservation: Reservation, why: str = "") -> None:
        with self._locked():
            self._append({"kind": "release", "id": reservation.id, "why": why})

    def status(self) -> SpendStatus:
        with self._locked() as rows:
            st = self._state(rows)
        reserved = sum(st["open"].values())
        total = st["spent"] + reserved
        level = ("hard_stop" if total >= self.hard_stop - EPS else "over_alarm" if total > self.alarm + EPS
                 else "over_planned" if total > self.planned + EPS else "ok")
        return SpendStatus(path=str(self.path), spent_usd=st["spent"], reserved_usd=reserved,
                           estimated_usd=st["estimated"], planned=self.planned, alarm=self.alarm,
                           hard_stop=self.hard_stop, level=level, calls=st["calls"],
                           open_reservations=sorted(st["open"]), over_alarm_reasons=st["reasons"])
