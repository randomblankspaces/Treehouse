"""verify(): re-check everything a sealed store promises; report each problem with path and seq.

Checks, in order:
- **runs**: manifest bytes are canonical and hash to ``manifest_hash``; SEALED names it; every listed file is
  present with its sha and nothing else is in the run; each trial's trace chain matches its head; the claims
  file matches ``claims_sha256``; span run-context attributes match the manifest; and the run has exactly one
  ``kind=run`` ledger line naming its current manifest hash.
- **ledger** and **evals index**: both chains verify; ``prev_manifest_hash`` follows the ledger's run order;
  every ledger line names something on disk; a store that holds runs must hold a ledger.
- **evals**: every ``evals/<run>/<kind>/<sha>.json`` has a known kind, matching bytes, exactly one ledger
  line after the run's seal line and exactly one index line naming the run's current manifest hash.
- **blobs**: bytes match their name and prefix, metadata names a licence, and every ``*_ref`` span attribute
  holding a sha256 resolves to a blob.

The report carries the ledger head (``ledger_head``/``ledger_n_lines``); ``expected_head`` checks that a head
recorded earlier is still a line of the ledger. That is the only defence against a forger who recomputes the
whole store (see ``store/local.py``).
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from treehouse.canon import canonical_json, sha256_bytes
from treehouse.schemas.manifest import Manifest
from treehouse.store.base import EVAL_KINDS
from treehouse.store.local import INDEX_GENESIS, LEDGER_GENESIS, LocalStore, check_run_id
from treehouse.store.seal import RESERVED, claims_file_for, safe_run_path
from treehouse.trace.chain import read_chain, trial_genesis, verify_chain

SHA_REF = re.compile(r"^sha256:[0-9a-f]{64}$")
SPAN_BINDINGS = (("treehouse.run.id", "run_id"), ("treehouse.config.hash", "config_hash"))


@dataclass(frozen=True)
class Problem:
    path: str
    seq: int | None
    message: str

    def __str__(self) -> str:
        return f"FAIL {self.path}" + (f" seq={self.seq}" if self.seq is not None else "") + f": {self.message}"


@dataclass
class VerifyReport:
    problems: list[Problem] = field(default_factory=list)
    runs: int = 0
    blobs: int = 0
    records: int = 0
    ledger_head: str = LEDGER_GENESIS  # h of the last ledger line (genesis when the ledger is empty)
    ledger_n_lines: int = 0

    @property
    def ok(self) -> bool:
        return not self.problems

    def add(self, path: Path | str, message: str, seq: int | None = None) -> None:
        self.problems.append(Problem(str(path), seq, message))


@dataclass
class _Ledger:
    ok: bool = True
    exists: bool = False
    lines: list[dict[str, Any]] = field(default_factory=list)
    runs: dict[str, list[tuple[int, str]]] = field(default_factory=lambda: defaultdict(list))  # rid -> (seq, ref)
    records: dict[tuple[str, str, str], list[int]] = field(default_factory=lambda: defaultdict(list))
    index: dict[tuple[str, str, str], list[str]] = field(default_factory=lambda: defaultdict(list))
    index_ok: bool = True


def verify(store: LocalStore, run_id: str | None = None, *, expected_head: str | None = None) -> VerifyReport:
    rep = VerifyReport()
    if run_id is not None:
        try:
            check_run_id(run_id)
        except ValueError as e:
            rep.add(run_id, str(e))
            return rep
    runs_root = store.root / "runs"
    if run_id is not None:
        run_ids = [run_id]
    else:
        run_ids = sorted(d.name for d in runs_root.iterdir() if d.is_dir() and not d.name.startswith(".tmp-")) \
            if runs_root.is_dir() else []
    led = _read_ledger(store, rep, expected_head)
    sealed: dict[str, tuple[Manifest, int | None]] = {}
    for rid in run_ids:
        m = _verify_run(store, rid, rep, led)
        if m is not None:
            sealed[rid] = m
    _verify_ledger(store, rep, run_id, led, bool(sealed))
    _verify_evals(store, rep, run_id, led, sealed)
    _verify_blobs(store, rep, sealed)
    return rep


# --- ledger ---------------------------------------------------------------------------------------


def _read_ledger(store: LocalStore, rep: VerifyReport, expected_head: str | None) -> _Ledger:
    led = _Ledger(exists=store.ledger_path.exists())
    for path, genesis in ((store.ledger_path, LEDGER_GENESIS), (store.index_path, INDEX_GENESIS)):
        if not path.exists():
            continue
        check = verify_chain(path, genesis=genesis)
        if not check.ok:
            rep.add(path, check.reason or "chain does not verify", check.first_bad_seq)
            if path == store.ledger_path:
                led.ok = False
            else:
                led.index_ok = False
    if led.exists and led.ok:
        led.lines = read_chain(store.ledger_path)
        rep.ledger_n_lines = len(led.lines)
        rep.ledger_head = led.lines[-1]["h"] if led.lines else LEDGER_GENESIS
        for ln in led.lines:
            rec = ln["rec"]
            key = (str(rec.get("run_id")), str(rec.get("kind")), str(rec.get("ref")))
            if rec.get("kind") == "run":
                led.runs[key[0]].append((ln["seq"], key[2]))
            else:
                led.records[key].append(ln["seq"])
    if expected_head is not None and led.ok and expected_head != LEDGER_GENESIS \
            and expected_head not in {ln["h"] for ln in led.lines}:
        rep.add(store.ledger_path, f"recorded head {expected_head} is not a line of this ledger (rewritten)")
    if store.index_path.exists() and led.index_ok:
        for ln in read_chain(store.index_path):
            rec = ln["rec"]
            led.index[(str(rec.get("run_id")), str(rec.get("kind")), str(rec.get("ref")))].append(
                str(rec.get("manifest_hash")))
    return led


def _verify_ledger(store: LocalStore, rep: VerifyReport, run_id: str | None, led: _Ledger, any_runs: bool) -> None:
    if any_runs and not led.exists:
        rep.add(store.ledger_path, "store holds sealed runs but has no ledger (deleted?)")
        return
    if not led.ok:
        return
    prev: str | None = None
    for ln in led.lines:
        rec = ln["rec"]
        rid = rec.get("run_id")
        try:
            run = store.run_dir(str(rid))
        except ValueError as e:
            rep.add(store.ledger_path, f"ledger line names an invalid run id: {e}", ln["seq"])
            continue
        if rec.get("kind") == "run":
            mp = run / "manifest.json"
            try:
                m = json.loads(mp.read_text()) if mp.is_file() else None
            except ValueError:
                m = None
            if run_id is None or rid == run_id:
                if m is None or m.get("manifest_hash") != rec.get("ref"):
                    rep.add(store.ledger_path, f"ledger names run {rid} with a manifest hash that is not on disk",
                            ln["seq"])
                elif m.get("prev_manifest_hash") != prev:
                    rep.add(mp, f"prev_manifest_hash {m.get('prev_manifest_hash')} != previous ledger run {prev}",
                            ln["seq"])
            prev = rec.get("ref")
        elif run_id is None or rid == run_id:
            kind, ref = str(rec.get("kind")), str(rec.get("ref"))
            if kind not in EVAL_KINDS or not SHA_REF.match(ref):
                rep.add(store.ledger_path, f"ledger line has unknown kind {kind!r} or bad ref", ln["seq"])
                continue
            rel = f"evals/{rid}/{kind}/{ref.removeprefix('sha256:')}.json"
            if not (store.root / rel).is_file():
                rep.add(store.ledger_path, f"ledger names missing record {rel}", ln["seq"])


# --- runs -----------------------------------------------------------------------------------------


def _verify_run(store: LocalStore, rid: str, rep: VerifyReport, led: _Ledger) -> tuple[Manifest, int | None] | None:
    rep.runs += 1
    try:
        run = store.run_dir(rid)
    except ValueError as e:
        rep.add(rid, str(e))
        return None
    if not run.is_dir():
        rep.add(run, "run not found")
        return None
    if not (run / "SEALED").is_file():
        rep.add(run / "SEALED", "run is not sealed")
        return None
    raw = (run / "manifest.json").read_bytes() if (run / "manifest.json").is_file() else b""
    try:
        m = Manifest.model_validate_json(raw)
    except ValueError as e:
        rep.add(run / "manifest.json", f"unreadable manifest: {e}")
        return None
    if m.compute_hash() != m.manifest_hash:
        rep.add(run / "manifest.json", "manifest hash does not match its contents")
    if canonical_json(m).encode("utf-8") != raw:
        rep.add(run / "manifest.json", "manifest bytes are not canonical JSON")
    if (run / "SEALED").read_text().strip() != m.manifest_hash:
        rep.add(run / "SEALED", "SEALED does not name the manifest hash")
    if m.run_id != rid:
        rep.add(run / "manifest.json", f"manifest run_id {m.run_id!r} != directory {rid!r}")
    for rel, sha in sorted(m.files.items()):
        bad = safe_run_path(rel)
        p = run / rel
        if bad:
            rep.add(run / "manifest.json", f"manifest lists an unsafe path: {bad}")
        elif p.is_symlink() or not p.is_file():
            rep.add(p, "file listed in manifest is missing (or a symlink)")
        elif sha256_bytes(p.read_bytes()) != sha:
            rep.add(p, "file sha256 does not match the manifest")
    for p in sorted(run.rglob("*")):
        rel = p.relative_to(run).as_posix()
        if (p.is_file() or p.is_symlink()) and rel not in m.files and rel not in RESERVED:
            rep.add(p, "file not listed in the manifest")
    for th in m.trials:
        claims = claims_file_for(th.trace_file)
        if safe_run_path(th.trace_file) or th.trace_file not in m.files or claims not in m.files:
            rep.add(run / "manifest.json", f"trial {th.trial_id}: trace and claims files must be sealed run files "
                                           "named <tid>.trace.jsonl and <tid>.claims.jsonl")
            continue
        p = run / th.trace_file
        check = verify_chain(p, genesis=trial_genesis(th.trial_id), expected=th.head)
        if not check.ok:
            rep.add(p, check.reason or "chain does not verify", check.first_bad_seq)
        else:
            _check_span_bindings(p, m, th.trial_id, rep)
        cp = run / str(claims)
        if cp.is_file() and sha256_bytes(cp.read_bytes()) != th.claims_sha256:
            rep.add(cp, "claims sha256 does not match the trial head")
    seal_seq: int | None = None
    if led.exists and led.ok:
        lines = led.runs.get(rid, [])
        if len(lines) != 1:
            rep.add(store.ledger_path, f"run {rid} has {len(lines)} ledger run lines (expected exactly 1: "
                                       f"{'never ledgered or line removed' if not lines else 're-sealed'})")
        elif lines[0][1] != m.manifest_hash:
            rep.add(store.ledger_path, f"ledger run line for {rid} names another manifest hash", lines[0][0])
        if lines:
            seal_seq = lines[-1][0]
    return m, seal_seq


def _check_span_bindings(path: Path, m: Manifest, trial_id: str, rep: VerifyReport) -> None:
    """Span-shaped lines must carry this run's id, trial id, config and task hashes."""
    want = {"treehouse.trial.id": trial_id, "treehouse.task.hash": m.task.hash,
            **{attr: getattr(m, f) for attr, f in SPAN_BINDINGS}}
    for ln in read_chain(path):
        attrs = ln["rec"].get("attributes")
        if not isinstance(attrs, dict):
            continue
        for k, v in want.items():
            if k in attrs and attrs[k] != v:
                rep.add(path, f"span attribute {k}={attrs[k]!r} does not match the manifest ({v!r})", ln["seq"])


# --- evals ----------------------------------------------------------------------------------------


def _verify_evals(store: LocalStore, rep: VerifyReport, run_id: str | None, led: _Ledger,
                  sealed: dict[str, tuple[Manifest, int | None]]) -> None:
    if led.index_ok:
        for key, hashes in led.index.items():
            if run_id is not None and key[0] != run_id:
                continue
            if led.ok and not led.records.get(key):
                rep.add(store.index_path, f"index names {key[1]} record {key[2]} of run {key[0]} with no ledger line")
            if len(hashes) > 1:
                rep.add(store.index_path, f"{key[1]} record {key[2]} of run {key[0]} indexed {len(hashes)} times")
    for key, seqs in led.records.items():
        if run_id is not None and key[0] != run_id:
            continue
        if len(seqs) > 1:
            rep.add(store.ledger_path, f"{key[1]} record {key[2]} ledgered {len(seqs)} times", seqs[1])
    evals = store.root / "evals"
    if not evals.is_dir():
        return
    for d in sorted(evals.iterdir()):
        if d == store.index_path or (d.is_file() and d.name.startswith(".")):
            continue
        if not d.is_dir():
            rep.add(d, "stray file in evals/")
            continue
        if run_id is not None and d.name != run_id:
            continue
        try:
            is_sealed = store.is_sealed(d.name)
        except ValueError as e:
            rep.add(d, str(e))
            continue
        if not is_sealed:
            rep.add(d, "evaluation records for a run that is not sealed")
        manifest, seal_seq = sealed.get(d.name, (None, None))
        for f in sorted(d.rglob("*")):
            if f.is_dir():
                if f.parent == d and f.name not in EVAL_KINDS:
                    rep.add(f, f"unknown eval kind {f.name!r}")
                continue
            rel = f.relative_to(d).parts
            if len(rel) != 2 or rel[0] not in EVAL_KINDS or not f.name.endswith(".json"):
                rep.add(f, "stray file in evals (expected evals/<run>/<kind>/<sha>.json)")
                continue
            rep.records += 1
            ref = "sha256:" + f.stem
            if sha256_bytes(f.read_bytes()) != ref:
                rep.add(f, "record bytes do not match their content hash")
            key = (d.name, rel[0], ref)
            if led.ok:
                seqs = led.records.get(key, [])
                if not seqs:
                    rep.add(f, "record has no ledger line (not appended through the store)")
                elif seal_seq is not None and seqs[0] <= seal_seq:
                    rep.add(f, f"record ledger seq {seqs[0]} is not after the run's seal line {seal_seq}", seqs[0])
            if led.index_ok:
                hashes = led.index.get(key, [])
                if not hashes:
                    rep.add(f, "record has no evals index line")
                elif manifest is not None and hashes[0] != manifest.manifest_hash:
                    rep.add(f, "index line names a manifest hash other than the run's current one")


# --- blobs ----------------------------------------------------------------------------------------


def _span_refs(store: LocalStore, sealed: dict[str, tuple[Manifest, int | None]]) -> dict[str, tuple[Path, int]]:
    """sha256 values of every ``*_ref`` span attribute in sealed traces -> first (trace path, seq)."""
    refs: dict[str, tuple[Path, int]] = {}
    for rid, (m, _) in sealed.items():
        for th in m.trials:
            p = store.run_dir(rid) / th.trace_file
            if safe_run_path(th.trace_file) or not p.is_file():
                continue
            try:
                lines = read_chain(p)
            except ValueError:
                continue
            for ln in lines:
                attrs = ln["rec"].get("attributes")
                if isinstance(attrs, dict):
                    for k, v in attrs.items():
                        if k.endswith("_ref") and isinstance(v, str) and SHA_REF.match(v):
                            refs.setdefault(v, (p, ln["seq"]))
    return refs


def _verify_blobs(store: LocalStore, rep: VerifyReport, sealed: dict[str, tuple[Manifest, int | None]]) -> None:
    for ref, (p, seq) in sorted(_span_refs(store, sealed).items()):
        if not store.blob_path(ref).is_file():
            rep.add(p, f"span references blob {ref}, which is not in the store", seq)
    root = store.root / "blobs" / "sha256"
    if not root.is_dir():
        return
    for f in sorted(root.glob("*/*")):
        if f.name.endswith(".meta.json") or f.name.startswith("."):
            continue
        rep.blobs += 1
        if sha256_bytes(f.read_bytes()) != "sha256:" + f.name:
            rep.add(f, "blob bytes do not match their name")
        elif f.parent.name != f.name[:2]:
            rep.add(f, "blob filed under the wrong prefix directory")
        meta = f.with_name(f.name + ".meta.json")
        try:
            if "license" not in json.loads(meta.read_text()):
                rep.add(meta, "blob metadata has no license")
        except (OSError, ValueError):
            rep.add(meta, "blob metadata missing or unreadable")
