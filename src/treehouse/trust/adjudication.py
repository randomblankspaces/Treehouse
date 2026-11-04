"""Adjudication queue file I/O (A5: two human queues). Labels read back here carry ``sealed_ref`` starting
with ``ADJ_PREFIX`` and are refused as PPI gold by the tier ladder: disagreement selection would bias it."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

from treehouse.schemas.sampling import BlindItem
from treehouse.schemas.verdicts import GoldLabel

ADJ_PREFIX = "adjudication/"


def write_queue(path: Path, items: Iterable[BlindItem]) -> None:
    """One BlindItem per line: the labeller sees nothing beyond what the verifier saw."""
    Path(path).write_text("".join(i.model_dump_json() + "\n" for i in items), encoding="utf-8")


def read_labels(path: Path, *, labeller: str, labeller_kind: str, blind_protocol_hash: str,
                synthetic: bool) -> list[GoldLabel]:
    """Rows: {unit_id, question_id, label, ts}. Each becomes a GoldLabel tagged as adjudication."""
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        ref = ADJ_PREFIX + hashlib.sha256(line.encode()).hexdigest()[:16]
        out.append(GoldLabel(unit_id=row["unit_id"], question_id=row["question_id"], label=row["label"],
                             labeller=labeller, labeller_kind=labeller_kind, blind_protocol_hash=blind_protocol_hash,
                             ts=row["ts"], sealed_ref=ref, synthetic=synthetic))
    return out
