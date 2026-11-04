"""SpendLedger: the account-wide dollar guard across every live Bedrock call (§3, AWS-B1).

An append-only JSONL file. Path: ``$TREEHOUSE_SPEND_LEDGER`` (resolved to an absolute path), else the
repo's ``.spend/spend.jsonl`` inside a checkout, else ``~/.treehouse/spend.jsonl``. Kiro commits ``.spend/``
after every K step so a session reset cannot zero the guard.

THE LEDGER IS NOT THE AWS BILL. It counts only Treehouse's own Converse calls at our own dated price table.
CloudWatch, S3, CDK stacks, other tools in the account and pricing mistakes are invisible to it; compare
with AWS Billing / Cost Explorer after each live step and record the figure with ``treehouse budget
reconcile`` (M12).

* The file must exist and start with a ``genesis`` row (``treehouse budget init``): ``reserve()`` refuses
  a missing, empty or genesis-less ledger, so a moved/deleted/fresh file can never silently restart at $0 (B1).
* A torn FINAL line (a crash mid-append) is ignored with a warning; that is always conservative (a torn
  reserve means the process died before calling; a torn commit/release leaves its reservation open at
  worst case). The next write seals it with a ``torn`` row. Any other unparseable line (a merge conflict)
  raises: repair the file by hand, never delete it.
* ``reserve()`` runs before each call. Worst case = ``est_input_tokens * in_price + max_tokens * out_price``.
  If spent + reserved + worst case would pass ``hard_stop`` ($450) it raises ``BudgetHardStop``: only
  replay (which costs $0) can continue. Above ``alarm`` ($350) it needs ``allow_over_alarm=True`` and a
  ``reason``, which is logged. Above ``planned`` ($250) it warns. A null price is refused
  (``UnpricedModel``) unless ``unpriced_cap_usd`` is given; the reservation is then that cap.
* ``commit()`` records the actual cost (usage × dated price) and any overshoot over the reservation. An
  unpriced reservation is committed at ``price_override`` (the probe-ceiling table) or at its cap, and is
  tagged ``estimated``. ``commit_worst()`` books the full reservation when the outcome is ambiguous (read
  timeout, dropped connection, cancel: Bedrock may have billed), tagged ``ambiguous``.
* ``release()`` drops a reservation whose call failed before Bedrock billed it.
* Synthetic and placeholder price tables are refused unless ``allow_synthetic=True`` (tests).

The state is recomputed from the file under an exclusive lock on every operation, so two processes
sharing one ledger cannot both slip under the cap. Open reservations from a crashed process stay
reserved (conservative); ``treehouse budget open`` lists them and ``treehouse budget release-stale``
resolves them (as spent at worst case by default).
"""

from __future__ import annotations

import hashlib
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
from treehouse.paths import repo_root
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


class LedgerMissing(SpendError):
    """The ledger file is absent, empty or has no genesis row: run ``treehouse budget init``."""


class LedgerCorrupt(SpendError):
    """A non-final ledger line is not JSON (e.g. a merge conflict). Repair by hand; never delete."""


class SpendWarning(UserWarning):
    pass


def repo_ledger_path() -> Path | None:
    try:
        return repo_root() / ".spend" / "spend.jsonl"
    except FileNotFoundError:
        return None


def default_ledger_path() -> Path:
    env = os.environ.get("TREEHOUSE_SPEND_LEDGER")
    if env:
        return Path(env).expanduser().resolve()
    return repo_ledger_path() or (Path.home() / ".treehouse" / "spend.jsonl")


def _sha(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def parse_rows(text: str, path: Path | str = "ledger") -> tuple[list[dict[str, Any]], str | None]:
    """(rows, torn final line or None). Raises LedgerCorrupt for an unsealed non-final bad line."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    rows: list[dict[str, Any]] = []
    torn: str | None = None
    bad: dict[int, str] = {}
    for i, ln in enumerate(lines):
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            bad[i] = ln
            rows.append({"kind": "_bad", "sha256": _sha(ln)})
    for i, ln in bad.items():
        sealed = i + 1 < len(rows) and rows[i + 1].get("kind") == "torn" and rows[i + 1].get("sha256") == _sha(ln)
        if sealed:
            continue
        if i == len(lines) - 1:
            torn = ln
            continue
        raise LedgerCorrupt(f"{path}: line {i + 1} is not JSON ({ln[:60]!r}; merge conflict?). Repair the file by "
                            "hand (keep every reserve/commit row); do NOT delete it: that zeroes the spend guard")
    return [r for r in rows if r.get("kind") != "_bad"], torn


@dataclass(frozen=True)
class Reservation:
    id: str
    model_key: str
    price_ref: str
    worst_usd: float
    unpriced: bool
    price_version: str | None
    profile: str | None = None


class SpendStatus(Frozen):
    path: str
    initialized: bool = True  # the file exists with a genesis row
    spent_usd: float
    reserved_usd: float
    estimated_usd: float  # part of spent_usd committed at placeholder (estimated) prices
    ambiguous_usd: float = 0.0  # part of spent_usd booked at worst case after an ambiguous failure
    overshoot_usd: float = 0.0  # actual cost above the reservation, summed
    last_reconcile: dict[str, Any] | None = None  # the last `budget reconcile` row (AWS billing figure)
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
        allow_synthetic: bool = False,
    ) -> None:
        if not planned <= alarm <= hard_stop:
            raise ValueError("need planned <= alarm <= hard_stop")
        if hard_stop > HARD_STOP + EPS and not os.environ.get("TREEHOUSE_HARD_STOP_OVERRIDE"):
            raise ValueError(f"hard_stop ${hard_stop} > ${HARD_STOP}: set TREEHOUSE_HARD_STOP_OVERRIDE to allow")
        if prices is not None and not prices.live_ok and not allow_synthetic:
            raise SpendError(f"price table {prices.version} is synthetic/placeholder; refusing it for live spend "
                             "(tests pass allow_synthetic=True)")
        self.path = Path(path).expanduser().resolve() if path is not None else default_ledger_path()
        self.planned, self.alarm, self.hard_stop = planned, alarm, hard_stop
        self.prices, self.registry = prices, registry

    # -- file ---------------------------------------------------------------------------------
    @property
    def initialized(self) -> bool:
        if not self.path.is_file():
            return False
        with open(self.path, encoding="utf-8") as f:
            first = f.readline()
        try:
            return json.loads(first).get("kind") == "genesis"
        except (json.JSONDecodeError, AttributeError):
            return False

    def init(self, *, account: str | None = None, note: str | None = None) -> None:
        """Create the ledger with a genesis row. Refuses an existing non-empty file."""
        if self.path.is_file() and self.path.stat().st_size > 0:
            raise SpendError(f"{self.path} already exists; never re-init a ledger (it would hide spend)")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(canonical_json({"kind": "genesis", "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
                                    "account": account, "note": note, "hard_stop": self.hard_stop}) + "\n")

    @contextmanager
    def _locked(self, *, require_init: bool = False, create: bool = True) -> Iterator[list[dict[str, Any]]]:
        if require_init and not self.initialized:
            raise LedgerMissing(f"spend ledger {self.path} does not exist or has no genesis row; refusing to reserve. "
                                "Run `uv run treehouse budget init` once (then commit .spend/), or point "
                                "TREEHOUSE_SPEND_LEDGER at the existing ledger")
        if not create and not self.path.is_file():
            yield []
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a+", encoding="utf-8") as f:
            if fcntl is not None:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.seek(0)
                text = f.read()
                rows, torn = parse_rows(text, self.path)
                if torn is not None:
                    warnings.warn(f"{self.path}: ignoring a torn final line ({torn[:40]!r}...); conservative",
                                  SpendWarning, stacklevel=3)
                self._f, self._torn, self._needs_nl = f, torn, bool(text) and not text.endswith("\n")
                yield rows
            finally:
                self._f = None
                if fcntl is not None:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _append(self, row: dict[str, Any]) -> None:
        now = datetime.now(UTC).isoformat(timespec="milliseconds")
        if self._needs_nl:
            self._f.write("\n")
            self._needs_nl = False
        if self._torn is not None:  # seal the torn line so it is no longer "final"
            self._f.write(canonical_json({"kind": "torn", "ts": now, "sha256": _sha(self._torn)}) + "\n")
            self._torn = None
        self._f.write(canonical_json({"ts": now, **row}) + "\n")
        self._f.flush()

    @staticmethod
    def _state(rows: list[dict[str, Any]]) -> dict[str, Any]:
        open_: dict[str, float] = {}
        open_rows: dict[str, dict[str, Any]] = {}
        spent = est = amb = over = 0.0
        calls = 0
        reasons: list[str] = []
        reconcile = None
        committed: set[str] = set()
        for r in rows:
            k = r.get("kind")
            if k == "reserve":
                open_[r["id"]] = float(r["worst_usd"])
                open_rows[r["id"]] = r
                if r.get("over_alarm_reason"):
                    reasons.append(r["over_alarm_reason"])
            elif k == "commit":
                if r["id"] not in committed:  # count each reservation once
                    committed.add(r["id"])
                    spent += float(r["usd"])
                    calls += 1
                    est += float(r["usd"]) if r.get("estimated") else 0.0
                    amb += float(r["usd"]) if r.get("ambiguous") else 0.0
                    over += float(r.get("overshoot_usd") or 0.0)
                open_.pop(r["id"], None)
            elif k == "release":
                open_.pop(r["id"], None)
            elif k == "reconcile":
                reconcile = r
        return {"open": open_, "open_rows": {i: open_rows[i] for i in open_}, "spent": spent, "estimated": est,
                "ambiguous": amb, "overshoot": over, "calls": calls, "reasons": reasons, "reconcile": reconcile}

    # -- API ----------------------------------------------------------------------------------
    def _price_ref(self, model_key: str) -> str:
        """Registry ``price_ref`` for ``model_key`` (the provider passes ``price_ref`` explicitly instead)."""
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
        price_ref: str | None = None,
        profile: str | None = None,
    ) -> Reservation:
        if est_input_tokens < 0 or max_tokens < 0:
            raise ValueError("token counts must be >= 0")
        ref = price_ref or self._price_ref(model_key)
        price = self.prices.price(ref, profile) if self.prices is not None else None
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
        with self._locked(require_init=True) as rows:
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
                              unpriced=unpriced, price_version=self.prices.version if self.prices else None,
                              profile=profile)
            self._append({"kind": "reserve", "id": res.id, "model_key": model_key, "price_ref": ref,
                          "profile": profile,
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
            p = self.prices.price(reservation.price_ref, reservation.profile)  # type: ignore[union-attr]
            usd = p.cost(usage)  # type: ignore[union-attr]
            estimated = bool(self.prices.estimated)  # type: ignore[union-attr]
        overshoot = max(0.0, usd - reservation.worst_usd)
        if overshoot > EPS:
            warnings.warn(f"call cost ${usd:.4f} > reserved ${reservation.worst_usd:.4f}", SpendWarning, stacklevel=2)
        with self._locked():
            self._append({"kind": "commit", "id": reservation.id, "model_key": reservation.model_key,
                          "usd": usd, "estimated": estimated, "price_version": version,
                          "usage": usage.model_dump(mode="json"),
                          **({"overshoot_usd": overshoot} if overshoot > EPS else {})})
        return usd

    def commit_worst(self, reservation: Reservation, why: str) -> float:
        """Book the whole reservation as spent (``estimated``, ``ambiguous``): the call may have been billed
        but its usage is unknown (read timeout, dropped connection, cancel, unparseable response)."""
        return self._commit_worst_row(reservation.id, reservation.model_key, reservation.worst_usd,
                                      reservation.price_version, why)

    def _commit_worst_row(self, rid: str, model_key: str, usd: float, version: str | None, why: str) -> float:
        with self._locked():
            self._append({"kind": "commit", "id": rid, "model_key": model_key, "usd": usd, "estimated": True,
                          "ambiguous": True, "why": why, "price_version": version, "usage": None})
        return usd

    def release(self, reservation: Reservation, why: str = "") -> None:
        with self._locked():
            self._append({"kind": "release", "id": reservation.id, "why": why})

    def open_reservations(self) -> list[dict[str, Any]]:
        """The reserve rows that were neither committed nor released, oldest first."""
        with self._locked(create=False) as rows:
            return list(self._state(rows)["open_rows"].values())

    def resolve_stale(self, *, older_than_s: float, release: bool = False, reason: str) -> list[dict[str, Any]]:
        """Resolve open reservations older than ``older_than_s``: by default book them as spent at worst case
        (the crashed call may have been billed); ``release=True`` drops them. Returns the rows resolved."""
        if not reason:
            raise ValueError("a reason is required")
        now = datetime.now(UTC)
        done = []
        with self._locked(require_init=True) as rows:
            for r in self._state(rows)["open_rows"].values():
                if (now - datetime.fromisoformat(r["ts"])).total_seconds() < older_than_s:
                    continue
                if release:
                    self._append({"kind": "release", "id": r["id"], "why": f"stale: {reason}"})
                else:
                    self._append({"kind": "commit", "id": r["id"], "model_key": r.get("model_key"),
                                  "usd": float(r["worst_usd"]), "estimated": True, "ambiguous": True,
                                  "why": f"stale: {reason}", "price_version": r.get("price_version"), "usage": None})
                done.append(r)
        return done

    def reconcile(self, aws_usd: float, *, source: str, note: str | None = None) -> dict[str, Any]:
        """Record an AWS Billing / Cost Explorer figure next to the ledger total (M12)."""
        with self._locked(require_init=True) as rows:
            st = self._state(rows)
            row = {"kind": "reconcile", "aws_usd": float(aws_usd), "ledger_spent_usd": st["spent"],
                   "delta_usd": float(aws_usd) - st["spent"], "source": source, "note": note}
            self._append(row)
        return row

    def status(self) -> SpendStatus:
        initialized = self.initialized
        with self._locked(create=False) as rows:
            st = self._state(rows)
        reserved = sum(st["open"].values())
        total = st["spent"] + reserved
        level = ("hard_stop" if total >= self.hard_stop - EPS else "over_alarm" if total > self.alarm + EPS
                 else "over_planned" if total > self.planned + EPS else "ok")
        return SpendStatus(path=str(self.path), initialized=initialized, spent_usd=st["spent"], reserved_usd=reserved,
                           estimated_usd=st["estimated"], ambiguous_usd=st["ambiguous"],
                           overshoot_usd=st["overshoot"], last_reconcile=st["reconcile"], planned=self.planned, alarm=self.alarm,
                           hard_stop=self.hard_stop, level=level, calls=st["calls"],
                           open_reservations=sorted(st["open"]), over_alarm_reasons=st["reasons"])
