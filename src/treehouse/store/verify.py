"""verify(): re-check everything a sealed store promises; report each problem with path and seq."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from treehouse.canon import sha256_bytes
from treehouse.schemas.manifest import Manifest
from treehouse.store.local import INDEX_GENESIS, LEDGER_GENESIS, LocalStore
from treehouse.store.seal import RESERVED
from treehouse.trace.chain import read_chain, trial_genesis, verify_chain


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

    @property
    def ok(self) -> bool:
        return not self.problems

    def add(self, path: Path | str, message: str, seq: int | None = None) -> None:
        self.problems.append(Problem(str(path), seq, message))


def verify(store: LocalStore, run_id: str | None = None) -> VerifyReport:
    rep = VerifyReport()
    runs_root = store.root / "runs"
    if run_id is not None:
        run_ids = [run_id]
    else:
        run_ids = sorted(d.name for d in runs_root.iterdir() if d.is_dir() and not d.name.startswith(".tmp-")) \
            if runs_root.is_dir() else []
    sealed: dict[str, str] = {}
    for rid in run_ids:
        h = _verify_run(store, rid, rep)
        if h:
            sealed[rid] = h
    _verify_ledger(store, rep, run_id)
    _verify_evals(store, rep, run_id)
    _verify_blobs(store, rep)
    return rep


def _verify_run(store: LocalStore, rid: str, rep: VerifyReport) -> str | None:
    run = store.run_dir(rid)
    rep.runs += 1
    if not run.is_dir():
        rep.add(run, "run not found")
        return None
    if not (run / "SEALED").is_file():
        rep.add(run / "SEALED", "run is not sealed")
        return None
    try:
        m = Manifest.model_validate_json((run / "manifest.json").read_bytes())
    except (OSError, ValueError) as e:
        rep.add(run / "manifest.json", f"unreadable manifest: {e}")
        return None
    if m.compute_hash() != m.manifest_hash:
        rep.add(run / "manifest.json", "manifest hash does not match its contents")
    if (run / "SEALED").read_text().strip() != m.manifest_hash:
        rep.add(run / "SEALED", "SEALED does not name the manifest hash")
    if m.run_id != rid:
        rep.add(run / "manifest.json", f"manifest run_id {m.run_id!r} != directory {rid!r}")
    for rel, sha in sorted(m.files.items()):
        p = run / rel
        if not p.is_file():
            rep.add(p, "file listed in manifest is missing")
        elif sha256_bytes(p.read_bytes()) != sha:
            rep.add(p, "file sha256 does not match the manifest")
    for p in sorted(run.rglob("*")):
        rel = p.relative_to(run).as_posix()
        if p.is_file() and rel not in m.files and rel not in RESERVED:
            rep.add(p, "file not listed in the manifest")
    for th in m.trials:
        p = run / th.trace_file
        check = verify_chain(p, genesis=trial_genesis(th.trial_id), expected=th.head)
        if not check.ok:
            rep.add(p, check.reason or "chain does not verify", check.first_bad_seq)
        claims = p.with_name(p.name.replace(".trace.jsonl", ".claims.jsonl"))
        if claims.is_file() and sha256_bytes(claims.read_bytes()) != th.claims_sha256:
            rep.add(claims, "claims sha256 does not match the trial head")
    return m.manifest_hash


def _verify_ledger(store: LocalStore, rep: VerifyReport, run_id: str | None) -> None:
    for path, genesis in ((store.ledger_path, LEDGER_GENESIS), (store.index_path, INDEX_GENESIS)):
        if not path.exists():
            continue
        check = verify_chain(path, genesis=genesis)
        if not check.ok:
            rep.add(path, check.reason or "chain does not verify", check.first_bad_seq)
            continue
        if path != store.ledger_path:
            continue
        for line in read_chain(path):
            rec = line["rec"]
            rid = rec.get("run_id")
            if run_id is not None and rid != run_id:
                continue
            run = store.run_dir(rid)
            if rec.get("kind") == "run":
                mp = run / "manifest.json"
                if not mp.is_file() or json.loads(mp.read_text()).get("manifest_hash") != rec.get("ref"):
                    rep.add(path, f"ledger names run {rid} with a manifest hash that is not on disk", line["seq"])
            else:
                rel = f"evals/{rid}/{rec.get('kind')}/{str(rec.get('ref')).removeprefix('sha256:')}.json"
                if not (store.root / rel).is_file():
                    rep.add(path, f"ledger names missing record {rel}", line["seq"])


def _verify_evals(store: LocalStore, rep: VerifyReport, run_id: str | None) -> None:
    evals = store.root / "evals"
    if not evals.is_dir():
        return
    for d in sorted(x for x in evals.iterdir() if x.is_dir()):
        if run_id is not None and d.name != run_id:
            continue
        if not store.is_sealed(d.name):
            rep.add(d, "evaluation records for a run that is not sealed")
        for f in sorted(d.rglob("*.json")):
            rep.records += 1
            if sha256_bytes(f.read_bytes()) != "sha256:" + f.stem:
                rep.add(f, "record bytes do not match their content hash")


def _verify_blobs(store: LocalStore, rep: VerifyReport) -> None:
    root = store.root / "blobs" / "sha256"
    if not root.is_dir():
        return
    for f in sorted(root.glob("*/*")):
        if f.name.endswith(".meta.json") or f.name.startswith("."):
            continue
        rep.blobs += 1
        if sha256_bytes(f.read_bytes()) != "sha256:" + f.name:
            rep.add(f, "blob bytes do not match their name")
        meta = f.with_name(f.name + ".meta.json")
        try:
            if "license" not in json.loads(meta.read_text()):
                rep.add(meta, "blob metadata has no license")
        except (OSError, ValueError):
            rep.add(meta, "blob metadata missing or unreadable")
